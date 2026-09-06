import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import HTTPException, Response
from starlette.requests import Request
from requests.exceptions import ConnectionError, Timeout

from test_app import app
from src.direct_proxy import DirectRouteProxy


def request(query):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/route/v1/bike/test",
            "query_string": query.encode(),
            "headers": [],
        }
    )


class DirectRoutingTest(unittest.IsolatedAsyncioTestCase):
    async def test_public_apis_report_upstream_failures_and_recover(self):
        upstream = Mock(
            content=b'{"code":"Ok","routes":[]}', status_code=200, headers={}
        )
        for variant in ("standard", "direct"):
            for error, status in (
                (Timeout("slow"), 504),
                (ConnectionError("offline"), 503),
            ):
                with self.subTest(variant=variant, error=error):
                    with (
                        patch.object(app, "ROUTING_VARIANT", variant),
                        patch.object(app, "routing_auth_headers", return_value={}),
                        patch.object(app, "get", side_effect=[error, upstream]),
                    ):
                        async with httpx.AsyncClient(
                            transport=httpx.ASGITransport(app=app.app),
                            base_url="http://test",
                        ) as client:
                            path = f"/route/v1/bike/11,48;11.1,48.1?variant={variant}"
                            failed = await client.get(path)
                            self.assertEqual(status, failed.status_code)
                            recovered = await client.get(path)
                            self.assertEqual(200, recovered.status_code)
                            self.assertEqual(
                                variant, recovered.headers["x-routing-variant"]
                            )

    async def test_direct_comfort_failure_preserves_route_and_navigation(self):
        payload = {
            "code": "Ok",
            "routes": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[11, 48], [11.1, 48.1]],
                    },
                    "legs": [
                        {
                            "annotation": {"nodes": [1, 2], "distance": [20]},
                            "steps": [{"maneuver": {"type": "arrive"}}],
                        }
                    ],
                }
            ],
        }
        upstream = Mock(
            content=json.dumps(payload).encode(),
            status_code=200,
            headers={},
            json=lambda: payload,
        )
        with (
            patch.object(app, "ROUTING_VARIANT", "direct"),
            patch.object(app, "get", return_value=upstream),
            patch.object(app, "routing_auth_headers", return_value={}),
            patch.object(
                app, "analyze_route", side_effect=RuntimeError("analysis unavailable")
            ),
            patch.object(app.logger, "exception"),
        ):
            result = await app.osrm_route_proxy(
                request("variant=direct&comfort=true&steps=true"),
                "bike",
                "11,48;11.1,48.1",
            )
        route = json.loads(result.body)["routes"][0]
        self.assertEqual(200, result.status_code)
        self.assertEqual("arrive", route["legs"][0]["steps"][0]["maneuver"]["type"])
        self.assertNotIn("comfort", route)
        self.assertNotIn("annotation", route["legs"][0])

    async def test_capabilities_discover_separate_public_api_without_proxy(self):
        with (
            patch.object(app, "PUBLIC_DIRECT_API_URL", "https://direct.example"),
            patch.object(app, "DIRECT_API_URL", None),
        ):
            capabilities = await app.routing_variants()
        self.assertTrue(capabilities["direct"]["available"])
        self.assertEqual("https://direct.example", capabilities["direct"]["base_url"])
        self.assertEqual("standard", capabilities["default"])

    async def test_forwarding_keeps_all_waypoints_and_navigation_options(self):
        proxy = Mock(request=AsyncMock(return_value=Response(b'{"code":"Ok"}')))
        coordinates = "11,48;11.1,48.1;11.2,48.2;11.3,48.3"
        query = "variant=direct&steps=true&annotations=nodes,distance&comfort=true&exclude=ferry&exclude=motorway"
        with (
            patch.object(app, "direct_proxy", proxy),
            patch.object(app, "get") as standard,
        ):
            response = await app.osrm_route_proxy(request(query), "bike", coordinates)
        self.assertEqual(b'{"code":"Ok"}', response.body)
        proxy.request.assert_awaited_once_with(
            "GET",
            f"/route/v1/bike/{coordinates}",
            params=[
                ("variant", "direct"),
                ("steps", "true"),
                ("annotations", "nodes,distance"),
                ("comfort", "true"),
                ("exclude", "ferry"),
                ("exclude", "motorway"),
            ],
        )
        standard.assert_not_called()

    async def test_direct_analysis_is_not_run_in_the_standard_process(self):
        proxy = Mock(request=AsyncMock(return_value=Response(b'{"ok":true}')))
        context = app.NodeList(
            variant="direct", legs=[app.AnalysisLeg(nodes=[1, 2], distance=[12])]
        )
        with (
            patch.object(app, "direct_proxy", proxy),
            patch.object(app, "analyze_route") as analyze,
        ):
            await app.tag_distribution(context)
        analyze.assert_not_called()
        proxy.request.assert_awaited_once_with(
            "POST",
            "/tag_distribution",
            json={"variant": "direct", "legs": [{"nodes": [1, 2], "distance": [12.0]}]},
        )

    async def test_disabled_direct_never_falls_back_to_standard(self):
        with (
            patch.object(app, "direct_proxy", None),
            patch.object(app, "get") as standard,
        ):
            with self.assertRaises(HTTPException) as caught:
                await app.osrm_route_proxy(request("variant=direct"), "bike", "test")
        self.assertEqual(503, caught.exception.status_code)
        standard.assert_not_called()

    async def test_unknown_variant_is_rejected_before_any_routing(self):
        with patch.object(app, "get") as route:
            with self.assertRaises(HTTPException) as caught:
                await app.osrm_route_proxy(request("variant=other"), "bike", "test")
        self.assertEqual(400, caught.exception.status_code)
        route.assert_not_called()

    async def test_direct_worker_uses_its_own_upstream_without_forwarding_loop(self):
        upstream = Mock(
            content=b'{"code":"Ok","routes":[]}', status_code=200, headers={}
        )
        with (
            patch.object(app, "ROUTING_VARIANT", "direct"),
            patch.object(app, "get", return_value=upstream) as get,
            patch.object(app, "routing_auth_headers", return_value={}),
            patch.object(app, "forward_direct") as forward,
        ):
            response = await app.osrm_route_proxy(
                request("variant=direct&steps=true"), "bike", "test"
            )
            with self.assertRaises(HTTPException):
                await app.osrm_route_proxy(request("variant=standard"), "bike", "test")
        self.assertEqual("direct", response.headers["x-routing-variant"])
        self.assertEqual([("steps", "true")], get.call_args.kwargs["params"])
        forward.assert_not_called()

    async def test_pending_direct_request_does_not_block_standard(self):
        started, release = asyncio.Event(), asyncio.Event()

        async def slow(*args, **kwargs):
            started.set()
            await release.wait()
            return Response(b"direct")

        upstream = Mock(content=b"standard", status_code=200, headers={})
        with (
            patch.object(app, "direct_proxy", Mock(request=slow)),
            patch.object(app, "get", return_value=upstream),
            patch.object(app, "routing_auth_headers", return_value={}),
        ):
            task = asyncio.create_task(
                app.osrm_route_proxy(request("variant=direct"), "bike", "test")
            )
            await started.wait()
            try:
                response = await asyncio.wait_for(
                    app.osrm_route_proxy(request(""), "bike", "test"), 0.2
                )
                self.assertEqual(b"standard", response.body)
                self.assertFalse(task.done())
            finally:
                release.set()
                await task

    async def test_legacy_wrapper_selects_direct_explicitly(self):
        proxy = Mock(request=AsyncMock(return_value=Response(b"direct")))
        with (
            patch.object(app, "direct_proxy", proxy),
            patch.object(app, "get") as standard,
        ):
            response = await app.route(48, 11, 49, 12, variant="direct")
        self.assertEqual(b"direct", response.body)
        standard.assert_not_called()
        self.assertEqual("direct", proxy.request.call_args.kwargs["params"]["variant"])


