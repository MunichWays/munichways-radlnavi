import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from starlette.requests import Request


os.environ.setdefault("OSRM_BACKEND_URL", "http://routing:8080")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
app = importlib.import_module("src.app")


class RoutingAuthenticationTest(unittest.TestCase):
    def test_local_routing_does_not_send_authorization(self):
        with patch.object(app, "OSRM_AUTH_AUDIENCE", None):
            self.assertEqual({}, app.routing_auth_headers())

    def test_cloud_routing_uses_identity_token(self):
        with (
            patch.object(app, "OSRM_AUTH_AUDIENCE", "https://routing.example"),
            patch.object(app.id_token, "fetch_id_token", return_value="token") as fetch,
        ):
            self.assertEqual(
                {"Authorization": "Bearer token"}, app.routing_auth_headers()
            )
            fetch.assert_called_once()


class RouteTest(unittest.TestCase):
    def test_osrm_proxy_preserves_path_query_response_and_error_status(self):
        response = Mock()
        response.status_code = 400
        response.content = b'{"code":"InvalidOptions"}'
        response.headers = {"content-type": "application/json"}
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/route/v1/bike/coordinates",
                "query_string": (
                    b"alternatives=false&steps=true&exclude=ferry&exclude=motorway"
                ),
                "headers": [],
            }
        )

        with (
            patch.object(app, "get", return_value=response) as get,
            patch.object(
                app,
                "routing_auth_headers",
                return_value={"Authorization": "Bearer token"},
            ),
        ):
            result = asyncio.run(
                app.osrm_route_proxy(
                    request,
                    "bike",
                    "11.5,48.1;11.55,48.15;11.6,48.2",
                )
            )

        self.assertEqual(400, result.status_code)
        self.assertEqual(b'{"code":"InvalidOptions"}', result.body)
        self.assertEqual("application/json", result.headers["content-type"])
        get.assert_called_once_with(
            "http://routing:8080/route/v1/bike/" "11.5,48.1;11.55,48.15;11.6,48.2",
            params=[
                ("alternatives", "false"),
                ("steps", "true"),
                ("exclude", "ferry"),
                ("exclude", "motorway"),
            ],
            headers={"Authorization": "Bearer token"},
            timeout=30,
        )


class VersionTest(unittest.TestCase):
    def test_version_reports_backend_routing_and_osrm_builds(self):
        with (
            patch.object(app, "APP_VERSION", "backend-commit"),
            patch.object(app, "APP_COMMIT", "abcdef123456"),
            patch.object(app, "ROUTING_VERSION", "routing-commit"),
            patch.object(app, "ROUTING_COMMIT", "123456abcdef"),
            patch.object(app, "OSRM_VERSION", "26.6.5"),
        ):
            self.assertEqual(
                {
                    "backend": "backend-commit",
                    "backendCommit": "abcdef123456",
                    "routing": "routing-commit",
                    "routingCommit": "123456abcdef",
                    "osrm": "26.6.5",
                },
                asyncio.run(app.version()),
            )


