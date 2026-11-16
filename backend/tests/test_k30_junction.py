"""K30 three-arm activation with real routes and ordinary-guidance fallback."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog, validate_catalog


class K30JunctionTests(unittest.TestCase):
    def test_real_routes_and_explicit_exclusion(self):
        data = catalog()
        validate_catalog(data)
        site = next(j for j in data['junctions'] if j['id'] == 'lenbach-pacelli')
        self.assertNotIn('armTopology', site)
        self.assertEqual(sum(m['enabled'] for m in site['movements']), 3)
        fixtures = Path(__file__).with_name('fixtures') / 'big-junctions/k30'
        expected = {'entry-1-exit-3-left': 'left', 'entry-2-exit-1-straight': 'straight',
                    'entry-4-exit-2-left': 'left'}
        counts = dict(positive=0, negative=0)
        for path in fixtures.glob('*.json'):
            payload = json.loads(path.read_text(encoding='utf-8'))
            before = deepcopy(payload)
            result = add_guidance(payload)
            key = path.stem.removeprefix('lenbach-pacelli-')
            with self.subTest(route=key):
                if key not in expected:
                    self.assertIsNone(result)
                    counts['negative'] += 1
                else:
                    self.assertIsNotNone(result)
                    hit, = result['routes'][0].pop('guidance')['junctions']
                    self.assertEqual(hit['id'], site['id'])
                    self.assertEqual(hit['movement'], expected[key])
                    self.assertEqual(result, before)
                    counts['positive'] += 1
                    walking = deepcopy(payload)
                    for leg in walking['routes'][0]['legs']:
                        for step in leg['steps']:
                            step['mode'] = 'walking'
                    self.assertIsNone(add_guidance(walking))
                self.assertEqual(payload, before)
        self.assertEqual(counts, dict(positive=3, negative=3))
