"""Offline regressions for the BA04 Schwabing-West technical batch."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import verify_ba04_project as ba04
from junction_review.model import geometry_fingerprint
from src.big_junctions import add_guidance, validate_catalog

batch = ba04.batch


class SchwabingWestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = batch.checks.review.read(ba04.SOURCE)
        cls.report = batch.checks.review.read(ba04.REPORT)
        cls.proposal = batch.checks.review.read(batch.ROOT / (ba04.PREFIX + '-proposed-catalog.json'))

    def test_both_approvals_remain_exactly_bound(self):
        self.assertEqual([s['number'] for s in self.source['sites']], [108, 109])
        self.assertEqual(self.source['blocked'], [])
        self.assertEqual(self.report['status'], 'complete')
        self.assertFalse(self.report['runtimeModified'])
        validate_catalog(self.proposal)
        for site in self.source['sites']:
            self.assertEqual(geometry_fingerprint(site), site['reviewBinding']['geometryFingerprint'])
            record = next(r for r in self.report['junctions'] if r['id'] == site['id'])
            self.assertEqual(record['reviewBinding'], site['reviewBinding'])
            self.assertEqual(record['reviewProjectId'], 'area-8192789c4e8926dd')

    def test_entry3_on_carriageway_gives_plain_four_arms(self):
        site = next(s for s in self.source['sites'] if s['id'] == 'osm-junction-1955541')
        self.assertEqual(site['geometryRevision'], 3)
        gate = next(g for g in site['gates'] if g['label'] == 'Entry-3')
        self.assertEqual((gate['osmWayId'], gate['onRoad']), (486767219, True))
        self.assertEqual({arm: sorted(labels) for arm, labels in site['proposedLogicalArms'].items()}, {
            'north': ['Entry-4', 'Exit-1'], 'east': ['Entry-1', 'Exit-2'],
            'south': ['Entry-2', 'Exit-3'], 'west': ['Entry-3', 'Exit-4']})

    def test_thomas_exclusion_stays_disabled(self):
        record = next(r for r in self.report['junctions'] if r['id'] == 'osm-junction-1955522')
        move = next(m for m in record['movements'] if (m['entryLabel'], m['exitLabel']) == ('Entry-1', 'Exit-2'))
        self.assertFalse(move['enabled'])
        self.assertTrue(move['explicitlyExcluded'])
        self.assertTrue(move['reason'].startswith('Thomas'))
        counts = {}
        for record in self.report['junctions']:
            moves = record['movements']
            counts[record['id']] = (sum(bool(m.get('enabled')) for m in moves if m['kind'] != 'right'),
                                    sum(bool(m.get('verified')) for m in moves if m['kind'] == 'right'))
        self.assertEqual(counts, {'osm-junction-1955541': (8, 4), 'osm-junction-1955522': (7, 4)})

    def test_runtime_catalog_holds_exactly_the_verified_movements(self):
        runtime = {j['id']: j for j in batch.checks.review.read(batch.checks.REPO / 'backend/src/big_junctions.json')['junctions']}
        for junction in self.proposal['junctions']:
            self.assertEqual(runtime[junction['id']], junction)
        record = runtime['osm-junction-1955522']
        move = next(m for m in record['movements'] if m['id'] == 'north-east-left-entry-1-exit-2')
        self.assertFalse(move['enabled'])

    def test_complete_catalog_preserves_real_routes_and_rejects_walking(self):
        positive = right = 0
        with patch('src.big_junctions.catalog', return_value=self.proposal):
            for junction in self.report['junctions']:
                for move in junction['movements']:
                    path = ba04.FIXTURES / move['fixture']
                    if not path.exists():
                        self.assertTrue(move.get('explicitlyExcluded'))
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
        self.assertEqual((positive, right), (15, 8))


if __name__ == '__main__':
    unittest.main()