class RouteForwardingTest(unittest.TestCase):
    def test_internal_annotations_are_filtered_for_success_and_failure(self):
        for query, expected in (
            (b"annotations=nodes&comfort=true", {"nodes": [1, 2]}),
            (b"annotations=duration&comfort=true", {"duration": [2.0]}),
            (
                b"annotations=true&comfort=true",
                {"nodes": [1, 2], "distance": [12.0], "duration": [2.0]},
            ),
        ):
            for failed in (False, True):
                with self.subTest(query=query, failed=failed):
                    payload = {
                        "code": "Ok",
                        "routes": [
                            {
                                "distance": 12.0,
                                "duration": 2.0,
                                "geometry": "unchanged",
                                "legs": [
                                    {
                                        "distance": 12.0,
                                        "steps": [{"maneuver": {"type": "arrive"}}],
                                        "annotation": {
                                            "nodes": [1, 2],
                                            "distance": [12.0],
                                            "duration": [2.0],
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                    response = Mock(
                        status_code=200,
                        headers={"content-type": "application/json"},
                        content=json.dumps(payload).encode(),
                    )
                    response.json.return_value = payload
                    request = Request(
                        {
                            "type": "http",
                            "method": "GET",
                            "path": "/route/v1/bike/test",
                            "query_string": query,
                            "headers": [],
                        }
                    )
                    with (
                        patch.object(app, "get", return_value=response),
                        patch.object(app, "routing_auth_headers", return_value={}),
                        patch.object(
                            app,
                            "analyze_route",
                            return_value={"comfort": {}, "analysis": {}},
                            side_effect=(
                                ValueError("bad annotations") if failed else None
                            ),
                        ),
                        patch.object(app.logger, "exception"),
                    ):
                        result = asyncio.run(
                            app.osrm_route_proxy(request, "bike", "test")
                        )
                    route = json.loads(result.body)["routes"][0]
                    self.assertEqual(expected, route["legs"][0]["annotation"])
                    self.assertEqual("unchanged", route["geometry"])
                    self.assertEqual(12.0, route["distance"])
                    self.assertEqual(
                        [{"maneuver": {"type": "arrive"}}], route["legs"][0]["steps"]
                    )
                    self.assertEqual(not failed, "comfort" in route)

    def test_plain_proxy_has_no_analysis_work(self):
        response = Mock(status_code=200, headers={}, content=b'{"code":"Ok"}')
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/route/v1/bike/test",
                "query_string": b"steps=true&annotations=nodes",
                "headers": [],
            }
        )
        with (
            patch.object(app, "get", return_value=response),
            patch.object(app, "routing_auth_headers", return_value={}),
            patch.object(app, "analyze_route") as analyze,
        ):
            result = asyncio.run(app.osrm_route_proxy(request, "bike", "test"))
        self.assertEqual(response.content, result.body)
        response.json.assert_not_called()
        analyze.assert_not_called()

    def test_route_forwards_coordinates_and_osrm_options(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "routes": [
                {
                    "legs": [{"annotation": {"nodes": []}, "steps": []}],
                    "geometry": {"type": "LineString", "coordinates": []},
                    "duration": 12,
                    "distance": 34,
                }
            ]
        }

        with (
            patch.object(app, "get", return_value=response) as get,
            patch.object(app, "routing_auth_headers", return_value={}),
        ):
            result = asyncio.run(app.route(48.1, 11.5, 48.2, 11.6))

        self.assertTrue(result["ok"])
        self.assertEqual([{"nodes": []}], result["route"]["analysis_legs"])
        get.assert_called_once_with(
            "http://routing:8080/route/v1/bike/11.5,48.1;11.6,48.2",
            params={
                "overview": "full",
                "alternatives": "true",
                "steps": "true",
                "geometries": "geojson",
                "annotations": "true",
            },
            headers={},
            timeout=30,
        )

    def test_comfort_option_enriches_route_without_exposing_internal_nodes(self):
        payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 100,
                    "legs": [
                        {"annotation": {"nodes": [1, 2, 3]}, "steps": []},
                        {"annotation": {"nodes": [3, 4]}, "steps": []},
                    ],
                }
            ],
        }
        response = Mock(
            status_code=200,
            content=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )
        response.json.return_value = payload
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/route/v1/bike/coordinates",
                "query_string": b"steps=true&annotations=false&comfort=true",
                "headers": [],
            }
        )
        comfort = {
            "index": 80,
            "coverage": 90,
            "sufficientCoverage": True,
            "distribution": {
                "black": 0,
                "red": 10,
                "yellow": 20,
                "green": 60,
                "unrated": 10,
            },
        }

        with (
            patch.object(app, "get", return_value=response) as get,
            patch.object(app, "routing_auth_headers", return_value={}),
            patch.object(
                app, "analyze_route", return_value={"comfort": comfort, "analysis": {}}
            ) as calculate,
        ):
            result = asyncio.run(app.osrm_route_proxy(request, "bike", "coordinates"))

        body = json.loads(result.body)
        self.assertEqual(comfort, body["routes"][0]["comfort"])
        self.assertNotIn("annotation", body["routes"][0]["legs"][0])
        calculate.assert_called_once_with(
            [app.AnalysisLeg(nodes=[1, 2, 3]), app.AnalysisLeg(nodes=[3, 4])]
        )
        get.assert_called_once_with(
            "http://routing:8080/route/v1/bike/coordinates",
            params=[("steps", "true"), ("annotations", "distance,nodes")],
            headers={},
            timeout=30,
        )

    def test_comfort_failure_does_not_break_valid_route(self):
        payload = {
            "code": "Ok",
            "routes": [{"legs": [{"annotation": {"nodes": [1, 2]}}]}],
        }
        content = json.dumps(payload).encode()
        response = Mock(
            status_code=200,
            content=content,
            headers={"content-type": "application/json"},
        )
        response.json.return_value = payload
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/route/v1/bike/coordinates",
                "query_string": b"comfort=true",
                "headers": [],
            }
        )

        with self.assertLogs(app.logger, level="ERROR") as logs:
            with (
                patch.object(app, "get", return_value=response),
                patch.object(app, "routing_auth_headers", return_value={}),
                patch.object(
                    app,
                    "analyze_route",
                    side_effect=RuntimeError("analysis unavailable"),
                ),
            ):
                result = asyncio.run(
                    app.osrm_route_proxy(request, "bike", "coordinates")
                )

        self.assertEqual(200, result.status_code)
        self.assertEqual(
            {"code": "Ok", "routes": [{"legs": [{}]}]}, json.loads(result.body)
        )
        self.assertIn("Could not add comfort information", logs.output[0])


