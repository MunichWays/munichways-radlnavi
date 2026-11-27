from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from junction_review.model import summarize
from junction_review.adapters import import_radlnavi
from junction_review.radlnavi_overview import import_overview
from junction_review.store import ProjectStore

REPO = Path(__file__).resolve().parents[3]


class OverviewMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = import_overview(REPO)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ProjectStore(Path(self.temp.name) / 'full')
        self.store.import_dataset(self.dataset)

    def test_counts_live_evidence_positions_and_existing_labels_survive(self):
        snapshot = self.store.snapshot()
        report = summarize(snapshot)
        self.assertEqual(report['total'], 98)
        self.assertEqual(report['counts'], dict(confirmed=42, open=41, excluded=15, deferred=0))
        self.assertEqual(sum(s['deploymentStatus'] == 'live' for s in snapshot['sites']), 42)
        self.assertTrue(all(s['origin'] for s in snapshot['sites']))
        self.assertEqual(sum(s['status'] == 'open' and s['geometryMode'] == 'none' for s in snapshot['sites']), 41)
        sites = {s['number']: s for s in snapshot['sites'] if s['number']}
        self.assertEqual(sites[47]['gates'][0]['label'], 'Exit-1')
        # K44/K46 rechecks were resolved (passed, live with 2.4.22) on 2026-11-26.
        self.assertEqual([r for s in snapshot['sites'] for r in s['evidence']['rechecks']], [])
        self.assertFalse(sites[9]['provenance']['exclusion']['enabled'])
        self.assertTrue(sites[9]['provenance']['exclusion']['permanent'])

    def test_imported_live_status_becomes_historical_when_geometry_changes(self):
        site = next(s for s in self.store.snapshot()['sites'] if s['number'] == 42)
        result = self.store.save(site['id'], dict(expectedVersion=0, polygon=[[p[0]+.000001, p[1]] for p in site['polygon']]))
        self.assertEqual(result['status'], 'open')
        self.assertFalse(result['decisionCurrent'])
        self.assertFalse(result['evidenceCurrent'])
        self.assertEqual(result['deploymentStatus'], 'older-geometry')
        self.assertEqual(result['technicalStatus'], 'not-run')
        self.assertTrue(result['evidence']['liveMovements'])

    def test_inventory_can_be_commented_or_deferred_but_not_confirmed(self):
        site = next(s for s in self.store.snapshot()['sites'] if s['status'] == 'open' and s['geometryMode'] == 'none')
        with self.assertRaisesRegex(ValueError, 'Ohne Geometrie'):
            self.store.save(site['id'], dict(expectedVersion=0, status='confirmed'))
        result = self.store.save(site['id'], dict(expectedVersion=0, status='deferred', note='Baustelle prüfen'))
        self.assertEqual(result['status'], 'deferred')

    def test_prior_pilot_project_edits_are_carried_without_overwriting_full_review(self):
        subset = import_radlnavi(REPO / 'docs/large-junction-analysis/review-batch-09-nine-lanes-images/review-data.json', 'subset', 'München')
        old = ProjectStore(Path(self.temp.name) / 'subset')
        old.import_dataset(subset)
        site = subset['sites'][1]
        old.save(site['id'], dict(expectedVersion=0, status='confirmed', note='Schon geprüft'))
        self.assertEqual(self.store.carry_edits(old), 1)
        self.assertEqual(self.store.carry_edits(old), 0)
        result = next(s for s in self.store.snapshot()['sites'] if s['id'] == site['id'])
        self.assertEqual(result['decision']['note'], 'Schon geprüft')
        self.assertEqual(result['status'], 'confirmed')
        self.assertEqual(summarize(self.store.snapshot())['counts']['confirmed'], 42)
