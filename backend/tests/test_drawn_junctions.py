"""Frozen real-route regressions for the first map-editor-approved batch."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from src.big_junctions import add_guidance, catalog

ROOT = BACKEND.parent / 'docs/large-junction-analysis'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


class DrawnJunctionTests(unittest.TestCase):
    def test_approved_geometry_exactly_matches_active_catalog(self):
        source = read(ROOT / 'review-batch-10-drawn-six-approved.json')
        active = {j['id']: j for j in catalog()['junctions']}
        for site in source['sites']:
            junction = active[site['id']]
            self.assertTrue(junction['enabled'])
            self.assertEqual(junction['polygon']['coordinates'][0], site['polygon'])
            self.assertEqual(sum(bool(m['enabled']) for m in junction['movements']), 8)
        disabled = [m for m in active['osm-junction-2041371']['movements'] if not m['enabled']]
        self.assertEqual({(m['entryLabel'], m['exitLabel']) for m in disabled},
                         {('Entry-5', 'Exit-1'), ('Entry-5', 'Exit-2')})

    def test_all_real_routes_and_controls_against_complete_production_catalog(self):
        report = read(ROOT / 'review-batch-10-drawn-six-routes.json')
        counts = dict(positive=0, right=0, walking=0)
        for junction in report['junctions']:
            for move in junction['movements']:
                original = read(BACKEND / 'tests/fixtures/big-junctions/batch-10' / move['fixture'])
                before = deepcopy(original)
                result = add_guidance(original)
                self.assertEqual(original, before)
                with self.subTest(junction=junction['id'], movement=move['id']):
                    if move.get('enabled'):
                        self.assertIsNotNone(result)
                        hits = result['routes'][0].pop('guidance')['junctions']
                        self.assertEqual(result, original)
                        self.assertEqual(len(hits), 1)
                        self.assertEqual((hits[0]['id'], hits[0]['movement'], hits[0]['entryArm'], hits[0]['exitArm']),
                                         (junction['id'], move['kind'], move['entryArm'], move['exitArm']))
                        counts['positive'] += 1
                        walking = deepcopy(original)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = 'walking'
                        self.assertIsNone(add_guidance(walking))
                        counts['walking'] += 1
                    elif move['kind'] == 'right':
                        self.assertIsNone(result)
                        counts['right'] += 1
                    else:
                        self.assertEqual(move['entryLabel'], 'Entry-5')
                        self.assertFalse(move.get('verified', False))
        self.assertEqual(counts, dict(positive=24, right=13, walking=24))
