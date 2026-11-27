"""Offline regressions for batch 15: BA05 Au-Haidhausen, finished as standard cases in the review app."""
import json
import unittest

import activate_app_checks as app
from junction_review.model import geometry_fingerprint
from src.big_junctions import catalog, validate_catalog

PREFIX = 'review-batch-15-ba05-app'
FIXTURES = app.REPO / 'backend/tests/fixtures/big-junctions/batch-15'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class AppActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read(app.ROOT / (PREFIX + '-activation.json'))
        cls.candidates = read(app.ROOT / (PREFIX + '-catalog.json'))['junctions']
        cls.records, cls.sources = [], {}
        for item in cls.manifest['activated']:
            folder = app.ROOT / PREFIX / item['appCheckFolder']
            report = read(folder / 'check-routes.json')
            cls.records.append(dict(next(r for r in report['junctions'] if r['id'] == item['id']), number=item['number']))
            cls.sources[item['id']] = read(folder / 'check-approved.json')['sites'][0]

    def test_numbers_and_exact_approval_binding(self):
        self.assertEqual({a['number'] for a in self.manifest['activated']}, {110, 111, 112, 113, 114})
        self.assertEqual(self.manifest['backendVersion'], '2.4.23')
        for item in self.manifest['activated']:
            source = self.sources[item['id']]
            self.assertEqual(geometry_fingerprint(source), item['reviewBinding']['geometryFingerprint'])
            self.assertEqual(source['reviewBinding'], item['reviewBinding'])
            result = read(app.ROOT / PREFIX / item['appCheckFolder'] / 'result.json')
            self.assertTrue(result['standard'])
            self.assertEqual(result['issues'], [])

    def test_no_report_number_leaks_into_the_runtime(self):
        text = json.dumps(self.candidates)
        self.assertNotIn('K900', text)
        for item, candidate in zip(self.manifest['activated'], self.candidates):
            self.assertIn(f"K{item['number']} ", candidate['review']['evidence'])

    def test_runtime_catalog_holds_exactly_the_activated_junctions(self):
        runtime = {j['id']: j for j in catalog()['junctions']}
        validate_catalog(catalog())
        for candidate in self.candidates:
            self.assertEqual(runtime[candidate['id']], candidate)

    def test_balanstrasse_variants_and_bypass(self):
        record = next(r for r in self.records if r['id'] == 'osm-junction-1955146')
        moves = {(m['entryLabel'], m['exitLabel']): m for m in record['movements']}
        self.assertTrue(moves[('Entry-2', 'Exit-4')]['enabled'] and moves[('Entry-2', 'Exit-5')]['enabled'])
        self.assertEqual(moves[('Entry-4', 'Exit-4')]['coverageStatus'], 'covered-equivalent-exit')
        self.assertFalse(moves[('Entry-4', 'Exit-4')]['enabled'])
        self.assertTrue(moves[('Entry-6', 'Exit-3')]['bypassesPolygon'])

    def test_real_routes_replay_against_the_runtime_catalog(self):
        self.assertEqual(app.replay(catalog(), self.records, lambda r: FIXTURES), (48, 25))


if __name__ == '__main__':
    unittest.main()
