"""Directional lane counts must not promote incoming turn lanes into priorities."""
import unittest

from count_outgoing_lanes import exits_for, lane_count


class OutgoingLaneTests(unittest.TestCase):
    def test_directional_counts_exclude_opposing_and_centre_lanes(self):
        tags = {'lanes': '7', 'lanes:forward': '4', 'lanes:backward': '2', 'lanes:both_ways': '1'}
        self.assertEqual(lane_count(tags, False)['count'], 2)
        del tags['lanes:backward']
        self.assertEqual(lane_count(tags, False)['count'], 2)
        self.assertEqual(lane_count({'lanes': '4'}, True),
                         dict(count=None, estimated=2, basis='direction missing; equal split estimate'))
        self.assertIsNone(lane_count({}, True)['count'])

    def test_reverse_oneway_and_incoming_carriageways(self):
        self.assertIsNone(lane_count({'oneway': 'yes', 'lanes': '5'}, False))
        self.assertIsNone(lane_count({'oneway': '-1', 'lanes': '5'}, True))
        self.assertEqual(lane_count({'oneway': '-1', 'lanes': '2'}, False)['count'], 2)
        self.assertIsNone(lane_count({'oneway': 'yes', 'lanes': '3', 'lanes:forward': '2'}, True)['count'])

    def test_four_two_lane_exits_make_eight_despite_wider_incoming_roads(self):
        origin = [11.5, 48.1]
        group = dict(locations=[origin], roadNames=['NS', 'EW'])
        ways = []
        for index, (dx, dy) in enumerate(((0, .001), (.001, 0), (0, -.001), (-.001, 0))):
            outside = [origin[0]+dx, origin[1]+dy]
            for outgoing in (True, False):
                a, b = (origin, outside) if outgoing else (outside, origin)
                ways.append(dict(id=len(ways), geometry=[dict(lon=p[0], lat=p[1]) for p in (a,b)],
                    tags={'name': 'NS' if index%2==0 else 'EW', 'highway': 'primary',
                          'oneway': 'yes', 'lanes': '2' if outgoing else '4'}))
        result = exits_for(group, ways)
        self.assertEqual(result['geometricArms'], 4)
        self.assertEqual(result['taggedTotal'], 8)
        self.assertEqual(len(result['outgoing']), 4)
        self.assertEqual(result['warnings'], [])


if __name__ == '__main__':
    unittest.main()
