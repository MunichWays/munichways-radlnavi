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
            'total': 28, '1-bestaetigt': 20, '2-offen': 1, '3-ausgeschlossen': 7})
        self.assertEqual(sum(s.get('textOnly', False) for items in groups.values() for s in items), 6)

    def test_duplicate_records_cannot_inflate_totals(self):
        groups, catalog, records = self.groups()
        with self.assertRaises(ValueError):
            add_supplemental_sites(groups, catalog, records)

    def test_city_scope_is_raw_candidate_count_not_reviewed_site_count(self):
        scope = city_scope()
        self.assertEqual(scope, {'candidatePoints': 495, 'date': '2026-11-06'})
        self.assertNotIn('junctionCount', scope)
