"""Offline regressions for junctions finished as standard cases in the review app.

batch 15: BA05 Au-Haidhausen (K110–K114). batch 16: K110 replaced in place after
Thomas added the road gates Exit-5/Entry-6 next to the non-compulsory cycleways.
batch 17: BA06/BA07 (K115–K120); K117 Elsenheimerstraße is a special case Thomas
released with its failed movements kept on normal guidance.
A junction replaced by a later activation is checked against that later
evidence only; its earlier report stays in the repository as history.
"""
import json
import unittest

import activate_app_checks as app
from junction_review.model import geometry_fingerprint
from src.big_junctions import catalog, validate_catalog

ACTIVATIONS = ('review-batch-15-ba05-app', 'review-batch-16-k110-app', 'review-batch-17-ba06-ba07-app')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def superseded(prefix):
    """Site ids replaced by an activation after `prefix`."""
    later = ACTIVATIONS[ACTIVATIONS.index(prefix) + 1:]
    return {i for p in later for i in read(app.ROOT / (p + '-activation.json')).get('replaced', [])}


class AppActivation:
    PREFIX = BATCH = None
    NUMBERS = VERSION = REPLAY = None

    @classmethod
    def setUpClass(cls):
        cls.manifest = read(app.ROOT / (cls.PREFIX + '-activation.json'))
        cls.candidates = read(app.ROOT / (cls.PREFIX + '-catalog.json'))['junctions']
        cls.replaced_later = superseded(cls.PREFIX)
        cls.records, cls.sources = [], {}
        for item in cls.manifest['activated']:
            folder = app.ROOT / cls.PREFIX / item['appCheckFolder']
            report = read(folder / 'check-routes.json')
            cls.records.append(dict(next(r for r in report['junctions'] if r['id'] == item['id']), number=item['number']))
            cls.sources[item['id']] = read(folder / 'check-approved.json')['sites'][0]

    def test_numbers_and_exact_approval_binding(self):
        self.assertEqual({a['number'] for a in self.manifest['activated']}, self.NUMBERS)
        self.assertEqual(self.manifest['backendVersion'], self.VERSION)
        for item in self.manifest['activated']:
            source = self.sources[item['id']]
            self.assertEqual(geometry_fingerprint(source), item['reviewBinding']['geometryFingerprint'])
            self.assertEqual(source['reviewBinding'], item['reviewBinding'])
            result = read(app.ROOT / self.PREFIX / item['appCheckFolder'] / 'result.json')
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
            if candidate['id'] in self.replaced_later:
                self.assertNotEqual(runtime[candidate['id']], candidate)
            else:
                self.assertEqual(runtime[candidate['id']], candidate)

    def test_real_routes_replay_against_the_runtime_catalog(self):
        current = [r for r in self.records if r['id'] not in self.replaced_later]
        fixtures = app.REPO / 'backend/tests/fixtures/big-junctions' / self.BATCH
        self.assertEqual(app.replay(catalog(), current, lambda r: fixtures), self.REPLAY)


class Batch15Tests(AppActivation, unittest.TestCase):
    PREFIX, BATCH = 'review-batch-15-ba05-app', 'batch-15'
    NUMBERS, VERSION = {110, 111, 112, 113, 114}, '2.4.23'
    REPLAY = (40, 21)  # Without old K110 (8 + 4 routes), replaced in batch 16.

    def test_balanstrasse_variants_and_bypass(self):
        record = next(r for r in self.records if r['id'] == 'osm-junction-1955146')
        moves = {(m['entryLabel'], m['exitLabel']): m for m in record['movements']}
        self.assertTrue(moves[('Entry-2', 'Exit-4')]['enabled'] and moves[('Entry-2', 'Exit-5')]['enabled'])
        self.assertEqual(moves[('Entry-4', 'Exit-4')]['coverageStatus'], 'covered-equivalent-exit')
        self.assertFalse(moves[('Entry-4', 'Exit-4')]['enabled'])
        self.assertTrue(moves[('Entry-6', 'Exit-3')]['bypassesPolygon'])


