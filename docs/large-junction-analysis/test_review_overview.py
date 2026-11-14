import json
import unittest

from organize_review_images import ROOT, GROUPS, BATCHES, add_supplemental_sites, review_counts, city_scope


class OverviewCountsTests(unittest.TestCase):
    def groups(self):
        groups = {key: [] for key in GROUPS}
        for batch in BATCHES:
            for site in json.loads((batch / 'review-data.json').read_text(encoding='utf-8'))['sites']:
                group = '1-bestaetigt' if site['status'] == 'geometry-approved' else (
                    '3-ausgeschlossen' if site['status'] == 'permanently-excluded' else '2-offen')
                groups[group].append(site)
        catalog = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        records = json.loads((ROOT / 'review-supplemental-sites.json').read_text(encoding='utf-8'))['sites']
        add_supplemental_sites(groups, catalog, records)
        return groups, catalog, records

    def test_complete_counts_include_pilots_and_previous_exclusions_once(self):
        groups, _, _ = self.groups()
        self.assertEqual(review_counts(groups), {
            'total': 28, '1-bestaetigt': 21, '2-offen': 0, '3-ausgeschlossen': 7})

    def test_wilram_draft_preserves_other_gates_and_records_special_guidance(self):
        groups, catalog, _ = self.groups()
        site = next(s for s in groups['1-bestaetigt'] if s['id'] == 'thomasiusplatz')
        old = json.loads((ROOT / 'review-reference-archives/k10-v2.json').read_text(encoding='utf-8'))
        gates = {g['label']: g for g in site['gates']}
        for gate in old['gates']:
            if gate['label'] not in ('Entry-2', 'Exit-2'):
                self.assertEqual(gates[gate['label']], gate)
        self.assertLess(gates['Entry-2']['location'][1], next(g['location'][1] for g in old['gates'] if g['label'] == 'Entry-2'))
        self.assertEqual(gates['Entry-5']['osmWayId'], 913592181)
        self.assertEqual(gates['Exit-5']['osmWayId'], 913592181)
        plan = json.loads((ROOT / site['review']['specialGuidancePlan']).read_text(encoding='utf-8'))
        self.assertEqual(len(plan['relationships']), 6)
        self.assertFalse(plan['runtimeUnchanged'])
        self.assertTrue(plan['deploymentUnchanged'])
        standard = next(m for m in plan['relationships'] if m['entry'] == 'Entry-5' and m['exit'] == 'Exit-2')
        self.assertEqual(standard['guidance'], 'standard')
        self.assertIsNone(standard['advance'])
        runtime = next(j for j in catalog['junctions'] if j['id'] == 'thomasiusplatz')
        self.assertEqual(sum(bool(m.get('sequence')) for m in runtime['movements']), 5)

    def test_k10_exit2_stops_before_thomasiusplatz_side_street(self):
        from src.big_junctions import crossings, inside, meters, simple_ring
        groups, _, _ = self.groups()
        site = next(s for s in groups['1-bestaetigt'] if s['id'] == 'thomasiusplatz')
        correction = site['review']['exit2BoundaryCorrection']
        old = json.loads((ROOT / correction['draftArchive']).read_text(encoding='utf-8'))
        gates = {g['label']: g for g in site['gates']}
        self.assertEqual(site['version'], 4)
        self.assertTrue(simple_ring(site['polygon']))
        for gate in old['gates']:
            if gate['label'] != 'Exit-2':
                self.assertEqual(gates[gate['label']], gate)
        exit = gates['Exit-2']['location']
        self.assertEqual(gates['Exit-2']['osmWayId'], 71390770)
        self.assertLess(exit[0], correction['previousGate'][0])
        self.assertAlmostEqual(meters(exit, correction['junctionNodeLocation']), 5, delta=.02)
        street = next(w for w in site['ways'] if w['id'] == correction['excludedSideStreetWayId'])
        line = [[p['lon'], p['lat']] for p in street['geometry']]
        self.assertEqual(crossings(line, site['polygon']), [])
        self.assertFalse(any(inside(p, site['polygon']) for p in line))
        self.assertEqual(sum(s.get('textOnly', False) for items in groups.values() for s in items), 6)

    def test_duplicate_records_cannot_inflate_totals(self):
        groups, catalog, records = self.groups()
        with self.assertRaises(ValueError):
            add_supplemental_sites(groups, catalog, records)

    def test_city_scope_is_raw_candidate_count_not_reviewed_site_count(self):
        scope = city_scope()
        self.assertEqual(scope, {'candidatePoints': 495, 'date': '2026-11-06'})
        self.assertNotIn('junctionCount', scope)
