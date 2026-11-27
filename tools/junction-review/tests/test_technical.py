"""App-started technical checks and explicit pair exclusions, without network access."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import unittest

from test_discovery import crossing
from junction_review.discovery import prepare
from junction_review.store import Conflict, ProjectStore
from junction_review.workspace import Workspace
from junction_review import technical


def project(directory):
    store = ProjectStore(Path(directory) / 'area-test')
    site = deepcopy(prepare(crossing(), {})[0][0])
    store.import_dataset(dict(schemaVersion=1, project=dict(id='area-test', city='City'), source={}, sites=[site]))
    current = store.snapshot()['sites'][0]
    store.save(current['id'], dict(expectedVersion=current['editVersion'], status='confirmed', note='ok'))
    return store, store.snapshot()['sites'][0]


def fake_report(site, enabled=True):
    moves = [dict(id='a', entryLabel=site['gates'][0]['label'], exitLabel='Exit-2', kind='left', enabled=enabled,
                  verified=enabled, reason='' if enabled else 'ValueError: Route does not cross polygon exactly once',
                  failureStage=None if enabled else 'polygon-crossing'),
             dict(id='b', entryLabel='Entry-1', exitLabel='Exit-1', kind='right', verified=True)]
    record = dict(id=site['id'], name=site['name'], number=900, movements=moves,
                  reviewBinding={k: site[k] for k in ('geometryFingerprint', 'sourceFingerprint')})
    return dict(status='complete', runtimeModified=False, completedAt='2026-11-26T18:00:00+00:00', junctions=[record])


def runner_for(site, enabled=True):
    def run(project_dir, site_id, out, progress, cancelled):
        out.mkdir(parents=True)
        progress('Echte Standardrouten abrufen und prüfen')
        report = fake_report(site, enabled)
        issues = [] if enabled else [dict(stage='polygon-crossing', entryLabel='Entry-1', exitLabel='Exit-2',
                                          kind='left', text='Route führt nicht genau einmal durch die Fläche', reason='')]
        result = dict(standard=enabled, passed=int(enabled), attempted=1, rightVerified=1, rightAttempted=1,
                      excluded=[], connectors=[30816875] if enabled else [], issues=issues)
        (out / 'check-routes.json').write_text(json.dumps(report), encoding='utf-8')
        (out / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    return run


class TechnicalCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store, self.site = project(self.temp.name)

    def test_exclusions_need_existing_pair_and_reason_and_keep_approval(self):
        gates = {g['kind']: g['label'] for g in self.site['gates']}
        with self.assertRaises(ValueError):
            self.store.set_exclusions(self.site['id'], dict(expectedVersion=self.site['editVersion'],
                exclusions=[dict(entryLabel=gates['entry'], exitLabel=gates['exit'], reason=' ')]))
        with self.assertRaises(ValueError):
            self.store.set_exclusions(self.site['id'], dict(expectedVersion=self.site['editVersion'],
                exclusions=[dict(entryLabel=gates['exit'], exitLabel=gates['entry'], reason='x')]))
        with self.assertRaises(Conflict):
            self.store.set_exclusions(self.site['id'], dict(expectedVersion=self.site['editVersion'] - 1, exclusions=[]))
        result = self.store.set_exclusions(self.site['id'], dict(expectedVersion=self.site['editVersion'],
            exclusions=[dict(entryLabel=gates['entry'], exitLabel=gates['exit'], reason='gibt es real nicht')]))
        self.assertEqual(result['status'], 'confirmed')
        self.assertTrue(result['decisionCurrent'])
        self.assertEqual(result['geometryFingerprint'], self.site['geometryFingerprint'])
        self.assertIn(dict(entryLabel=gates['entry'], exitLabel=gates['exit'], reason='gibt es real nicht'),
                      result['constraints']['excludedMovements'])
        self.assertEqual(result['history'][-1]['action'], 'movement-exclusions')

    def test_check_requires_current_confirmation(self):
        self.store.save(self.site['id'], dict(expectedVersion=self.site['editVersion'], status='open', note=''))
        with self.assertRaises(ValueError):
            technical.run_check(self.store, self.site['id'], runner=runner_for(self.site))

    def test_standard_result_is_imported_bound_and_marked(self):
        site = technical.run_check(self.store, self.site['id'], runner=runner_for(self.site))
        self.assertTrue(site['evidenceCurrent'])
        self.assertIn('Standardfall', site['technicalStatus'])
        self.assertEqual(site['evidence']['appCheck']['connectors'], [30816875])
        self.assertTrue(site['evidence']['appCheck']['folder'].startswith('technical'))
        self.assertEqual(site['deploymentStatus'], 'not-live')

    def test_special_case_and_live_state_preserved_on_recheck(self):
        with self.store.lock:
            state, _ = self.store._read()
            state['sites'][self.site['id']]['technicalEvidence'] = dict(
                geometryFingerprint=self.site['geometryFingerprint'], sourceFingerprint=self.site['sourceFingerprint'],
                deploymentStatus='live', deployment='LIVE · Backend 2.4.22', liveMovements=8, backendVersion='2.4.22',
                fieldTests=[], rechecks=[], movements=[])
            from junction_review.store import atomic_write
            atomic_write(self.store.directory / 'project.json', state)
        site = technical.run_check(self.store, self.site['id'], runner=runner_for(self.site, enabled=False))
        self.assertIn('Sonderfall', site['technicalStatus'])
        self.assertEqual(site['deploymentStatus'], 'live')
        self.assertEqual(site['evidence']['liveMovements'], 8)
        self.assertFalse(site['evidence']['appCheck']['standard'])

    def test_geometry_change_during_check_rejects_import(self):
        def runner(project_dir, site_id, out, progress, cancelled):
            runner_for(self.site)(project_dir, site_id, out, progress, cancelled)
            current = self.store.snapshot()['sites'][0]
            moved = [[p[0] + .000001, p[1]] for p in current['polygon']]
            self.store.save(site_id, dict(expectedVersion=current['editVersion'], polygon=moved))
        with self.assertRaises(Conflict):
            technical.run_check(self.store, self.site['id'], runner=runner)

    def test_workspace_job_runs_in_background_and_reports(self):
        original = technical.available
        technical.available = lambda: True
        self.addCleanup(setattr, technical, 'available', original)
        workspace = Workspace(self.store, prepare=lambda selection: None)
        job = workspace.start_technical(self.store, self.site['id'], runner=runner_for(self.site))
        self.assertEqual(job['kind'], 'technical')
        self.assertIsNone(workspace.current())  # Area preparation does not see this job.
        for _ in range(100):
            job = workspace.job(job['id'])
            if job['status'] != 'running':
                break
            time.sleep(.05)
        self.assertEqual(job['status'], 'complete')
        self.assertTrue(job['standard'])


if __name__ == '__main__':
    unittest.main()