class Batch16Tests(AppActivation, unittest.TestCase):
    PREFIX, BATCH = 'review-batch-16-k110-app', 'batch-16'
    NUMBERS, VERSION = {110}, '2.4.24'
    REPLAY = (12, 6)

    def test_k110_replaced_in_place_with_road_variants(self):
        self.assertEqual(self.manifest['replaced'], ['osm-junction-704607965'])
        self.assertEqual(self.manifest['assignedNumbers'], {})
        ids = [j['id'] for j in catalog()['junctions']]
        self.assertEqual(ids.count('osm-junction-704607965'), 1)
        result = read(app.ROOT / self.PREFIX / self.manifest['activated'][0]['appCheckFolder'] / 'result.json')
        self.assertEqual(result['variants'], {'exit': [['Exit-1', 'Exit-5']], 'entry': [['Entry-1', 'Entry-6']]})
        moves = {(m['entryLabel'], m['exitLabel']) for m in self.records[0]['movements'] if m.get('enabled')}
        # Road and cycleway variants get the same macro.
        for entry, exit_ in (('Entry-1', 'Exit-2'), ('Entry-6', 'Exit-2'), ('Entry-1', 'Exit-3'), ('Entry-6', 'Exit-3'),
                             ('Entry-3', 'Exit-1'), ('Entry-3', 'Exit-5'), ('Entry-5', 'Exit-1'), ('Entry-5', 'Exit-5')):
            self.assertIn((entry, exit_), moves)
        self.assertEqual(len(moves), 12)


class Batch17Tests(AppActivation, unittest.TestCase):
    PREFIX, BATCH = 'review-batch-17-ba06-ba07-app', 'batch-17'
    NUMBERS, VERSION = {115, 116, 117, 118, 119, 120}, '2.4.25'
    REPLAY = (52, 32)

    def test_numbers_and_exact_approval_binding(self):
        # K117 is the released special case; all others are standard.
        special = {'osm-junction-21134869'}
        self.assertEqual(self.manifest['acceptedSpecialCases'], sorted(special))
        self.assertEqual({a['number'] for a in self.manifest['activated']}, self.NUMBERS)
        for item in self.manifest['activated']:
            source = self.sources[item['id']]
            self.assertEqual(geometry_fingerprint(source), item['reviewBinding']['geometryFingerprint'])
            result = read(app.ROOT / self.PREFIX / item['appCheckFolder'] / 'result.json')
            self.assertEqual(result['standard'], item['id'] not in special)

    def test_k117_failures_stay_on_normal_guidance(self):
        record = next(r for r in self.records if r['id'] == 'osm-junction-21134869')
        moves = {(m['entryLabel'], m['exitLabel']): m for m in record['movements']}
        for pair in (('Entry-2', 'Exit-4'), ('Entry-3', 'Exit-4'), ('Entry-5', 'Exit-3'), ('Entry-1', 'Exit-4')):
            self.assertFalse(moves[pair]['enabled'], pair)
        self.assertEqual(sum(bool(m.get('enabled')) for m in record['movements']), 8)

    def test_foreign_macro_only_where_the_route_takes_an_enabled_movement(self):
        # Entry-2 -> Exit-4 really leaves through Exit-5 and gets the verified Entry-2 -> Exit-5 macro.
        record = next(r for r in self.records if r['id'] == 'osm-junction-21134869')
        fixtures = app.REPO / 'backend/tests/fixtures/big-junctions' / self.BATCH
        only = dict(record, movements=[m for m in record['movements'] if (m['entryLabel'], m['exitLabel']) == ('Entry-2', 'Exit-4')])
        self.assertEqual(app.replay(catalog(), [only], lambda r: fixtures), (0, 1))
        junction = next(j for j in catalog()['junctions'] if j['id'] == record['id'])
        partner = next(m for m in junction['movements'] if m['id'] == 'south-north-straight-entry-2-exit-5')
        hit = dict(movement='straight', entry=dict(location=partner['entry']), exit=dict(location=partner['exit']))
        self.assertTrue(app._matches_enabled(junction, hit))
        self.assertFalse(app._matches_enabled(junction, dict(hit, movement='left')))
        shifted = [partner['exit'][0] + 0.00013, partner['exit'][1]]  # about 10 m east
        self.assertFalse(app._matches_enabled(junction, dict(hit, exit=dict(location=shifted))))

if __name__ == '__main__':
    unittest.main()
