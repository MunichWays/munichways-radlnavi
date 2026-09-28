"""Run the actual Lua speech classifier: pip install lupa==2.6."""

from pathlib import Path
import unittest

from lupa import LuaRuntime


class GuidanceWayTypeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.module = self.lua.execute(
            (Path(__file__).resolve().parents[1] / "guidance_way_type.lua").read_text()
        )
        self.make_way = self.lua.eval(
            "function(tags) return {get_value_by_key=function(self,key) "
            "return tags[key] end} end"
        )

    def classify(self, tags, forward=True):
        return self.module.classify(self.make_way(self.lua.table_from(tags)), forward)

    def test_basic_types(self):
        for highway in ("cycleway", "path"):
            self.assertEqual("cycleway", self.classify({"highway": highway}))
        for highway in ("living_street", "residential", "tertiary", "secondary",
                        "primary", "unclassified", "road", "trunk_link"):
            self.assertEqual("road", self.classify({"highway": highway}))
        for highway in ("footway", "track", "service", "pedestrian", "steps", ""):
            self.assertIsNone(self.classify({"highway": highway,
                                           "cycleway": "lane",
                                           "cycleway:lane": "exclusive"}))
        self.assertIsNone(self.classify({}))

    def test_only_exclusive_lanes_count(self):
        for lane in (None, "advisory", "exclusive"):
            tags = {"highway": "residential", "cycleway": "lane"}
            if lane:
                tags["cycleway:lane"] = lane
            for forward in (True, False):
                self.assertEqual("cycleway" if lane == "exclusive" else "road",
                                 self.classify(tags, forward))
        self.assertEqual("road", self.classify({"highway": "residential",
                                               "cycleway": "track",
                                               "cycleway:lane": "exclusive"}))

    def test_sided_lanes_follow_travel_direction(self):
        tags = {"highway": "secondary", "cycleway:right": "lane",
                "cycleway:right:lane": "exclusive"}
        self.assertEqual("cycleway", self.classify(tags, True))
        self.assertEqual("road", self.classify(tags, False))
        tags["cycleway:right:oneway"] = "-1"
        self.assertEqual("road", self.classify(tags, True))
        self.assertEqual("cycleway", self.classify(tags, False))
        tags["cycleway:right:oneway"] = "no"
        self.assertEqual("cycleway", self.classify(tags, True))
        self.assertEqual("cycleway", self.classify(tags, False))

    def test_specific_tags_override_common_tags(self):
        tags = {"highway": "residential", "cycleway:both": "lane",
                "cycleway:both:lane": "exclusive", "cycleway:left": "no"}
        self.assertEqual("cycleway", self.classify(tags, True))
        self.assertEqual("road", self.classify(tags, False))

    def test_left_lane_oneway_is_relative_to_osm_way_order(self):
        tags = {"highway": "residential", "cycleway:left": "lane",
                "cycleway:left:lane": "exclusive", "cycleway:left:oneway": "-1"}
        self.assertEqual("road", self.classify(tags, True))
        self.assertEqual("cycleway", self.classify(tags, False))
        tags["cycleway:left:oneway"] = "yes"
        self.assertEqual("cycleway", self.classify(tags, True))
        self.assertEqual("road", self.classify(tags, False))
        del tags["cycleway:left:oneway"]
        tags["oneway"] = "yes"
        self.assertEqual("cycleway", self.classify(tags, True))
        self.assertEqual("road", self.classify(tags, False))

    def test_metadata_does_not_change_routing_or_mark_pushing(self):
        self.lua.execute("mode = {cycling=1, pushing_bike=2}")
        result = self.lua.eval("{forward_mode=1, backward_mode=2, "
                               "forward_classes={tunnel=true}, backward_classes={}, "
                               "forward_speed=20, forward_rate=5, backward_speed=4}")
        self.module.apply(self.make_way(self.lua.table_from({"highway": "cycleway"})), result)
        self.assertTrue(result.forward_classes.cycleway)
        self.assertTrue(result.forward_classes.tunnel)
        self.assertIsNone(result.backward_classes.cycleway)
        self.assertEqual(20, result.forward_speed)
        self.assertEqual(5, result.forward_rate)
        self.assertEqual(4, result.backward_speed)


if __name__ == "__main__":
    unittest.main()
