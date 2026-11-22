from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from junction_review.gate_edit import edit_gate, geometry_of
from junction_review.geometry import inside, distance
from junction_review.model import validate_site
from junction_review.store import ProjectStore

FIXTURE=Path(__file__).with_name('fixtures')/'gate-edit-p3.json'
MERGE=dict(action='merge',gateId='entry-2',mergeIds=['entry-3'],wayId=421302932,location=[11.6465695,48.1087776])


class GateEditTests(unittest.TestCase):
    def setUp(self):
        self.site=json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=ProjectStore(self.temp.name)
        self.store.import_dataset(dict(schemaVersion=1,project=dict(id='test',city='München'),source=dict(adapter='test'),sites=[self.site]))

    def test_real_p3_merge_keeps_label_on_common_way_and_contains_branch(self):
        original=deepcopy(self.site)
        result=edit_gate(self.site,MERGE)
        validate_site(result)
        self.assertEqual(self.site,original)
        self.assertEqual(len(result['gates']),len(self.site['gates'])-1)
        gate=next(g for g in result['gates'] if g['id']=='entry-2')
        self.assertEqual(gate['label'],'Entry-2')
        self.assertEqual(gate['osmWayId'],421302932)
        self.assertGreater(gate['forward'][1],.99)
        self.assertTrue(inside([11.6465708,48.1088225],result['polygon']))
        self.assertLess(min(p[1] for p in result['polygon']),min(p[1] for p in self.site['polygon']))
        self.assertNotIn('Entry-3',sum(result['logicalArms'].values(),[]))

    def test_preview_does_not_save_and_commit_preserves_topology_after_restart(self):
        saved=self.store.save(self.site['id'],dict(expectedVersion=0,status='confirmed'))
        preview=self.store.save(self.site['id'],dict(expectedVersion=1,gateEdit=MERGE),preview=True)
        self.assertEqual(self.store.snapshot()['sites'][0],saved)
        final=self.store.save(self.site['id'],dict(expectedVersion=1,geometry=geometry_of(preview)))
        self.assertEqual(final['status'],'open')
        self.assertFalse(final['decisionCurrent'])
        self.assertEqual(final['geometryRevision'],2)
        reopened=ProjectStore(self.temp.name).snapshot()['sites'][0]
        self.assertEqual(reopened,final)
        self.assertEqual(final['history'][-1]['gateChanges']['removed'],['Entry-3'])
        self.assertIn('Entry-2',final['history'][-1]['gateChanges']['moved'])

    def test_polygon_edit_after_merge_keeps_merged_gate_and_deleted_label_absent(self):
        preview=self.store.save(self.site['id'],dict(expectedVersion=0,gateEdit=MERGE),preview=True)
        geometry=geometry_of(preview)
        # Move an unrelated northern corner; no gate reset to the saved base.
        geometry['polygon'][0][1]+=.00001
        geometry['polygon'][-1]=geometry['polygon'][0][:]
        again=self.store.save(self.site['id'],dict(expectedVersion=0,geometry=geometry),preview=True)
        self.assertNotIn('entry-3',[g['id'] for g in again['gates']])
        self.assertEqual(next(g['osmWayId'] for g in again['gates'] if g['id']=='entry-2'),421302932)
        self.assertEqual(again['logicalArms']['Arm-3'],['Entry-2','Exit-3'])

    def test_delete_prunes_membership_without_renumbering_other_gates(self):
        result=edit_gate(self.site,dict(action='delete',gateId='entry-3'))
        self.assertEqual([g['label'] for g in result['gates']],[g['label'] for g in self.site['gates'] if g['id']!='entry-3'])
        self.assertNotIn('Entry-3',sum(result['logicalArms'].values(),[]))

    def test_merge_rejects_mixed_types_different_arms_or_forbidden_way(self):
        for patch in [dict(mergeIds=['exit-3']),dict(mergeIds=['entry-1']),dict(wayId=414695764)]:
            with self.assertRaises(ValueError):
                edit_gate(self.site,{**MERGE,**patch})

    def test_real_p5_add_residential_exit_stages_saves_and_reserves_deleted_number(self):
        site=json.loads(FIXTURE.with_name('gate-edit-p5.json').read_text(encoding='utf-8'))
        store=ProjectStore(Path(self.temp.name)/'p5')
        store.import_dataset(dict(schemaVersion=1,project=dict(id='p5',city='Test'),source=dict(adapter='test'),sites=[site]))
        operation=dict(action='add',kind='exit',arm='Arm-3',wayId=3302001,location=[11.64685,48.0962087])
        preview=store.save(site['id'],dict(expectedVersion=0,gateEdit=operation),preview=True)
        new=preview['gates'][-1]
        self.assertEqual((new['label'],new['osmWayId']),('Exit-4',3302001))
        self.assertTrue(new['onRoad'])
        self.assertGreater(new['forward'][0],.9)
        self.assertEqual(len(store.snapshot()['sites'][0]['gates']),len(site['gates']))
        # A full staged draft must survive subsequent preview and save.
        again=store.save(site['id'],dict(expectedVersion=0,geometry=geometry_of(preview)),preview=True)
        final=store.save(site['id'],dict(expectedVersion=0,geometry=geometry_of(again)))
        self.assertEqual(final['history'][-1]['gateChanges']['added'],['Exit-4'])
        self.assertEqual(final['history'][-1]['gateChanges']['moved'],[])
        reopened=ProjectStore(Path(self.temp.name)/'p5')
        deleted=reopened.save(site['id'],dict(expectedVersion=1,gateEdit=dict(action='delete',gateId=new['id'])))
        added=reopened.save(site['id'],dict(expectedVersion=2,gateEdit=operation),preview=True)
        self.assertEqual(added['gates'][-1]['label'],'Exit-5')
        self.assertNotIn('Exit-4',sum(deleted['logicalArms'].values(),[]))
        for patch in [dict(kind='bad'),dict(arm='unknown'),dict(wayId=3301996)]:
            with self.assertRaises(ValueError):
                edit_gate(site,{**operation,**patch})

    def test_full_draft_cannot_invent_or_rename_gate_identities(self):
        geometry=geometry_of(self.site)
        geometry['gates'][0]['label']='Exit-99'
        with self.assertRaises(ValueError):
            self.store.save(self.site['id'],dict(expectedVersion=0,geometry=geometry))


if __name__=='__main__':
    unittest.main()
