import json
import unittest

from prepare_ba09_remaining import ROOT, OUT, coverage
from review_preflight import validate_references
from src.big_junctions import catalog, simple_ring
from organize_review_images import BATCHES


class RemainingBA09Tests(unittest.TestCase):
    def sites(self):
        return json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']

    def test_every_candidate_is_assigned_once(self):
        inventory = coverage()
        self.assertEqual((inventory['candidateNodes'], inventory['existingSites'], inventory['remainingSites']), (32, 9, 5))
        nodes = [n for group in inventory['assignments'].values() for n in group]
        self.assertEqual(len(nodes), len(set(nodes)))

    def test_new_cases_cannot_activate_runtime_or_inherit_approval(self):
        active = {j['id'] for j in catalog()['junctions'] if j.get('enabled')}
        self.assertEqual({s['number'] for s in self.sites()}, set(range(18, 23)))
        for site in self.sites():
            with self.subTest(site=site['number']):
                self.assertFalse(site['enabled'])
                self.assertEqual(site['polygonApproved'], site['number'] in (18, 19, 21))
                self.assertEqual(site['id'] in active, site['number'] == 19)
                if site['polygon']:
                    self.assertTrue(simple_ring(site['polygon']))
                else:
                    self.assertTrue(site['review']['diagnosticOnly'])
                    self.assertEqual(site['gates'], [])

    def test_four_arm_drafts_cover_each_gate_and_keep_carriageway_evidence(self):
        sites = {s['number']: s for s in self.sites()}
        for number in (18, 19, 21):
            site = sites[number]
            arms = site['review']['proposedLogicalArms']
            assigned = [label for arm in arms.values() for labels in arm.values() for label in labels]
            self.assertEqual(len(arms), 4)
            self.assertEqual(set(assigned), {g['label'] for g in site['gates']})
            self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(sites[19]['onRoadWayIds'], [4623552, 1176949329, 1176949330])
        self.assertNotIn('Entry-2', {g['label'] for g in sites[18]['gates']})
        self.assertNotIn(1391209196, {g['osmWayId'] for g in sites[18]['gates']})
        self.assertEqual(sites[20]['review']['recommendation'], 'exclude-three-arm-junction')
        self.assertEqual(sites[22]['review']['recommendation'], 'withhold-complex-scope')
        self.assertEqual(sum(g['osmWayId'] == 105739191 for g in sites[22]['gates']), 2)

    def test_existing_approved_geometry_is_unchanged(self):
        sites = [s for batch in BATCHES for s in json.loads((batch / 'review-data.json').read_text(encoding='utf-8'))['sites']]
        references = json.loads((ROOT / 'review-reference-cases.json').read_text(encoding='utf-8'))['cases']
        validate_references(sites, references)

    def test_k19_real_routes_match_only_six_approved_relationships(self):
        from src.big_junctions import add_guidance
        report = json.loads((ROOT / 'review-batch-03-ba09-routes.json').read_text(encoding='utf-8'))
        record = next(j for j in report['junctions'] if j['number'] == 19)
        positives = 0
        for item in record['movements']:
            payload = json.loads((ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-03' / item['fixture']).read_text(encoding='utf-8'))
            with self.subTest(movement=item['id']):
                result = add_guidance(payload)
                self.assertEqual(bool(result), bool(item.get('enabled')))
                if result:
                    positives += 1
                    result['routes'][0].pop('guidance')
                    self.assertEqual(result, payload)
        self.assertEqual(positives, 6)
