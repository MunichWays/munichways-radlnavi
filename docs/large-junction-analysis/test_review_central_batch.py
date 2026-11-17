"""Frozen central drafts retain legal lane directions and distinct junction scope."""
from copy import deepcopy
import gzip
import json
import unittest
from unittest.mock import patch

from prepare_central_review import ROOT, SOURCE, DRAFTS, OUT, prepare
from src.big_junctions import add_guidance, inside, simple_ring


class CentralBatchTests(unittest.TestCase):
    def test_drafts_reproduce_offline_without_changing_source_or_runtime(self):
        sources = {s['id']: s['elements'] for s in
                   json.loads(gzip.decompress(SOURCE.read_bytes()))['sites']}
        original = deepcopy(sources)
        records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
        sites = json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']
        self.assertEqual([prepare(r, sources[r['id']]) for r in records], sites)
        self.assertEqual(sources, original)
        catalog = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        self.assertEqual([s['number'] for s in sites], list(range(42, 47)))
        for site, count in zip(sites, [8, 8, 8, 8, 9]):
            with self.subTest(number=site['number']):
                self.assertTrue(simple_ring(site['polygon']))
                self.assertFalse(site['enabled'])
                self.assertTrue(site['polygonApproved'])
                self.assertEqual(site['status'], 'geometry-approved')
                self.assertEqual(len(site['gates']), count)
                assigned = [label for labels in site['proposedLogicalArms'].values() for label in labels]
                self.assertEqual(len(assigned), len(set(assigned)))
                self.assertEqual(set(assigned), {g['label'] for g in site['gates']})
                self.assertTrue(all(site['proposedLogicalArms'].values()))
                if site['number'] != 46:
                    for labels in site['proposedLogicalArms'].values():
                        self.assertEqual(sum(label.startswith('Entry-') for label in labels), 1)
                        self.assertEqual(sum(label.startswith('Exit-') for label in labels), 1)
                self.assertIn(site['id'], {j['id'] for j in catalog['junctions']})
                ways = {w['id']: w for w in site['ways']}
                for gate in site['gates']:
                    if gate['osmWayId'] in site['onRoadWayIds']:
                        self.assertNotIn(ways[gate['osmWayId']]['tags'].get('bicycle'), {'no', 'use_sidepath'})
                        self.assertTrue(gate['laneEvidence'])

    def test_stiglmaier_excludes_schleissheimer_and_preserves_lane_direction(self):
        site = next(s for s in json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']
                    if s['number'] == 45)
        branch = next(w for w in site['ways'] if w['id'] == 168045899)
        self.assertFalse(any(inside([p['lon'], p['lat']], site['polygon']) for p in branch['geometry']))
        self.assertFalse(any(g['osmWayId'] == branch['id'] for g in site['gates']))
        lane = [g for g in site['gates'] if g['osmWayId'] == 86969970]
        self.assertEqual([g['kind'] for g in lane], ['exit'])
        source = next(w for w in site['ways'] if w['id'] == 86969970)
        self.assertEqual(source['tags']['cycleway:left'], 'separate')
        self.assertEqual(source['tags']['cycleway:right'], 'lane')
        self.assertNotIn('oneway:bicycle', source['tags'])

    def test_technical_proposal_keeps_detouring_k44_relationship_disabled(self):
        report = json.loads((ROOT / 'review-batch-08-central-routes.json').read_text(encoding='utf-8'))
        self.assertFalse(report['runtimeModified'])
        self.assertEqual(report['fullCatalogChecks'],
                         dict(positive=38, rightTurnControls=21, walkingControls=38))
        records = {s['number']: s for s in report['junctions']}
        self.assertEqual(set(records), {42, 43, 44, 45, 46})
        for number, expected in [(42, 8), (43, 8), (44, 7), (45, 8), (46, 7)]:
            self.assertEqual(sum(bool(m.get('enabled')) for m in records[number]['movements']), expected)
        self.assertEqual(records[43]['gateEvidence']['Entry-1']['distanceMeters'], 25)
        self.assertEqual(records[43]['gateEvidence']['Exit-2']['distanceMeters'], 15)
        blocked = [m for m in records[44]['movements'] if m['kind'] != 'right' and not m.get('enabled')]
        self.assertEqual([(m['entryLabel'], m['exitLabel']) for m in blocked], [('Entry-3', 'Exit-1')])
        self.assertEqual(blocked[0]['diagnosis']['stage'], 'route-selection')
        self.assertIn('Hirtenstraße', blocked[0]['reason'])
        self.assertEqual(blocked[0]['deferredUntil'], '2026-11-23')
        fixture = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-08' / blocked[0]['fixture']
        payload = json.loads(fixture.read_text(encoding='utf-8'))
        original = deepcopy(payload)
        proposal = json.loads((ROOT / 'review-batch-08-central-proposed-catalog.json').read_text(encoding='utf-8'))
        with patch('src.big_junctions.catalog', return_value=proposal):
            result = add_guidance(payload)
        # This detour crosses twice: west/east, then south/north. Those two
        # actually ridden straight crossings remain valid; no left macro may
        # describe the requested west/north relationship.
        hits = result['routes'][0].pop('guidance')['junctions']
        self.assertEqual([(h['entryArm'], h['exitArm'], h['movement']) for h in hits],
                         [('west', 'east', 'straight'), ('south', 'north', 'straight')])
        self.assertEqual(result, original)
        self.assertEqual(payload, original)

    def test_k46_right_only_entry_and_unsupported_footway_remain_excluded(self):
        report = json.loads((ROOT / 'review-batch-08-central-routes.json').read_text(encoding='utf-8'))
        site = next(s for s in report['junctions'] if s['number'] == 46)
        entry = [m for m in site['movements'] if m['entryLabel'] == 'Entry-1']
        self.assertEqual(len(entry), 3)
        right = next(m for m in entry if m['kind'] == 'right')
        self.assertEqual(right['exitLabel'], 'Exit-1')
        self.assertTrue(right['verified'])
        for m in entry:
            if m['kind'] != 'right':
                self.assertTrue(m['explicitlyExcluded'])
                self.assertFalse(m['enabled'])
        failed = next(m for m in site['movements']
                      if (m['entryLabel'], m['exitLabel']) == ('Entry-3', 'Exit-4'))
        self.assertFalse(failed['enabled'])
        self.assertEqual(failed['diagnosis']['osmWayId'], 1017221653)
        self.assertEqual(failed['deferredUntil'], '2026-11-23')
        self.assertIn('except=bicycle', failed['recheckReason'])


if __name__ == '__main__':
    unittest.main()
