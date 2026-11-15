"""K24 templates, right-side standard behavior and capability fallback."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from src.big_junctions import add_guidance, validate_catalog, catalog
from starlette.requests import Request
from test_big_junctions import app, response_for, OPTIONS

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name('fixtures') / 'big-junctions/k24-two-way'
CONTRACTS = FIXTURES.parent / 'k24-instructions'


def proposal():
    return json.loads((ROOT / 'docs/large-junction-analysis/review-k24-proposed-catalog.json').read_text(encoding='utf-8'))


class JunctionInstructionTests(unittest.TestCase):
    def test_approved_k24_is_enabled_in_runtime_catalog(self):
        actual = next(j for j in catalog()['junctions'] if j['id'] == 'maximilian-ring')
        expected = next(j for j in proposal()['junctions'] if j['id'] == actual['id'])
        self.assertEqual(actual, expected)
        self.assertTrue(actual['enabled'])
        self.assertEqual(len(actual['movements']), 15)
        self.assertEqual(sum(bool(m.get('instructionTemplate')) for m in actual['movements']), 5)

    def test_real_k24_routes_templates_and_legacy_fallback(self):
        data = proposal()
        validate_catalog(data)
        counts = {'standard': 0, 'special': 0, 'right': 0}
        with patch('src.big_junctions.catalog', return_value=data):
            for path in FIXTURES.glob('*.json'):
                payload = json.loads(path.read_text(encoding='utf-8'))
                before = deepcopy(payload)
                modern = add_guidance(payload, instruction_guidance=True)
                legacy = add_guidance(payload, sequence_guidance=True)
                with self.subTest(route=path.name):
                    if '-right-' in path.name:
                        self.assertIsNone(modern)
                        self.assertIsNone(legacy)
                        counts['right'] += 1
                        continue
                    self.assertIsNotNone(modern)
                    self.assertEqual(modern, json.loads((CONTRACTS / path.name).read_text(encoding='utf-8')))
                    hit, = modern['routes'][0]['guidance']['junctions']
                    if hit.get('instruction'):
                        counts['special'] += 1
                        self.assertIsNone(legacy)
                        self.assertEqual(modern['routes'][0]['guidance']['version'], 'big-junctions-v3')
                        self.assertNotIn('sequence', hit)
                    else:
                        counts['standard'] += 1
                        self.assertIsNotNone(legacy)
                    modern['routes'][0].pop('guidance')
                    self.assertEqual(modern, before)
                    self.assertEqual(payload, before)
                    for leg in payload['routes'][0]['legs']:
                        for step in leg['steps']:
                            step['mode'] = 'pushing bike'
                    self.assertIsNone(add_guidance(payload, instruction_guidance=True))
        self.assertEqual(counts, dict(standard=10, special=5, right=7))

    def test_unsupported_or_wrong_side_templates_fail_closed(self):
        for change in ({'instructionTemplate': 'opposite-left'}, {'targetCyclingSide': 'right'},
                       {'targetWayType': 'road'}, {'instructionTemplate': []}):
            data = proposal()
            move = next(m for j in data['junctions'] for m in j['movements'] if m.get('instructionTemplate'))
            move.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_catalog(data)

    def test_endpoint_requires_version_three_and_keeps_version_two_fallback(self):
        raw = json.loads((FIXTURES / 'maximilian-ring-west-north-left-entry-4-exit-6.json').read_text(encoding='utf-8'))
        import asyncio
        with patch('src.big_junctions.catalog', return_value=proposal()), patch.object(
                app, '_get_endpoint_routing_response', return_value=response_for(raw)):
            for version in ('2', '3'):
                query = '&'.join(f'{k}={v}' for k, v in OPTIONS.items()).encode()
                request = Request(dict(type='http', method='GET', path='/route/v1/bike/a;b',
                    query_string=query, headers=[(b'x-junction-guidance-version', version.encode())]))
                result = asyncio.run(app.osrm_route_proxy(request, 'bike', 'a;b'))
                body = json.loads(result.body)
                self.assertEqual('guidance' in body['routes'][0], version == '3')

    def test_original_45m_detour_remains_without_macro(self):
        raw = json.loads((FIXTURES.parent / 'k24-two-way-detours/maximilian-ring-west-north-left-entry-4-exit-6.json').read_text(encoding='utf-8'))
        with patch('src.big_junctions.catalog', return_value=proposal()):
            self.assertIsNone(add_guidance(raw, instruction_guidance=True))

    def test_direct_and_discovery_proxy_preserve_version_three(self):
        import asyncio
        import httpx
        from src.direct_proxy import DirectRouteProxy
        async def run():
            for variant in ('direct', 'discovery'):
                async def handler(request):
                    self.assertEqual(request.headers['x-junction-guidance-version'], '3')
                    return httpx.Response(200, json={'ok': True})
                client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
                proxy = DirectRouteProxy('https://private.example', auth_headers=lambda: {}, variant=variant)
                await proxy.client.aclose()
                proxy.client = client
                try:
                    await proxy.request('GET', '/route', instruction_guidance=True)
                finally:
                    await proxy.close()
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
