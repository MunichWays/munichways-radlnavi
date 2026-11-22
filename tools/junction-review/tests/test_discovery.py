"""Offline topology, direction, priority and workspace integration regressions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from junction_review.discovery import administrative_rings, discover, direction, lane_count, prepare, selection_query
from junction_review.model import validate_site
from junction_review.store import ProjectStore
from junction_review.render import review_svg
from junction_review.server import create_server


def crossing(three=False, roundabout=False):
    elements = [dict(type='relation', id=123, tags=dict(type='boundary'), members=[dict(type='way', role='outer', ref=999,
                     geometry=[dict(lon=x, lat=y) for x, y in [[10.9, 47.9], [11.1, 47.9], [11.1, 48.1], [10.9, 48.1], [10.9, 47.9]]])])]
    coords = {1: [11, 48], 2: [11, 48.002], 3: [11, 47.998], 4: [10.997, 48], 5: [11.003, 48]}
    for nid, p in coords.items():
        elements.append(dict(type='node', id=nid, lon=p[0], lat=p[1]))
    for wid, ids, name in [(10, [3, 1, 2], 'Nordstraße'), (20, [4, 1] if three else [4, 1, 5], 'Querstraße')]:
        tags = dict(highway='primary', name=name, lanes='4', cycleway='lane')
        if roundabout:
            tags['junction'] = 'roundabout'
        elements.append(dict(type='way', id=wid, nodes=ids, tags=tags,
                             geometry=[dict(lon=coords[n][0], lat=coords[n][1]) for n in ids]))
    return dict(elements=elements, osm3s=dict(timestamp_osm_base='2026-11-21T00:00:00Z'))


class DiscoveryTests(unittest.TestCase):
    def test_regular_four_arm_draft_is_valid_clockwise_and_repeatable(self):
        raw = crossing()
        before = deepcopy(raw)
        sites, rejected = prepare(raw, {})
        self.assertFalse(rejected)
        self.assertEqual(len(sites), 1)
        s = sites[0]
        validate_site(s)
        self.assertEqual(len(s['gates']), 8)
        self.assertEqual(s['outgoingLanes'], 8)
        self.assertEqual(len(s['logicalArms']), 4)
        self.assertTrue(all(len(labels) == 2 for labels in s['logicalArms'].values()))
        self.assertEqual(prepare(raw, {}), (sites, rejected))
        self.assertEqual(raw, before)
        self.assertNotIn('importedDecision', s)

    def test_t_and_roundabout_are_not_prepared(self):
        sites, rejected = prepare(crossing(three=True), {})
        self.assertFalse(sites)
        self.assertIn('T-Kreuzung', rejected[0]['reason'])
        self.assertFalse(prepare(crossing(roundabout=True), {})[0])

    def test_standalone_image_contains_gates_directions_and_escaped_name(self):
        site = prepare(crossing(), {})[0][0]
        site['name'] = 'Test < Nord & Süd'
        svg = review_svg(site)
        ET.fromstring(svg)
        self.assertIn('Test &lt; Nord &amp; Süd', svg)
        self.assertIn('Entry-4', svg)
        self.assertIn('Exit-4', svg)
        self.assertIn('marker-end=', svg)
        self.assertNotIn('tile.openstreetmap', svg)

    def test_missing_lanes_are_unknown_and_do_not_precede_known_large_site(self):
        raw = crossing()
        for e in raw['elements']:
            if e['type'] == 'way':
                e['tags'].pop('lanes')
        site = prepare(raw, {})[0][0]
        self.assertIsNone(site['outgoingLanes'])
        self.assertTrue(any('unbekannt' in w for w in site['preparation']['warnings']))

    def test_bicycle_direction_overrides_and_prohibitions(self):
        self.assertEqual(direction(dict(highway='residential', oneway='yes', **{'oneway:bicycle': 'no'})), [1, -1])
        self.assertEqual(direction(dict(highway='cycleway', **{'oneway:bicycle': '-1'})), [-1])
        for highway in ['motorway', 'motorway_link', 'trunk', 'steps', 'footway']:
            self.assertEqual(direction(dict(highway=highway)), [])
        self.assertEqual(direction(dict(highway='residential', bicycle='use_sidepath')), [])

    def test_no_invented_lane_counts_or_turn_lane_rounding(self):
        self.assertIsNone(lane_count(dict(lanes='3'), 1))
        self.assertIsNone(lane_count({}, 1))
        self.assertEqual(lane_count({'lanes': '5', 'lanes:both_ways': '1'}, 1), 2)
        self.assertEqual(lane_count({'lanes:forward': '3'}, 1), 3)

    def test_priority_known_lanes_descending_and_unknown_last(self):
        raw = crossing()
        for offset, lanes in [(100, '6'), (200, None)]:
            other = crossing()
            for e in other['elements']:
                e['id'] += offset
                if e['type'] == 'node':
                    e['lat'] += offset / 10000
                elif e['type'] == 'way':
                    e['nodes'] = [n + offset for n in e['nodes']]
                    for p in e['geometry']:
                        p['lat'] += offset / 10000
                    if lanes:
                        e['tags']['lanes'] = lanes
                    else:
                        e['tags'].pop('lanes')
            raw['elements'].extend(other['elements'])
        sites, _ = prepare(raw, {})
        self.assertEqual([s['outgoingLanes'] for s in sites], [12, 8, None])
        self.assertEqual([s['priorityRank'] for s in sites], [1, 2, 3])

    def test_visual_crossing_without_shared_osm_node_is_not_a_junction(self):
        raw = crossing()
        raw['elements'].append(dict(type='node', id=6, lon=11, lat=48))
        raw['elements'][-2]['nodes'] = [4, 6, 5]
        self.assertFalse(prepare(raw, {})[0])

    def test_area_filters_centers_not_intersection_polygons(self):
        area = dict(type='Polygon', coordinates=[[[10.9999, 47.9999], [11.0001, 47.9999], [11.0001, 48.0001], [10.9999, 48.0001], [10.9999, 47.9999]]])
        sites, _ = prepare(crossing(), dict(area=area))
        self.assertEqual(len(sites), 1)
        self.assertGreater(sites[0]['polygon'][0][1], 48.0001)
        with self.assertRaises(ValueError):
            selection_query(dict(area=None))
        with self.assertRaises(ValueError):
            selection_query(dict(relationId='1);out;'))

    def test_boundary_joins_reversed_segments_and_holes_exclude_centers(self):
        raw = crossing()
        relation = raw['elements'][0]
        coords = relation['members'][0]['geometry']
        relation['members'] = [dict(type='way', role='outer', ref=900, geometry=coords[:3]),
                               dict(type='way', role='outer', ref=901, geometry=list(reversed(coords[2:])))]
        self.assertEqual(administrative_rings(relation, 'outer'), [[[p['lon'], p['lat']] for p in coords]])
        self.assertEqual(len(prepare(raw, dict(relationId=123))[0]), 1)
        hole = [[10.999, 47.999], [11.001, 47.999], [11.001, 48.001], [10.999, 48.001], [10.999, 47.999]]
        relation['members'].append(dict(type='way', role='inner', ref=902, geometry=[dict(lon=x, lat=y) for x, y in hole]))
        self.assertFalse(prepare(raw, dict(relationId=123))[0])
        relation['members'].pop(1)
        with self.assertRaises(ValueError):
            prepare(raw, dict(relationId=123))

    def test_frozen_snapshot_project_roundtrip_preserves_decision(self):
        selection = dict(name='Teststadt', relationId=123)
        dataset, raw = discover(selection, fetch=lambda query: crossing())
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(directory)
            store.import_dataset(dataset)
            site = store.snapshot()['sites'][0]
            store.save(site['id'], dict(expectedVersion=0, status='confirmed'))
            self.assertFalse(store.import_dataset(dataset))
            self.assertEqual(store.snapshot()['sites'][0]['status'], 'confirmed')
            shifted = [[p[0] + .00001, p[1]] for p in site['polygon']]
            moved = store.save(site['id'], dict(expectedVersion=1, polygon=shifted))
            self.assertEqual(len(moved['gates']), 8)
            self.assertEqual(moved['status'], 'open')
            self.assertFalse(moved['decisionCurrent'])
            validate_site(moved)
        self.assertEqual(raw, crossing())
        self.assertIn('rel(123)', dataset['source']['query'])

    def test_http_preparation_switch_back_and_reopen_keep_old_and_new_decisions(self):
        selection = dict(name='Neue Stadt', relationId=123)
        data, raw = discover(selection, fetch=lambda query: crossing())
        with tempfile.TemporaryDirectory() as directory:
            original = ProjectStore(Path(directory) / 'original')
            old_data = deepcopy(data)
            # This test exercises two different junctions. Identical OSM identities
            # are deliberately skipped by cross-project deduplication.
            old_id = 'osm-junction-999999'
            old_data['sites'][0]['id'] = old_id
            old_data['sites'][0]['preparation']['candidateNodes'] = [999999]
            original.import_dataset(old_data)
            site_id = data['sites'][0]['id']
            original.save(old_id, dict(expectedVersion=0, status='excluded', note='Alter Fall bleibt geschlossen'))
            server = create_server(original, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                token = json.load(urlopen(base + '/api/project'))['token']
                project_id = 'original'
                def post(path, body):
                    nonlocal token, project_id
                    req = Request(base + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'X-Review-Token': token, 'X-Review-Project': project_id})
                    with urlopen(req, timeout=5) as response:
                        result = json.load(response)
                        if isinstance(result, dict) and 'token' in result:
                            token = result['token']
                            project_id = result['workspaceId']
                        return result
                def prepare_project():
                    job = post('/api/areas/prepare', dict(selection=selection))
                    deadline = time.monotonic() + 5
                    while job['status'] == 'running' and time.monotonic() < deadline:
                        time.sleep(.01)
                        with urlopen(base + '/api/jobs/' + job['id']) as response:
                            job = json.load(response)
                    self.assertEqual(job['status'], 'complete', job)
                    return post('/api/projects/select', dict(id=job['projectId']))
                with patch('junction_review.server.discover', return_value=(data, raw)) as fetch:
                    new = prepare_project()
                    self.assertEqual(new['sites'][0]['status'], 'open')
                    post(f'/api/sites/{site_id}/save', dict(expectedVersion=0, status='confirmed'))
                    reopened = prepare_project()
                    self.assertEqual(reopened['sites'][0]['status'], 'confirmed')
                    self.assertEqual(fetch.call_count, 1)
                self.assertTrue((Path(directory) / data['project']['id'] / 'osm-snapshot.json').exists())
                previous = post('/api/projects/select', dict(id='original'))
                self.assertEqual(previous['sites'][0]['status'], 'excluded')
                with urlopen(base + f'/api/sites/{old_id}/image.svg') as image:
                    ET.fromstring(image.read())
            finally:
                server.shutdown()
                server.server_close()
                worker.join()


if __name__ == '__main__':
    unittest.main()
