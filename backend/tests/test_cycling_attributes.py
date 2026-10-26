from dataclasses import asdict
import json
from pathlib import Path
import unittest

from src.cycling_attributes import resolve_cycling_attribute


CASES = Path(__file__).resolve().parents[2] / "routing/tests/cycling-attribute-cases.json"


class CyclingAttributeTest(unittest.TestCase):
    def test_shared_contract(self):
        for case in json.loads(CASES.read_text(encoding="utf-8")):
            for direction in ("forward", "backward"):
                with self.subTest(case=case["id"], direction=direction):
                    result = resolve_cycling_attribute(
                        case["tags"], case["key"], direction == "forward"
                    )
                    self.assertEqual(case[direction], asdict(result))

    def test_unknown_way_order_does_not_choose_a_side(self):
        result = resolve_cycling_attribute(
            {"cycleway:right:surface": "asphalt", "cycleway:left:surface": "gravel"},
            "surface", None,
        )
        self.assertIsNone(result.value)
        self.assertTrue(result.ambiguous)


if __name__ == "__main__":
    unittest.main()
