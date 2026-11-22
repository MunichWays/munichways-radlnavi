from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from test_discovery import crossing
from junction_review.discovery import prepare
from junction_review.prepare_open import prepare_missing
from junction_review.store import ProjectStore


class PrepareOpenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'main'
        raw = crossing()
        original = prepare(raw, {})[0][0]
        blank = dict(deepcopy(original), id='lane-candidate-1', polygon=[], gates=[], ways=[],
                     logicalArms={}, geometryMode='none', geometryRevision=0, sourceFingerprint='placeholder')
        protected = dict(deepcopy(original), id='protected', origin=[11.05, 48.05])
        self.store = ProjectStore(self.path)
        self.store.import_dataset(dict(schemaVersion=1, project=dict(id='main', city='Test'),
            source=dict(adapter='test'), sites=[blank, protected]))
        self.store.save('protected', dict(expectedVersion=0, status='confirmed'))
        self.raw = raw

    def test_fills_only_missing_draft_and_is_repeatable(self):
        before = self.store.snapshot()['sites'][1]
        calls = []
        result = prepare_missing(self.path, fetch=lambda q: (calls.append(q) or self.raw), progress=lambda *a, **k: None)
        self.assertEqual(len(result['prepared']), 1)
        after = self.store.snapshot()['sites']
        self.assertEqual(after[1], before)
        self.assertEqual(after[0]['id'], 'lane-candidate-1')
        self.assertEqual(after[0]['status'], 'open')
        self.assertEqual(after[0]['geometryMode'], 'editable')
        self.assertEqual(len(after[0]['gates']), 8)
        prepare_missing(self.path, fetch=lambda q: self.fail('No second request'), progress=lambda *a, **k: None)
        self.assertEqual(self.store.snapshot()['sites'], after)

    def test_other_project_decision_prevents_duplicate_preparation(self):
        other = ProjectStore(Path(self.temp.name) / 'other')
        base = prepare(self.raw, {})[0][0]
        other.import_dataset(dict(schemaVersion=1, project=dict(id='other', city='Test'),
            source=dict(adapter='test'), sites=[base]))
        other.save(base['id'], dict(expectedVersion=0, status='excluded', note='Test exclusion'))
        result = prepare_missing(self.path, fetch=lambda q: self.fail('Already reviewed'), progress=lambda *a, **k: None)
        self.assertEqual(len(result['linked']), 1)
        site = self.store.snapshot()['sites'][0]
        self.assertEqual(site['linkedReviews'][0]['status'], 'excluded')
        self.assertEqual(site['status'], 'open')
        self.assertEqual(site['geometryMode'], 'none')

    def test_failed_fetch_never_changes_project(self):
        before = self.store.snapshot()
        result = prepare_missing(self.path, fetch=lambda q: dict(remark='timeout', elements=[]), progress=lambda *a, **k: None)
        self.assertEqual(len(result['errors']), 1)
        self.assertEqual(self.store.snapshot(), before)

    def test_untagged_map_way_is_not_an_overpass_scope_marker(self):
        raw = deepcopy(self.raw)
        raw['elements'].append(dict(type='way', id=999999, nodes=[1, 2], version=1,
            geometry=[dict(lon=11, lat=48), dict(lon=11, lat=48.002)]))
        self.assertEqual(len(prepare(raw, {})[0]), 1)
