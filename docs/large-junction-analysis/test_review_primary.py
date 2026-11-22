"""Primary follow-up: reproducible four-arm drafts with grade-separated roads out."""
from copy import deepcopy
import gzip
import json
import sys
import unittest

from prepare_primary_review import ROOT, SOURCE, DRAFTS, OUT, prepare

sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import simple_ring


class PrimaryReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = json.loads(gzip.decompress(SOURCE.read_bytes()))
        cls.sources = {s['id']: s['elements'] for s in snapshot['sites']}
        cls.records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
        cls.sites = json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']

    def test_frozen_sources_reproduce_without_mutation(self):
        original = deepcopy(self.sources)
        self.assertEqual([prepare(s, self.sources[s.get('sourceId', s['id'])]) for s in self.records], self.sites)
        self.assertEqual(original, self.sources)

    def test_review_decisions_match_active_catalog(self):
        runtime = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        runtime_ids = {j['id'] for j in runtime['junctions']}
        self.assertEqual([s['number'] for s in self.sites], [34, 35, 36, 37])
        for site in self.sites:
            self.assertIn(site['id'], runtime_ids)
            self.assertFalse(site['enabled'])
            self.assertTrue(site['polygonApproved'])
            self.assertEqual(site['status'], 'geometry-approved')
            self.assertTrue(simple_ring(site['polygon']))
            self.assertEqual(len(site['gates']), 8 if site['number'] in (34, 36) else 6)
            self.assertEqual(len(site['proposedLogicalArms']), 4)
            assigned = [g for arm in site['proposedLogicalArms'].values() for g in arm]
            self.assertEqual(len(assigned), len(set(assigned)))
            self.assertEqual(set(assigned), {g['label'] for g in site['gates']})
            ways = {w['id']: w for w in site['ways']}
            for gate in site['gates']:
                tags = ways[gate['osmWayId']]['tags']
                self.assertNotIn(tags.get('bicycle'), ('no', 'use_sidepath'))
                self.assertNotEqual(tags.get('tunnel'), 'yes')
                self.assertNotEqual(tags.get('highway'), 'trunk')
                self.assertEqual(tags.get('layer', '0'), '0')

    def test_leuchtenberg_northern_exit_keeps_real_cycleway_lane_transition(self):
        site = next(s for s in self.sites if s['number'] == 36)
        gate = next(g for g in site['gates'] if g['label'] == 'Exit-1')
        self.assertEqual(gate['osmWayId'], 796891858)
        self.assertEqual(gate['laneEvidence']['cycleway:right'], 'lane')
        path = next(w for w in site['ways'] if w['id'] == 1361432421)
        lane = next(w for w in site['ways'] if w['id'] == 796891858)
        self.assertEqual(path['nodes'][-1], lane['nodes'][0])
        self.assertEqual(gate['directionBasis'], 'yes')

    def test_landsberger_halves_have_separate_areas_and_directed_connectors(self):
        west = next(s for s in self.sites if s['number'] == 35)
        east = next(s for s in self.sites if s['number'] == 37)
        self.assertLess(max(p[0] for p in west['polygon']),
                        min(p[0] for p in east['polygon']))
        for site in (west, east):
            self.assertEqual(sum(g['kind'] == 'entry' for g in site['gates']), 3)
            self.assertEqual(sum(g['kind'] == 'exit' for g in site['gates']), 3)
        for way_id, west_kind, east_kind in (
                (946928532, 'entry', 'exit'), (211464646, 'exit', 'entry')):
            a = next(g for g in west['gates'] if g['osmWayId'] == way_id)
            b = next(g for g in east['gates'] if g['osmWayId'] == way_id)
            self.assertEqual((a['kind'], b['kind']), (west_kind, east_kind))
            self.assertLess(a['location'][0], b['location'][0])


if __name__ == '__main__':
    unittest.main()
