"""Approved Sendlinger-Tor-Platz: eight macros, ordinary right-turn guidance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog


class K33JunctionTests(unittest.TestCase):
    def test_all_real_routes_against_complete_active_catalog(self):
        site = next(j for j in catalog()['junctions'] if j['id'] == 'sendlinger-tor')
        self.assertEqual(sum(m.get('enabled', False) for m in site['movements']), 8)
        paths = list((Path(__file__).with_name('fixtures') / 'big-junctions/k33').glob('*.json'))
        self.assertEqual(len(paths), 12)
        positive = right = 0
        for path in paths:
            payload = json.loads(path.read_text(encoding='utf-8'))
            original = deepcopy(payload)
            result = add_guidance(payload)
            with self.subTest(route=path.name):
                if '-right-' in path.name:
                    self.assertIsNone(result)
                    right += 1
                else:
                    self.assertIsNotNone(result)
                    hit, = result['routes'][0].pop('guidance')['junctions']
                    self.assertEqual(hit['id'], site['id'])
                    self.assertEqual(hit['movement'], 'left' if '-left-' in path.name else 'straight')
                    self.assertEqual(result, original)
                    positive += 1
                    for mode in ('walking', 'pushing bike'):
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = mode
                        self.assertIsNone(add_guidance(walking))
                self.assertEqual(payload, original)
        self.assertEqual((positive, right), (8, 4))
