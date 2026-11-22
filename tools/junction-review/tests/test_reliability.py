from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from junction_review.osm_client import OverpassClient, OsmUnavailable
from junction_review.discovery import search_areas, areas_at, discover
from junction_review.store import ProjectStore, Conflict
from junction_review.workspace import Workspace
from test_discovery import crossing


class TransportTests(unittest.TestCase):
    def test_502_is_retried_then_cached_without_mutable_aliases(self):
        calls, delays = [], []
        def opener(request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 502, 'Bad Gateway', {}, BytesIO())
            return BytesIO(json.dumps(dict(elements=[])).encode())
        client = OverpassClient(opener=opener, sleep=delays.append)
        result = client.query('[timeout:25];query;')
        result['elements'].append('local edit')
        self.assertEqual(client.query('[timeout:25];query;'), dict(elements=[]))
        self.assertEqual(len(calls), 2)
        self.assertEqual(delays, [2])

    def test_persistent_502_and_html_become_actionable_bounded_errors(self):
        attempts = []
        def broken(request, timeout):
            attempts.append(1)
            raise HTTPError(request.full_url, 502, 'Bad Gateway', {}, BytesIO())
        with self.assertRaises(OsmUnavailable):
            OverpassClient(opener=broken, sleep=lambda _: None).query('[timeout:25];q;')
        self.assertEqual(len(attempts), 3)
        with self.assertRaises(OsmUnavailable):
            OverpassClient(opener=lambda *a, **k: BytesIO(b'<html>gateway</html>'), sleep=lambda _: None).query('q;')

    def test_searches_do_not_download_all_boundary_geometries(self):
        queries = []
        def fetch(query):
            queries.append(query)
            return dict(elements=[])
        self.assertEqual(search_areas('dachau', fetch), [])
        self.assertEqual(areas_at([11,48], fetch), [])
        self.assertTrue(all('out tags bb' in q and 'out geom' not in q for q in queries))
        self.assertIn(',i]', queries[0])


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.selection = dict(name='Teststadt', relationId=123)
        self.data, self.raw = discover(self.selection, fetch=lambda _: crossing())
        self.original = ProjectStore(Path(self.temp.name) / 'original')
        self.original.import_dataset(self.data)

    def test_selecting_another_project_does_not_redirect_default_or_explicit_saves(self):
        workspace = Workspace(self.original)
        other = workspace.store('other')
        self.assertIs(other, workspace.store('other'))
        other.import_dataset(self.data)
        site_id = self.data['sites'][0]['id']
        workspace.snapshot(other)
        workspace.store().save(site_id, dict(expectedVersion=0, status='excluded', note='Original'))
        self.assertEqual(other.snapshot()['sites'][0]['status'], 'open')
        self.assertEqual(self.original.snapshot()['sites'][0]['status'], 'excluded')

    def test_cancelled_job_never_imports_and_background_work_is_bounded(self):
        started, release = threading.Event(), threading.Event()
        def prepare(selection):
            started.set()
            release.wait(3)
            return self.data, self.raw
        workspace = Workspace(self.original, prepare=prepare)
        job = workspace.start(self.selection)
        self.assertTrue(started.wait(1))
        self.assertEqual(workspace.current()['id'], job['id'])
        workspace.cancel(job['id'])
        with self.assertRaises(Conflict):
            workspace.start(self.selection)
        release.set()
        deadline = time.monotonic() + 3
        while workspace.working and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(workspace.job(job['id'])['status'], 'cancelled')
        self.assertFalse((Path(self.temp.name) / self.data['project']['id'] / 'project.json').exists())
        self.assertEqual(self.original.snapshot()['sites'][0]['status'], 'open')

    def test_simultaneous_updates_accept_one_and_reject_the_stale_version(self):
        workspace = Workspace(self.original)
        other = workspace.store('other')
        other.import_dataset(self.data)
        barrier = threading.Barrier(2)
        def update(status):
            store = workspace.store('other')
            barrier.wait(2)
            try:
                store.save(self.data['sites'][0]['id'], dict(expectedVersion=0, status=status, note='Concurrent test'))
                return 'saved'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ['confirmed', 'excluded']))
        self.assertCountEqual(results, ['saved','conflict'])
        self.assertEqual(other.snapshot()['sites'][0]['editVersion'], 1)


if __name__ == '__main__':
    unittest.main()
