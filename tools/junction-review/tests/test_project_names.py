from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from test_discovery import crossing
from junction_review.discovery import prepare
from junction_review.store import Conflict, ProjectStore
from junction_review.workspace import Workspace


class ProjectNameTests(unittest.TestCase):
    def test_rename_survives_restart_and_refresh_without_touching_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory) / 'stable-id')
            dataset = dict(schemaVersion=1, project=dict(id='stable-id', city='City'),
                source=dict(adapter='test'), sites=prepare(crossing(), {})[0])
            store.import_dataset(dataset)
            site_id = dataset['sites'][0]['id']
            store.save(site_id, dict(expectedVersion=0, status='confirmed'))
            before = store.snapshot()['sites']
            result = store.rename('  My six cases  ', 'City')
            self.assertEqual(result['project']['name'], 'My six cases')
            self.assertEqual(result['project']['city'], 'City')
            self.assertEqual(result['project']['id'], 'stable-id')
            self.assertEqual(result['sites'], before)
            reopened = ProjectStore(store.directory)
            self.assertEqual(reopened.snapshot(), result)
            updated = deepcopy(dataset)
            updated['source']['note'] = 'Source refresh'
            reopened.import_dataset(updated, refresh=True)
            self.assertEqual(reopened.snapshot()['project']['name'], 'My six cases')
            self.assertEqual(reopened.snapshot()['sites'], before)
            self.assertEqual(Workspace(reopened).projects(reopened)[0]['name'], 'My six cases')
            with self.assertRaises(Conflict):
                reopened.rename('Stale write', 'City')
            for name in ['', ' ', 'x'*121, 'two\nlines', None]:
                with self.assertRaises(ValueError):
                    reopened.rename(name, 'My six cases')
