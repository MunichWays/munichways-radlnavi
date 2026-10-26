"""Run the production Lua resolver against the same contract as the backend."""

import json
from pathlib import Path
import unittest

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parent


class CyclingAttributeTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.module = self.lua.execute(
            (ROOT.parent / "cycling_attributes.lua").read_text(encoding="utf-8")
        )
        self.make_way = self.lua.eval(
            "function(tags) return {get_value_by_key=function(self,key) "
            "return tags[key] end} end"
        )

    def test_shared_contract(self):
        for case in json.loads((ROOT / "cycling-attribute-cases.json").read_text()):
            for direction in ("forward", "backward"):
                with self.subTest(case=case["id"], direction=direction):
                    result = self.module.resolve(
                        self.make_way(self.lua.table_from(case["tags"])),
                        case["key"], direction == "forward",
                    )
                    self.assertEqual(
                        case[direction], {key: result[key] for key in case[direction]}
                    )

    def test_unknown_way_order_does_not_choose_a_side(self):
        result = self.module.resolve(
            self.make_way(self.lua.table_from({
                "cycleway:right:surface": "asphalt", "cycleway:left:surface": "gravel",
            })), "surface", None,
        )
        self.assertIsNone(result.value)
        self.assertTrue(result.ambiguous)

    def test_committed_graph_fixture_matches_contract_and_osm_snapshot(self):
        from build_cycling_fixture import build

        self.assertEqual((ROOT / "fixtures/cycling-attributes.osm").read_bytes(), build())


if __name__ == "__main__":
    unittest.main()
