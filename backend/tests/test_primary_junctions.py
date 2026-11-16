"""Primary crossings, including asymmetric arms and consecutive split areas."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog, reviewed_arm_topology, validate_catalog


class PrimaryJunctionTests(unittest.TestCase):
    def test_real_routes_preserve_data_and_match_reviewed_movements(self):
        paths = list((Path(__file__).parent / 'fixtures/big-junctions/batch-06').glob('*.json'))
        self.assertEqual(len(paths), 40)
        positive = right = combined = 0
        for path in paths:
            with self.subTest(route=path.name):
                payload = json.loads(path.read_text(encoding='utf-8'))
                original = deepcopy(payload)
                result = add_guidance(payload)
                if '-right-' in path.name:
                    self.assertIsNone(result)
                    right += 1
                else:
                    self.assertIsNotNone(result)
                    hits = result['routes'][0].pop('guidance')['junctions']
                    if path.name.startswith('combined-'):
                        expected = ['landsberger-trappentreu', 'landsberger-trappentreu-ost']
                        if path.name == 'combined-east-west.json':
                            expected.reverse()
                        self.assertEqual([h['id'] for h in hits], expected)
                        self.assertEqual([h['movement'] for h in hits], ['straight', 'straight'])
                        combined += 1
                    else:
                        self.assertEqual(len(hits), 1)
                        self.assertTrue(path.name.startswith(hits[0]['id'] + '-'))
                        self.assertEqual(hits[0]['movement'], 'left' if '-left-' in path.name else 'straight')
                        positive += 1
                    self.assertEqual(result, original)
                    for mode in ('walking', 'pushing bike'):
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = mode
                        self.assertIsNone(add_guidance(walking))
                self.assertEqual(payload, original)
        self.assertEqual((positive, right, combined), (26, 12, 2))

    def test_one_way_arms_require_explicit_lists_and_reject_unavailable_direction(self):
        site = deepcopy(next(j for j in catalog()['junctions'] if j['id'] == 'landsberger-trappentreu'))
        self.assertEqual(site['armTopology']['gates']['north']['exits'], [])
        self.assertEqual(site['armTopology']['gates']['south']['entries'], [])
        self.assertIsNotNone(reviewed_arm_topology(site))
        for invalid in ({'entries': [], 'exits': []}, {'entries': [[11.534, 48.1403]]},
                        {'entries': [[11.534, 48.1403]], 'exits': None}):
            broken = deepcopy(site)
            broken['armTopology']['gates']['north'] = invalid
            with self.subTest(arm=invalid), self.assertRaises(ValueError):
                reviewed_arm_topology(broken)
        movement = next(m for m in site['movements'] if m['entryArm'] == 'north')
        movement['entryArm'] = 'south'
        value = deepcopy(catalog())
        value['junctions'] = [site]
        with self.assertRaises(ValueError):
            validate_catalog(value)
