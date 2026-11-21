"""Map-editor approval bindings, conservative arm rules and frozen routes."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import verify_munich_project as batch
from src.big_junctions import add_guidance
from junction_review.model import geometry_fingerprint


class MunichProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = batch.review.read(batch.SOURCE)
        cls.report = batch.review.read(batch.REPORT)
        cls.proposal = batch.review.read(batch.PROPOSAL)

    def normalized(self, identifier):
        site = deepcopy(next(s for s in self.source['sites'] if s['id'] == identifier))
        for way in site['ways']:
            way['coordinates'] = [[p['lon'], p['lat']] for p in way['geometry']]
        return site

    def test_no_approval_is_regenerated_and_no_topology_block_is_activated(self):
        self.assertEqual((len(self.source['sites']), len(self.source['blocked'])), (25, 1))
        proposed = {j['id']: j for j in self.proposal['junctions']}
        for site in self.source['sites']:
            self.assertEqual(geometry_fingerprint(site), site['reviewBinding']['geometryFingerprint'])
            self.assertEqual(proposed[site['id']]['polygon']['coordinates'][0], site['polygon'])
        self.assertNotIn(self.source['blocked'][0]['id'], proposed)
        self.assertEqual(self.report['status'], 'complete')
        self.assertFalse(self.report['runtimeModified'])

    def test_direction_groups_repair_split_positional_arms_and_reject_missing_arm(self):
        site = self.normalized('lane-candidate-1955160')
        arms = batch.technical_arms(site)
        self.assertTrue(any({'Entry-1','Exit-1'} <= set(labels) for labels in arms.values()))
        # Empty north direction must never be inferred into an approved arm.
        site = self.normalized('lane-candidate-1955511')
        site['gates'] = [g for g in site['gates'] if g['label'] not in ('Entry-4','Exit-1')]
        with self.assertRaises(ValueError):
            batch.technical_arms(site)

    def test_duplicate_target_instructions_remain_disabled(self):
        for site in self.source['sites']:
            excluded = batch.ambiguous_exits(site)
            junction = next(j for j in self.proposal['junctions'] if j['id'] == site['id'])
            for exclusion in excluded:
                found = [m for m in junction['movements'] if m.get('entryLabel') == exclusion['entryLabel']
                         and m.get('exitLabel') == exclusion['exitLabel']]
                self.assertEqual(len(found), 1)
                self.assertFalse(found[0]['enabled'])

    def test_frozen_real_routes_against_whole_proposal_and_keep_raw_routes(self):
        counts = dict(positive=0, right=0, walking=0)
        with patch('src.big_junctions.catalog', return_value=self.proposal):
            for junction in self.report['junctions']:
                for move in junction['movements']:
                    path = batch.FIXTURES / move['fixture']
                    if not path.exists():
                        continue
                    original = batch.review.read(path)
                    before = deepcopy(original)
                    enriched = add_guidance(original)
                    self.assertEqual(original, before)
                    with self.subTest(junction=junction['id'], movement=move['id']):
                        if move.get('enabled'):
                            self.assertIsNotNone(enriched)
                            hits = enriched['routes'][0].pop('guidance')['junctions']
                            self.assertEqual(enriched, original)
                            self.assertEqual(len(hits), 1)
                            self.assertEqual((hits[0]['id'], hits[0]['movement'], hits[0]['entryArm'], hits[0]['exitArm']),
                                             (junction['id'], move['kind'], move['entryArm'], move['exitArm']))
                            counts['positive'] += 1
                            walking = deepcopy(original)
                            for leg in walking['routes'][0]['legs']:
                                for step in leg['steps']:
                                    step['mode'] = 'walking'
                            self.assertIsNone(add_guidance(walking))
                            counts['walking'] += 1
                        elif move['kind'] == 'right':
                            self.assertIsNone(enriched)
                            counts['right'] += 1
                        elif move.get('failureStage') == 'response-continuity':
                            self.assertGreater(move['arrivalMarkerOffsetMeters'], .75)
                            self.assertIsNone(enriched)
        self.assertEqual(counts, dict(positive=185, right=107, walking=185))
