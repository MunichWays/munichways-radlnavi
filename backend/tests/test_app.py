import asyncio
import importlib
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
            "http://routing:8080/route/v1/bike/"
            "11.5,48.1;11.55,48.15;11.6,48.2",
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
            patch.object(app, "ROUTING_VERSION", "routing-commit"),
            patch.object(app, "OSRM_VERSION", "26.6.5"),
        ):
            self.assertEqual(
                {
                    "backend": "backend-commit",
                    "routing": "routing-commit",
                    "osrm": "26.6.5",
                },
                asyncio.run(app.version()),
            )


class RouteForwardingTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
