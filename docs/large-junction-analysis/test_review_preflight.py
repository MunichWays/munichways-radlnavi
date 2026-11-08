"""Human reference cases plus graph false positives; offline, stdlib only."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from review_preflight import fingerprint, merge_suggestions, outside_graph, review, validate_references, carriageway_suggestions
from src.big_junctions import simple_ring

ROOT = Path(__file__).resolve().parent


def sites():
    return [s for batch in ("review-batch-01-images", "review-batch-02-ba09-images")
        for s in json.loads((ROOT / batch / "review-data.json").read_text(encoding="utf-8"))["sites"]]


class ReviewPreflightTest(unittest.TestCase):
    def test_k05_approved_replacement_preserves_accepted_reference(self):
        site = next(s for s in sites() if s["number"] == 5)
        archive = json.loads((ROOT / "review-reference-k05-v2.json").read_text(encoding="utf-8"))
        self.assertTrue(site["polygonApproved"])
        self.assertEqual(3, site["version"])
        gates = {g["label"]: g for g in site["gates"]}
        self.assertNotIn("Exit-4", gates)
        old = {g["label"]: g for g in archive["gates"]}
        self.assertLess(gates["Entry-4"]["location"][0], old["Entry-4"]["location"][0])
        self.assertLess(gates["Entry-4"]["location"][1], old["Entry-4"]["location"][1])
        for label in gates.keys() - {"Entry-4"}:
            self.assertEqual(old[label]["location"], gates[label]["location"])
        self.assertTrue(archive["polygonApproved"])

    def test_requested_k14_k15_k17_revisions_preserve_other_gates(self):
        current = {s["number"]: s for s in sites()}
        old = json.loads((ROOT / "review-batch-02-ba09-v1-geometry.json").read_text(encoding="utf-8"))["sites"]
        original = {current_site["number"]: next(s for s in old if s["id"] == current_site["id"])
            for current_site in current.values() if current_site["number"] in (14, 15)}
        for number, moved in [(14, {"Exit-2", "Entry-2", "Exit-3"}),
            (15, {"Exit-2", "Entry-3", "Exit-3"})]:
            gates = {g["label"]: g for g in current[number]["gates"]}
            for previous in original[number]["gates"]:
                if previous["label"] not in moved:
                    self.assertEqual(previous["location"], gates[previous["label"]]["location"])
            self.assertTrue(simple_ring(current[number]["polygon"]))
        gates = {g["label"]: g for g in current[15]["gates"]}
        self.assertEqual(1460781865, gates["Exit-2"]["osmWayId"])
        self.assertLess(gates["Exit-2"]["location"][1], 48.1540001)
        self.assertEqual(95857037, gates["Entry-3"]["osmWayId"])
        self.assertLess(gates["Entry-3"]["location"][0], 11.5366973)
        self.assertLess(gates["Exit-3"]["location"][1], 48.1535725)
        self.assertEqual([], review(current[15])["unverifiedAccessWays"])
        gates = {g["label"]: g for g in current[17]["gates"]}
        self.assertNotIn("Entry-4", gates)
        self.assertNotIn("Exit-5", gates)
        self.assertIn("Entry-5", gates)  # Preserve the unchanged label despite the gap.
        self.assertGreater(gates["Exit-4"]["location"][0], 11.553459566)
        self.assertLess(gates["Exit-4"]["location"][1], 48.154726565)
        self.assertTrue(simple_ring(current[17]["polygon"]))

    def test_k17_explicit_carriageway_continuation_is_suggested_then_drafted(self):
        site = deepcopy(next(s for s in sites() if s["number"] == 17))
        original = json.loads((ROOT / "review-batch-02-ba09-v1-geometry.json").read_text(encoding="utf-8"))["sites"][-1]
        draft = deepcopy(site)
        draft.update(original)
        draft["onRoadWayIds"] = [1393204543]
        self.assertIn(163989143, [p["osmWayId"] for p in carriageway_suggestions(draft)])
        new = [g for g in site["gates"] if g["osmWayId"] == 163989143]
        self.assertEqual({"Entry-2", "Exit-3"}, {g["label"] for g in new})
        self.assertEqual(new[0]["location"], new[1]["location"])
        self.assertEqual(site["status"] == "geometry-approved", site["polygonApproved"])
        self.assertFalse(site["enabled"])
        self.assertNotIn(163989143, [p["osmWayId"] for p in carriageway_suggestions(site)])
        way = next(w for w in draft["ways"] if w["id"] == 163989143)
        way["tags"]["bicycle"] = "no"
        self.assertNotIn(163989143, [p["osmWayId"] for p in carriageway_suggestions(draft)])

    def test_human_decisions_remain_pinned(self):
        references = json.loads((ROOT / "review-reference-cases.json").read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(references), 13)
        self.assertGreaterEqual(sum(r["status"] == "geometry-approved" for r in references), 12)
        validate_references(sites(), references)
        changed = deepcopy(sites())
        changed[0]["gates"][0]["location"][0] += .00001
        with self.assertRaises(ValueError):
            validate_references(changed, references)
        changed = deepcopy(sites())
        next(s for s in changed if s["number"] == 9)["status"] = "geometry-draft"
        with self.assertRaises(ValueError):
            validate_references(changed, references)

    def test_historical_k11_and_k12_find_actual_outside_joins(self):
        current = {s["id"]: s for s in sites()}
        old = json.loads((ROOT / "review-batch-02-ba09-v1-geometry.json").read_text(encoding="utf-8"))["sites"]
        for number, node, kind, labels in [(11, 1348200070, "entry", {"Entry-1", "Entry-5"}),
            (12, 1348199881, "exit", {"Exit-3", "Exit-4"})]:
            original = next(s for s in old if current[s["id"]]["number"] == number)
            candidate = deepcopy(current[original["id"]])
            candidate.update(original)
            found = merge_suggestions(candidate)
            self.assertTrue(any(m["node"] == node and m["kind"] == kind and set(m["gates"]) == labels for m in found))

    def test_shared_gates_are_preserved_and_report_never_mutates_input(self):
        for number in (11, 16):
            site = next(s for s in sites() if s["number"] == number)
            saved = deepcopy(site)
            report = review(site)
            self.assertTrue(report["sharedGates"])
            self.assertGreater(report["entries"] + report["exits"], 8)
            self.assertEqual(saved, site)
            self.assertEqual(fingerprint(saved), report["geometrySha256"])

    def test_graph_respects_bicycle_direction_access_and_polygon(self):
        site = {"polygon": [[-.001, -.001], [.001, -.001], [.001, .001], [-.001, .001], [-.001, -.001]],
            "ways": [{"id": 1, "nodes": [1, 2], "geometry": [{"lon": .002, "lat": 0}, {"lon": .003, "lat": 0}],
                "tags": {"highway": "cycleway", "oneway": "yes", "oneway:bicycle": "-1"}}]}
        _, graph = outside_graph(site)
        self.assertIn(2, graph)
        self.assertNotIn(1, graph)
        _, reverse = outside_graph(site, reverse=True)
        self.assertIn(1, reverse)
        site["ways"][0]["tags"]["access"] = "private"
        self.assertFalse(outside_graph(site)[1])
        site["ways"][0]["tags"].pop("access")
        site["ways"][0]["geometry"][1]["lon"] = -.002
        self.assertFalse(outside_graph(site)[1])

    def test_close_but_disconnected_paths_are_not_merged(self):
        site = deepcopy(next(s for s in sites() if s["number"] == 11))
        site["ways"] = [w for w in site["ways"] if w["id"] in {g["osmWayId"] for g in site["gates"]}]
        # Disconnect every way's node identities without changing coordinates.
        for i, way in enumerate(site["ways"], 1):
            way["nodes"] = [node + i * 10**14 for node in way["nodes"]]
        self.assertFalse(merge_suggestions(site))


if __name__ == "__main__":
    unittest.main()
