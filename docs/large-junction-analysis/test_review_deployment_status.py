import unittest
from review_deployment_status import status_for


class DeploymentStatusTests(unittest.TestCase):
    def setUp(self):
        self.site = {'id': 'test', 'version': 3, 'status': 'geometry-approved', 'polygon': [[1, 2]]}
        self.live = {'id': 'test', 'enabled': True, 'polygon': {'coordinates': [[[1, 2]]]},
                     'movements': [{'enabled': True}, {'enabled': False}]}

    def test_approval_without_deployment_is_pending(self):
        result = status_for(self.site, {'junctions': []})
        self.assertEqual(result['text'], 'NICHT DEPLOYED')

    def test_old_live_polygon_does_not_claim_current_revision(self):
        self.live['polygon']['coordinates'] = [[[2, 3]]]
        result = status_for(self.site, {'junctions': [self.live]})
        self.assertEqual(result['css'], 'older')
        self.assertFalse(result['geometryMatches'])

    def test_live_counts_only_enabled_movements(self):
        result = status_for(self.site, {'junctions': [self.live]})
        self.assertEqual(result['css'], 'live')
        self.assertEqual(result['liveMovements'], 1)

    def test_stale_technical_revision_is_not_reused(self):
        result = status_for(self.site, {'junctions': []},
                            {'geometryRevision': 2, 'status': 'complete', 'movements': [{'enabled': True}]})
        self.assertIn('ausstehend', result['technical'])

    def test_right_controls_do_not_count_as_activation(self):
        result = status_for(self.site, {'junctions': []}, {'geometryRevision': 3, 'status': 'complete',
            'movements': [{'kind': 'left', 'enabled': True}, {'kind': 'straight', 'enabled': False},
                          {'kind': 'right', 'verified': True, 'enabled': False}]})
        self.assertTrue(result['technical'].startswith('1/2 '))
