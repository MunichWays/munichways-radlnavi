import unittest
from junction_review.publication import public_snapshot


class PublicationTests(unittest.TestCase):
    def test_only_public_fields_and_current_evidence_are_exported(self):
        site = dict(id='one', number=1, name='Test', origin=[11,48], polygon=[],
            gates=[dict(label='Entry-1',kind='entry',location=[11,48],forward=[1,0],wayId=123)],
            status='confirmed',geometryRevision=2,evidenceCurrent=True,technicalStatus='passed',
            deploymentStatus='branch-ready',decision={'note':'Freigegeben'},
            evidence={'movements':[{'entryLabel':'Entry-1','exitLabel':'Exit-1','enabled':True,'routeUrl':'private'}]},
            history=['private'],token='private')
        snapshot=dict(project={'name':'München','path':'private'},source={},sites=[site])
        result=public_snapshot(snapshot)
        self.assertTrue(result['readOnly'])
        self.assertNotIn('private',str(result))
        self.assertNotIn('wayId',result['sites'][0]['gates'][0])
        result['sites'][0]['origin'][0]=12
        self.assertEqual(site['origin'][0],11)
        site['evidenceCurrent']=False
        self.assertEqual(public_snapshot(snapshot)['sites'][0]['movements'],[])
