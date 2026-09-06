from __future__ import annotations

import logging
import os
import sqlite3
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from json import dumps, loads
from math import floor, isfinite
from typing import List, Optional, Literal

from pydantic import BaseModel, model_validator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from geopy import distance
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from requests import get

from src.direct_proxy import DirectRouteProxy

from src.route_analysis import (
    AnalysisLeg,
    INTERESTING_TAGS,
    analysis_metadata,
    route_segments,
)

script_dir = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)


@dataclass
class Node(object):
    id: int
    lat: float
    lon: float
    tags: dict[str, str]

    @property
    def location(self) -> tuple[float, float]:
        return (self.lat, self.lon)

    @property
    def coord(self) -> tuple[float, float]:
        return (self.lon, self.lat)


@dataclass
class Way(object):
    id: int
    nodes: list[int]
    tags: dict[str, str]


def get_geo_store() -> sqlite3.Connection:
    geo_folder = os.path.join(script_dir, "../geo")
    geo_store_path = os.path.join(geo_folder, "geo.db")
    geo_store_exists = os.path.exists(geo_store_path)
    if not geo_store_exists:
        raise Exception(f"geo store '{geo_store_path}' does not exist!")
    else:
        db_con = sqlite3.connect(
            f"file:{geo_store_path}?mode=ro&nolock=1",
            uri=True,
            isolation_level="EXCLUSIVE",
        )
        return db_con


geo_store: Optional[sqlite3.Connection] = None
OSRM_BACKEND_URL = os.environ["OSRM_BACKEND_URL"]
OSRM_AUTH_AUDIENCE = os.environ.get("OSRM_AUTH_AUDIENCE")
ROUTING_VARIANT = os.environ.get("ROUTING_VARIANT", "standard")
DIRECT_API_URL = os.environ.get("DIRECT_API_URL")
PUBLIC_DIRECT_API_URL = os.environ.get("PUBLIC_DIRECT_API_URL")
DIRECT_API_AUTH_AUDIENCE = os.environ.get("DIRECT_API_AUTH_AUDIENCE")
direct_proxy: Optional[DirectRouteProxy] = None
APP_VERSION = os.environ.get("APP_VERSION", "local")
APP_COMMIT = os.environ.get("APP_COMMIT", "")
ROUTING_VERSION = os.environ.get("ROUTING_VERSION", "unknown")
ROUTING_COMMIT = os.environ.get("ROUTING_COMMIT", "")
OSRM_VERSION = os.environ.get("OSRM_VERSION", "unknown")

default_origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
    "https://www.radlnavi.de",
    "https://radlnavi.de",
    "https://radlnavi.munichways.de",
]
origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", ";".join(default_origins)).split(";")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    global geo_store, direct_proxy
    if ROUTING_VARIANT not in ("standard", "direct"):
        raise ValueError("ROUTING_VARIANT must be standard or direct")
    geo_store = get_geo_store()
    if ROUTING_VARIANT == "standard" and DIRECT_API_URL:
        direct_proxy = DirectRouteProxy(DIRECT_API_URL, direct_auth_headers)
    try:
        yield
    finally:
        if direct_proxy is not None:
            await direct_proxy.close()
            direct_proxy = None
        geo_store.close()
        geo_store = None


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/route/v1/{profile}/{coordinates:path}")
async def osrm_route_proxy(
    request: Request, profile: str, coordinates: str
) -> Response:
    """Expose the private routing service through an OSRM-compatible API."""
    query_params = list(request.query_params.multi_items())
    variant = resolve_variant(request.query_params.get("variant"))
    if variant != ROUTING_VARIANT:
        return await forward_direct(
            "GET", f"/route/v1/{profile}/{coordinates}", params=query_params
        )
    query_params = [(key, value) for key, value in query_params if key != "variant"]
    comfort_requested = any(
        key == "comfort" and value.lower() == "true" for key, value in query_params
    )
    upstream_params = [(key, value) for key, value in query_params if key != "comfort"]
    original_annotations = next(
        (value for key, value in reversed(upstream_params) if key == "annotations"),
        None,
    )
    if comfort_requested and original_annotations != "true":
        upstream_params = [
            (key, value) for key, value in upstream_params if key != "annotations"
        ]
        requested_annotations = {
            annotation.strip()
            for annotation in (original_annotations or "").split(",")
            if annotation.strip() and annotation != "false"
        }
        requested_annotations.update(("nodes", "distance"))
        upstream_params.append(("annotations", ",".join(sorted(requested_annotations))))

    response = get(
        f"{OSRM_BACKEND_URL}/route/v1/{profile}/{coordinates}",
        params=upstream_params,
        headers=routing_auth_headers(),
        timeout=30,
    )
    headers = {"x-routing-variant": variant}
    content_type = response.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type
    if not comfort_requested or response.status_code != 200:
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=headers,
        )

    try:
        payload = response.json()
        for route in payload.get("routes", []):
            try:
                analysis = analyze_route(
                    osrm_analysis_legs(route, payload.get("waypoints", []))
                )
                route["comfort"] = analysis["comfort"]
                route["comfortAnalysis"] = analysis["analysis"]
            except Exception:
                logger.exception(
                    "Could not add comfort information to routing response"
                )
            # Internal annotations must also be removed after analysis errors.
            if original_annotations != "true":
                keep = {
                    value.strip() for value in (original_annotations or "").split(",")
                } - {"", "false"}
                for leg in route.get("legs", []):
                    if not keep:
                        leg.pop("annotation", None)
                    elif "annotation" in leg:
                        leg["annotation"] = {
                            key: value
                            for key, value in leg["annotation"].items()
                            if key in keep
                            or (key == "metadata" and "datasources" in keep)
                        }
        return Response(
            content=dumps(payload, separators=(",", ":")),
            status_code=response.status_code,
            headers=headers,
        )
    except Exception:
        # Comfort data is optional metadata and must never make a valid route fail.
        logger.exception("Could not add comfort information to routing response")
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=headers,
        )


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/routing_variants")
async def routing_variants():
    return {
        "default": ROUTING_VARIANT,
        "standard": {"available": ROUTING_VARIANT == "standard"},
        "direct": {
            "available": ROUTING_VARIANT == "direct"
            or bool(PUBLIC_DIRECT_API_URL or DIRECT_API_URL),
            "objective": "distance",
            "base_url": PUBLIC_DIRECT_API_URL,
        },
    }


