"""Activated lane-priority crossings retain ordinary guidance for exclusions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog


class LanePriorityJunctionTests(unittest.TestCase):
    def test_active_catalog_preserves_permanent_exclusions(self):
        value = catalog()
        self.assertNotIn('landsberger-fuerstenrieder', {j['id'] for j in value['junctions']})
        self.assertTrue(next(j for j in value['excluded'] if j['id'] == 'landsberger-fuerstenrieder')['permanent'])
        for identifier, count in [('dachauer-georg-brauchle', 8), ('innsbrucker-bad-schachener', 8), ('candid-gruenwalder', 6)]:
            site = next(j for j in value['junctions'] if j['id'] == identifier)
            self.assertTrue(site['enabled'])
            self.assertEqual(sum(bool(m.get('enabled')) for m in site['movements']), count)
        site = next(j for j in value['junctions'] if j['id'] == 'candid-gruenwalder')
        excluded = [m for m in site['movements'] if not m['enabled']]
        self.assertEqual({(m['entryLabel'], m['exitLabel']) for m in excluded},
                         {('Entry-1', 'Exit-3'), ('Entry-1', 'Exit-4')})
        self.assertTrue(all('class:bicycle=-3' in m['disabledReason'] for m in excluded))

    def test_frozen_real_routes_match_without_changing_route_data(self):
        root = Path(__file__).resolve().parents[2]
        report = json.loads((root / 'docs/large-junction-analysis/review-batch-07-lanes-routes.json').read_text(encoding='utf-8'))
        fixtures = Path(__file__).parent / 'fixtures/big-junctions/batch-07'
        positive = right = excluded = 0
        for site in report['junctions']:
            for item in site['movements']:
                with self.subTest(site=site['number'], pair=item['id']):
                    payload = json.loads((fixtures / item['fixture']).read_text(encoding='utf-8'))
                    original = deepcopy(payload)
                    result = add_guidance(payload)
                    hits = result['routes'][0].pop('guidance')['junctions'] if result else []
                    if item.get('enabled'):
                        self.assertEqual(len(hits), 1)
                        self.assertEqual((hits[0]['id'], hits[0]['movement'], hits[0]['entryArm'], hits[0]['exitArm']),
                                         (site['id'], item['kind'], item['entryArm'], item['exitArm']))
                        positive += 1
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = 'walking'
                        self.assertIsNone(add_guidance(walking))
                    elif item.get('explicitlyExcluded'):
                        self.assertFalse(any(h['id'] == site['id'] and h['entryArm'] == item['entryArm']
                                             and h['exitArm'] == item['exitArm'] for h in hits))
                        excluded += 1
                    elif item.get('verified') and item['kind'] == 'right':
                        self.assertEqual(hits, [])
                        right += 1
                    if result is not None:
                        self.assertEqual(result, original)
                    self.assertEqual(payload, original)
        self.assertEqual((positive, right, excluded), (22, 11, 2))
