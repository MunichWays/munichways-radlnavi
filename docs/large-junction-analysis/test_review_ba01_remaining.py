"""Frozen BA01 follow-up: four proposed arms, legal road directions and scope."""

from copy import deepcopy
import gzip
import json
import sys
import unittest

from prepare_ba01_remaining import DRAFTS, OUT, ROOT, SNAPSHOT, prepare

sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import inside, simple_ring


class BA01RemainingReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = json.loads(gzip.decompress(SNAPSHOT.read_bytes()))
        cls.ways = [w for w in snapshot['response']['elements'] if w['type'] == 'way']
        cls.records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
        cls.sites = json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']

    def test_reproduces_without_modifying_frozen_source(self):
        original = deepcopy(self.ways)
        self.assertEqual([prepare(s, self.ways) for s in self.records], self.sites)
        self.assertEqual(self.ways, original)

    def test_all_proposed_arms_and_gates_remain_unapproved_and_inactive(self):
        runtime = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        runtime_ids = {j['id'] for j in runtime['junctions']}
        self.assertEqual([s['number'] for s in self.sites], [30, 31, 32, 33])
        for site in self.sites:
            self.assertEqual(site['id'] in runtime_ids, site['number'] in (30, 33))
            self.assertFalse(site['enabled'])
            self.assertEqual(site['polygonApproved'], site['number'] in (30, 33))
            self.assertEqual(site['status'], 'geometry-approved' if site['number'] in (30, 33) else 'permanently-excluded')
            self.assertTrue(simple_ring(site['polygon']))
            self.assertEqual(len(site['proposedLogicalArms']), 3 if site['number'] == 30 else 4)
            labels = [label for arm in site['proposedLogicalArms'].values() for label in arm]
            self.assertEqual(len(labels), len(set(labels)))
            self.assertEqual(set(labels), {g['label'] for g in site['gates']})

    def test_adjacent_intersections_stay_outside(self):
        excluded = {30: [[11.568828, 48.1419005]],
                    31: [[11.5705246, 48.142768], [11.5719205, 48.1414922]],
                    32: [[11.5833619, 48.1415921]],
                    33: [[11.5654565, 48.1335928], [11.565577, 48.1337707],
                         [11.5675141, 48.1336666], [11.5665032, 48.1331258]]}
        for site in self.sites:
            for point in excluded[site['number']]:
                self.assertFalse(inside(point, site['polygon']), (site['number'], point))

    def test_k30_removes_otto_preserves_other_gates_and_excludes_uncontrolled_straight(self):
        site = self.sites[0]
        old = json.loads((ROOT / 'review-draft-archives/ba01-k30-before-otto-removal.json').read_text(encoding='utf-8'))
        gates = {g['label']: g for g in site['gates']}
        self.assertEqual(site['version'], 3)
        self.assertNotIn('Entry-3', gates)
        self.assertNotIn('Exit-4', gates)
        self.assertNotIn('Exit-5', gates)
        for gate in old['gates']:
            if gate['label'] not in ('Entry-3', 'Exit-4', 'Entry-4'):
                self.assertEqual(gate, gates[gate['label']])
        old_entry = next(g for g in old['gates'] if g['label'] == 'Entry-4')
        self.assertLess(gates['Entry-4']['location'][0], old_entry['location'][0])
        self.assertEqual(gates['Entry-4']['osmWayId'], 303437709)
        previous = json.loads((ROOT / 'review-draft-archives/ba01-k30-v2-before-northeast-entry.json').read_text(encoding='utf-8'))
        previous_entry = next(g for g in previous['gates'] if g['label'] == 'Entry-4')
        self.assertGreater(gates['Entry-4']['location'][0], previous_entry['location'][0])
        self.assertGreater(gates['Entry-4']['location'][1], previous_entry['location'][1])
        self.assertLess(gates['Entry-4']['location'][1], 48.1417104)
        self.assertGreater(gates['Entry-4']['location'][1], 48.1414581)
        self.assertFalse(inside([11.5691706, 48.1417104], site['polygon']))
        excluded, = site['excludedMovements']
        self.assertEqual((excluded['entryLabel'], excluded['exitLabel']), ('Entry-4', 'Exit-3'))

    def test_christoph_bicycle_exception_keeps_both_carriageway_directions(self):
        site = next(s for s in self.sites if s['number'] == 32)
        gates = [g for g in site['gates'] if g['osmWayId'] == 4662372]
        self.assertEqual({g['kind'] for g in gates}, {'entry', 'exit'})
        self.assertEqual(gates[0]['location'], gates[1]['location'])
        self.assertEqual(gates[0]['forward'], [-v for v in gates[1]['forward']])
        way = next(w for w in self.ways if w['id'] == 4662372)
        self.assertEqual(way['tags']['oneway'], 'yes')
        self.assertEqual(way['tags']['oneway:bicycle'], 'no')

    def test_sendlinger_tor_has_four_main_cycling_arms_with_lindwurm_lane(self):
        site = next(s for s in self.sites if s['number'] == 33)
        self.assertEqual(len(site['gates']), 8)
        for labels in site['proposedLogicalArms'].values():
            self.assertEqual(len(labels), 2)
            self.assertTrue(any(label.startswith('Entry-') for label in labels))
            self.assertTrue(any(label.startswith('Exit-') for label in labels))
        lane = next(g for g in site['gates'] if g['label'] == 'Entry-3')
        self.assertEqual(lane['osmWayId'], 315202576)
        self.assertEqual(lane['laneEvidence']['cycleway:right'], 'lane')
        self.assertTrue(inside([11.5665043, 48.133447], site['polygon']))
        self.assertTrue(inside([11.5667895, 48.1334043], site['polygon']))

    def test_sendlinger_inward_revision_preserves_two_accepted_gates(self):
        site = next(s for s in self.sites if s['number'] == 33)
        old = json.loads((ROOT / 'review-draft-archives/ba01-k33-v1-before-gates-inward.json').read_text(encoding='utf-8'))
        current = {g['label']: g for g in site['gates']}
        self.assertEqual(site['version'], 2)
        from src.big_junctions import meters
        for gate in old['gates']:
            label = gate['label']
            if label in ('Entry-3', 'Exit-3'):
                self.assertEqual(current[label], gate)
            else:
                self.assertEqual(current[label]['osmWayId'], gate['osmWayId'])
                shift = meters(current[label]['location'], gate['location'])
                self.assertGreater(shift, 8)
                self.assertLess(shift, 18)


if __name__ == '__main__':
    unittest.main()