def resolve_variant(value):
    variant = value if value is not None else ROUTING_VARIANT
    if variant not in ("standard", "direct"):
        raise HTTPException(400, "Unknown routing variant")
    if ROUTING_VARIANT == "direct" and variant != "direct":
        raise HTTPException(503, "Standard routing is not hosted by this service")
    return variant


async def forward_direct(method, path, **kwargs):
    if direct_proxy is None:
        raise HTTPException(503, "Direct routing is not configured")
    return await direct_proxy.request(method, path, **kwargs)


def direct_auth_headers():
    if not DIRECT_API_AUTH_AUDIENCE:
        return {}
    token = id_token.fetch_id_token(GoogleAuthRequest(), DIRECT_API_AUTH_AUDIENCE)
    return {"Authorization": f"Bearer {token}"}


@app.get("/version")
async def version():
    return {
        "backend": APP_VERSION,
        "backendCommit": APP_COMMIT,
        "routing": ROUTING_VERSION,
        "routingCommit": ROUTING_COMMIT,
        "osrm": OSRM_VERSION,
    }


def routing_auth_headers() -> dict[str, str]:
    if not OSRM_AUTH_AUDIENCE:
        return {}

    token = id_token.fetch_id_token(GoogleAuthRequest(), OSRM_AUTH_AUDIENCE)
    return {"Authorization": f"Bearer {token}"}


@dataclass
class LineStringGeometry(object):
    coordinates: list[tuple[float, float]]
    type: str = "LineString"


@dataclass
class WayInfo(object):
    name: str
    geometry: LineStringGeometry


@dataclass
class TagInfo(object):
    distance: float = 0.0
    ways: dict[int | str, WayInfo] = field(default_factory=lambda: dict())


MIN_COMFORT_COVERAGE = 0.7
COMFORT_SCORES = {
    "black": 0,
    "red": 35,
    "yellow": 70,
    "green": 100,
}
COMFORT_CLASSES = {
    "-3": "black",
    "-2": "black",
    "-1": "red",
    "1": "yellow",
    "2": "green",
    "3": "green",
}


def calculate_comfort_index(class_distribution: dict[str, TagInfo]) -> dict:
    """Aggregate an existing class:bicycle distribution without further I/O."""
    distances = {category: 0.0 for category in (*COMFORT_SCORES, "unrated")}
    for bicycle_class, tag_info in class_distribution.items():
        category = COMFORT_CLASSES.get(bicycle_class, "unrated")
        distances[category] += tag_info.distance

    total_distance = sum(distances.values())
    rated_distance = sum(distances[category] for category in COMFORT_SCORES)
    coverage_ratio = rated_distance / total_distance if total_distance > 0 else 0.0
    weighted_score = sum(
        distances[category] * score for category, score in COMFORT_SCORES.items()
    )
    index = int(weighted_score / rated_distance + 0.5) if rated_distance > 0 else None

    distribution = {category: 0 for category in distances}
    if total_distance > 0:
        exact_percentages = {
            category: category_distance / total_distance * 100
            for category, category_distance in distances.items()
        }
        distribution = {
            category: floor(percentage)
            for category, percentage in exact_percentages.items()
        }
        remainder = 100 - sum(distribution.values())
        largest_fractions = sorted(
            exact_percentages,
            key=lambda category: exact_percentages[category] - distribution[category],
            reverse=True,
        )
        for category in largest_fractions[:remainder]:
            distribution[category] += 1

    return {
        "index": index if coverage_ratio >= MIN_COMFORT_COVERAGE else None,
        "coverage": int(coverage_ratio * 100 + 0.5),
        "sufficientCoverage": coverage_ratio >= MIN_COMFORT_COVERAGE,
        "distribution": distribution,
    }


