"""Entries before a road-to-cycleway split belong on the road (K108, BA05 P4)."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from junction_review import split_entries
from junction_review.split_entries import _m

FIXTURES = Path(__file__).with_name('fixtures')


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


class SplitEntryTests(unittest.TestCase):
    def assert_only_moved(self, before, after, label, way_id):
        old = {g['label']: g for g in before['gates']}
        for gate in after['gates']:
            if gate['label'] == label:
                self.assertEqual(gate['osmWayId'], way_id)
                self.assertTrue(gate['onRoad'])
            else:
                self.assertEqual(gate['osmWayId'], old[gate['label']]['osmWayId'])
                self.assertLess(_m(gate['location'], old[gate['label']]['location']), .05)

    def test_ohlmueller_merges_both_entries_onto_the_road_before_the_split(self):
        site = load('split-entry-ohlmueller-p4-v1.json')
        result, notes = split_entries.apply(site)
        self.assertEqual([g['label'] for g in result['gates'] if g['kind'] == 'entry'],
                         ['Entry-1', 'Entry-2', 'Entry-3', 'Entry-5'])
        self.assertEqual(result['logicalArms']['Arm-4'], ['Entry-5', 'Exit-4'])
        self.assert_only_moved(site, result, 'Entry-5', 1436464483)
        self.assertIn('Entry-4 entfällt', notes[0])
        self.assertEqual(split_entries.apply(result)[1], [])  # Idempotent.

    def test_hohenzollern_diagonal_entry_matches_the_approved_correction(self):
        site = load('split-entry-hohenzollern-k108-v2.json')
        result, notes = split_entries.apply(site)
        self.assert_only_moved(site, result, 'Entry-3', 486767219)
        gate = next(g for g in result['gates'] if g['label'] == 'Entry-3')
        # Thomas approved v3 with Entry-3 at this point on the same road piece.
        self.assertLess(_m(gate['location'], [11.562903, 48.1609265]), 1.5)
        self.assertEqual(len(notes), 1)

    def test_a_cycleway_arriving_at_the_split_leaves_the_geometry_alone(self):
        site = load('split-entry-ohlmueller-p4-v1.json')
        node = next(w for w in site['ways'] if w['id'] == 1436464483)['coordinates'][-1]
        site['ways'].append(dict(id=1, tags=dict(highway='cycleway', oneway='yes'),
                                 coordinates=[[node[0] - .0003, node[1] + .0002], node]))
        self.assertEqual(split_entries.corrections(site), [])
        self.assertEqual(split_entries.apply(site), (site, []))

    def test_ordinary_entries_without_a_split_are_not_touched(self):
        site = load('split-entry-ohlmueller-p4-v1.json')
        site['gates'] = [g for g in site['gates'] if g['label'] not in ('Entry-4', 'Entry-5')]
        site['logicalArms']['Arm-4'] = ['Exit-4']
        before = deepcopy(site)
        self.assertEqual(split_entries.apply(site), (before, []))


if __name__ == '__main__':
    unittest.main()
