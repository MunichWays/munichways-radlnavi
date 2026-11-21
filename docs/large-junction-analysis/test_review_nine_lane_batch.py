"""Frozen geometry checks for the next four nine-lane candidates."""
from copy import deepcopy
import gzip
import json
import sys
import unittest

from prepare_nine_lane_review import ROOT, SOURCE, DRAFTS, OUT, prepare

sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import simple_ring


class NineLaneBatchTests(unittest.TestCase):
    def test_frozen_drafts_reproduce_without_activation(self):
        sources = {s['id']: s['elements'] for s in json.loads(gzip.decompress(SOURCE.read_bytes()))['sites']}
        original = deepcopy(sources)
        records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
        sites = json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']
        self.assertEqual([prepare(r, sources[r['id']]) for r in records], sites)
        self.assertEqual(sources, original)
        runtime = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        for site, count in zip(sites, [10, 10, 8, 9]):
            with self.subTest(number=site['number']):
                self.assertEqual(site['id'] in {j['id'] for j in runtime['junctions']}, site['number'] != 47)
                self.assertFalse(site['enabled'])
                self.assertEqual(site['polygonApproved'], site['number'] != 47)
                self.assertEqual(site['status'], 'permanently-excluded' if site['number'] == 47 else 'geometry-approved')
                self.assertTrue(simple_ring(site['polygon']))
                self.assertEqual(len(site['gates']), count)
                if site['number'] != 48:
                    arms = site['proposedLogicalArms']
                    self.assertEqual(len(arms), 4)
                    labels = [label for gates in arms.values() for label in gates]
                    self.assertEqual(len(labels), len(set(labels)))
                    self.assertEqual(set(labels), {g['label'] for g in site['gates']})
        self.assertNotIn(153583742, {g['osmWayId'] for g in sites[-1]['gates']})
        self.assertEqual({g['kind'] for g in sites[1]['gates'] if g['osmWayId'] == 30442176}, {'entry', 'exit'})

    def test_full_proposal_replays_real_routes_with_standard_only_and_excluded_controls(self):
        from unittest.mock import patch
        from src.big_junctions import add_guidance, validate_catalog
        report = json.loads((ROOT / 'review-batch-09-nine-lanes-routes.json').read_text(encoding='utf-8'))
        proposal = json.loads((ROOT / 'review-batch-09-nine-lanes-proposed-catalog.json').read_text(encoding='utf-8'))
        validate_catalog(proposal)
        self.assertFalse(report['runtimeModified'])
        self.assertEqual({s['number'] for s in report['junctions']}, {48, 49, 50})
        counts = dict(positive=0, ordinary=0, right=0, excluded=0, walking=0)
        fixtures = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-09'
        with patch('src.big_junctions.catalog', return_value=proposal):
            for site in report['junctions']:
                self.assertEqual(sum(bool(m.get('enabled')) for m in site['movements']), 8)
                for item in site['movements']:
                    payload = json.loads((fixtures / item['fixture']).read_text(encoding='utf-8'))
                    result = add_guidance(payload)
                    if item.get('enabled'):
                        self.assertIsNotNone(result)
                        hit, = result['routes'][0].pop('guidance')['junctions']
                        self.assertEqual(hit['movement'], item['kind'])
                        self.assertEqual(result, payload)
                        counts['positive'] += 1
                        walking = deepcopy(payload)
                        for leg in walking['routes'][0]['legs']:
                            for step in leg['steps']:
                                step['mode'] = 'walking'
                        self.assertIsNone(add_guidance(walking))
                        counts['walking'] += 1
                    else:
                        self.assertIsNone(result)
                        counts['ordinary' if item['kind'] == 'standard' else 'right' if item['kind'] == 'right' else 'excluded'] += 1
        self.assertEqual(counts, dict(positive=24, ordinary=8, right=13, excluded=2, walking=24))
        site = next(s for s in report['junctions'] if s['number'] == 48)
        self.assertEqual(site['normalGuidanceGates'], ['Entry-1', 'Exit-2'])
        self.assertTrue(all(m['kind'] == 'standard' for m in site['movements'] if m['entryLabel'] == 'Entry-1' or m['exitLabel'] == 'Exit-2'))