class DirectProxyTest(unittest.IsolatedAsyncioTestCase):
    async def proxy(self, handler):
        proxy = DirectRouteProxy("http://direct.invalid", lambda: {})
        await proxy.client.aclose()
        proxy.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(proxy.close)
        return proxy

    async def test_upstream_error_status_and_body_are_preserved(self):
        proxy = await self.proxy(
            lambda request: httpx.Response(400, json={"code": "NoRoute"})
        )
        result = await proxy.request("GET", "/route/v1/bike/test")
        self.assertEqual(400, result.status_code)
        self.assertEqual({"code": "NoRoute"}, json.loads(result.body))

    async def test_transport_errors_have_bounded_actionable_responses(self):
        for error, code in (
            (httpx.ReadTimeout("slow"), 504),
            (httpx.PoolTimeout("busy"), 503),
            (httpx.ConnectError("offline"), 503),
        ):
            with self.subTest(error=error):

                def fail(request):
                    raise error

                proxy = await self.proxy(fail)
                with self.assertRaises(HTTPException) as caught:
                    await proxy.request("GET", "/route")
                self.assertEqual(code, caught.exception.status_code)
                self.assertEqual(4, proxy.slots._value)

    async def test_admission_is_bounded_and_recovers_after_cancellation(self):
        entered = 0
        ready, release = asyncio.Event(), asyncio.Event()

        async def slow(request):
            nonlocal entered
            entered += 1
            if entered == 4:
                ready.set()
            await release.wait()
            return httpx.Response(200, json={"ok": True})

        proxy = await self.proxy(slow)
        tasks = [asyncio.create_task(proxy.request("GET", "/route")) for _ in range(4)]
        try:
            await asyncio.wait_for(ready.wait(), 2)
            with self.assertRaises(HTTPException) as caught:
                await proxy.request("GET", "/route")
            self.assertEqual(503, caught.exception.status_code)
            self.assertEqual(4, entered)
            tasks[0].cancel()
            await asyncio.gather(tasks[0], return_exceptions=True)
            release.set()
            await asyncio.gather(*tasks[1:])
            result = await proxy.request("GET", "/route")
            self.assertEqual(200, result.status_code)
        finally:
            release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
