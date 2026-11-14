"""Reproduce the approved revision checks against every frozen real response."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from src.big_junctions import add_guidance, catalog, crossings
from verify_review_updates import ROOT, REPORT, FIXTURES, read, verify_wilram
from verify_ba09_movements import verify, ARMS


class UpdatedReviewTests(unittest.TestCase):
    def test_activated_catalog_matches_all_updated_regular_routes(self):
        positives = 0
        for record in read(REPORT)['junctions']:
            for item in record['movements']:
                if item['kind'] == 'special':
                    continue
                with self.subTest(junction=record['id'], movement=item['id']):
                    payload = read(FIXTURES / item['fixture'])
                    result = add_guidance(payload)
                    self.assertEqual(bool(result), item['enabled'])
                    if result:
                        positives += 1
                        hit, = result['routes'][0].pop('guidance')['junctions']
                        self.assertEqual(hit['id'], record['id'])
                        self.assertEqual(result, payload)
        self.assertEqual(positives, 24)

    def sites(self):
        return {s['number']: s for batch in ('review-batch-01-images', 'review-batch-03-ba09-remaining-images')
                for s in read(ROOT / batch / 'review-data.json')['sites']}

    def test_all_42_routes_and_walking_controls_reproduce_without_activation(self):
        report = read(REPORT)
        proposed = read(ROOT / 'review-updates-2026-11-14-proposed-catalog.json')
        sites = self.sites()
        self.assertFalse(report['runtimeModified'])
        self.assertTrue(report['wholeCatalogVerified'])
        self.assertEqual(report['walkingControlsPassed'], 24)
        total = 0
        for record in report['junctions']:
            site = sites[record['number']]
            self.assertTrue(site['polygonApproved'])
            self.assertEqual(record['geometryRevision'], site['version'])
            self.assertEqual(sum(m.get('enabled', False) for m in record['movements']), 8)
            self.assertEqual(sum(m.get('verified', False) for m in record['movements'] if m['kind'] == 'right' and m['scope'] == 'standard-four-arm'), 4)
            standard = deepcopy(site)
            if site['number'] == 10:
                standard['gates'] = [g for g in standard['gates'] if g['label'] not in ('Entry-5', 'Exit-5')]
            ARMS[site['number']] = {arm: (v['entries'], v['exits']) for arm, v in site['review']['proposedLogicalArms'].items()}
            for item in record['movements']:
                total += 1
                payload = read(FIXTURES / item['fixture'])
                before = deepcopy(payload)
                if item['scope'] == 'wilram':
                    self.assertTrue(verify_wilram(site, item, payload)['geometryVerified'])
                else:
                    _, evidence = verify(standard, item, payload, catalog())
                    self.assertTrue(evidence['verified'])
                with patch('src.big_junctions.catalog', return_value=proposed):
                    result = add_guidance(payload)
                    self.assertEqual(bool(result), bool(item.get('enabled')), item['id'])
                    if result:
                        result['routes'][0].pop('guidance')
                        self.assertEqual(result, payload)
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = 'pushing bike'
                        self.assertIsNone(add_guidance(walking))
                self.assertEqual(payload, before)
        self.assertEqual(total, 42)

    def test_wilram_special_sequences_are_not_falsely_marked_implemented(self):
        # This report preserves the earlier geometry-only technical stage.
        record = next(j for j in read(REPORT)['junctions'] if j['number'] == 10)
        special = [m for m in record['movements'] if m['kind'] == 'special']
        self.assertEqual(len(special), 5)
        for item in special:
            self.assertTrue(item['geometryVerified'])
            self.assertTrue(item['implementationPending'])
            self.assertFalse(item['enabled'])
        right = next(m for m in record['movements'] if m['scope'] == 'wilram' and m['kind'] == 'right')
        self.assertTrue(right['bypassesPolygon'])
        self.assertIn(145178206, right['verifiedCyclingWayIds'])
        site = self.sites()[10]
        payload = read(FIXTURES / right['fixture'])
        self.assertEqual(crossings(payload['routes'][0]['geometry']['coordinates'], site['polygon']), [])
        self.assertFalse(record['specialGuidanceImplemented'])

    def test_implementation_stage_is_separate_and_protocol_gated(self):
        report = read(ROOT / 'review-wilram-sequences-implementation.json')
        self.assertFalse(report['deploymentChanged'])
        record, = report['junctions']
        self.assertTrue(record['specialGuidanceImplemented'])
        special = [m for m in record['movements'] if m['kind'] == 'special']
        self.assertEqual(len(special), 5)
        self.assertTrue(all(m['enabled'] and m['verified'] and m['requiresProtocolVersion'] == 2 for m in special))
        self.assertTrue(all(not m['implementationPending'] for m in special))

    def test_runtime_uses_approved_k07_k10_k19(self):
        current = {j['id']: j for j in catalog()['junctions']}
        proposed = read(ROOT / 'review-updates-2026-11-14-proposed-catalog.json')
        for identifier in ('mars-pappenheim', 'romanplatz-nord'):
            self.assertEqual(current[identifier], next(j for j in proposed['junctions'] if j['id'] == identifier))
        for number, identifier in ((10, 'thomasiusplatz'), (19, 'romanplatz-nord')):
            archived = read(ROOT / f'review-reference-archives/k{number}-v2.json')
            from review_preflight import fingerprint
            self.assertEqual(fingerprint(archived), archived['review']['reviewedGeometrySha256'])
            if number == 19:
                self.assertEqual(current[identifier]['polygon']['coordinates'][0], self.sites()[19]['polygon'])
            else:
                self.assertEqual(current[identifier]['polygon']['coordinates'][0], self.sites()[10]['polygon'])
                self.assertEqual(sum(bool(m.get('sequence')) for m in current[identifier]['movements']), 5)
        self.assertEqual(sum(m.get('enabled', False) for m in current['romanplatz-nord']['movements']), 8)