def route_node_ids(route: dict) -> list[int]:
    """Combine OSRM leg annotations without duplicating waypoint nodes."""
    node_ids: list[int] = []
    for leg in route.get("legs", []):
        leg_nodes = leg.get("annotation", {}).get("nodes", [])
        if node_ids and leg_nodes and node_ids[-1] == leg_nodes[0]:
            node_ids.extend(leg_nodes[1:])
        else:
            node_ids.extend(leg_nodes)
    return node_ids


def osrm_analysis_legs(route: dict, waypoints: list[dict]) -> list[AnalysisLeg]:
    """Adapt OSRM 26.6.5 annotations without flattening waypoint boundaries."""
    legs = route.get("legs", [])
    result = []
    for index, leg in enumerate(legs):
        annotation = leg.get("annotation", {})
        endpoints = {}
        if len(waypoints) == len(legs) + 1:
            endpoints = {
                "start": waypoints[index].get("location"),
                "end": waypoints[index + 1].get("location"),
            }
        context = AnalysisLeg(
            nodes=annotation.get("nodes", []),
            distance=annotation.get("distance"),
            **endpoints,
        )
        # Mismatched annotations must not silently produce a different route.
        if "distance" in leg:
            if not isfinite(leg["distance"]) or leg["distance"] < 0:
                raise ValueError("Invalid OSRM leg distance")
            if leg["distance"] > 0 and len(context.nodes) < 2:
                raise ValueError("Missing OSRM leg nodes")
            if (
                context.distance is not None
                and abs(sum(context.distance) - leg["distance"]) > 0.2
            ):
                raise ValueError("OSRM leg distance does not match its annotations")
        result.append(context)
    return result


def retrieve_nodes_by_id(
    db_con: sqlite3.Connection, node_ids: list[int]
) -> dict[int, Node]:
    nodes_by_id = {}
    for batch in lookup_batches(db_con, node_ids):
        rows = db_con.execute(
            f"SELECT id, lat, lon, tags FROM nodes WHERE id IN ({','.join('?' * len(batch))})",
            batch,
        )
        for node in rows:
            nodes_by_id[node[0]] = Node(node[0], node[1], node[2], loads(node[3]))
    return nodes_by_id


def retrieve_ways_by_node_ids(
    db_con: sqlite3.Connection, node_ids: list[int]
) -> dict[int, Way]:
    # First select unique IDs using the node index, then read/decode each way
    # once. A long way can be encountered in several SQL batches.
    way_ids = set()
    for batch in lookup_batches(db_con, node_ids):
        way_ids.update(
            row[0]
            for row in db_con.execute(
                f"SELECT DISTINCT way_id FROM node_to_ways WHERE node_id IN ({','.join('?' * len(batch))})",
                batch,
            )
        )
    way_by_id = {}
    for batch in lookup_batches(db_con, sorted(way_ids)):
        for way in db_con.execute(
            f"SELECT id, node_list, tags FROM ways WHERE id IN ({','.join('?' * len(batch))})",
            batch,
        ):
            way_by_id[way[0]] = Way(way[0], loads(way[1]), loads(way[2]))
    return way_by_id


def lookup_batches(db_con, ids):
    ids = list(dict.fromkeys(ids))
    size = min(900, db_con.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER))
    for start in range(0, len(ids), size):
        yield ids[start : start + size]


def retrieve_route_segments(legs):
    assert geo_store is not None
    ids = [node for leg in legs for node in leg.nodes]
    nodes = retrieve_nodes_by_id(geo_store, ids)
    ways = retrieve_ways_by_node_ids(geo_store, ids)
    return route_segments(legs, nodes, ways)


