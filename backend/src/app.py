from __future__ import annotations

import logging
import os
import sqlite3
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from json import dumps, loads
from math import floor
from typing import List, Optional

from pydantic import BaseModel

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from geopy import distance
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from requests import get

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
        db_con = sqlite3.connect(f"file:{geo_store_path}?mode=ro&nolock=1", uri=True, isolation_level="EXCLUSIVE")
        return db_con

geo_store: Optional[sqlite3.Connection] = None
OSRM_BACKEND_URL = os.environ["OSRM_BACKEND_URL"]
OSRM_AUTH_AUDIENCE = os.environ.get("OSRM_AUTH_AUDIENCE")
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
    global geo_store
    geo_store = get_geo_store()
    yield
    pass


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
    comfort_requested = any(
        key == "comfort" and value.lower() == "true"
        for key, value in query_params
    )
    upstream_params = [(key, value) for key, value in query_params if key != "comfort"]
    original_annotations = next(
        (value for key, value in reversed(upstream_params) if key == "annotations"),
        None,
    )
    if comfort_requested and original_annotations not in ("true", "nodes"):
        upstream_params = [
            (key, value) for key, value in upstream_params if key != "annotations"
        ]
        requested_annotations = {
            annotation.strip()
            for annotation in (original_annotations or "").split(",")
            if annotation.strip() and annotation != "false"
        }
        requested_annotations.add("nodes")
        upstream_params.append(("annotations", ",".join(sorted(requested_annotations))))

    response = get(
        f"{OSRM_BACKEND_URL}/route/v1/{profile}/{coordinates}",
        params=upstream_params,
        headers=routing_auth_headers(),
        timeout=30,
    )
    headers = {}
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
        keep_annotations = original_annotations not in (None, "false")
        for route in payload.get("routes", []):
            node_ids = route_node_ids(route)
            route["comfort"] = calculate_comfort_for_node_ids(node_ids)
            if not keep_annotations:
                for leg in route.get("legs", []):
                    leg.pop("annotation", None)
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
    ways: dict[int, WayInfo] = field(default_factory=lambda: dict())


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


def retrieve_nodes_by_id(
    db_con: sqlite3.Connection, node_ids: list[int]
) -> dict[int, Node]:
    c = db_con.cursor()
    c.execute(
        f"SELECT id, lat, lon, tags FROM nodes WHERE id IN ({','.join('?' * len(node_ids))})",
        node_ids,
    )
    node_data = c.fetchall()
    nodes_by_id = dict(
        map(
            lambda node: (node[0], Node(node[0], node[1], node[2], loads(node[3]))),
            node_data,
        )
    )
    return nodes_by_id


def retrieve_ways_by_node_ids(
    db_con: sqlite3.Connection, node_ids: list[int]
) -> dict[int, Way]:
    c = db_con.cursor()
    c.execute(
        f"SELECT w.id, w.node_list, w.tags FROM node_to_ways ntw INNER JOIN ways w ON (ntw.way_id = w.id) WHERE ntw.node_id IN ({','.join('?' * len(node_ids))})",
        node_ids,
    )
    ways = c.fetchall()
    way_by_id = dict(
        map(lambda way: (way[0], Way(way[0], loads(way[1]), loads(way[2]))), ways)
    )

    return way_by_id


def retrieve_route_ways(node_ids: list[int]) -> tuple[dict[int, list[Node]], dict[int, Way]]:
    assert geo_store is not None

    nodes_by_id = retrieve_nodes_by_id(geo_store, node_ids)
    ways_by_id = retrieve_ways_by_node_ids(geo_store, node_ids)
    route_nodes = [nodes_by_id[node_id] for node_id in node_ids if node_id in nodes_by_id]

    route_ways: dict[int, list[Node]] = defaultdict(list)
    for node_a, node_b in zip(route_nodes, route_nodes[1:]):
        ways = filter(
            lambda way: node_a.id in way.nodes
            and node_b.id in way.nodes
            and abs(way.nodes.index(node_a.id) - way.nodes.index(node_b.id)) == 1,
            ways_by_id.values(),
        )
        for way in ways:
            way_nodes = route_ways[way.id]
            if way_nodes and way_nodes[-1] == node_a:
                way_nodes.append(node_b)
            else:
                way_nodes.extend((node_a, node_b))

    return route_ways, ways_by_id


def route_way_distance(nodes: list[Node]) -> float:
    return sum(
        distance.distance(node_a.location, node_b.location).meters
        for node_a, node_b in zip(nodes, nodes[1:])
    )


def calculate_comfort_for_node_ids(node_ids: list[int]) -> dict:
    if not node_ids:
        return calculate_comfort_index({})

    route_ways, ways_by_id = retrieve_route_ways(node_ids)
    class_distribution: dict[str, TagInfo] = defaultdict(TagInfo)
    for way_id, nodes in route_ways.items():
        bicycle_class = ways_by_id[way_id].tags.get("class:bicycle", "unknown")
        class_distribution[bicycle_class].distance += route_way_distance(nodes)
    return calculate_comfort_index(class_distribution)

class NodeList(BaseModel):
    node_ids: List[int]

@app.post("/tag_distribution")
async def tag_distribution(
    node_list: NodeList
):
    node_ids = node_list.node_ids
    route_ways, ways_by_id = retrieve_route_ways(node_ids)

    interesting_tags = ["class:bicycle", "lit", "surface"]
    tag_distribution: dict[str, dict[str, TagInfo]] = defaultdict(lambda: defaultdict(TagInfo))
    for way_id, nodes in route_ways.items():
        way = ways_by_id[way_id]
        geometry = LineStringGeometry(list(map(lambda node: node.coord, nodes)))
        way_distance = route_way_distance(nodes)
        for tag in interesting_tags:
            way_tag_value = way.tags.get(tag, "unknown")
            tag_info = tag_distribution[tag][way_tag_value]
            tag_info.ways[way_id] = WayInfo(way.tags.get("name", ""), geometry)
            tag_info.distance += way_distance

    return {
        "ok": True,
        "tag_distribution": tag_distribution,
        "comfort": calculate_comfort_index(tag_distribution["class:bicycle"]),
    }


@app.get("/route")
async def route(
    start_lat: float, start_lon: float, target_lat: float, target_lon: float
):
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

    return {
        "ok": True,
        "route": {
            "annotation": osrm_response["routes"][0]["legs"][0]["annotation"],
            "steps": osrm_response["routes"][0]["legs"][0]["steps"],
            "geometry": osrm_response["routes"][0]["geometry"],
            "duration": osrm_response["routes"][0]["duration"],
            "distance": osrm_response["routes"][0]["distance"],
        },
    }
