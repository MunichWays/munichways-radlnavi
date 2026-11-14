"""Real Wilram contracts, fail-closed validation and protocol compatibility."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch, AsyncMock
import httpx

from starlette.requests import Request
from src.big_junctions import add_guidance, validate_catalog
from test_big_junctions import app, response_for, OPTIONS
from src.direct_proxy import DirectRouteProxy

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'docs/large-junction-analysis'
RAW = Path(__file__).with_name('fixtures') / 'big-junctions/review-updates-2026-11-14'
CONTRACTS = Path(__file__).with_name('fixtures') / 'big-junctions/wilram-sequences'


def proposed():
    return json.loads((REPORTS / 'review-wilram-sequences-proposed-catalog.json').read_text(encoding='utf-8'))


class JunctionSequenceTests(unittest.TestCase):
    def test_repeated_sequence_visits_use_their_own_checkpoint_indices(self):
        original = json.loads((RAW / 'thomasiusplatz-wilram-entry-3-exit-5.json').read_text(encoding='utf-8'))
        line = original['routes'][0]['geometry']['coordinates']
        line = line + line[-2::-1] + line[1:]
        original['routes'][0]['geometry']['coordinates'] = line
        original['routes'][0]['legs'] = [{'steps': [dict(mode='cycling',
            maneuver={'type': 'depart' if i == 0 else 'continue', 'location': a},
            geometry={'type': 'LineString', 'coordinates': [a, b]})
            for i, (a, b) in enumerate(zip(line, line[1:]))]}]
        with patch('src.big_junctions.catalog', return_value=proposed()):
            result = add_guidance(original, sequence_guidance=True)
        hits = [h for h in result['routes'][0]['guidance']['junctions'] if h.get('sequence')]
        self.assertEqual(len(hits), 2)
        self.assertNotEqual(hits[0]['occurrenceId'], hits[1]['occurrenceId'])
        for hit in hits:
            for cp in hit['sequence']['checkpoints']:
                self.assertLess(hit['entry']['distanceAlongRouteMeters'], cp['anchor']['distanceAlongRouteMeters'])
                self.assertGreater(hit['exit']['distanceAlongRouteMeters'], cp['anchor']['distanceAlongRouteMeters'])

    def test_five_real_contracts_preserve_routes_and_require_capability(self):
        value = proposed()
        with patch('src.big_junctions.catalog', return_value=value):
            for file in CONTRACTS.glob('*.json'):
                raw = json.loads((RAW / ('thomasiusplatz-'+file.name)).read_text(encoding='utf-8'))
                saved = deepcopy(raw)
                self.assertIsNone(add_guidance(raw))
                result = add_guidance(raw, sequence_guidance=True)
                self.assertEqual(result, json.loads(file.read_text(encoding='utf-8')))
                guidance = result['routes'][0].pop('guidance')
                self.assertEqual(guidance['version'], 'big-junctions-v2')
                self.assertEqual(len(guidance['junctions']), 1)
                hit = guidance['junctions'][0]
                self.assertIn(hit['movement'], ('left', 'straight', 'uturn'))
                self.assertTrue(hit['sequence']['checkpoints'])
                for cp in hit['sequence']['checkpoints']:
                    self.assertTrue(hit['entry']['distanceAlongRouteMeters'] < cp['anchor']['distanceAlongRouteMeters'] < hit['exit']['distanceAlongRouteMeters'])
                self.assertEqual(result, raw)
                self.assertEqual(raw, saved)
                walking = deepcopy(raw)
                for leg in walking['routes'][0]['legs']:
                    for step in leg['steps']:
                        step['mode'] = 'pushing bike'
                self.assertIsNone(add_guidance(walking, sequence_guidance=True))

    def test_invalid_sequences_fail_closed(self):
        for corruption in ('language', 'location', 'duplicate', 'review', 'direction', 'version', 'modifier'):
            value = proposed()
            movement = next(m for j in value['junctions'] for m in j['movements'] if m.get('sequence'))
            seq = movement['sequence']
            if corruption == 'language': seq['advance'].pop('en')
            if corruption == 'location': seq['checkpoints'][0]['location'] = [11.7, 48.2]
            if corruption == 'duplicate': seq['checkpoints'].append(deepcopy(seq['checkpoints'][0]))
            if corruption == 'review': seq['review']['status'] = 'draft'
            if corruption == 'direction': seq['checkpoints'][0]['approach'].reverse()
            if corruption == 'version': seq['version'] = 99
            if corruption == 'modifier': seq['checkpoints'][0]['modifier'] = 'guess'
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                validate_catalog(value)

    def test_v1_clients_and_capability_opt_out_keep_normal_guidance(self):
        file = next(CONTRACTS.glob('*.json'))
        original = response_for(json.loads((RAW / ('thomasiusplatz-'+file.name)).read_text(encoding='utf-8')))
        with patch('src.big_junctions.catalog', return_value=proposed()), \
             patch.object(app, 'ROUTING_VARIANT', 'standard'), \
             patch.object(app, '_get_endpoint_routing_response', return_value=original) as fetch:
            self.assertIs(app.get_endpoint_routing_response('bike', 'coords', OPTIONS), original)
            result = app.get_endpoint_routing_response('bike', 'coords', OPTIONS, sequence_guidance=True)
            self.assertEqual(result.json()['routes'][0]['guidance']['version'], 'big-junctions-v2')
            self.assertNotIn('junction_guidance', dict(fetch.call_args.args[2]))
            self.assertIs(app.get_endpoint_routing_response('bike', 'coords', {}, sequence_guidance=True), original)

    def test_capability_header_survives_variant_gateway_without_upstream_query_options(self):
        for variant in ('direct', 'discovery'):
            query = ('&'.join(f'{k}={v}' for k, v in OPTIONS.items())+'&variant='+variant).encode()
            request = Request(dict(type='http', method='GET', path='/route/v1/bike/coords',
                headers=[(b'x-junction-guidance-version', b'2')], query_string=query))
            with patch.object(app, 'ROUTING_VARIANT', 'standard'), \
                 patch.object(app, 'forward_variant', new_callable=AsyncMock) as forward:
                asyncio.run(app.osrm_route_proxy(request, 'bike', 'coords'))
                self.assertTrue(forward.call_args.kwargs['sequence_guidance'])
                self.assertFalse(any(k == 'junction_guidance_version' for k, _ in forward.call_args.kwargs['params']))

    def test_variant_transport_preserves_auth_and_sends_capability_as_header(self):
        async def check():
            def handler(request):
                self.assertEqual(request.headers['authorization'], 'Bearer service-token')
                self.assertEqual(request.headers['x-junction-guidance-version'], '2')
                self.assertNotIn('junction_guidance_version', request.url.params)
                return httpx.Response(200, json={'code': 'Ok'})
            proxy = DirectRouteProxy('https://worker.example', lambda: {'Authorization': 'Bearer service-token'})
            await proxy.client.aclose()
            proxy.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            try:
                response = await proxy.request('GET', '/route/v1/bike/coords',
                    params={'junction_guidance': 'true'}, sequence_guidance=True)
                self.assertEqual(response.status_code, 200)
            finally:
                await proxy.close()
        asyncio.run(check())
