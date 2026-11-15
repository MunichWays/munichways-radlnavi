"""Frozen BA01 drafts: mixed lane directions, scope boundaries and no activation."""

from copy import deepcopy
import gzip
import json
import sys
import unittest
from math import cos, radians

from prepare_ba01_radlring import DRAFTS, OUT, ROOT, SNAPSHOT, prepare
sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import inside, simple_ring
from build_review_images import extract_gates


class BA01ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(gzip.decompress(SNAPSHOT.read_bytes()))
        cls.ways = [w for w in cls.snapshot['response']['elements'] if w['type'] == 'way']
        cls.records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
        cls.sites = json.loads((OUT / 'review-data.json').read_text(encoding='utf-8'))['sites']

    def test_frozen_drafts_reproduce_without_altering_osm(self):
        saved = deepcopy(self.ways)
        for record, site in zip(self.records, self.sites):
            self.assertEqual(prepare(record, self.ways), site)
        self.assertEqual(saved, self.ways)
        self.assertTrue(any(e['type'] == 'relation' and e['id'] == 56391
                            for e in self.snapshot['response']['elements']))

    def test_approved_sites_active_other_drafts_and_exclusions_outside_runtime_catalog(self):
        catalog = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        runtime_ids = {s['id'] for s in catalog['junctions']}
        self.assertEqual([s['number'] for s in self.sites], list(range(23, 30)))
        for site in self.sites:
            self.assertFalse(site['enabled'])
            approved = site['number'] in (23, 24, 25, 28)
            self.assertEqual(site['polygonApproved'], approved)
            self.assertEqual(site['status'], 'geometry-approved' if approved else
                             'permanently-excluded' if site['number'] in (26, 27, 29) else 'geometry-draft')
            self.assertEqual(site['id'] in runtime_ids, approved)
            self.assertTrue(simple_ring(site['polygon']))
            arms = site['proposedLogicalArms']
            self.assertEqual(len(arms), 3 if site['number'] == 26 else 4)
            assigned = [label for labels in arms.values() for label in labels]
            self.assertEqual(len(assigned), len(set(assigned)))
            self.assertEqual(set(assigned), {g['label'] for g in site['gates']})

    def test_mixed_blumen_lanes_do_not_duplicate_separate_reverse_side(self):
        for number, way_id, kind in [(28, 984435670, 'entry'), (29, 51109540, 'exit')]:
            site = next(s for s in self.sites if s['number'] == number)
            self.assertEqual(len(site['gates']), 8)
            gates = [g for g in site['gates'] if g['osmWayId'] == way_id]
            self.assertEqual([g['kind'] for g in gates], [kind])
            self.assertFalse(gates[0].get('shared', False))
            self.assertEqual(gates[0]['laneEvidence']['cycleway:right'], 'lane')
            self.assertGreater(gates[0]['forward'][0], 0)
            self.assertGreater(gates[0]['forward'][1], 0)
            source = next(w for w in site['ways'] if w['id'] == way_id)
            self.assertEqual(source['tags']['cycleway:left'], 'separate')
            self.assertNotIn('oneway:bicycle', source['tags'])

    def test_neighboring_intersections_and_previous_exclusion_stay_out(self):
        positions = {n: [p['lon'], p['lat']] for w in self.ways
                     for n, p in zip(w['nodes'], w['geometry'])}
        for number, nodes in [(23, [18290982]), (26, [283538629]),
                              (28, [1485006481]), (29, [3607037929, 3607037942])]:
            site = next(s for s in self.sites if s['number'] == number)
            # For K28 inspect the actual adjacent road's nearest endpoint.
            if number == 28:
                road = next(w for w in self.ways if w['id'] == nodes[0])
                nodes = road['nodes']
            for node in nodes:
                self.assertFalse(inside(positions[node], site['polygon']), (number, node))
        inventory = json.loads((ROOT / 'review-batch-04-ba01-radlring-inventory.json').read_text(encoding='utf-8'))
        self.assertIn('gabelsberger-oskar-von-miller', inventory['preservedExclusions'])
        self.assertEqual(set(inventory['prepared']), {s['id'] for s in self.sites})

    def test_k26_removes_herzogspital_and_k29_retains_exact_geometry(self):
        archive = json.loads((ROOT / 'review-draft-archives/ba01-step1-before-exclusions.json').read_text(encoding='utf-8'))
        old = {s['number']: s for s in archive['sites']}
        current = {s['number']: s for s in self.sites}
        site = current[26]
        self.assertEqual(site['version'], 2)
        self.assertNotIn('Herzogspital', site['name'])
        self.assertNotIn(361793, site['candidateNodeIds'])
        self.assertFalse(inside([11.5653498, 48.1379117], site['polygon']))
        gates = {g['label']: g for g in site['gates']}
        self.assertNotIn('Entry-1', gates)
        self.assertNotIn('Exit-2', gates)
        for gate in old[26]['gates']:
            if gate['label'] in gates and gate['label'] != 'Exit-1':
                self.assertEqual(gate, gates[gate['label']])
        self.assertEqual(current[29]['polygon'], old[29]['polygon'])
        self.assertEqual(current[29]['gates'], old[29]['gates'])
        self.assertEqual(current[29]['review']['disposition'], 'permanently-deferred')

    def test_bicycle_exception_overrides_motor_oneway_without_changing_source(self):
        way = next(w for w in self.ways if w['id'] == 342008589)
        self.assertEqual(way['tags']['oneway'], 'yes')
        self.assertEqual(way['tags']['oneway:bicycle'], 'no')
        archive = json.loads((ROOT / 'review-draft-archives/ba01-step1-before-exclusions.json').read_text(encoding='utf-8'))
        site = next(s for s in archive['sites'] if s['number'] == 26)
        lon, lat = next(s for s in self.sites if s['number'] == 26)['origin']
        mx = 111320 * cos(radians(lat))
        project = lambda p: ((p[0] - lon) * mx, (p[1] - lat) * 111320)
        gates = extract_gates([way], site['polygon'], project, [way['id']])
        self.assertEqual({g['kind'] for g in gates}, {'entry', 'exit'})
        self.assertEqual(len(gates), 2)
        self.assertEqual(gates[0]['location'], gates[1]['location'])
        self.assertEqual(gates[0]['forward'], [-v for v in gates[1]['forward']])

    def test_k27_confirmed_josephspital_reverse_keeps_existing_labels_and_exclusion(self):
        site = next(s for s in self.sites if s['number'] == 27)
        self.assertEqual(site['version'], 2)
        self.assertEqual(site['status'], 'permanently-excluded')
        self.assertFalse(site['enabled'])
        gates = {g['label']: g for g in site['gates']}
        self.assertEqual(gates['Exit-5']['osmWayId'], 144135870)
        self.assertEqual(gates['Entry-1']['location'], gates['Exit-5']['location'])
        self.assertEqual(gates['Entry-1']['forward'], [-v for v in gates['Exit-5']['forward']])
        archive = json.loads((ROOT / 'review-draft-archives/ba01-step1-before-exclusions.json').read_text(encoding='utf-8'))
        old = next(s for s in archive['sites'] if s['number'] == 27)
        self.assertEqual(old['polygon'], site['polygon'])
        for gate in old['gates']:
            if gate['label'] != 'Entry-1':
                self.assertEqual(gate, gates[gate['label']])
        self.assertEqual(site['review']['directionCorrection']['oneway:bicycle'], 'no')
        source = next(w for w in site['ways'] if w['id'] == 144135870)
        self.assertNotIn('oneway:bicycle', source['tags'])


if __name__ == '__main__':
    unittest.main()
