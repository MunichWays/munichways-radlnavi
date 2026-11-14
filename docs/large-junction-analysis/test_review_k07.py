"""Frozen refresh and side-specific lane regression for the K07 redraw."""
import gzip
import json
import unittest

from build_review_images import ROOT, cycling
from src.big_junctions import simple_ring


class K07LaneReviewTests(unittest.TestCase):
    def site(self):
        data = json.loads((ROOT / 'review-batch-01-images/review-data.json').read_text(encoding='utf-8'))
        return next(s for s in data['sites'] if s['number'] == 7)

    def test_refresh_is_local_to_k07_and_retains_frozen_source(self):
        site = self.site()
        snapshot = json.loads(gzip.decompress((ROOT / site['review']['osmSnapshot']).read_bytes()))
        self.assertEqual(site['osmRetrievedAt'], snapshot['retrievedAt'])
        self.assertTrue(site['osmSource'].startswith('https://api.openstreetmap.org/api/0.6/map?'))
        self.assertEqual(site['version'], 2)
        self.assertEqual(site['status'], 'geometry-approved')
        self.assertTrue(site['polygonApproved'])
        self.assertFalse(site['enabled'])
        old = json.loads((ROOT / 'review-draft-archives/k07-v1.json').read_text(encoding='utf-8'))
        self.assertEqual(site['polygon'], old['polygon'])
        self.assertTrue(simple_ring(site['polygon']))

    def test_four_arms_have_eight_directed_gates_without_duplicate_separate_side(self):
        site = self.site()
        gates = {g['label']: g for g in site['gates']}
        self.assertEqual(len(gates), 8)
        expected = {'Entry-1': 313579592, 'Exit-2': 313579600,
                    'Entry-4': 1331965616, 'Exit-3': 71822768}
        ways = {w['id']: w for w in site['ways']}
        for label, identifier in expected.items():
            gate = gates[label]
            self.assertEqual(gate['osmWayId'], identifier)
            self.assertIn('laneEvidence', gate)
            self.assertIn('centerline', gate['positionBasis'])
            self.assertIn('lane', ways[identifier]['tags'].values())
            self.assertFalse(gate.get('shared', False))
        self.assertLess(gates['Entry-4']['forward'][1], 0)
        self.assertLess(gates['Exit-3']['forward'][1], 0)
        self.assertEqual(gates['Exit-1']['osmWayId'], 1331965615)
        self.assertEqual(gates['Entry-2']['osmWayId'], 372004858)
        self.assertTrue(cycling(ways[gates['Exit-1']['osmWayId']]))
        arms = site['review']['proposedLogicalArms']
        assigned = [label for arm in arms.values() for labels in arm.values() for label in labels]
        self.assertEqual(len(assigned), 8)
        self.assertEqual(set(assigned), set(gates))

    def test_existing_four_positions_survive_with_explicit_clockwise_migration(self):
        site = self.site()
        gates = {g['label']: g for g in site['gates']}
        old = json.loads((ROOT / 'review-draft-archives/k07-v1.json').read_text(encoding='utf-8'))
        for gate in old['gates']:
            new = gates[site['review']['labelMigration'][gate['label']]]
            for field in ('osmWayId', 'location', 'forward', 'kind'):
                self.assertEqual(new[field], gate[field])
