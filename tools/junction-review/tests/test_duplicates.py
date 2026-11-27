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
    def test_named_legacy_junction_matches_reordered_streets_near_same_centre(self):
        old = dict(id='ludwig-tann', name='Ludwigstraße / Von-der-Tann-Straße / Oskar-von-Miller-Ring',
                   origin=[11.57886, 48.14531], provenance={'adapter': 'radlnavi-overview-v1'})
        new = dict(id='osm-junction-1955487', origin=[11.57885925, 48.1453067],
                   name=' Ludwigstraße / Oskar-von-Miller-Ring / Von-der-Tann-Straße ')
        self.assertEqual(duplicate_of(new, [('main', old)])['siteId'], 'ludwig-tann')
        self.assertEqual(duplicate_of(old, [('area', new)])['siteId'], new['id'])
        for replacement in (
                dict(origin=[11.57886, 48.1456]),  # Same streets, separate crossing.
                dict(name='Ludwigstraße / Galeriestraße'),  # Only partly shared streets.
                dict(provenance={'adapter': 'other-source'}),
                dict(preparation={'candidateNodes': [999]})):  # Different known identity.
            changed = dict(old, **replacement)
            self.assertIsNone(duplicate_of(new, [('main', changed)]), replacement)
        self.assertIsNone(duplicate_of(new, [('one', old), ('two', dict(old, id='split'))]))
        # Stable identity takes priority over an otherwise plausible legacy match.
        self.assertEqual(duplicate_of(new, [('main', old), ('area', new)])['projectId'], 'area')

    def test_new_area_skips_legacy_named_import_without_altering_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            main = ProjectStore(Path(directory) / 'main')
            generated = prepare(crossing(), {})[0]
            legacy = deepcopy(generated[0])
            legacy.update(id='named-old-crossing', provenance={'adapter': 'radlnavi-overview-v1'})
            legacy.pop('preparation')
            dataset = dict(schemaVersion=1, project=dict(id='main', city='City'), source={}, sites=[legacy])
            main.import_dataset(dataset)
            main.save(legacy['id'], dict(expectedVersion=0, status='confirmed'))
            before = main.snapshot()
            incoming = dict(schemaVersion=1, project=dict(id='new-area', city='City'), source={}, sites=generated)
            workspace = Workspace(main, prepare=lambda selection: (incoming, {}))
            workspace.jobs['job'] = dict(id='job', status='running')
            workspace.working.add('job')
            workspace._run('job', {'test': 'legacy-area'})
            job = workspace.job('job')
            self.assertEqual(job['status'], 'complete', job)
            self.assertEqual(job['skippedDuplicates'], 1)
            self.assertEqual(workspace.store(job['projectId']).snapshot()['sites'], [])
            self.assertEqual(main.snapshot(), before)

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
