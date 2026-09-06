"""Bounded async gateway to the separately provisioned direct-route API.

The destination is deployment configuration, never a URL supplied by a client.
Direct OSRM work AND optional comfort analysis run outside the standard service.
"""

import asyncio

import httpx
from fastapi import HTTPException, Response
from google.auth.exceptions import GoogleAuthError
from starlette.concurrency import run_in_threadpool


class DirectRouteProxy:
    def __init__(self, url, auth_headers):
        self.url = url.rstrip("/")
        self.auth_headers = auth_headers
        self.slots = asyncio.Semaphore(4)
        self.client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            timeout=httpx.Timeout(45, connect=5, pool=0.1),
            follow_redirects=False,
        )

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, *, params=None, json=None):
        try:
            await asyncio.wait_for(self.slots.acquire(), timeout=0.1)
        except TimeoutError as error:
            raise HTTPException(503, "Direct routing capacity is busy") from error
        try:
            return await self._request(method, path, params=params, json=json)
        finally:
            self.slots.release()

    async def _request(self, method, path, *, params=None, json=None):
        try:
            headers = await run_in_threadpool(self.auth_headers)
            upstream = await self.client.request(
                method, self.url + path, params=params, json=json, headers=headers
            )
        except httpx.PoolTimeout as error:
            raise HTTPException(503, "Direct routing capacity is busy") from error
        except httpx.TimeoutException as error:
            raise HTTPException(504, "Direct routing timed out") from error
        except (httpx.HTTPError, OSError, GoogleAuthError) as error:
            raise HTTPException(503, "Direct routing is unavailable") from error
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers={
                "content-type": upstream.headers.get(
                    "content-type", "application/json"
                ),
                "x-routing-variant": "direct",
            },
        )
