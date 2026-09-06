import asyncio
import json
from pathlib import Path
import random
import sqlite3
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from test_app import app
from src.route_analysis import AnalysisLeg, edge_index, route_segments


class SegmentAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript(
            """
            CREATE TABLE nodes (id INTEGER PRIMARY KEY, lat FLOAT, lon FLOAT, tags TEXT);
            CREATE TABLE ways (id INTEGER PRIMARY KEY, node_list TEXT, tags TEXT);
            CREATE TABLE node_to_ways (node_id INTEGER, way_id INTEGER);
            CREATE INDEX node_to_ways_node_id ON node_to_ways(node_id);
        """
        )
        self.db.executemany(
            "INSERT INTO nodes VALUES (?, ?, ?, ?)",
            [(i, 48.0, 11.0 + i / 10000, "{}") for i in range(1, 101)],
        )
        self.store = patch.object(app, "geo_store", self.db)
        self.store.start()
        self.addCleanup(self.store.stop)
        self.meters = patch.object(
            app.distance, "geodesic", return_value=Mock(measure=Mock(return_value=0.1))
        )
        self.calculate_distance = self.meters.start().return_value.measure
        self.addCleanup(self.meters.stop)

    def way(self, way_id, nodes, rating="2", **tags):
        self.db.execute(
            "INSERT INTO ways VALUES (?, ?, ?)",
            (way_id, json.dumps(nodes), json.dumps({"class:bicycle": rating, **tags})),
        )
        self.db.executemany(
            "INSERT INTO node_to_ways VALUES (?, ?)", [(n, way_id) for n in nodes]
        )

    def analyze(self, nodes=None, *, legs=None):
        request = (
            app.NodeList(legs=legs)
            if legs is not None
            else app.NodeList(node_ids=nodes)
        )
        return asyncio.run(app.tag_distribution(request))

    def test_closed_way_in_both_directions_retains_closing_edge(self):
        self.way(10, [1, 2, 3, 1])
        for nodes in ([1, 2, 3, 1], [1, 3, 2, 1]):
            with self.subTest(nodes=nodes):
                result = self.analyze(nodes)
                self.assertEqual(300, result["analysis"]["totalDistance"])
                self.assertEqual(100, result["comfort"]["index"])
                self.assertEqual(0, result["analysis"]["unresolvedSegments"])

    def test_repeated_nodes_in_one_way_do_not_lose_or_duplicate_edges(self):
        self.way(10, [1, 2, 3, 2, 4])
        result = self.analyze([1, 2, 3, 2, 4, 2, 1])
        self.assertEqual(600, result["analysis"]["totalDistance"])
        self.assertEqual(100, result["comfort"]["coverage"])
        self.assertEqual(3, self.calculate_distance.call_count)
        index = edge_index(app.retrieve_ways_by_node_ids(self.db, [2]))
        self.assertEqual({1, 2}, {entry.edge_index for entry in index[2, 3]})

    def test_disconnected_way_visits_have_separate_lines_and_no_invented_distance(self):
        self.way(10, [1, 2, 3, 4])
        self.way(20, [2, 5, 3], rating="-1")
        result = self.analyze([1, 2, 5, 3, 4])
        green = result["tag_distribution"]["class:bicycle"]["2"]
        self.assertEqual(200, green.distance)
        self.assertEqual(2, len(green.ways))
        self.assertEqual(400, result["analysis"]["totalDistance"])
        self.assertEqual(68, result["comfort"]["index"])
        self.assertTrue(
            all(len(info.geometry.coordinates) == 2 for info in green.ways.values())
        )

    def test_subsection_of_a_way_counts_only_traversed_edges(self):
        self.way(10, [1, 2, 3, 4, 5])
        result = self.analyze([2, 3, 4])
        self.assertEqual(200, result["analysis"]["totalDistance"])
        geometry = result["tag_distribution"]["class:bicycle"]["2"].ways[10].geometry
        self.assertEqual(
            [(11.0002, 48.0), (11.0003, 48.0), (11.0004, 48.0)], geometry.coordinates
        )

    def test_different_ways_on_same_pair_are_unrated_once_regardless_of_order(self):
        for order in ([10, 20], [20, 10]):
            with self.subTest(order=order):
                self.db.execute("DELETE FROM ways")
                self.db.execute("DELETE FROM node_to_ways")
                for way in order:
                    self.way(way, [1, 2], rating="2" if way == 10 else "-3")
                result = self.analyze([1, 2, 1])
                self.assertEqual(200, result["analysis"]["totalDistance"])
                self.assertEqual(2, result["analysis"]["ambiguousSegments"])
                self.assertEqual(100, result["comfort"]["distribution"]["unrated"])
                self.assertIsNone(result["comfort"]["index"])

    def test_unknown_edge_stays_in_the_coverage_denominator(self):
        self.way(10, [1, 2, 3])
        result = self.analyze([1, 2, 3, 4])
        self.assertEqual(300, result["analysis"]["totalDistance"])
        self.assertEqual(67, result["comfort"]["coverage"])
        self.assertIsNone(result["comfort"]["index"])
        for tag in ("class:bicycle", "lit", "surface"):
            self.assertEqual(
                300, sum(v.distance for v in result["tag_distribution"][tag].values())
            )

    def test_missing_node_is_not_removed_or_bridged(self):
        self.way(10, [1, 3, 4])
        self.db.execute("DELETE FROM nodes WHERE id = 2")
        result = self.analyze([1, 2, 3, 4])
        self.assertEqual(100, result["analysis"]["totalDistance"])
        self.assertFalse(result["analysis"]["distanceComplete"])
        self.assertEqual(2, result["analysis"]["missingNodeSegments"])
        self.assertIsNone(result["comfort"]["index"])
        self.assertEqual(0, result["comfort"]["coverage"])
        green = result["tag_distribution"]["class:bicycle"]["2"]
        self.assertEqual(
            [[(11.0003, 48.0), (11.0004, 48.0)]],
            [info.geometry.coordinates for info in green.ways.values()],
        )

    def test_missing_node_with_distances_still_counts_full_unrated_length(self):
        self.way(10, [1, 2, 3, 4])
        self.db.execute("DELETE FROM nodes WHERE id = 2")
        result = self.analyze(
            legs=[AnalysisLeg(nodes=[1, 2, 3, 4], distance=[20, 30, 50])]
        )
        self.assertTrue(result["analysis"]["distanceComplete"])
        self.assertEqual(100, result["analysis"]["totalDistance"])
        self.assertEqual(50, result["comfort"]["coverage"])
        self.calculate_distance.assert_not_called()

    def test_partial_edges_and_return_at_waypoint_keep_both_legs(self):
        self.way(10, [1, 2, 3])
        legs = [
            AnalysisLeg(
                nodes=[1, 2], distance=[40], start=(11.00012, 48), end=(11.00016, 48)
            ),
            AnalysisLeg(
                nodes=[2, 1], distance=[25], start=(11.00016, 48), end=(11.000135, 48)
            ),
        ]
        result = self.analyze(legs=legs)
        self.assertEqual(65, result["analysis"]["totalDistance"])
        self.assertEqual(100, result["comfort"]["index"])
        green = result["tag_distribution"]["class:bicycle"]["2"]
        self.assertEqual(
            [[leg.start, leg.end] for leg in legs],
            [info.geometry.coordinates for info in green.ways.values()],
        )
        self.calculate_distance.assert_not_called()

    def test_two_legs_on_same_forward_edge_are_not_joined_or_deduplicated(self):
        self.way(10, [1, 2])
        result = self.analyze(
            legs=[
                AnalysisLeg(
                    nodes=[1, 2],
                    distance=[20],
                    start=(11.00012, 48),
                    end=(11.00014, 48),
                ),
                AnalysisLeg(
                    nodes=[1, 2],
                    distance=[30],
                    start=(11.00014, 48),
                    end=(11.00017, 48),
                ),
            ]
        )
        self.assertEqual(50, result["analysis"]["totalDistance"])
        self.assertEqual(2, len(result["tag_distribution"]["class:bicycle"]["2"].ways))

    def test_no_synthetic_edge_between_disconnected_legs(self):
        self.way(10, [1, 2, 3, 4])
        result = self.analyze(
            legs=[AnalysisLeg(nodes=[1, 2]), AnalysisLeg(nodes=[3, 4])]
        )
        self.assertEqual(200, result["analysis"]["totalDistance"])
        self.assertEqual(2, len(result["tag_distribution"]["class:bicycle"]["2"].ways))

    def test_partial_lengths_without_endpoints_do_not_draw_full_boundary_edges(self):
        self.way(10, [1, 2, 3, 4])
        result = self.analyze(
            legs=[AnalysisLeg(nodes=[1, 2, 3, 4], distance=[20, 100, 30])]
        )
        self.assertEqual(150, result["analysis"]["totalDistance"])
        geometries = result["tag_distribution"]["class:bicycle"]["2"].ways.values()
        self.assertEqual(
            [[(11.0002, 48.0), (11.0003, 48.0)]],
            [info.geometry.coordinates for info in geometries],
        )

    def test_empty_and_zero_length_routes_have_all_three_empty_tag_groups(self):
        for nodes in ([], [1], [1, 1]):
            with (
                self.subTest(nodes=nodes),
                patch.object(
                    app.distance,
                    "geodesic",
                    return_value=Mock(measure=Mock(return_value=0)),
                ),
            ):
                result = self.analyze(nodes)
                self.assertEqual(
                    {"class:bicycle": {}, "lit": {}, "surface": {}},
                    result["tag_distribution"],
                )
                self.assertIsNone(result["comfort"]["index"])

    def test_query_batches_deduplicate_ids_and_decode_a_long_way_only_once(self):
        self.way(10, list(range(1, 101)))
        self.db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 10)
        with patch.object(app, "loads", wraps=json.loads) as decode:
            ways = app.retrieve_ways_by_node_ids(self.db, list(range(1, 101)) * 2)
            self.assertEqual([10], list(ways))
            self.assertEqual(2, decode.call_count)
        self.assertEqual(
            100, len(app.retrieve_nodes_by_id(self.db, list(range(1, 101)) * 2))
        )

    def test_random_walks_preserve_every_traversal_and_tag_distance(self):
        # Independent edge-count oracle, including repeated returns and turns.
        for i in range(1, 20):
            self.way(i, [i, i + 1], rating="2" if i % 2 else "-1")
        randomizer = random.Random(20260906)
        for _ in range(30):
            nodes = [10]
            expected = {"2": 0, "-1": 0}
            for _ in range(60):
                node = nodes[-1]
                next_node = node + randomizer.choice([-1, 1])
                if not 1 <= next_node <= 20:
                    next_node = node - (next_node - node)
                expected["2" if min(node, next_node) % 2 else "-1"] += 100
                nodes.append(next_node)
            result = self.analyze(nodes)
            self.assertEqual(
                expected,
                {
                    k: v.distance
                    for k, v in result["tag_distribution"]["class:bicycle"].items()
                },
            )
            self.assertEqual(6000, result["analysis"]["totalDistance"])


