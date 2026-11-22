"""Central rollout keeps right-only entries, deferrals and raw routes intact."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog


class CentralJunctionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[2]

    def test_activation_and_deferred_pairs(self):
        sites = {j['id']: j for j in catalog()['junctions']}
        for node, count in [(363119, 8), (472070, 8), (361786, 8), (361790, 8), (428767, 8)]:
            site = sites[f'lane-candidate-{node}']
            self.assertTrue(site['enabled'])
            self.assertEqual(sum(bool(m.get('enabled')) for m in site['movements']), count)
        for node, pairs in [(361786, set()),
                            (428767, {('Entry-1', 'Exit-3'), ('Entry-1', 'Exit-4')})]:
            disabled = [m for m in sites[f'lane-candidate-{node}']['movements'] if not m.get('enabled')]
            self.assertEqual({(m['entryLabel'], m['exitLabel']) for m in disabled}, pairs)
            for m in disabled:
                if m['entryLabel'] == 'Entry-3':
                    self.assertIn('23.11.2026', m['disabledReason'])

    def test_frozen_routes_against_actual_runtime_catalog(self):
        report = json.loads((self.root / 'docs/large-junction-analysis/review-batch-08-central-routes.json').read_text(encoding='utf-8'))
        counts = dict(positive=0, right=0)
        for site in report['junctions']:
            for item in site['movements']:
                fixture = self.root / 'backend/tests/fixtures/big-junctions/batch-08' / item['fixture']
                if item.get('explicitlyExcluded'):
                    self.assertFalse(item['enabled'])
                    continue
                with self.subTest(site=site['number'], pair=item['id']):
                    payload = json.loads(fixture.read_text(encoding='utf-8'))
                    original = deepcopy(payload)
                    result = add_guidance(payload)
                    hits = result['routes'][0].pop('guidance')['junctions'] if result else []
                    if item.get('enabled'):
                        self.assertEqual(len(hits), 1)
                        self.assertEqual((hits[0]['id'], hits[0]['movement'], hits[0]['entryArm'], hits[0]['exitArm']),
                                         (site['id'], item['kind'], item['entryArm'], item['exitArm']))
                        counts['positive'] += 1
                        for mode in ('walking', 'pushing bike'):
                            on_foot = deepcopy(payload)
                            for leg in on_foot['routes'][0]['legs']:
                                for step in leg['steps']:
                                    step['mode'] = mode
                            self.assertIsNone(add_guidance(on_foot))
                    elif item['kind'] == 'right':
                        self.assertTrue(item['verified'])
                        self.assertEqual(hits, [])
                        counts['right'] += 1
                    else:
                        self.assertFalse(any(h['id'] == site['id'] and h['entryArm'] == item['entryArm']
                                             and h['exitArm'] == item['exitArm'] for h in hits))
                    if result is not None:
                        self.assertEqual(result, original)
                    self.assertEqual(payload, original)
        self.assertEqual(counts, dict(positive=38, right=21))
