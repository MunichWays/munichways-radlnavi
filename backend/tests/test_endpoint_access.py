"""Endpoint access must never change the bicycle graph or invent a connection."""

import json
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch
import httpx
from requests import Response

from test_app import app
from src.endpoint_access import AccessGraph, passable, rideable, walkable
from src.endpoint_routes import encode_geometry, endpoint_route


def database():
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE nodes (id INTEGER PRIMARY KEY, lat REAL, lon REAL, tags TEXT);
        CREATE TABLE ways (id INTEGER PRIMARY KEY, node_list TEXT, tags TEXT);
        CREATE TABLE node_to_ways (node_id INTEGER, way_id INTEGER);
        CREATE VIRTUAL TABLE access_way_bounds USING rtree(id,min_lon,max_lon,min_lat,max_lat);
    """)
    return db


def node(db, i, lon, lat=48, **tags):
    db.execute("INSERT INTO nodes VALUES (?,?,?,?)", (i, lat, lon, json.dumps(tags)))


def way(db, i, refs, **tags):
    db.execute("INSERT INTO ways VALUES (?,?,?)", (i, json.dumps(refs), json.dumps(tags)))
    db.executemany("INSERT INTO node_to_ways VALUES (?,?)", [(n, i) for n in refs])
    rows = db.execute(f"SELECT lon,lat FROM nodes WHERE id IN ({','.join('?' for _ in refs)})", refs).fetchall()
    if "highway" in tags:
        db.execute("INSERT INTO access_way_bounds VALUES (?,?,?,?,?)", (
            i, min(r[0] for r in rows), max(r[0] for r in rows),
            min(r[1] for r in rows), max(r[1] for r in rows)))


def network():
    db = database()
    for i in range(1, 5):
        node(db, i, 11 + (i - 1) / 1000)
    way(db, 1, [1, 2], highway="footway", bicycle="no")
    way(db, 2, [2, 3], highway="cycleway")
    way(db, 3, [3, 4], highway="footway", bicycle="no")
    return db


def core_payload():
    a, b = [11.001, 48], [11.002, 48]
    return {"code": "Ok", "waypoints": [
        {"location": a, "distance": 0, "hint": "old-start"},
        {"location": b, "distance": 0, "hint": "old-end"},
    ], "routes": [{"geometry": {"type": "LineString", "coordinates": [a, b]},
        "distance": 100, "duration": 20, "weight": 40, "weight_name": "cyclability",
        "legs": [{"distance": 100, "duration": 20, "weight": 40, "summary": "Bike road",
            "annotation": {"nodes": [2, 3], "distance": [100], "duration": [20],
                "weight": [40], "speed": [5], "datasources": [0],
                "metadata": {"datasource_names": ["lua profile"]}},
            "steps": [{"name": "Bike road", "mode": "cycling", "distance": 100,
                "duration": 20, "weight": 40, "intersections": [],
                "maneuver": {"type": "depart", "location": a},
                "geometry": {"type": "LineString", "coordinates": [a, b]}},
                {"name": "Bike road", "mode": "cycling", "distance": 0,
                 "duration": 0, "weight": 0, "intersections": [],
                 "maneuver": {"type": "arrive", "location": b},
                 "geometry": {"type": "LineString", "coordinates": [b, b]}}]}]}]}


class AccessGraphTest(unittest.TestCase):
    def test_public_pushing_access_is_separate_from_cycling_permission(self):
        self.assertTrue(walkable({"highway": "footway", "bicycle": "no"}))
        self.assertTrue(walkable({"highway": "path", "bicycle": "no", "foot": "designated"}))
        for tags in (
            {"highway": "residential", "bicycle": "no", "foot": "yes"},
            {"highway": "path", "bicycle": "designated", "oneway": "yes"},
            {"highway": "footway", "bicycle": "no", "foot": "no"},
            {"highway": "footway", "bicycle": "no", "access": "private"},
            {"highway": "footway", "bicycle": "no", "foot": "customers"},
            {"highway": "footway", "bicycle": "no", "bicycle:pushing": "no"},
            {"highway": "footway", "bicycle": "no", "bicycle:physical": "no"},
            {"highway": "footway", "bicycle": "no", "foot:conditional": "no @ (Mo)"},
            {"highway": "footway", "bicycle": "no", "bicycle:conditional": "no @ (Jul 01 - Oct 22)"},
        ):
            with self.subTest(tags=tags):
                self.assertFalse(walkable(tags))
        self.assertFalse(rideable({"highway": "path", "bicycle": "no"}))
        self.assertFalse(rideable({"highway": "primary", "bicycle": "use_sidepath"}))

    def test_barriers_and_explicit_pedestrian_gate_access(self):
        self.assertFalse(passable({"barrier": "fence"}))
        self.assertFalse(passable({"barrier": "gate", "locked": "yes"}))
        self.assertFalse(passable({"barrier": "gate", "foot": "private"}))
        self.assertTrue(passable({"barrier": "gate", "locked": "yes", "foot": "yes"}))
        self.assertFalse(passable({"barrier": "gate", "foot": "yes", "bicycle:pushing": "no"}))
        self.assertFalse(passable({"barrier": "gate", "foot": "yes", "bicycle": "no"}))
        self.assertTrue(passable({"barrier": "gate", "foot": "yes", "bicycle": "no", "bicycle:pushing": "yes"}))

    def test_projection_on_long_segments_does_not_need_nearby_bounding_nodes(self):
        with database() as db:
            node(db, 1, 11)
            node(db, 2, 11.006)
            node(db, 3, 11.007)
            way(db, 1, [1, 2], highway="footway", bicycle="no")
            way(db, 2, [2, 3], highway="cycleway")
            graph = AccessGraph(db, (11.003, 48), 21)
            self.assertAlmostEqual(0, graph.nearest((11.003, 48))[0])
            connections = AccessGraph(db, (11.003, 48), 501).connections((11.003, 48))
            self.assertEqual([2], [c.nodes[-1] for c in connections])
            self.assertGreater(connections[0].distance, 200)

    def test_walk_direction_and_bound_apply_to_both_ends(self):
        with network() as db:
            db.execute("UPDATE ways SET tags=? WHERE id=1", (json.dumps({
                "highway": "footway", "bicycle": "no", "oneway:foot": "yes"}),))
            graph = AccessGraph(db, (11.0002, 48), 501)
            self.assertEqual(1, len(graph.connections((11.0002, 48))))
            self.assertEqual([], graph.connections((11.0002, 48), incoming=True))
        with database() as db:
            node(db, 1, 11)
            node(db, 2, 11.02)
            node(db, 3, 11.021)
            way(db, 1, [1, 2], highway="footway", bicycle="no")
            way(db, 2, [2, 3], highway="cycleway")
            self.assertEqual([], AccessGraph(db, (11.0001, 48), 501).connections((11.0001, 48)))

    def test_explicitly_cycleable_footway_is_a_valid_bicycle_exit(self):
        with network() as db:
            db.execute("UPDATE ways SET tags=? WHERE id=2", (json.dumps({
                "highway": "footway", "bicycle": "designated"}),))
            connections = AccessGraph(db, (11.0001, 48), 501).connections((11.0001, 48))
            self.assertEqual([2], [c.nodes[-1] for c in connections])

    def test_blocked_node_cannot_be_crossed_by_endpoint_connection(self):
        with network() as db:
            db.execute("UPDATE nodes SET tags=? WHERE id=2", ('{"barrier":"fence"}',))
            self.assertEqual([], AccessGraph(db, (11.0001, 48), 501).connections((11.0001, 48)))


class EndpointRoutingTest(unittest.TestCase):
    def original(self, start_gap=70, end_gap=70):
        payload = core_payload()
        payload["waypoints"][0]["distance"] = start_gap
        payload["waypoints"][-1]["distance"] = end_gap
        return payload

    def test_both_endpoints_are_attached_without_changing_core_or_leg_count(self):
        for variant in ("standard", "direct"):
            with self.subTest(variant=variant), network() as db:
                core = core_payload()
                fetch = Mock(return_value=SimpleNamespace(status_code=200, json=lambda:core))
                payload = endpoint_route(db, "bike", "11.0001,48;11.0029,48",
                    [("geometries", "geojson"), ("steps", "true"), ("annotations", "true")],
                    self.original(), fetch, variant)
                route = payload["routes"][0]
                self.assertEqual(1, len(route["legs"]))
                self.assertEqual(2, len(payload["waypoints"]))
                leg = route["legs"][0]
                self.assertEqual([1, 2, 3, 4], leg["annotation"]["nodes"])
                self.assertEqual({"datasource_names": ["lua profile"]}, leg["annotation"]["metadata"])
                self.assertAlmostEqual(route["distance"], sum(leg["annotation"]["distance"]))
                self.assertEqual(["pushing bike", "cycling", "pushing bike", "pushing bike"],
                    [s["mode"] for s in leg["steps"]])
                self.assertEqual(100, leg["steps"][1]["distance"])
                self.assertEqual(20, leg["steps"][1]["duration"])
                self.assertEqual(40, leg["steps"][1]["weight"])
                self.assertEqual("notification", leg["steps"][1]["maneuver"]["type"])
                self.assertEqual("arrive", leg["steps"][-1]["maneuver"]["type"])
                self.assertNotIn("hint", payload["waypoints"][0])
                self.assertEqual(0, payload["waypoints"][0]["distance"])
                self.assertEqual("11.001,48.0;11.002,48.0", fetch.call_args.args[0])
                options = dict(fetch.call_args.args[1])
                self.assertEqual("0.75;0.75", options["radiuses"])
                # All overview coordinates must match the ordered step geometry.
                from_steps = []
                for step in leg["steps"]:
                    if step["maneuver"]["type"] == "arrive": continue
                    for point in step["geometry"]["coordinates"]:
                        if not from_steps or point != from_steps[-1]: from_steps.append(point)
                self.assertEqual(route["geometry"]["coordinates"], from_steps)
                self.assertEqual(core_payload(), core)
                app.osrm_analysis_legs(route, payload["waypoints"])

    def test_ordinary_cycling_endpoints_do_not_issue_additional_route_queries(self):
        with network() as db:
            fetch = Mock()
            self.assertIsNone(endpoint_route(db, "bike", "11.001,48;11.002,48", [],
                self.original(0, 0), fetch, "standard"))
            fetch.assert_not_called()

    def test_no_route_on_a_cycling_road_cannot_be_bypassed_via_nearby_footpath(self):
        with network() as db:
            # Even when the upstream supplies no snapped waypoints (e.g. a
            # forbidden direction), a road endpoint must remain on that road.
            fetch = Mock()
            self.assertIsNone(endpoint_route(db, "bike", "11.001,48;11.002,48", [],
                {"code": "NoRoute"}, fetch, "standard"))
            fetch.assert_not_called()

    def test_already_snapped_pushing_endpoint_also_works_without_optional_steps(self):
        with network() as db:
            db.execute("UPDATE ways SET tags=? WHERE id=1", ('{"highway":"footway"}',))
            original = self.original(0, 0)
            original["waypoints"][0]["location"] = [11.0001, 48]
            original["routes"][0]["legs"][0].pop("steps")
            fetch = Mock(return_value=SimpleNamespace(status_code=200, json=core_payload))
            payload = endpoint_route(db, "bike", "11.0001,48;11.002,48",
                [("geometries", "geojson"), ("annotations", "nodes,distance")],
                original, fetch, "standard")
            self.assertEqual([11.0001, 48.0], payload["routes"][0]["geometry"]["coordinates"][0])
            self.assertEqual([1, 2, 3], payload["routes"][0]["legs"][0]["annotation"]["nodes"])
            self.assertNotIn("steps", payload["routes"][0]["legs"][0])
            fetch.assert_called_once()

    def test_wholly_walked_route_and_reverse_work_without_a_bicycle_exit(self):
        with database() as db:
            node(db, 1, 11)
            node(db, 2, 11.001)
            way(db, 1, [1, 2], highway="footway", bicycle="no")
            for text in ("11.0002,48;11.0008,48", "11.0008,48;11.0002,48"):
                fetch = Mock()
                payload = endpoint_route(db, "bike", text,
                    [("geometries", "geojson"), ("steps", "true"), ("annotations", "nodes,distance")],
                    {"code": "NoSegment"}, fetch, "standard")
                route = payload["routes"][0]
                self.assertGreater(route["distance"], 40)
                self.assertLess(route["distance"], 50)
                self.assertTrue(all(s["mode"] == "pushing bike" for s in route["legs"][0]["steps"]))
                self.assertEqual({"nodes", "distance"}, set(route["legs"][0]["annotation"]))
                fetch.assert_not_called()
                app.osrm_analysis_legs(route, payload["waypoints"])

    def test_failed_join_does_not_invent_an_annotation_edge(self):
        with network() as db:
            core = core_payload()
            core["routes"][0]["legs"][0]["annotation"]["nodes"] = [900, 901]
            fetch = Mock(return_value=SimpleNamespace(status_code=200, json=lambda:core))
            self.assertIsNone(endpoint_route(db, "bike", "11.0001,48;11.002,48", [],
                self.original(70, 0), fetch, "standard"))

    def test_response_options_and_polyline_encoding(self):
        self.assertEqual('_p~iF~ps|U_ulLnnqC_mqNvxq`@', encode_geometry(
            [(-120.2, 38.5), (-120.95, 40.7), (-126.453, 43.252)], 'polyline'))
        with network() as db:
            fetch = Mock(return_value=SimpleNamespace(status_code=200, json=core_payload))
            payload = endpoint_route(db, "bike", "11.0001,48;11.002,48",
                [("overview", "false"), ("skip_waypoints", "true")],
                self.original(70, 0), fetch, "standard")
            self.assertNotIn("waypoints", payload)
            route = payload["routes"][0]
            self.assertNotIn("geometry", route)
            self.assertNotIn("steps", route["legs"][0])
            self.assertNotIn("annotation", route["legs"][0])

    def test_explicit_snapping_and_invalid_requests_are_forwarded_unchanged(self):
        with network() as db:
            for text, params in (("11,48;11.002,48", [("hints", "explicit;")]),
                ("11,48;11.002,48", [("waypoints", "0;1")]),
                ("broken", []), ("nan,48;11,48", [])):
                fetch = Mock()
                self.assertIsNone(endpoint_route(db, "bike", text, params,
                    self.original(), fetch, "standard"))
                fetch.assert_not_called()

    def test_databases_from_older_deployments_fall_back_without_scanning(self):
        with sqlite3.connect(":memory:") as db:
            fetch = Mock()
            self.assertIsNone(endpoint_route(db, "bike", "11,48;11.002,48", [],
                self.original(), fetch, "standard"))
            fetch.assert_not_called()


class EndpointApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_osrm_and_legacy_apis_in_both_variants_include_real_access(self):
        for variant in ("standard", "direct"):
            with self.subTest(variant=variant), network() as db:
                def upstream(url, **kwargs):
                    payload = core_payload()
                    if "11.0001,48" in url:
                        payload["waypoints"][0]["distance"] = 70
                    response = Response()
                    response.status_code = 200
                    response._content = json.dumps(payload).encode()
                    response.headers["content-type"] = "application/json"
                    return response
                with (patch.object(app, "geo_store", db),
                      patch.object(app, "ROUTING_VARIANT", variant),
                      patch.object(app, "routing_auth_headers", return_value={}),
                      patch.object(app, "get", side_effect=upstream)):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url="http://test") as client:
                        response = await client.get(
                            f"/route/v1/bike/11.0001,48;11.002,48?variant={variant}"
                            "&geometries=geojson&steps=true&annotations=nodes,distance&comfort=true")
                        self.assertEqual(200, response.status_code)
                        payload = response.json()
                        route = payload["routes"][0]
                        self.assertEqual("pushing bike", route["legs"][0]["steps"][0]["mode"])
                        self.assertGreater(route["distance"], 160)
                        self.assertIn("comfort", route)
                        self.assertEqual({"nodes", "distance"}, set(route["legs"][0]["annotation"]))
                        app.osrm_analysis_legs(route, payload["waypoints"])
                        legacy = await client.get(
                            f"/route?start_lon=11.0001&start_lat=48&target_lon=11.002&target_lat=48&variant={variant}")
                        self.assertEqual(200, legacy.status_code)
                        self.assertTrue(legacy.json()["ok"])
                        self.assertEqual("pushing bike", legacy.json()["route"]["steps"][0]["mode"])
                        self.assertAlmostEqual(route["distance"], legacy.json()["route"]["distance"])


if __name__ == "__main__":
    unittest.main()