class AnalysisContextTest(unittest.TestCase):
    def test_cached_wgs84_calculation_matches_original_geopy_lengths(self):
        coords = [
            (48.156304, 11.540013),
            (48.102548, 11.568796),
            (48.120477, 11.655645),
            (47.991860, 11.828568),
        ]
        nodes = {i: app.Node(i, lat, lon, {}) for i, (lat, lon) in enumerate(coords, 1)}
        ids = [1, 2, 3, 4, 3, 2, 1]
        segments = route_segments(
            [AnalysisLeg(nodes=ids)], nodes, {10: app.Way(10, [1, 2, 3, 4], {})}
        )
        for segment, a, b in zip(segments, ids, ids[1:]):
            self.assertAlmostEqual(
                app.distance.distance(nodes[a].location, nodes[b].location).meters,
                segment.distance,
                delta=1e-6,
            )

    def test_recorded_partial_edges_keep_snapped_endpoints_and_travelled_lengths(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "benchmarks/munich-partial-edge-annotations.json"
        )
        fixture = json.loads(path.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            with self.subTest(case=case["case"]):
                legs = app.osrm_analysis_legs(
                    {"legs": case["legs"]},
                    [{"location": point} for point in case["waypoints"]],
                )
                pair = legs[0].nodes
                nodes = {i: app.Node(i, 48, 11, {}) for i in pair}
                with (
                    patch.object(app, "geo_store", Mock()),
                    patch.object(app, "retrieve_nodes_by_id", return_value=nodes),
                    patch.object(
                        app,
                        "retrieve_ways_by_node_ids",
                        return_value={10: app.Way(10, pair, {"class:bicycle": "2"})},
                    ),
                    patch.object(app.distance, "geodesic") as geodesic,
                ):
                    result = app.analyze_route(legs, details=True)
                self.assertAlmostEqual(
                    case["distance"], result["analysis"]["totalDistance"], delta=0.2
                )
                self.assertEqual(100, result["comfort"]["index"])
                self.assertEqual(
                    [[leg.start, leg.end] for leg in legs],
                    [
                        info.geometry.coordinates
                        for info in result["tag_distribution"]["class:bicycle"][
                            "2"
                        ].ways.values()
                    ],
                )
                geodesic.assert_not_called()

    def test_rejects_inconsistent_distances_and_invalid_coordinates(self):
        for fields in (
            {"distance": []},
            {"distance": [-1]},
            {"distance": [float("nan")]},
            {"distance": [float("inf")]},
            {"start": (11, 48)},
            {"start": (200, 48), "end": (11, 48)},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                AnalysisLeg(nodes=[1, 2], **fields)
        for context in ({}, {"node_ids": [], "legs": []}):
            with self.assertRaises(ValidationError):
                app.NodeList(**context)

    def test_recorded_munich_route_has_one_distance_per_pair_for_all_legs(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "benchmarks/munich-route-annotations.json"
        )
        fixture = json.loads(path.read_text(encoding="utf-8"))
        legs = app.osrm_analysis_legs(
            {"legs": fixture["legs"]}, [{"location": p} for p in fixture["waypoints"]]
        )
        self.assertEqual(3, len(legs))
        self.assertAlmostEqual(
            fixture["distance"], sum(sum(leg.distance) for leg in legs), delta=0.2
        )
        for i, leg in enumerate(legs):
            self.assertEqual(len(leg.nodes) - 1, len(leg.distance))
            self.assertEqual(tuple(fixture["waypoints"][i]), leg.start)
            self.assertEqual(tuple(fixture["waypoints"][i + 1]), leg.end)

    def test_adapter_rejects_total_distance_mismatch(self):
        with self.assertRaises(ValueError):
            app.osrm_analysis_legs(
                {
                    "legs": [
                        {
                            "distance": 100,
                            "annotation": {"nodes": [1, 2], "distance": [50]},
                        }
                    ]
                },
                [],
            )


if __name__ == "__main__":
    unittest.main()
