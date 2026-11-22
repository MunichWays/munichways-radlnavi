from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from junction_review.adapters import export_review, import_radlnavi
from junction_review.geometry import ring
from junction_review.model import summarize, validate_dataset
from junction_review.server import create_server
from junction_review.store import Conflict, ProjectStore

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / 'docs/large-junction-analysis/review-batch-09-nine-lanes-images/review-data.json'


class ProjectFixture:
    @classmethod
    def setUpClass(cls):
        cls.dataset = import_radlnavi(SOURCE, 'munich', 'München')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ProjectStore(self.temp.name)
        self.store.import_dataset(self.dataset)
        self.site = self.store.snapshot()['sites'][0]


class ProjectTests(ProjectFixture, unittest.TestCase):
    def test_import_is_idempotent_preserves_source_and_decisions(self):
        original = SOURCE.read_bytes()
        approved = self.store.save(self.site['id'], dict(expectedVersion=0, status='confirmed', note='Geprüft'))
        self.assertFalse(self.store.import_dataset(self.dataset))
        reopened = ProjectStore(self.temp.name).snapshot()['sites'][0]
        self.assertEqual(reopened, approved)
        self.assertEqual(SOURCE.read_bytes(), original)
        self.assertEqual(approved['technicalStatus'], 'not-run')
        self.assertEqual(approved['deploymentStatus'], 'unknown')

    def test_geometry_edit_relocates_gates_invalidates_approval_and_preserves_history(self):
        self.store.save(self.site['id'], dict(expectedVersion=0, status='confirmed'))
        polygon = [[p[0] + .000002, p[1]] for p in self.site['polygon']]
        preview = self.store.save(self.site['id'], dict(expectedVersion=1, polygon=polygon), preview=True)
        self.assertEqual(self.store.snapshot()['sites'][0]['editVersion'], 1)
        result = self.store.save(self.site['id'], dict(expectedVersion=1, polygon=polygon))
        self.assertEqual(result['geometryFingerprint'], preview['geometryFingerprint'])
        self.assertEqual(result['status'], 'open')
        self.assertFalse(result['decisionCurrent'])
        self.assertEqual(result['geometryRevision'], 2)
        self.assertEqual([g['id'] for g in result['gates']], [g['id'] for g in self.site['gates']])
        self.assertNotEqual(result['gates'], self.site['gates'])
        self.assertEqual(result['history'][-1]['previousGeometry']['polygon'], self.site['polygon'])
        self.assertEqual(export_review(self.store.snapshot())['sites'], [])

    def test_stale_tab_cannot_overwrite_another_decision(self):
        self.store.save(self.site['id'], dict(expectedVersion=0, status='confirmed'))
        with self.assertRaises(Conflict):
            self.store.save(self.site['id'], dict(expectedVersion=0, status='excluded', note='alt'))
        self.assertEqual(self.store.snapshot()['sites'][0]['status'], 'confirmed')

    def test_technical_results_are_bound_to_geometry_and_never_activate(self):
        with self.assertRaises(ValueError):
            self.store.import_technical(dict(status='complete', runtimeModified=True))
        self.store.save(self.site['id'], dict(expectedVersion=0, status='confirmed'))
        report = dict(status='complete', runtimeModified=False, junctions=[dict(id=self.site['id'],
            reviewBinding={k:self.site[k] for k in ('geometryFingerprint', 'sourceFingerprint')},
            movements=[dict(kind='left', enabled=True), dict(kind='straight', enabled=False, reason='ambiguous')])])
        self.assertEqual(self.store.import_technical(report), 1)
        self.assertEqual(self.store.import_technical(report), 0)
        result = self.store.snapshot()['sites'][0]
        self.assertEqual(result['technicalStatus'], '1/2 Links-/Geradeausbeziehungen technisch bestanden')
        self.assertEqual(result['deploymentStatus'], 'not-live')
        self.assertEqual(result['status'], 'confirmed')
        result = self.store.save(self.site['id'], dict(expectedVersion=2, polygon=[[p[0]+.000001,p[1]] for p in self.site['polygon']]))
        self.assertFalse(result['evidenceCurrent'])
        with self.assertRaises(Conflict):
            self.store.import_technical(report)

    def test_invalid_shape_and_missing_gate_crossings_cannot_be_saved(self):
        before = self.store.snapshot()
        for polygon in [
            [[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]],
            [[0, 0], [1, 0], [1, 1], [0, 0]],
        ]:
            with self.assertRaises(ValueError):
                self.store.save(self.site['id'], dict(expectedVersion=0, polygon=polygon))
        self.assertEqual(self.store.snapshot(), before)

    def test_exclusions_and_deferrals_require_reason_and_export_only_confirmed(self):
        with self.assertRaises(ValueError):
            self.store.save(self.site['id'], dict(expectedVersion=0, status='excluded'))
        self.store.save(self.site['id'], dict(expectedVersion=0, status='deferred', note='OSM abwarten', deferredUntil='2026-11-23'))
        other = self.dataset['sites'][1]
        self.store.save(other['id'], dict(expectedVersion=0, status='confirmed'))
        result = export_review(self.store.snapshot())
        self.assertEqual([s['id'] for s in result['sites']], [other['id']])
        self.assertTrue(result['requiresTechnicalValidation'])
        self.assertNotIn('enabled', result['sites'][0])

    def test_source_refresh_invalidates_only_changed_site_and_archives_edits(self):
        for base in self.dataset['sites'][:2]:
            self.store.save(base['id'], dict(expectedVersion=0, status='confirmed'))
        edited_polygon = [[p[0] + .000002, p[1]] for p in self.site['polygon']]
        self.store.save(self.site['id'], dict(expectedVersion=1, polygon=edited_polygon, status='confirmed'))
        dataset = deepcopy(self.dataset)
        dataset['sites'][0]['sourceFingerprint'] = 'different-osm'
        with self.assertRaises(Conflict):
            self.store.import_dataset(dataset)
        self.store.import_dataset(dataset, refresh=True)
        sites = self.store.snapshot()['sites']
        self.assertEqual([s['status'] for s in sites[:2]], ['open', 'confirmed'])
        self.assertFalse(sites[0]['decisionCurrent'])
        self.assertEqual(sites[0]['history'][-1]['action'], 'source-refresh')
        self.assertEqual(sites[0]['history'][-1]['previousGeometry']['polygon'], edited_polygon)
        self.assertEqual(sites[0]['polygon'], self.site['polygon'])
        self.assertEqual(len(list((Path(self.temp.name) / 'imports').glob('*.json'))), 2)

    def test_generic_city_and_area_are_not_tied_to_munich(self):
        other = deepcopy(self.dataset)
        other['project'] = dict(id='other-city', city='Andere Stadt', district='Zentrum', area=None)
        validate_dataset(other)
        p = self.site['origin']
        area = dict(type='Polygon', coordinates=[[[p[0]-.001, p[1]-.001], [p[0]+.001,p[1]-.001],
            [p[0]+.001,p[1]+.001], [p[0]-.001,p[1]+.001], [p[0]-.001,p[1]-.001]]])
        subset = import_radlnavi(SOURCE, 'subset', 'München', area=area)
        self.assertEqual([s['number'] for s in subset['sites']], [47])

    def test_bad_coordinates_and_collinear_polygons_rejected(self):
        for polygon in [[[0, 0], [1, 0], [2, 0], [0, 0]], [[0, 0], [float('nan'), 1], [1, 0], [0, 0]]]:
            with self.assertRaises(ValueError):
                ring(polygon)

    def test_gate_evidence_must_lie_on_both_boundary_and_source_way(self):
        dataset = deepcopy(self.dataset)
        dataset['sites'][0]['gates'][0]['location'] = dataset['sites'][0]['polygon'][0]
        with self.assertRaisesRegex(ValueError, 'OSM-Weg'):
            validate_dataset(dataset)

    def test_compact_report_names_open_topology_without_large_geometry(self):
        report = summarize(self.store.snapshot())
        self.assertEqual(report['total'], 4)
        self.assertEqual(report['counts']['open'], 4)
        self.assertEqual([s['number'] for s in report['sites']], [50, 49, 48, 47])
        self.assertEqual(len(next(s for s in report['sites'] if s['number'] == 48)['unassignedGates']), 10)
        self.assertNotIn('polygon', report['sites'][0])

    def test_unchanged_polygon_does_not_create_an_edit_or_invalidate_approval(self):
        approved = self.store.save(self.site['id'], dict(expectedVersion=0, status='confirmed'))
        preview = self.store.save(self.site['id'], dict(expectedVersion=1, polygon=self.site['polygon']), preview=True)
        self.assertEqual(preview, approved)
        with self.assertRaisesRegex(ValueError, 'Keine Änderung'):
            self.store.save(self.site['id'], dict(expectedVersion=1, polygon=self.site['polygon']))

    def test_display_metadata_refresh_does_not_require_rechecking_geometry(self):
        raw = json.loads(SOURCE.read_text(encoding='utf-8'))
        raw['sites'][0]['note'] = 'Nur eine redaktionelle Änderung'
        source = Path(self.temp.name) / 'updated.json'
        source.write_text(json.dumps(raw), encoding='utf-8')
        updated = import_radlnavi(source, 'munich', 'München')
        self.store.save(self.site['id'], dict(expectedVersion=0, status='confirmed'))
        self.store.import_dataset(updated, refresh=True)
        result = self.store.snapshot()['sites'][0]
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(result['note'], raw['sites'][0]['note'])

    def test_edit_all_four_real_sites_retains_labels_and_directed_crossings(self):
        for site in self.store.snapshot()['sites']:
            polygon = [[p[0] + .000001, p[1]] for p in site['polygon']]
            result = self.store.save(site['id'], dict(expectedVersion=0, polygon=polygon), preview=True)
            self.assertEqual([g['label'] for g in result['gates']], [g['label'] for g in site['gates']])
            self.assertTrue(all(.99 < sum(v*v for v in g['forward']) < 1.01 for g in result['gates']))


