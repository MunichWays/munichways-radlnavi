import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from junction_review.districts import district_feature
from junction_review.discovery import selection_query, prepare
from test_discovery import crossing


class DistrictTests(unittest.TestCase):
    def test_all_25_districts_match_radlnavi_data(self):
        repo = Path(__file__).resolve().parents[3]
        original = (repo / 'frontend/public/data/stadtbezirke.geojson').read_bytes()
        bundled = (Path(__file__).resolve().parents[1] / 'junction_review/web/stadtbezirke.geojson').read_bytes()
        self.assertEqual(original, bundled)
        for number in range(1, 26):
            code = f'BA{number:02}'
            self.assertEqual(district_feature(code)['properties']['bezirk_nummer'], code)
        self.assertEqual(district_feature('BA04')['properties']['name'], '04 Schwabing-West')

    def test_disjoint_parts_are_both_in_query(self):
        for code in ['BA18', 'BA19']:
            polygons = district_feature(code)['geometry']['coordinates']
            query = selection_query(dict(districtId=code))
            self.assertEqual(query.count('way[highway](poly:'), len(polygons))
            for polygon in polygons:
                lon, lat = polygon[0][0]
                self.assertIn(f'{lat:.7f} {lon:.7f}', query)
            self.assertIn('around.roads:130', query)
            self.assertIn('rel(bw.all)[type=restriction]', query)

    def test_unknown_district_is_rejected_before_network(self):
        for code in ['BA00', 'BA26', '../BA04', 4]:
            with self.assertRaises(ValueError):
                selection_query(dict(districtId=code))

    def test_candidates_outside_selected_district_are_excluded(self):
        self.assertTrue(prepare(crossing(), {})[0])
        self.assertEqual(prepare(crossing(), dict(districtId='BA04'))[0], [])
