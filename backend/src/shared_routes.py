"""Immutable, expiring route transfers. GCS in production; explicit local storage in dev."""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import quote, urlparse

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

MAX_BYTES = 4 * 1024 * 1024
MAX_STOPS = 50
TTL_DAYS = 90
router = APIRouter()


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def coordinate(value):
    return (isinstance(value, list) and len(value) == 2
            and all(valid_number(v) for v in value)
            and abs(value[0]) <= 180 and abs(value[1]) <= 90)


def require(condition):
    if not condition:
        raise ValueError('Invalid route transfer')


def validate_transfer(value):
    try:
        require(value['version'] == 1 and type(value['version']) is int)
        require(value['provider'] == 'radlnavi')
        require(value['variant'] in ('standard', 'direct'))
        require(isinstance(value['name'], str) and 0 < len(value['name'].strip()) <= 200)
        require(isinstance(value['createdAt'], str))
        datetime.fromisoformat(value['createdAt'].replace('Z', '+00:00'))
        plan = value['plan']
        require(isinstance(plan, list) and 2 <= len(plan) <= MAX_STOPS + 2)
        require(all((isinstance(p['name'], str) and len(p['name']) <= 500 and coordinate(p['coordinates']) for p in plan)))
        payload = value['response']
        require(payload['code'] == 'Ok' and len(payload['routes']) == 1)
        route = payload['routes'][0]
        require(route['geometry']['type'] == 'LineString')
        coords = route['geometry']['coordinates']
        require(isinstance(coords, list) and 2 <= len(coords) <= 100000)
        require(all((coordinate(p) for p in coords)))
        require(all((valid_number(route[key]) and route[key] >= 0 for key in ('distance', 'duration'))))
        legs = route['legs']
        require(isinstance(legs, list) and len(legs) == len(plan) - 1)
        for leg in legs:
            steps = leg['steps']
            require(isinstance(steps, list) and 2 <= len(steps) <= 100000)
            require(steps[0]['maneuver']['type'] == 'depart')
            require(steps[-1]['maneuver']['type'] == 'arrive')
            for step in steps:
                require(coordinate(step['maneuver']['location']))
                require(isinstance(step['maneuver']['type'], str))
                require(isinstance(step['mode'], str))
                require(all((valid_number(step[key]) and step[key] >= 0 for key in ('distance', 'duration'))))
                require(step['geometry']['type'] == 'LineString')
                require(isinstance(step['geometry']['coordinates'], list) and step['geometry']['coordinates'])
                require(all((coordinate(p) for p in step['geometry']['coordinates'])))
        require(len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) <= MAX_BYTES)
        joined = [p for leg in legs for step in leg['steps'] if step['maneuver']['type'] != 'arrive' for p in step['geometry']['coordinates']]

        def distinct(points):
            return [p for i, p in enumerate(points) if not i or p != points[i - 1]]
        require(distinct(joined) == distinct(coords))
    except (AssertionError, KeyError, TypeError, ValueError, OverflowError, IndexError):
        raise HTTPException(422, 'Invalid route transfer') from None
    return value


class ShareStore:
    def __init__(self, *, bucket=None, directory=None, clock=None):
        self.bucket = bucket
        self.directory = Path(directory) if directory else None
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _session(self):
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/devstorage.read_write'])
        return AuthorizedSession(credentials)

    def create(self, transfer):
        validate_transfer(transfer)
        route_id = secrets.token_urlsafe(24)
        expiry = self.clock() + timedelta(days=TTL_DAYS)
        body = json.dumps({'expiresAt': expiry.isoformat(), 'transfer': transfer},
                          ensure_ascii=False, allow_nan=False).encode()
        if self.bucket:
            with self._session() as session:
                result = session.post(
                    f'https://storage.googleapis.com/upload/storage/v1/b/{quote(self.bucket, safe="")}/o',
                    params={'uploadType': 'media', 'name': f'routes/{route_id}.json', 'ifGenerationMatch': '0'},
                    data=body, headers={'Content-Type': 'application/json'}, timeout=15)
                result.raise_for_status()
        elif self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / f'{route_id}.json').open('xb') as file:
                file.write(body)
            # Bounded opportunistic cleanup; read expiry still enforces TTL.
            for file in list(self.directory.glob('*.json'))[:100]:
                if datetime.fromtimestamp(file.stat().st_mtime, timezone.utc) < self.clock() - timedelta(days=TTL_DAYS):
                    file.unlink(missing_ok=True)
        else:
            raise HTTPException(503, 'Route sharing is not configured')
        return route_id, expiry

    def read(self, route_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{22,64}', route_id):
            raise HTTPException(404, 'Route not found')
        if self.bucket:
            with self._session() as session:
                result = session.get(
                    f'https://storage.googleapis.com/storage/v1/b/{quote(self.bucket, safe="")}/o/{quote("routes/" + route_id + ".json", safe="")}',
                    params={'alt': 'media'}, timeout=15)
                if result.status_code == 404:
                    raise HTTPException(404, 'Route not found')
                result.raise_for_status()
                stored = result.json()
        elif self.directory:
            try:
                stored = json.loads((self.directory / f'{route_id}.json').read_bytes())
            except FileNotFoundError:
                raise HTTPException(404, 'Route not found') from None
        else:
            raise HTTPException(503, 'Route sharing is not configured')
        if datetime.fromisoformat(stored['expiresAt']) <= self.clock():
            raise HTTPException(410, 'Route expired')
        return stored['transfer']


def get_store():
    return ShareStore(bucket=os.getenv('SHARED_ROUTES_BUCKET'), directory=os.getenv('SHARED_ROUTES_DIR'))


_requests = defaultdict(deque)
_lock = threading.Lock()


def limit_creation(key):
    # Per-instance guard in addition to deployment max-instances and bucket quotas.
    now = monotonic()
    with _lock:
        for old_key in list(_requests):
            if not _requests[old_key] or _requests[old_key][-1] <= now - 3600:
                del _requests[old_key]
        times = _requests[key]
        while times and times[0] <= now - 3600:
            times.popleft()
        if len(times) >= 30 or sum(map(len, _requests.values())) >= 300:
            raise HTTPException(429, 'Too many shared routes', headers={'Retry-After': '3600'})
        times.append(now)


@router.post('/shared_routes', status_code=201)
async def create_shared_route(request: Request):
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > MAX_BYTES:
            raise HTTPException(413, 'Route is too large')
    try:
        transfer = validate_transfer(json.loads(chunks))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, 'Invalid JSON') from None
    limit_creation(request.client.host if request.client else 'unknown')
    base = os.getenv('SHARE_PUBLIC_BASE_URL', 'https://radlnavi.munichways.de').rstrip('/')
    url = urlparse(base)
    if url.scheme not in ('http', 'https') or not url.netloc or url.query or url.fragment or url.username:
        raise HTTPException(503, 'Invalid sharing configuration')
    try:
        route_id, expiry = await run_in_threadpool(get_store().create, transfer)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Route storage is temporarily unavailable') from None
    return {'id': route_id, 'url': f'{base}/r/{route_id}', 'expiresAt': expiry.isoformat()}


@router.get('/shared_routes/{route_id}')
async def read_shared_route(route_id: str):
    try:
        transfer = await run_in_threadpool(get_store().read, route_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Route storage is temporarily unavailable') from None
    return Response(json.dumps(transfer, ensure_ascii=False, allow_nan=False),
                    media_type='application/json', headers={'Cache-Control': 'no-store'})