class HttpTests(ProjectFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.server = create_server(self.store, 0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop_server)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def request(self, path, data=None, headers=None):
        request = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
            headers=headers or {})
        return urlopen(request, timeout=5)

    def test_rename_saved_project_over_http(self):
        with self.request('/api/project') as response:
            before = json.load(response)
        headers = {'Content-Type': 'application/json', 'X-Review-Token': before['token']}
        with self.request('/api/projects/rename', dict(id=before['workspaceId'],
                name='Renamed project', expectedName=before['project']['name']), headers) as response:
            renamed = json.load(response)
        self.assertEqual(renamed['project']['name'], 'Renamed project')
        self.assertEqual(renamed['sites'], before['sites'])
        with self.request('/api/projects') as response:
            self.assertEqual(json.load(response)[0]['name'], 'Renamed project')

    def test_real_http_save_restart_export_and_csrf(self):
        with self.request('/api/project') as response:
            token = json.load(response)['token']
        path = f"/api/sites/{self.site['id']}/save"
        payload = dict(expectedVersion=0, status='confirmed', note='HTTP geprüft')
        for headers in [dict(), {'Origin': 'https://example.org', 'X-Review-Token': token}]:
            with self.assertRaises(HTTPError) as error:
                self.request(path, payload, headers)
            self.assertEqual(error.exception.code, 403)
        headers = {'Content-Type': 'application/json', 'X-Review-Token': token}
        with self.request(path, payload, headers) as response:
            self.assertEqual(json.load(response)['status'], 'confirmed')
        with self.assertRaises(HTTPError) as error:
            self.request(path, payload, headers)
        self.assertEqual(error.exception.code, 409)
        with self.request('/api/export') as response:
            result = json.load(response)
            self.assertEqual(len(result['sites']), 1)
        with self.request('/app.js') as response:
            self.assertIn('text/javascript', response.headers['Content-Type'])
            self.assertIn('img-src \'self\' data: https://tile.openstreetmap.org;', response.headers['Content-Security-Policy'])
            self.assertEqual(response.headers['Referrer-Policy'], 'strict-origin-when-cross-origin')
        with self.assertRaises(HTTPError) as error:
            self.request('/../../project.json')
        self.assertEqual(error.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
