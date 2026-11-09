"""Real-route regression evidence for the proposed, not yet deployed BA09 catalog."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import verify_ba09_movements as review


class BA09MovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(review.REPORT.read_text(encoding='utf-8'))
        cls.proposed = json.loads((review.ROOT / 'review-batch-02-ba09-proposed-catalog.json').read_text(encoding='utf-8'))
        cls.sites = json.loads((review.ROOT / 'review-batch-02-ba09-images/review-data.json').read_text(encoding='utf-8'))['sites']

    def test_evidence_matches_approved_geometry(self):
        review.validate_catalog(self.proposed)
        self.assertEqual(self.report['status'], 'complete')
        for site in self.sites:
            with self.subTest(site=site['number']):
                record = next(j for j in self.report['junctions'] if j['id'] == site['id'])
                proposed = next(j for j in self.proposed['junctions'] if j['id'] == site['id'])
                self.assertTrue(site['polygonApproved'])
                self.assertEqual(record['geometryRevision'], site['version'])
                self.assertEqual(proposed['polygon']['coordinates'][0], site['polygon'])
                self.assertEqual(len(record['movements']), len({m['id'] for m in record['movements']}))

    def test_runtime_catalog_matches_release_and_keeps_k13_exclusions(self):
        actual = {j["id"]: j for j in review.catalog()["junctions"]}
        for junction in self.proposed["junctions"]:
            self.assertEqual(actual[junction["id"]], junction)
        self.assertEqual(len(review.catalog()['junctions']), 18)
        self.assertEqual(sum(m.get('enabled', False) for j in review.catalog()['junctions'] for m in j['movements']), 150)
        junction = next(j for j in review.catalog()['junctions'] if j['id'] == 'arnulf-landshuter')
        disabled = [m for m in junction['movements'] if not m.get('enabled')]
        self.assertEqual({(m['entryLabel'], m['exitLabel']) for m in disabled},
                         {('Entry-2', 'Exit-5'), ('Entry-3', 'Exit-5')})
        self.assertTrue(all(m['disabledReason'] for m in disabled))
        self.assertTrue({'mars-pappenheim', 'landsberger-barth'}.isdisjoint(j['id'] for j in review.catalog()['junctions']))

    def test_post_deployment_check_includes_all_positive_and_negative_cases(self):
        from check_review_batch_live import review_cases
        cases = review_cases()
        self.assertEqual((len(cases), sum(c['expectGuidance'] for c in cases)), (240, 150))
        k13 = [c for c in cases if c.get('junctionId') == 'arnulf-landshuter' and not c['expectGuidance'] and c['kind'] != 'right']
        self.assertEqual({(c['entryLabel'], c['exitLabel']) for c in k13}, {('Entry-2', 'Exit-5'), ('Entry-3', 'Exit-5')})

    def test_all_real_routes_against_whole_catalog(self):
        positives = controls = rejected = 0
        with patch('src.big_junctions.catalog', return_value=self.proposed):
            for site in self.report['junctions']:
                for item in site['movements']:
                    with self.subTest(site=site['number'], movement=item['id']):
                        payload = json.loads((review.FIXTURES / item['fixture']).read_text(encoding='utf-8'))
                        result = review.add_guidance(payload)
                        if not item.get('enabled'):
                            self.assertIsNone(result)
                            controls += item['kind'] == 'right'
                            rejected += item['kind'] != 'right'
                            continue
                        positives += 1
                        self.assertIsNotNone(result)
                        guidance = result['routes'][0].pop('guidance')
                        hit, = guidance['junctions']
                        self.assertEqual(hit['movement'], item['kind'])
                        self.assertEqual(result, payload)
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = 'pushing bike'
                        self.assertIsNone(review.add_guidance(walking))
        self.assertEqual((positives, controls, rejected), (70, 36, 2))

    def test_arm_classification_requires_review_and_matching_gates(self):
        for fault in ('unreviewed', 'reversed', 'duplicate_arm', 'unknown_arm', 'wrong_gate', 'missing_gate', 'zero_heading'):
            proposed = deepcopy(self.proposed)
            junction = next(j for j in proposed['junctions'] if j['id'] == 'arnulf-landshuter')
            movement = junction['movements'][0]
            topology = junction['armTopology']
            if fault == 'unreviewed':
                topology['review']['status'] = 'draft'
            elif fault == 'reversed':
                topology['clockwise'].reverse()
            elif fault == 'duplicate_arm':
                topology['clockwise'][0] = topology['clockwise'][1]
            elif fault == 'unknown_arm':
                movement['entryArm'] = 'other'
            elif fault == 'wrong_gate':
                movement['entry'] = movement['exit']
            elif fault == 'missing_gate':
                topology['gates'][movement['entryArm']]['entries'] = []
            else:
                movement['approach'] = [movement['entry'], movement['entry']]
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                review.validate_catalog(proposed)

    def test_curved_arm_order_does_not_relax_unreviewed_catalogs(self):
        proposed = deepcopy(self.proposed)
        for junction in proposed['junctions']:
            junction.pop('armTopology', None)
        with self.assertRaisesRegex(ValueError, 'directions'):
            review.validate_catalog(proposed)

    def test_arm_order_does_not_bypass_local_direction_matching(self):
        item = next(m for j in self.report['junctions'] if j['number'] == 13
                    for m in j['movements'] if m['entryLabel'] == 'Entry-1' and m['exitLabel'] == 'Exit-5')
        payload = json.loads((review.FIXTURES / item['fixture']).read_text(encoding='utf-8'))
        proposed = deepcopy(self.proposed)
        junction = next(j for j in proposed['junctions'] if j['id'] == item['junctionId'])
        movement = next(m for m in junction['movements'] if m['id'] == item['id'])
        movement['approach'].reverse()
        with patch('src.big_junctions.catalog', return_value=proposed):
            self.assertIsNone(review.add_guidance(payload))

    def test_short_reference_samples_leave_runtime_evidence_margin(self):
        for site in self.report['junctions']:
            for label, evidence in site['gateEvidence'].items():
                with self.subTest(site=site['number'], gate=label):
                    self.assertGreaterEqual(evidence['distanceMeters'], 12)

    def test_internal_connector_cannot_override_access_restrictions(self):
        source = next(s for s in self.sites if s['number'] == 17)
        for key, value in [('bicycle', 'no'), ('bicycle', 'use_sidepath'), ('access', 'private')]:
            site = deepcopy(source)
            next(w for w in site['ways'] if w['id'] == 38349617)['tags'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                review.corridor_graph(site)
