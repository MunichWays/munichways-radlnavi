import asyncio
import importlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
shares = importlib.import_module('src.shared_routes')
FIXTURE = Path(__file__).resolve().parents[2] / 'frontend/src/fixtures/route-transfer.json'


class SharedRoutesTest(unittest.TestCase):
    def setUp(self):
        self.transfer = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime(2026, 10, 14, tzinfo=timezone.utc)
        self.store = shares.ShareStore(directory=self.directory.name, clock=lambda: self.now)

    def test_immutable_snapshots_expire_at_exactly_90_days(self):
        route_id, expires = self.store.create(self.transfer)
        self.assertEqual(self.now + timedelta(days=90), expires)
        self.assertEqual(self.transfer, self.store.read(route_id))
        self.now += timedelta(days=30)
        self.assertEqual(self.transfer, self.store.read(route_id))
        self.now += timedelta(days=60) - timedelta(seconds=1)
        self.assertEqual(self.transfer, self.store.read(route_id))
        self.now += timedelta(seconds=1)
        with self.assertRaises(HTTPException) as failure:
            self.store.read(route_id)
        self.assertEqual(410, failure.exception.status_code)

    def test_invalid_data_and_path_traversal_are_rejected(self):
        for value in [None, {}, {**self.transfer, 'version': 2}, {**self.transfer, 'plan': []}]:
            with self.assertRaises(HTTPException):
                shares.validate_transfer(value)
        with self.assertRaises(HTTPException) as failure:
            self.store.read('../secret')
        self.assertEqual(404, failure.exception.status_code)

    def test_fifty_intermediate_stops_can_be_shared_but_fifty_one_cannot(self):
        def transfer(stops):
            value = json.loads(json.dumps(self.transfer))
            points = [[11 + i / 1000, 48] for i in range(stops + 2)]
            value['plan'] = [{'name': str(i), 'coordinates': p} for i, p in enumerate(points)]
            route = value['response']['routes'][0]
            route['geometry']['coordinates'] = points
            route['legs'] = [{
                'steps': [{
                    'maneuver': {'type': kind, 'location': p}, 'mode': 'cycling',
                    'distance': 0, 'duration': 0,
                    'geometry': {'type': 'LineString', 'coordinates': coords},
                } for kind, p, coords in [('depart', a, [a, b]), ('arrive', b, [b])]]
            } for a, b in zip(points, points[1:])]
            return value
        shares.validate_transfer(transfer(50))
        with self.assertRaises(HTTPException):
            shares.validate_transfer(transfer(51))

    def test_http_errors_retry_and_limits(self):
        async def run():
            app = FastAPI()
            app.include_router(shares.router)
            with patch.object(shares, 'get_store', return_value=self.store), patch.dict('os.environ', {'SHARE_PUBLIC_BASE_URL': 'http://localhost:3000'}):
                async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                    invalid = await client.post('/shared_routes', content='broken')
                    self.assertEqual(422, invalid.status_code)
                    too_large = await client.post('/shared_routes', content=b'x' * (shares.MAX_BYTES + 1))
                    self.assertEqual(413, too_large.status_code)
                    created = await client.post('/shared_routes', json=self.transfer)
                    self.assertEqual(201, created.status_code)
                    route_id = created.json()['id']
                    fetched = await client.get('/shared_routes/' + route_id)
                    self.assertEqual(self.transfer, fetched.json())
                    self.assertEqual('no-store', fetched.headers['cache-control'])
                    with patch.object(self.store, 'create', side_effect=OSError('temporary failure')):
                        self.assertEqual(503, (await client.post('/shared_routes', json=self.transfer)).status_code)
                    self.assertEqual(201, (await client.post('/shared_routes', json=self.transfer)).status_code)
        asyncio.run(run())

    def test_unconfigured_storage_returns_503(self):
        with self.assertRaises(HTTPException) as failure:
            shares.ShareStore().create(self.transfer)
        self.assertEqual(503, failure.exception.status_code)

    def test_creation_limit_recovers_after_one_hour(self):
        with shares._lock:
            shares._requests.clear()
        with patch.object(shares, 'monotonic', return_value=100):
            for _ in range(30):
                shares.limit_creation('test-client')
            with self.assertRaises(HTTPException) as failure:
                shares.limit_creation('test-client')
            self.assertEqual(429, failure.exception.status_code)
        with patch.object(shares, 'monotonic', return_value=3701):
            shares.limit_creation('test-client')


if __name__ == '__main__':
    unittest.main()
