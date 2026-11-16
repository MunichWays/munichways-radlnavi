"""Real Standard-route regression for the three approved Altstadt-Radlring sites."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog

FIXTURES = Path(__file__).with_name('fixtures') / 'big-junctions/batch-04'
SITES = {'ludwig-tann', 'maximilians-brienner', 'blumen-cornelius'}


class BA01JunctionTests(unittest.TestCase):
    def test_complete_real_standard_batch_against_active_catalog(self):
        junctions = {j['id']: j for j in catalog()['junctions']}
        positive = right = walking = 0
        fixtures = list(FIXTURES.glob('*.json'))
        self.assertEqual(len(fixtures), 36)
        for path in fixtures:
            identifier = next(s for s in SITES if path.name.startswith(s+'-'))
            movement_id = path.stem[len(identifier)+1:]
            original = json.loads(path.read_text(encoding='utf-8'))
            saved = deepcopy(original)
            with self.subTest(fixture=path.name):
                result = add_guidance(original)
                if '-right-' in movement_id:
                    self.assertIsNone(result)
                    right += 1
                else:
                    self.assertIsNotNone(result)
                    expected = next(m for m in junctions[identifier]['movements'] if m['id'] == movement_id)
                    hit, = result['routes'][0].pop('guidance')['junctions']
                    self.assertEqual(hit['id'], identifier)
                    self.assertEqual(hit['movement'], expected['movement'])
                    self.assertEqual(result, saved)
                    positive += 1
                    for mode in ('walking', 'pushing bike'):
                        on_foot = deepcopy(original)
                        for leg in on_foot['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = mode
                        self.assertIsNone(add_guidance(on_foot))
                        walking += 1
                self.assertEqual(original, saved)
        self.assertEqual((positive, right, walking), (24, 12, 48))

    def test_only_approved_ba01_sites_are_active(self):
        junctions = {j['id']: j for j in catalog()['junctions']}
        for identifier in SITES:
            self.assertTrue(junctions[identifier]['enabled'])
            self.assertEqual(sum(bool(m.get('enabled')) for m in junctions[identifier]['movements']), 8)
        self.assertFalse({'sonnen-schwanthaler', 'sonnen-landwehr',
                          'blumen-papa-schmid'} & junctions.keys())


if __name__ == '__main__':
    unittest.main()
