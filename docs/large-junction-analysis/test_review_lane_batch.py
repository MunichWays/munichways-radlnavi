"""Lane-priority queue, approved activation and permanent exclusions."""
from copy import deepcopy
import gzip
import json
import sys
import unittest

from prepare_lane_priority_review import ROOT, SOURCE, DRAFTS, OUT, prepare

sys.path.insert(0,str(ROOT.parents[1]/'backend'))
from src.big_junctions import simple_ring


class LanePriorityBatchTests(unittest.TestCase):
    def test_k41_permanent_pair_exclusions_preserve_the_other_six_movements(self):
        sites=json.loads((OUT/'review-data.json').read_text(encoding='utf-8'))['sites']
        site=next(s for s in sites if s['number']==41)
        expected={('Entry-1','Exit-3'),('Entry-1','Exit-4')}
        self.assertEqual({(m['entryLabel'],m['exitLabel']) for m in site['excludedMovements']},expected)
        upstream=next(w for w in site['ways'] if w['id']==33196720)
        self.assertEqual(upstream['tags']['class:bicycle'],'-3')
        report=json.loads((ROOT/'review-batch-07-lanes-routes.json').read_text(encoding='utf-8'))
        record=next(s for s in report['junctions'] if s['number']==41)
        excluded=[m for m in record['movements'] if m.get('explicitlyExcluded')]
        self.assertEqual({(m['entryLabel'],m['exitLabel']) for m in excluded},expected)
        self.assertTrue(all(m['permanent'] and not m['enabled'] and 'class:bicycle=-3' in m['reason'] for m in excluded))
        proposal=json.loads((ROOT/'review-batch-07-lanes-proposed-catalog.json').read_text(encoding='utf-8'))
        junction=next(j for j in proposal['junctions'] if j['id']==site['id'])
        self.assertEqual(sum(bool(m.get('enabled')) for m in junction['movements']),6)
        self.assertEqual({(m['entryLabel'],m['exitLabel']) for m in junction['movements'] if not m['enabled']},expected)

    def test_frozen_geometry_reproduces_and_has_complete_arm_membership(self):
        snapshot=json.loads(gzip.decompress(SOURCE.read_bytes()))
        sources={s['id']:s['elements'] for s in snapshot['sites']}
        original=deepcopy(sources)
        records=json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
        sites=json.loads((OUT/'review-data.json').read_text(encoding='utf-8'))['sites']
        self.assertEqual([prepare(r,sources[r['id']]) for r in records],sites)
        self.assertEqual(sources,original)
        runtime=json.loads((ROOT.parents[1]/'backend/src/big_junctions.json').read_text(encoding='utf-8'))
        for site,count in zip(sites,[8,9,8,8]):
            with self.subTest(number=site['number']):
                self.assertEqual(site['id'] in {j['id'] for j in runtime['junctions']},site['number'] != 39)
                self.assertFalse(site['enabled'])
                self.assertEqual(site['polygonApproved'],site['number'] != 39)
                self.assertEqual(site['status'],'permanently-excluded' if site['number']==39 else 'geometry-approved')
                self.assertTrue(simple_ring(site['polygon']))
                self.assertEqual(len(site['gates']),count)
                assigned=[label for labels in site['proposedLogicalArms'].values() for label in labels]
                self.assertEqual(len(assigned),len(set(assigned)))
                self.assertEqual(set(assigned),{g['label'] for g in site['gates']})
        self.assertEqual(sites[-1]['onRoadWayIds'],[229715439,1534973622])

    def test_queue_is_text_only_until_prepared_and_preserves_prior_decisions(self):
        from organize_review_images import add_lane_queue, GROUPS
        queue=json.loads((ROOT/'review-lane-priority-queue.json').read_text(encoding='utf-8'))['sites']
        self.assertEqual(len(queue),55)
        self.assertTrue(all('polygon' not in s for s in queue))
        groups={g:[] for g in GROUPS}
        prepared=json.loads((OUT/'review-data.json').read_text(encoding='utf-8'))['sites']
        prepared += json.loads((ROOT/'review-batch-08-central-images/review-data.json').read_text(encoding='utf-8'))['sites']
        groups['2-offen']=deepcopy(prepared)
        add_lane_queue(groups)
        self.assertEqual(len(groups['2-offen']),54)
        pending=[s for s in groups['2-offen'] if s.get('textOnly')]
        self.assertEqual(len(pending),45)
        self.assertTrue(all(s['polygon']==[] and s['status']=='inventory-open' for s in pending))
        deferred = groups['3-ausgeschlossen']
        self.assertEqual(len(deferred), 1)
        self.assertEqual(deferred[0]['id'], 'lane-candidate-21263461')
        self.assertEqual(deferred[0]['status'], 'deferred')
        self.assertEqual(deferred[0]['polygon'], [])
        add_lane_queue(groups)
        self.assertEqual(len(groups['2-offen']),54)
        self.assertEqual(len(groups['3-ausgeschlossen']), 1)
        html=(ROOT/'kreuzungspruefung/index.html').read_text(encoding='utf-8')
        for site in pending:
            import html as escaping
            self.assertIn('<td>'+escaping.escape(site['name'])+'<small>',html)
