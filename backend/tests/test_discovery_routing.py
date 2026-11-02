import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch
import httpx
from fastapi import HTTPException, Response
from test_app import app
from src.direct_proxy import DirectRouteProxy


class DiscoveryRoutingTest(unittest.IsolatedAsyncioTestCase):
    async def test_route_and_comfort_are_forwarded_to_same_discovery_worker(self):
        proxy = Mock(request=AsyncMock(return_value=Response(b'{"code":"Ok"}', headers={"x-routing-variant":"discovery"})))
        with patch.object(app, "ROUTING_VARIANT", "standard"), patch.object(app, "discovery_proxy", proxy), patch.object(app, "direct_proxy", None):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url="http://test") as client:
                route = await client.get('/route/v1/bike/11,48;11.1,48.1?variant=discovery&steps=true')
                self.assertEqual(200, route.status_code)
                self.assertEqual('discovery', route.headers['x-routing-variant'])
                await client.post('/tag_distribution', json={'variant':'discovery','node_ids':[1,2]})
        self.assertEqual(2, proxy.request.await_count)
        self.assertEqual('GET', proxy.request.await_args_list[0].args[0])
        self.assertEqual('discovery', proxy.request.await_args_list[1].kwargs['json']['variant'])

    async def test_unconfigured_discovery_never_returns_standard_and_recovers(self):
        with patch.object(app, 'ROUTING_VARIANT', 'standard'), patch.object(app, 'discovery_proxy', None):
            with self.assertRaises(HTTPException) as error:
                await app.forward_variant('discovery','GET','/route')
            self.assertEqual(503, error.exception.status_code)
            proxy = Mock(request=AsyncMock(return_value=Response(b'ok')))
            with patch.object(app, 'discovery_proxy', proxy):
                self.assertEqual(b'ok', (await app.forward_variant('discovery','GET','/route')).body)

    async def test_discovery_worker_cannot_accidentally_serve_standard_or_direct(self):
        with patch.object(app, 'ROUTING_VARIANT', 'discovery'):
            self.assertEqual('discovery', app.resolve_variant(None))
            for variant in ('standard','direct'):
                with self.assertRaises(HTTPException): app.resolve_variant(variant)

    async def test_proxy_retains_variant_after_transient_failure(self):
        proxy = DirectRouteProxy('http://discovery', lambda: {}, variant='discovery')
        await proxy.client.aclose()
        calls = [0]
        def transport(request):
            calls[0] += 1
            if calls[0] == 1: raise httpx.ReadTimeout('temporary')
            return httpx.Response(200, json={'ok':True})
        proxy.client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            with self.assertRaises(HTTPException) as error:
                await proxy.request('GET','/route')
            self.assertEqual(504, error.exception.status_code)
            result = await proxy.request('GET','/route')
            self.assertEqual('discovery', result.headers['x-routing-variant'])
        finally:
            await proxy.close()
