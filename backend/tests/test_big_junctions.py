"""Frozen pilot acceptance plus false-positive and API compatibility cases."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from requests import Response
from starlette.requests import Request

from test_app import app
from src.big_junctions import add_guidance, meters, approved_movements, catalog, validate_catalog


FIXTURE = Path(__file__).with_name("fixtures") / "arnulf-steuben-route.json"


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def with_line(line):
    result = payload()
    route = result["routes"][0]
    route["geometry"]["coordinates"] = line
    middle = len(line) // 2
    route["legs"][0]["steps"] = [
        {"mode": "cycling", "maneuver": {"type": kind, "location": part[0]},
         "geometry": {"type": "LineString", "coordinates": part}}
        for kind, part in (("depart", line[:middle + 1]), ("turn", line[middle:]), ("arrive", [line[-1]]))
    ]
    return result


def response_for(value):
    response = Response()
    response.status_code = 200
    response.headers["content-type"] = "application/json"
    response._content = json.dumps(value).encode()
    return response


OPTIONS = {"junction_guidance": "true", "geometries": "geojson", "overview": "full", "steps": "true"}


class BigJunctionMatchingTest(unittest.TestCase):
    def test_catalog_requires_review_and_preserves_explicit_exclusions(self):
        value = deepcopy(catalog())
        self.assertEqual(1, len(approved_movements(value)))
        for kind in ("unreviewed_junction", "unreviewed_movement", "duplicate", "excluded", "self_intersection"):
            invalid = deepcopy(value)
            junction = invalid["junctions"][0]
            if kind == "unreviewed_junction":
                junction["review"]["status"] = "draft"
            elif kind == "unreviewed_movement":
                junction["movements"][0]["review"]["status"] = "draft"
            elif kind == "duplicate":
                invalid["junctions"].append(deepcopy(junction))
            elif kind == "excluded":
                invalid["excluded"].append({"id": junction["id"]})
            else:
                ring = junction["polygon"]["coordinates"][0]
                ring[1], ring[5] = ring[5], ring[1]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_catalog(invalid)
        value["junctions"][0]["movements"][0]["enabled"] = False
        self.assertEqual([], approved_movements(value))

    def test_repeated_visits_have_distinct_ids_and_step_intervals(self):
        original = payload()["routes"][0]["geometry"]["coordinates"]
        line = original + original[-2::-1] + original[1:]
        value = with_line(line)
        value["routes"][0]["legs"][0]["steps"] = [
            {"mode": "cycling", "maneuver": {"type": "depart" if i == 0 else "continue", "location": a},
             "geometry": {"type": "LineString", "coordinates": [a, b]}}
            for i, (a, b) in enumerate(zip(line, line[1:]))]
        hits = add_guidance(value)["routes"][0]["guidance"]["junctions"]
        self.assertEqual(2, len(hits))
        self.assertNotEqual(hits[0]["occurrenceId"], hits[1]["occurrenceId"])
        self.assertLess(hits[0]["exit"]["distanceAlongRouteMeters"], hits[1]["entry"]["distanceAlongRouteMeters"])
        self.assertLess(max(hits[0]["suppressedStepIndices"]), min(hits[1]["suppressedStepIndices"]))

    def test_multiple_catalog_junctions_in_one_leg(self):
        data = deepcopy(catalog())
        second = deepcopy(data["junctions"][0])
        second["id"] = "synthetic-second"
        def move(point):
            return [point[0] + .003, point[1]]
        second["polygon"]["coordinates"][0] = list(map(move, second["polygon"]["coordinates"][0]))
        movement = second["movements"][0]
        for key in ("entry", "exit"):
            movement[key] = move(movement[key])
        for key in ("corridor", "approach", "departure"):
            movement[key] = list(map(move, movement[key]))
        data["junctions"].append(second)
        original = payload()["routes"][0]["geometry"]["coordinates"]
        line = original + list(map(move, original))
        value = with_line(line)
        value["routes"][0]["legs"][0]["steps"] = [
            {"mode": "cycling", "maneuver": {"type": "continue", "location": a},
             "geometry": {"type": "LineString", "coordinates": [a, b]}}
            for a, b in zip(line, line[1:])]
        with patch("src.big_junctions.catalog", return_value=data):
            hits = add_guidance(value)["routes"][0]["guidance"]["junctions"]
        self.assertEqual(["arnulf-steuben", "synthetic-second"], [h["id"] for h in hits])
        self.assertLess(hits[0]["exit"]["geometrySegmentIndex"], hits[1]["entry"]["geometrySegmentIndex"])

    def test_straight_movement_and_ambiguous_catalog_fallback(self):
        data = deepcopy(catalog())
        junction = data["junctions"][0]
        junction["id"] = "synthetic-straight"
        ring = [[11.6, 48.15], [11.601, 48.15], [11.601, 48.151], [11.6, 48.151], [11.6, 48.15]]
        junction["polygon"]["coordinates"] = [ring]
        line = [[11.5995, 48.1505], [11.6, 48.1505], [11.6005, 48.1505], [11.601, 48.1505], [11.6015, 48.1505]]
        movement = junction["movements"][0]
        movement.update(movement="straight", entryArm="west", exitArm="east", entry=line[1], exit=line[3],
            approach=line[:2], departure=line[-2:], corridor=line[1:4])
        value = with_line(line)
        with patch("src.big_junctions.catalog", return_value=data):
            result = add_guidance(value)
            self.assertEqual("straight", result["routes"][0]["guidance"]["junctions"][0]["movement"])
            ambiguous = deepcopy(movement)
            ambiguous["id"] = "ambiguous-copy"
            junction["movements"].append(ambiguous)
            self.assertIsNone(add_guidance(value))

    def test_approved_route_gets_only_additional_metadata_without_mutation(self):
        original = payload()
        saved = deepcopy(original)
        result = add_guidance(original)
        guidance = result["routes"][0].pop("guidance")
        self.assertEqual(saved, original)
        self.assertEqual(saved, result)
        self.assertEqual("big-junctions-v1", guidance["version"])
        hit, = guidance["junctions"]
        self.assertEqual(("arnulf-steuben", "left", "west", "north"),
            (hit["id"], hit["movement"], hit["entryArm"], hit["exitArm"]))
        self.assertEqual([1, 2, 3], hit["suppressedStepIndices"])
        self.assertAlmostEqual(78.88, hit["entry"]["distanceAlongLegMeters"], places=1)
        self.assertAlmostEqual(186.01, hit["exit"]["distanceAlongLegMeters"], places=1)
        self.assertEqual(2, hit["entry"]["geometrySegmentIndex"])
        self.assertEqual(20, hit["exit"]["geometrySegmentIndex"])

    def test_rejects_reverse_partial_shifted_detour_shortcut_and_loop(self):
        line = payload()["routes"][0]["geometry"]["coordinates"]
        detour = deepcopy(line)
        detour[7][0] += 0.00012
        cases = {
            "reverse": line[::-1],
            "start_inside": line[5:],
            "end_inside": line[:15],
            "shifted": [[x + 0.00015, y] for x, y in line],
            "detour_inside_same_gates": detour,
            "shortcut_same_gates": line[:5] + line[17:],
            "backtracking_inside": line[:9] + line[6:8][::-1] + line[8:],
        }
        for name, coordinates in cases.items():
            with self.subTest(name=name):
                self.assertIsNone(add_guidance(with_line(coordinates)))

    def test_pushing_missing_geometry_and_discontinuous_route_do_not_match(self):
        for kind in ("pushing", "missing", "discontinuous", "simplified", "duplicate_overview", "nonfinite"):
            value = payload()
            route = value["routes"][0]
            if kind == "pushing":
                route["legs"][0]["steps"][2]["mode"] = "pushing bike"
            elif kind == "missing":
                del route["legs"][0]["steps"][1]["geometry"]
            elif kind == "discontinuous":
                route["legs"][0]["steps"][1]["geometry"]["coordinates"][0][0] += .001
            elif kind == "simplified":
                del route["geometry"]["coordinates"][4]
            elif kind == "duplicate_overview":
                route["geometry"]["coordinates"].insert(1, deepcopy(route["geometry"]["coordinates"][0]))
            else:
                route["geometry"]["coordinates"][0][0] = float("nan")
            with self.subTest(kind=kind):
                self.assertIsNone(add_guidance(value))

    def test_gate_location_alone_does_not_approve_wrong_approach_or_departure(self):
        line = payload()["routes"][0]["geometry"]["coordinates"]
        entry, exit = approved_movements()[0]["entry"], approved_movements()[0]["exit"]
        for altered in (
            [[entry[0], entry[1] - .0003], entry, *line[3:]],
            [*line[:21], exit, [exit[0] + .001, exit[1] + .0002]],
            [entry, *line[3:]],
        ):
            self.assertIsNone(add_guidance(with_line(altered)))

    def test_alternatives_are_independent(self):
        value = payload()
        line = value["routes"][0]["geometry"]["coordinates"]
        other = with_line(line[::-1])["routes"][0]
        value["routes"].append(other)
        result = add_guidance(value)
        self.assertIn("guidance", result["routes"][0])
        self.assertEqual(other, result["routes"][1])

    def test_leg_and_global_geometry_offsets(self):
        value = payload()
        route = value["routes"][0]
        first = route["geometry"]["coordinates"][0]
        before = [first[0] - .001, first[1] + .0002]
        prelude = {"steps": [{"mode": "cycling", "maneuver": {"type": "depart", "location": before},
            "geometry": {"type": "LineString", "coordinates": [before, first]}}]}
        route["legs"].insert(0, prelude)
        route["geometry"]["coordinates"].insert(0, before)
        hit = add_guidance(value)["routes"][0]["guidance"]["junctions"][0]
        self.assertEqual(1, hit["legIndex"])
        self.assertEqual(3, hit["entry"]["geometrySegmentIndex"])
        self.assertAlmostEqual(meters(before, first), hit["entry"]["distanceAlongRouteMeters"] - hit["entry"]["distanceAlongLegMeters"])

    def test_result_cannot_mutate_cached_catalog(self):
        original = deepcopy(approved_movements()[0])
        result = add_guidance(payload())
        result["routes"][0]["guidance"]["junctions"][0]["polygon"]["coordinates"][0][0][0] = 0
        self.assertEqual(original, approved_movements()[0])


class BigJunctionApiTest(unittest.TestCase):
    def test_opt_in_is_stripped_and_other_requests_keep_raw_response(self):
        original = response_for(payload())
        cases = (
            ({}, "standard", "bike"),
            ({**OPTIONS, "junction_guidance": "false"}, "standard", "bike"),
            (OPTIONS, "direct", "bike"),
            (OPTIONS, "discovery", "bike"),
            (OPTIONS, "standard", "foot"),
            ({**OPTIONS, "geometries": "polyline6"}, "standard", "bike"),
            ({**OPTIONS, "overview": "simplified"}, "standard", "bike"),
        )
        for options, variant, profile in cases:
            with self.subTest(options=options, variant=variant, profile=profile), \
                patch.object(app, "ROUTING_VARIANT", variant), \
                patch.object(app, "_get_endpoint_routing_response", return_value=original) as fetch:
                self.assertIs(original, app.get_endpoint_routing_response(profile, "coords", options))
                self.assertNotIn("junction_guidance", dict(fetch.call_args.args[2]))

    def test_valid_opt_in_and_failure_fallback(self):
        original = response_for(payload())
        with patch.object(app, "ROUTING_VARIANT", "standard"), \
            patch.object(app, "_get_endpoint_routing_response", return_value=original):
            result = app.get_endpoint_routing_response("bike", "coords", list(OPTIONS.items()))
            self.assertIn("guidance", result.json()["routes"][0])
            with patch.object(app, "add_big_junction_guidance", side_effect=ValueError("bad catalog")), \
                self.assertLogs(app.logger, level="ERROR"):
                self.assertIs(original, app.get_endpoint_routing_response("bike", "coords", OPTIONS))
            original.status_code = 400
            self.assertIs(original, app.get_endpoint_routing_response("bike", "coords", OPTIONS))

    def test_legacy_route_exposes_guidance_only_when_requested(self):
        original = response_for(payload())
        with patch.object(app, "ROUTING_VARIANT", "standard"), \
            patch.object(app, "_get_endpoint_routing_response", return_value=original), \
            patch.object(app, "osrm_analysis_legs", return_value=[]):
            for enabled in (False, True):
                result = asyncio.run(app.route(48.15, 11.519, 48.151, 11.5205, junction_guidance=enabled))
                self.assertEqual(enabled, "guidance" in result["route"])

    def test_comfort_and_annotation_cleanup_preserve_guidance(self):
        original = response_for(payload())
        query = "&".join(f"{k}={v}" for k, v in OPTIONS.items()) + "&comfort=true&annotations=false"
        request = Request({"type": "http", "method": "GET", "path": "/route/v1/bike/coords", "headers": [], "query_string": query.encode()})
        with patch.object(app, "ROUTING_VARIANT", "standard"), \
            patch.object(app, "_get_endpoint_routing_response", return_value=original), \
            patch.object(app, "analyze_route", return_value={"comfort": {"index": 75}, "analysis": {}}):
            result = asyncio.run(app.osrm_route_proxy(request, "bike", "coords"))
        route = json.loads(result.body)["routes"][0]
        self.assertIn("guidance", route)
        self.assertEqual(75, route["comfort"]["index"])
        self.assertNotIn("annotation", route["legs"][0])


if __name__ == "__main__":
    unittest.main()
