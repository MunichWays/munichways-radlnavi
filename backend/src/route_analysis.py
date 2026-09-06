"""Occurrence-based analysis of an already calculated route.

Only lookup IDs are deduplicated. Route edges, including return journeys and
leg boundaries, retain their order. No routing or global mutable cache lives here.
"""

from collections import defaultdict
from dataclasses import dataclass

from geopy import distance
from pydantic import BaseModel, model_validator


INTERESTING_TAGS = ("class:bicycle", "lit", "surface")
ANALYSIS_VERSION = "segments-v2"


class AnalysisLeg(BaseModel):
    """OSRM annotation arrays plus optional snapped endpoints, in lon/lat order.

    OSRM 26.6.5 includes the bounding OSM nodes of the first/last partial
    edge. Its distance array describes the traversed portions of those edges.
    Each leg must be passed separately, including legs on the same OSM edge.
    """

    nodes: list[int]
    distance: list[float] | None = None
    start: tuple[float, float] | None = None
    end: tuple[float, float] | None = None

    @model_validator(mode="after")
    def validate_context(self):
        from math import isfinite

        if self.distance is not None:
            if len(self.distance) != max(0, len(self.nodes) - 1):
                raise ValueError("Expected one distance per adjacent node pair")
            if any(not isfinite(value) or value < 0 for value in self.distance):
                raise ValueError("Distances must be finite and nonnegative")
        if (self.start is None) != (self.end is None):
            raise ValueError("Provide both snapped endpoints or neither")
        for point in (self.start, self.end):
            if point is not None:
                lon, lat = point
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ValueError("Invalid snapped endpoint")
        return self


@dataclass(frozen=True)
class EdgeCandidate:
    way_id: int
    edge_index: int
    forward: bool


@dataclass
class RouteSegment:
    leg_index: int
    segment_index: int
    node_a: int
    node_b: int
    distance: float | None
    coordinates: list[tuple[float, float]] | None
    way_id: int | None
    tags: dict[str, str]
    status: str


def edge_index(ways):
    """Index actual adjacent occurrences, including a closed way's last edge."""
    result = defaultdict(list)
    for way in ways.values():
        for index, (a, b) in enumerate(zip(way.nodes, way.nodes[1:])):
            result[a, b].append(EdgeCandidate(way.id, index, True))
            if a != b:
                result[b, a].append(EdgeCandidate(way.id, index, False))
    return result


def route_segments(legs, nodes, ways):
    by_pair = edge_index(ways)
    # Resolve each pair once, but retain every traversal in the output. Multiple
    # occurrences in ONE way have the same tags; different ways are ambiguous.
    resolved = {}
    lengths = {}
    geodesic = None
    segments = []
    for leg_index, leg in enumerate(legs):
        for index, (a, b) in enumerate(zip(leg.nodes, leg.nodes[1:])):
            node_a, node_b = nodes.get(a), nodes.get(b)
            if (a, b) not in resolved:
                candidates = {entry.way_id for entry in by_pair.get((a, b), ())}
                way_id = next(iter(candidates)) if len(candidates) == 1 else None
                status = (
                    "matched"
                    if way_id is not None
                    else ("ambiguous" if candidates else "unmatched")
                )
                resolved[a, b] = way_id, status
            way_id, status = resolved[a, b]
            if node_a is None or node_b is None:
                way_id, status = None, "missing_node"
            start = (
                leg.start
                if index == 0 and leg.start is not None
                else (node_a.coord if node_a is not None else None)
            )
            end = (
                leg.end
                if index == len(leg.nodes) - 2 and leg.end is not None
                else (node_b.coord if node_b is not None else None)
            )
            coordinates = (
                [start, end] if start is not None and end is not None else None
            )
            if (
                leg.distance is not None
                and leg.start is None
                and index in (0, len(leg.nodes) - 2)
            ):
                # The bounding OSM node can be beyond the snapped endpoint.
                # Its full edge must not appear as a traversed partial edge.
                coordinates = None
            if leg.distance is not None:
                meters = leg.distance[index]
            elif coordinates is not None:
                key = tuple(sorted(coordinates))
                if key not in lengths:
                    if geodesic is None:
                        geodesic = distance.geodesic()
                    # Reuse GeographicLib's WGS84 coefficients within this
                    # request. measure() returns kilometres, just like the
                    # original geopy distance calculation, without rebuilding
                    # the ellipsoid for every edge.
                    lengths[key] = geodesic.measure(start[::-1], end[::-1]) * 1000
                meters = lengths[key]
            else:
                meters = None
            segments.append(
                RouteSegment(
                    leg_index,
                    index,
                    a,
                    b,
                    meters,
                    coordinates,
                    way_id,
                    ways[way_id].tags if way_id is not None else {},
                    status,
                )
            )
    return segments


def analysis_metadata(legs, segments):
    bases = {"osrm" if leg.distance is not None else "node_geometry" for leg in legs}
    return {
        "version": ANALYSIS_VERSION,
        "distanceBasis": next(iter(bases)) if len(bases) == 1 else "mixed",
        "distanceComplete": all(segment.distance is not None for segment in segments),
        "totalDistance": sum(segment.distance or 0 for segment in segments),
        "unresolvedSegments": sum(segment.status != "matched" for segment in segments),
        "ambiguousSegments": sum(segment.status == "ambiguous" for segment in segments),
        "missingNodeSegments": sum(
            segment.status == "missing_node" for segment in segments
        ),
    }
