"""Real API acceptance for the reviewed eight-junction expansion."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, approved_movements, catalog

ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'docs/large-junction-analysis/review-batch-01-routes.json'
FIXTURES=Path(__file__).with_name('fixtures')/'big-junctions/batch-01'


class BatchCatalogTest(unittest.TestCase):
    def test_positive_and_rejected_real_routes(self):
        report=json.loads(REPORT.read_text(encoding='utf-8'))
        active={(m['junctionId'],m['id']):m for m in approved_movements()}
        self.assertEqual(8,len(report['junctions']))
        verified=0
        for junction in report['junctions']:
            for item in junction['movements']:
                with self.subTest(junction=junction['id'],movement=item['id']):
                    original=json.loads((FIXTURES/item['fixture']).read_text(encoding='utf-8'))
                    saved=deepcopy(original)
                    result=add_guidance(original)
                    if not item['enabled']:
                        self.assertNotIn((junction['id'],item['id']),active)
                        self.assertIsNone(result)
                        continue
                    verified+=1
                    hit,=result['routes'][0].pop('guidance')['junctions']
                    config=active[(junction['id'],item['id'])]
                    self.assertEqual((junction['id'],config['movement'],config['entryArm'],config['exitArm']),
                                     (hit['id'],hit['movement'],hit['entryArm'],hit['exitArm']))
                    self.assertEqual(saved,result)
                    self.assertEqual(saved,original)
                    bad=deepcopy(original)
                    bad['routes'][0]['legs'][0]['steps'][0]['mode']='pushing bike'
                    self.assertIsNone(add_guidance(bad))
        self.assertEqual(60,verified)

    def test_all_real_right_turn_controls_keep_raw_guidance(self):
        report=json.loads(REPORT.read_text(encoding='utf-8'))
        self.assertEqual(32,len(report['rightTurnChecks']))
        for item in report['rightTurnChecks']:
            with self.subTest(fixture=item['fixture']):
                value=json.loads((FIXTURES/item['fixture']).read_text(encoding='utf-8'))
                self.assertIsNone(add_guidance(value))

    def test_deferred_and_permanent_exclusions(self):
        value=catalog()
        self.assertNotIn('mars-pappenheim',{j['id'] for j in value['junctions']})
        self.assertNotIn('landsberger-barth',{j['id'] for j in value['junctions']})
        excluded={e['id']:e for e in value['excluded']}
        self.assertTrue(excluded['landsberger-barth']['permanent'])
        self.assertTrue(excluded['landsberger-barth']['closed'])
        junctions={j['id']:j for j in value['junctions']}
        nymphenburger=junctions['nymphenburger-waisenhaus']
        self.assertEqual(4,sum(m['enabled'] for m in nymphenburger['movements']))
        self.assertEqual(['Rufinistraße'],nymphenburger['excludedApproaches'])
        self.assertEqual(['Wilramstraße'],junctions['thomasiusplatz']['excludedApproaches'])


if __name__=='__main__':unittest.main()
