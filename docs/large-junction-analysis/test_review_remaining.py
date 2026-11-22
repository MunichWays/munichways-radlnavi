import json
import unittest

from prepare_ba09_remaining import ROOT, OUT, coverage
from review_preflight import validate_references
from src.big_junctions import catalog, simple_ring
from organize_review_images import BATCHES


class RemainingBA09Tests(unittest.TestCase):
    def test_k21_frozen_routes_match_runtime_with_two_explicit_exclusions(self):
        from copy import deepcopy
        from unittest.mock import patch
        from src.big_junctions import add_guidance
        proposed = json.loads((ROOT / 'review-k21-proposed-catalog.json').read_text(encoding='utf-8'))
        report = json.loads((ROOT / 'review-batch-03-ba09-routes.json').read_text(encoding='utf-8'))
        record = next(j for j in report['junctions'] if j['number'] == 21)
        self.assertEqual(record['geometryRevision'], 2)
        self.assertEqual(next(j for j in catalog()['junctions'] if j['id'] == record['id']), next(j for j in proposed['junctions'] if j['id'] == record['id']))
        self.assertEqual(len(record['movements']), 18)
        positives = controls = 0
        with patch('src.big_junctions.catalog', return_value=catalog()):
            for item in record['movements']:
                with self.subTest(movement=item['id']):
                    payload = json.loads((ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-03' / item['fixture']).read_text(encoding='utf-8'))
                    result = add_guidance(payload)
                    self.assertTrue(item['verified'])
                    self.assertEqual(bool(result), item['enabled'])
                    if not result:
                        controls += 1
                        continue
                    positives += 1
                    hit, = result['routes'][0].pop('guidance')['junctions']
                    self.assertEqual(hit['id'], record['id'])
                    self.assertEqual(result, payload)
                    walking = deepcopy(payload)
                    for leg in walking['routes'][0]['legs']:
                        for step in leg['steps']:
                            step['mode'] = 'pushing bike'
                    self.assertIsNone(add_guidance(walking))
        self.assertEqual((positives, controls), (10, 8))
        excluded = {(m['entryLabel'], m['exitLabel']) for m in record['movements'] if m.get('explicitlyExcluded')}
        self.assertEqual(excluded, {('Entry-4', 'Exit-2'), ('Entry-3', 'Exit-2')})
        self.assertTrue(all(m['reason'] for m in record['movements'] if m.get('explicitlyExcluded')))

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
                self.assertEqual(site['id'] in active, site['number'] in (18, 19, 21))
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
        self.assertIn('Entry-2', {g['label'] for g in sites[18]['gates']})
        self.assertIn(1391209196, {g['osmWayId'] for g in sites[18]['gates']})
        self.assertEqual(sites[20]['review']['recommendation'], 'exclude-three-arm-junction')
        self.assertEqual(sites[22]['review']['recommendation'], 'withhold-complex-scope')
        self.assertEqual(sum(g['osmWayId'] == 105739191 for g in sites[22]['gates']), 2)

    def test_existing_approved_geometry_is_unchanged(self):
        sites = [s for batch in BATCHES for s in json.loads((batch / 'review-data.json').read_text(encoding='utf-8'))['sites']]
        references = json.loads((ROOT / 'review-reference-cases.json').read_text(encoding='utf-8'))['cases']
        validate_references(sites, references)

    def test_k19_prior_real_routes_match_all_eight_approved_relationships(self):
        from src.big_junctions import add_guidance
        report = json.loads((ROOT / 'review-batch-03-ba09-routes.json').read_text(encoding='utf-8'))
        record = next(j for j in report['junctions'] if j['number'] == 19)
        positives = 0
        for item in record['movements']:
            payload = json.loads((ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-03' / item['fixture']).read_text(encoding='utf-8'))
            with self.subTest(movement=item['id']):
                result = add_guidance(payload)
                self.assertEqual(bool(result), item['kind'] in ('left', 'straight'))
                if result:
                    positives += 1
                    result['routes'][0].pop('guidance')
                    self.assertEqual(result, payload)
        self.assertEqual(positives, 8)

    def test_k19_northern_curve_preserves_prior_runtime_and_approved_gates(self):
        import verify_ba09_movements as check
        site = next(s for s in self.sites() if s['number'] == 19)
        self.assertEqual((site['version'], site['status']), (3, 'geometry-approved'))
        old = json.loads((ROOT / 'review-reference-archives/k19-v2.json').read_text(encoding='utf-8'))
        self.assertEqual(site['gates'], old['gates'])
        check.ARMS[19] = {arm: (value['entries'], value['exits']) for arm, value in site['review']['proposedLogicalArms'].items()}
        self.assertEqual(len(check.plan(site)[0]), 12)
        report = json.loads((ROOT / 'review-k19-v3-draft-technical.json').read_text(encoding='utf-8'))
        self.assertFalse(report['runtimeModified'])
        self.assertFalse(report['geometryApproved'])
        for item in report['movements']:
            payload = json.loads((ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-03' / item['fixture']).read_text(encoding='utf-8'))
            movement, evidence = check.verify(site, item, payload, catalog())
            self.assertTrue(evidence['verified'], item['id'])
            self.assertEqual(bool(movement), item['kind'] != 'right')
        self.assertEqual(sum(item.get('enabled', False) for item in report['movements']), 8)

    def test_k18_gunther_entries_share_instructions_and_entry5_is_out_of_scope(self):
        site = next(s for s in self.sites() if s['number'] == 18)
        arms = site['review']['proposedLogicalArms']
        self.assertEqual(set(arms['south']['entries']), {'Entry-2', 'Entry-3'})
        self.assertEqual(arms['west']['entries'], ['Entry-4'])
        report = json.loads((ROOT / 'review-k18-v5-routes.json').read_text(encoding='utf-8'))['junctions'][0]
        self.assertFalse(any(m['entryLabel'] == 'Entry-5' for m in report['movements']))
        for entry in ('Entry-2', 'Entry-3'):
            movements = {m['exitLabel']:m for m in report['movements'] if m['entryLabel']==entry}
            self.assertEqual(movements['Exit-1']['kind'], 'straight')
            self.assertEqual(movements['Exit-4']['kind'], 'left')
        self.assertEqual(sum(bool(m.get('enabled')) for m in report['movements']), 8)

    def test_k18_refreshed_osm_restores_only_incoming_gunther_path(self):
        from prepare_review_batch_routes import graph
        from cycling_direction import bicycle_direction
        site = next(s for s in self.sites() if s['number'] == 18)
        old = json.loads((ROOT / 'review-reference-archives/k18-v3.json').read_text(encoding='utf-8'))
        self.assertEqual(site['version'], 5)
        self.assertTrue(site['polygonApproved'])
        self.assertEqual(site['polygon'], old['polygon'])
        keys = ('kind', 'location', 'osmWayId', 'label', 'forward')
        current = {g['label']: {k:g[k] for k in keys} for g in site['gates']}
        for gate in old['gates']:
            if gate['label'] != 'Entry-5':
                self.assertEqual(current[gate['label']], {k:gate[k] for k in keys})
        self.assertNotIn('Entry-5', current)
        self.assertIn('Exit-4', current)
        gates = [g for g in site['gates'] if g['osmWayId'] == 1391209196]
        self.assertEqual([(g['label'], g['kind'], g['directionBasis']) for g in gates], [('Entry-2', 'entry', 'yes')])
        way = next(w for w in site['ways'] if w['id'] == 1391209196)
        self.assertEqual(way['tags']['bicycle'], 'designated')
        self.assertEqual(way['tags']['cycleway:oneway'], 'yes')
        self.assertNotIn('oneway:bicycle', way['tags'])
        edges = graph([way], [])
        self.assertEqual(len(edges), 1)
        self.assertLess(edges[0][0][1], edges[0][1][1])
        self.assertEqual(bicycle_direction(dict(way['tags'], **{'oneway:bicycle': 'no'})), 'no')
        self.assertEqual(bicycle_direction({'highway': 'secondary', 'cycleway:oneway': 'yes'}), 'no')
