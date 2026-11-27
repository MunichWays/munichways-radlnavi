"""App check rules: road/cycleway variants and routes bypassing the junction (BA05 P8)."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import verify_app_site as app

FIXTURE = Path(__file__).resolve().parents[2] / 'tools/junction-review/tests/fixtures/variants-balanstrasse-p8-v1.json'


def load():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


class VariantTests(unittest.TestCase):
    def test_balanstrasse_road_and_cycleway_gates_are_equivalent(self):
        groups = app.road_path_variants(load()['site'])
        self.assertEqual(groups, {'exit': [['Exit-4', 'Exit-5']], 'entry': [['Entry-5', 'Entry-6']]})

    def test_compulsory_cycleway_keeps_the_gates_apart(self):
        site = load()['site']
        road = next(g['osmWayId'] for g in site['gates'] if g['label'] == 'Exit-4')
        for way in site['ways']:
            if way['id'] == road:
                way['tags']['bicycle'] = 'use_sidepath'
        self.assertEqual(app.road_path_variants(site), {'exit': [], 'entry': []})

    def test_human_normal_guidance_decision_wins(self):
        site = load()['site']
        site['evidence'] = dict(guidanceReview=dict(normalGuidanceGates=['Exit-4']))
        self.assertEqual(app.road_path_variants(site)['exit'], [])

    def test_distant_gates_are_not_paired(self):
        site = load()['site']
        gate = next(g for g in site['gates'] if g['label'] == 'Exit-5')
        gate['location'] = [gate['location'][0] + .0003, gate['location'][1]]  # ~22 m east
        self.assertEqual(app.road_path_variants(site)['exit'], [])


class BypassTests(unittest.TestCase):
    def setUp(self):
        data = load()
        self.site = dict(data['site'], equivalentExitGroups=[['Exit-4', 'Exit-5']])
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixtures = Path(self.temp.name)
        for key, line in data['routes'].items():
            name = key.replace('|', '-') + '.json'
            (self.fixtures / name).write_text(json.dumps(dict(routes=[dict(geometry=dict(coordinates=line))])), encoding='utf-8')

    def move(self, entry, exit, kind, **extra):
        return dict(id=f'{entry}-{exit}', entryLabel=entry, exitLabel=exit, kind=kind,
                    fixture=f'{entry}-{exit}.json', **extra)

    def report(self, *moves):
        return dict(junctions=[dict(id=self.site['id'], movements=list(moves))])

    def test_bypassing_right_control_is_verified(self):
        report = self.report(self.move('Entry-6', 'Exit-3', 'right', failureStage='polygon-crossing'))
        rights, covered = app.accept_bypasses(report, self.site, self.fixtures)
        self.assertEqual((rights, covered), ([dict(entryLabel='Entry-6', exitLabel='Exit-3')], []))
        move = report['junctions'][0]['movements'][0]
        self.assertTrue(move['verified'] and move['bypassesPolygon'])

    def test_bypassing_left_is_covered_only_by_a_passed_equivalent_exit(self):
        failed = self.move('Entry-4', 'Exit-4', 'left', failureStage='polygon-crossing')
        report = self.report(deepcopy(failed), self.move('Entry-4', 'Exit-5', 'left', enabled=True))
        rights, covered = app.accept_bypasses(report, self.site, self.fixtures)
        self.assertEqual(covered, [dict(entryLabel='Entry-4', exitLabel='Exit-4', partner='Exit-5')])
        move = report['junctions'][0]['movements'][0]
        self.assertFalse(move.get('enabled'))
        self.assertEqual(move['coverageStatus'], 'covered-equivalent-exit')
        summary = app.summarize(report, self.site['id'], [])
        self.assertTrue(summary['standard'])

        alone = self.report(deepcopy(failed), self.move('Entry-4', 'Exit-5', 'left'))
        self.assertEqual(app.accept_bypasses(alone, self.site, self.fixtures), ([], []))
        self.assertFalse(app.summarize(alone, self.site['id'], [])['standard'])

    def test_route_through_the_polygon_is_never_accepted_as_bypass(self):
        report = self.report(self.move('Entry-4', 'Exit-5', 'right', failureStage='polygon-crossing'))
        self.assertEqual(app.accept_bypasses(report, self.site, self.fixtures), ([], []))


if __name__ == '__main__':
    unittest.main()