def analyze_route(legs: list[AnalysisLeg], *, details: bool = False):
    segments = retrieve_route_segments(legs)
    distributions = {tag: defaultdict(TagInfo) for tag in INTERESTING_TAGS}
    previous = None
    geometry = None
    seen_ways = set()
    for segment in segments:
        if segment.distance is None or segment.distance == 0:
            previous = None
            continue
        for tag in INTERESTING_TAGS:
            distributions[tag][
                segment.tags.get(tag, "unknown")
            ].distance += segment.distance
        if details and segment.coordinates is not None:
            # Merge only consecutive occurrences of the same way within a leg.
            # Returning to a way after a detour must start a new LineString.
            if (
                previous is not None
                and geometry is not None
                and previous.leg_index == segment.leg_index
                and previous.segment_index + 1 == segment.segment_index
                and previous.way_id == segment.way_id
                and previous.status == segment.status
                and geometry.coordinates[-1] == segment.coordinates[0]
            ):
                geometry.coordinates.append(segment.coordinates[1])
            else:
                geometry = LineStringGeometry(list(segment.coordinates))
                occurrence = f"{segment.way_id if segment.way_id is not None else segment.status}:{segment.leg_index}:{segment.segment_index}"
                if segment.way_id is not None and segment.way_id not in seen_ways:
                    occurrence = segment.way_id
                    seen_ways.add(segment.way_id)
                info = WayInfo(segment.tags.get("name", ""), geometry)
                for tag in INTERESTING_TAGS:
                    distributions[tag][segment.tags.get(tag, "unknown")].ways[
                        occurrence
                    ] = info
        else:
            geometry = None
        previous = segment
    metadata = analysis_metadata(legs, segments)
    comfort = calculate_comfort_index(distributions["class:bicycle"])
    if not metadata["distanceComplete"]:
        # An absent node without an OSRM distance has unknown length. Do not
        # turn coverage of the remaining fragments into coverage of the route.
        comfort.update(index=None, coverage=0, sufficientCoverage=False)
    return {
        "ok": True,
        "tag_distribution": distributions,
        "comfort": comfort,
        "analysis": metadata,
    }


def calculate_comfort_for_node_ids(node_ids: list[int]) -> dict:
    if not node_ids:
        return calculate_comfort_index({})
    return analyze_route([AnalysisLeg(nodes=node_ids)])["comfort"]


class NodeList(BaseModel):
    node_ids: List[int] | None = None
    legs: list[AnalysisLeg] | None = None
    variant: Literal["standard", "direct"] | None = None

    @model_validator(mode="after")
    def one_route_context(self):
        if (self.node_ids is None) == (self.legs is None):
            raise ValueError("Provide either node_ids or legs")
        return self


@app.post("/tag_distribution")
async def tag_distribution(node_list: NodeList):
    variant = resolve_variant(node_list.variant)
    if variant != ROUTING_VARIANT:
        return await forward_direct(
            "POST", "/tag_distribution", json=node_list.model_dump(exclude_none=True)
        )
    legs = (
        node_list.legs
        if node_list.legs is not None
        else [AnalysisLeg(nodes=node_list.node_ids)]
    )
    return analyze_route(legs, details=True)


@app.get("/route")
async def route(
    start_lat: float,
    start_lon: float,
    target_lat: float,
    target_lon: float,
    variant: Literal["standard", "direct"] | None = None,
):
    selected = resolve_variant(variant)
    if selected != ROUTING_VARIANT:
        return await forward_direct(
            "GET",
            "/route",
            params={
                "start_lat": start_lat,
                "start_lon": start_lon,
                "target_lat": target_lat,
                "target_lon": target_lon,
                "variant": selected,
            },
        )
    print("request start")
    response = get(
        f"{OSRM_BACKEND_URL}/route/v1/bike/{start_lon},{start_lat};{target_lon},{target_lat}",
        params={
            "overview": "full",
            "alternatives": "true",
            "steps": "true",
            "geometries": "geojson",
            "annotations": "true",
        },
        headers=routing_auth_headers(),
        timeout=30,
    )

    if response.status_code != 200:
        return {"ok": False}

    print("response start")
    osrm_response = response.json()
    print("response end")

    first_route = osrm_response["routes"][0]
    analysis_context = {}
    try:
        analysis_context["analysis_legs"] = [
            leg.model_dump(exclude_none=True)
            for leg in osrm_analysis_legs(
                first_route, osrm_response.get("waypoints", [])
            )
        ]
    except Exception:
        # Optional analysis must not invalidate the navigable OSRM response.
        logger.exception("Could not prepare route analysis context")

    return {
        "ok": True,
        "route": {
            **analysis_context,
            "annotation": osrm_response["routes"][0]["legs"][0]["annotation"],
            "steps": osrm_response["routes"][0]["legs"][0]["steps"],
            "geometry": osrm_response["routes"][0]["geometry"],
            "duration": osrm_response["routes"][0]["duration"],
            "distance": osrm_response["routes"][0]["distance"],
        },
    }
