"""Platform floating-point noise must not hide meaningful live mismatches."""
import unittest
from check_rollout_live import equivalent_metadata


class LiveMetadataTests(unittest.TestCase):
    def test_only_tiny_metadata_rounding_is_tolerated(self):
        self.assertTrue(equivalent_metadata({'meters': 213.05736530765552}, {'meters': 213.05736530765554}))
        self.assertFalse(equivalent_metadata({'meters': 213.0}, {'meters': 213.000001}))
        self.assertFalse(equivalent_metadata({'movement': 'left'}, {'movement': 'straight'}))
        self.assertFalse(equivalent_metadata({'geometrySegmentIndex': 12}, {'geometrySegmentIndex': 13}))
        self.assertFalse(equivalent_metadata({'junctions': []}, {'junctions': [{}]}))
