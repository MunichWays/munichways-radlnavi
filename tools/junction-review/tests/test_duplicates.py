from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from test_discovery import crossing
from junction_review.discovery import prepare
from junction_review.duplicates import duplicate_of
from junction_review.store import Conflict, ProjectStore
from junction_review.workspace import Workspace


class DuplicateTests(unittest.TestCase):
    def test_legacy_aliases_exclusions_and_adjacent_junctions(self):
        old = dict(id='lane-candidate-123', name='Old', origin=[11,48])
        self.assertIsNotNone(duplicate_of(dict(id='osm-junction-123'), [('main',old)]))
        legacy = dict(id='named', name='Excluded', provenance={'exclusion':{'referenceNodeIds':[456]}})
        self.assertIsNotNone(duplicate_of(dict(id='osm-junction-456'), [('main',legacy)]))
        # Nearby junctions and split geometries must not disappear by proximity.
        self.assertIsNone(duplicate_of(dict(id='osm-junction-999',origin=[11,48]), [('main',old)]))

    def test_new_area_skips_existing_and_preserves_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            main=ProjectStore(Path(directory)/'main')
            sites=prepare(crossing(), {})[0]
            dataset=dict(schemaVersion=1,project=dict(id='main',city='City'),source={},sites=sites)
            main.import_dataset(dataset)
            main.save(sites[0]['id'],dict(expectedVersion=0,status='excluded',note='Keep decision'))
            before=main.snapshot()
            incoming=deepcopy(dataset)
            incoming['project']['id']='new-area'
            workspace=Workspace(main,prepare=lambda selection:(incoming,{}))
            workspace.jobs['job']=dict(id='job',status='running')
            workspace.working.add('job')
            workspace._run('job',{'test':'area'})
            job=workspace.job('job')
            self.assertEqual(job['status'],'complete',job)
            self.assertEqual(job['skippedDuplicates'],len(sites))
            self.assertEqual(workspace.store(job['projectId']).snapshot()['sites'],[])
            self.assertEqual(main.snapshot(),before)

    def test_removed_duplicate_is_hidden_but_decision_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            store=ProjectStore(directory)
            sites=prepare(crossing(), {})[0]
            store.import_dataset(dict(schemaVersion=1,project=dict(id='area',city='City'),source={},sites=sites))
            site_id=sites[0]['id']
            store.save(site_id,dict(expectedVersion=0,status='confirmed'))
            store.remove_duplicates({site_id:dict(projectId='main',siteId='original')})
            self.assertNotIn(site_id,[s['id'] for s in store.snapshot()['sites']])
            state, frozen=store._read()
            self.assertEqual(state['sites'][site_id]['decision']['status'],'confirmed')
            self.assertIn(site_id,[s['id'] for s in frozen['sites']])
            with self.assertRaises(Conflict):
                store.save(site_id,dict(expectedVersion=1,status='open'))
