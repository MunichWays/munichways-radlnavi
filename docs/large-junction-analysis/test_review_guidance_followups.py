"""Explicit parallel-path semantics and all four Lachnerstrasse relationships."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import verify_guidance_followups as batch
from junction_review.model import geometry_fingerprint
from src.big_junctions import add_guidance, validate_catalog


class GuidanceFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = batch.batch.checks.review.read(batch.SOURCE)
        cls.report = batch.batch.checks.review.read(batch.REPORT)
        cls.proposal = batch.batch.checks.review.read(batch.batch.ROOT / (batch.PREFIX+'-proposed-catalog.json'))

    def test_maximilian_cycleway_gets_macro_and_side_road_stays_standard(self):
        site = next(s for s in self.source['sites'] if s['id']=='osm-junction-13353278127')
        self.assertEqual(site['normalGuidanceGates'], ['Exit-1'])
        self.assertNotIn('Exit-1', sum(site['proposedLogicalArms'].values(), []))
        record = next(s for s in self.report['junctions'] if s['id']==site['id'])
        for label in ('Entry-3','Entry-4'):
            self.assertTrue(next(m for m in record['movements'] if
                (m['entryLabel'],m['exitLabel'])==(label,'Exit-2'))['enabled'])
        self.assertTrue(all(not m['enabled'] for m in record['movements'] if m['exitLabel']=='Exit-1'))

    def test_parallel_exits_need_explicit_same_arm_equivalence(self):
        site = deepcopy(next(s for s in self.source['sites'] if s['id']=='osm-junction-618702506'))
        exclusions = batch.batch.checks.ambiguous_exits(site)
        self.assertFalse(any(m['exitLabel'] in ('Exit-1','Exit-2') for m in exclusions))
        self.assertEqual(exclusions, [])
        site.pop('equivalentExitGroups')
        self.assertTrue(any(m['exitLabel']=='Exit-1' for m in batch.batch.checks.ambiguous_exits(site)))
        site['equivalentExitGroups']=[['Exit-1','Exit-4']]
        with self.assertRaises(ValueError):
            batch.batch.checks.ambiguous_exits(site)

    def test_lachner_pairs_pass_without_moving_gates_or_widening_snapping_limit(self):
        site=next(s for s in self.source['sites'] if s['number']==6)
        self.assertEqual(geometry_fingerprint(site),site['reviewBinding']['geometryFingerprint'])
        record=next(s for s in self.report['junctions'] if s['number']==6)
        pairs={('Entry-4','Exit-3'),('Entry-1','Exit-3'),('Entry-2','Exit-1'),('Entry-2','Exit-4')}
        for move in record['movements']:
            if (move['entryLabel'],move['exitLabel']) in pairs:
                self.assertTrue(move['enabled'])
                payload=batch.batch.checks.review.read(batch.FIXTURES/move['fixture'])
                self.assertTrue(all(w['distance']<=5 for w in payload['waypoints']))
        self.assertEqual(sum(bool(m.get('enabled')) for m in record['movements']),8)

    def test_equivalent_entry_routes_really_receive_the_same_macro_without_duplicate_matches(self):
        record=next(s for s in self.report['junctions'] if s['id']=='osm-junction-618702506')
        covered=[m for m in record['movements'] if m.get('coverageStatus')=='covered-equivalent-entry']
        self.assertEqual(len(covered),2)
        with patch('src.big_junctions.catalog',return_value=self.proposal):
            for move in covered:
                payload=batch.batch.checks.review.read(batch.FIXTURES/move['fixture'])
                result=add_guidance(payload)
                hit,=result['routes'][0].pop('guidance')['junctions']
                self.assertEqual((hit['id'],hit['movement']),(record['id'],move['kind']))
                self.assertEqual(result,payload)

    def test_full_catalog_on_real_routes_and_walking_controls(self):
        validate_catalog(self.proposal)
        positive=right=0
        with patch('src.big_junctions.catalog',return_value=self.proposal):
            for site in self.report['junctions']:
                for move in site['movements']:
                    path=batch.FIXTURES/move['fixture']
                    if not path.exists():
                        continue
                    original=batch.batch.checks.review.read(path)
                    payload=deepcopy(original)
                    enriched=add_guidance(payload)
                    self.assertEqual(payload,original)
                    if move.get('enabled'):
                        hit,=enriched['routes'][0].pop('guidance')['junctions']
                        self.assertEqual((hit['id'],hit['movement']),(site['id'],move['kind']))
                        self.assertEqual(enriched,original)
                        positive+=1
                        for leg in payload['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode']='walking'
                        self.assertIsNone(add_guidance(payload))
                    elif move['kind'] in ('right','standard'):
                        self.assertIsNone(enriched)
                        right+=move['kind']=='right'
        self.assertEqual(positive,self.report['fullCatalogChecks']['positive'])
        self.assertGreaterEqual(positive,27)
        self.assertEqual(right,16)


if __name__=='__main__':
    unittest.main()