class ComfortIndexTest(unittest.TestCase):
    @staticmethod
    def distribution(**distances):
        return {
            bicycle_class: app.TagInfo(distance=distance)
            for bicycle_class, distance in distances.items()
        }

    def test_calculates_weighted_index_coverage_and_distribution(self):
        result = app.calculate_comfort_index(
            self.distribution(**{"-2": 10, "-1": 20, "1": 30, "2": 40})
        )

        self.assertEqual(68, result["index"])
        self.assertEqual(100, result["coverage"])
        self.assertTrue(result["sufficientCoverage"])
        self.assertEqual(
            {"black": 10, "red": 20, "yellow": 30, "green": 40, "unrated": 0},
            result["distribution"],
        )

    def test_excludes_unrated_distance_and_hides_index_below_threshold(self):
        result = app.calculate_comfort_index(
            self.distribution(**{"2": 69, "0": 10, "unknown": 20, "unexpected": 1})
        )

        self.assertIsNone(result["index"])
        self.assertEqual(69, result["coverage"])
        self.assertFalse(result["sufficientCoverage"])
        self.assertEqual(31, result["distribution"]["unrated"])

    def test_returns_index_at_exact_coverage_threshold(self):
        result = app.calculate_comfort_index(
            self.distribution(**{"1": 70, "unknown": 30})
        )

        self.assertEqual(70, result["index"])
        self.assertEqual(70, result["coverage"])
        self.assertTrue(result["sufficientCoverage"])

    def test_handles_empty_distribution(self):
        result = app.calculate_comfort_index({})

        self.assertIsNone(result["index"])
        self.assertEqual(0, result["coverage"])
        self.assertFalse(result["sufficientCoverage"])
        self.assertEqual(
            {"black": 0, "red": 0, "yellow": 0, "green": 0, "unrated": 0},
            result["distribution"],
        )

    def test_rounded_distribution_always_sums_to_one_hundred(self):
        result = app.calculate_comfort_index(
            self.distribution(**{"-2": 1, "-1": 1, "1": 1})
        )

        self.assertEqual(100, sum(result["distribution"].values()))


class TagDistributionComfortTest(unittest.TestCase):
    def test_response_includes_backend_calculated_comfort(self):
        nodes = {
            1: app.Node(1, 48.1, 11.5, {}),
            2: app.Node(2, 48.101, 11.501, {}),
        }
        ways = {
            10: app.Way(
                10,
                [1, 2],
                {"class:bicycle": "2", "surface": "asphalt", "lit": "yes"},
            )
        }

        with (
            patch.object(app, "geo_store", Mock()),
            patch.object(app, "retrieve_nodes_by_id", return_value=nodes),
            patch.object(app, "retrieve_ways_by_node_ids", return_value=ways),
            patch.object(
                app.distance,
                "geodesic",
                return_value=Mock(measure=Mock(return_value=0.1)),
            ) as calculate_distance,
        ):
            result = asyncio.run(app.tag_distribution(app.NodeList(node_ids=[1, 2])))

        self.assertTrue(result["ok"])
        self.assertEqual(100, result["comfort"]["index"])
        self.assertEqual(100, result["comfort"]["coverage"])
        self.assertEqual(100, result["comfort"]["distribution"]["green"])
        calculate_distance.assert_called_once()


if __name__ == "__main__":
    unittest.main()
