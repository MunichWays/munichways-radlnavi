"""Offline regressions for district approvals and post-OSM routing rechecks."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import verify_ba01_ba03_project as batch
from junction_review.model import geometry_fingerprint
from src.big_junctions import add_guidance, validate_catalog


class DistrictProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = batch.checks.review.read(batch.SOURCE)
        cls.report = batch.checks.review.read(batch.REPORT)
        cls.proposal = batch.checks.review.read(batch.ROOT / (batch.PREFIX + '-proposed-catalog.json'))

    def test_exact_approvals_and_all_ten_cases_remain_bound(self):
        self.assertEqual(len(self.source['sites']), 10)
        self.assertEqual(len(self.report['junctions']), 10)
        self.assertFalse(self.report['runtimeModified'])
        validate_catalog(self.proposal)
        for site in self.source['sites']:
            self.assertEqual(geometry_fingerprint(site), site['reviewBinding']['geometryFingerprint'])
            record = next(r for r in self.report['junctions'] if r['id'] == site['id'])
            self.assertEqual(record['reviewBinding'], site['reviewBinding'])

    def test_fresh_rechecks_pass_but_permanent_restrictions_stay_excluded(self):
        for number, pair in [(44, ('Entry-3', 'Exit-1')), (46, ('Entry-3', 'Exit-4'))]:
            record = next(r for r in self.report['junctions'] if r['number'] == number)
            movement = next(m for m in record['movements'] if (m['entryLabel'], m['exitLabel']) == pair)
            self.assertTrue(movement['enabled'])
        record = next(r for r in self.report['junctions'] if r['number'] == 46)
        for target in ('Exit-3', 'Exit-4'):
            move = next(m for m in record['movements'] if (m['entryLabel'], m['exitLabel']) == ('Entry-1', target))
            self.assertTrue(move['explicitlyExcluded'])
            self.assertFalse(move['enabled'])

    def test_stachus_uses_existing_angle_checks_for_only_one_straight(self):
        junction = next(j for j in self.proposal['junctions'] if j['id'] == 'osm-junction-1240216331')
        self.assertNotIn('armTopology', junction)
        self.assertEqual([(m['entryArm'], m['exitArm'], m['movement'])
                          for m in junction['movements'] if m['enabled']], [('north', 'south', 'straight')])

    def test_complete_catalog_preserves_real_routes_and_rejects_walking(self):
        positive = right = 0
        with patch('src.big_junctions.catalog', return_value=self.proposal):
            for junction in self.report['junctions']:
                for move in junction['movements']:
                    path = batch.FIXTURES / move['fixture']
                    if not path.exists():
                        continue
                    payload = batch.checks.review.read(path)
                    before = deepcopy(payload)
                    result = add_guidance(payload)
                    self.assertEqual(payload, before)
                    if move.get('enabled'):
                        hits = result['routes'][0].pop('guidance')['junctions']
                        self.assertEqual(result, payload)
                        self.assertEqual([(h['id'], h['movement']) for h in hits], [(junction['id'], move['kind'])])
                        positive += 1
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = 'walking'
                        self.assertIsNone(add_guidance(walking))
                    elif move['kind'] == 'right':
                        self.assertIsNone(result)
                        right += 1
        self.assertEqual((positive, right), (58, 41))


if __name__ == '__main__':
    unittest.main()
