import unittest
from junction_review.publication import district_for, public_snapshot


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

    def test_projects_are_merged_with_city_and_district(self):
        def site(number, origin, **extra):
            return dict(dict(id=f'id-{number}', number=number, name='Test', origin=origin, polygon=[], gates=[],
                status='excluded', geometryRevision=1, evidenceCurrent=False, technicalStatus='-',
                deploymentStatus='unknown'), **extra)
        munich = dict(project={'name':'München','city':'München'}, source={'osmRetrievedAt':'2026-11-20'},
                      sites=[site(21, [11.5530, 48.1614])])
        district = dict(project={'name':'BA04','city':'Schwabing-West'}, source={},
                        sites=[site(108, [11.5634, 48.1609]), site(None, [11.56, 48.16])])
        result = public_snapshot(munich, district)
        self.assertEqual(result['schemaVersion'], 2)
        self.assertEqual([s['number'] for s in result['sites']], [21, 108])
        self.assertEqual({(s['city'], s['district']['id']) for s in result['sites']}, {('München', 'BA04')})
        self.assertEqual(result['sites'][0]['district']['name'], 'Schwabing-West')
        outside = dict(project={'name':'Ort','city':'Augsburg'}, source={}, sites=[site(1, [10.9, 48.37])])
        self.assertEqual(public_snapshot(outside)['sites'][0]['city'], 'Augsburg')
        self.assertIsNone(district_for([10.9, 48.37]))
        with self.assertRaises(ValueError):
            public_snapshot(munich, munich)

