"""Opt-in metadata for one reviewed route corridor, never a routing change.

The pilot deliberately rejects other paths through the same polygon, incomplete
visits and repeated visits within a leg. No client may infer approval from the
polygon alone. Non-GeoJSON or simplified responses are left unchanged.
"""

from copy import deepcopy
from functools import lru_cache
import json
from math import asin, ceil, cos, hypot, isfinite, radians, sin, sqrt
from pathlib import Path


@lru_cache(maxsize=1)
def pilot():
    return json.loads(Path(__file__).with_name("big_junctions.json").read_text(encoding="utf-8"))


def points(geometry):
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise ValueError("Full GeoJSON required")
    result = []
    for p in geometry["coordinates"]:
        if len(p) != 2 or not all(isinstance(v, (int, float)) and isfinite(v) for v in p):
            raise ValueError("Invalid coordinate")
        if not (-180 <= p[0] <= 180 and -85 <= p[1] <= 85):
            raise ValueError("Invalid coordinate")
        if not result or p != result[-1]:
            result.append(list(p))
    return result


def meters(a, b):
    lat1, lat2 = radians(a[1]), radians(b[1])
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin(radians(b[0] - a[0]) / 2) ** 2
    return 6371008.8 * 2 * asin(min(1, sqrt(h)))


def inside(p, ring):
    x, y = p
    value = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            value = not value
    return value


def interpolate(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in (0, 1)]


def point_at(line, target):
    for a, b in zip(line, line[1:]):
        length = meters(a, b)
        if target <= length and length:
            return interpolate(a, b, target / length)
        target -= length
    return line[-1]


def aligned(a, b, reference):
    mx = cos(radians(a[1]))
    x, y = (b[0] - a[0]) * mx, b[1] - a[1]
    rx = (reference[-1][0] - reference[0][0]) * mx
    ry = reference[-1][1] - reference[0][1]
    scale = hypot(x, y) * hypot(rx, ry)
    return scale > 0 and (x * rx + y * ry) / scale >= cos(radians(30))


def crossings(line, ring):
    hits, distance = [], 0.0
    for index, (a, b) in enumerate(zip(line, line[1:])):
        length = meters(a, b)
        for c, d in zip(ring, ring[1:]):
            rx, ry, sx, sy = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
            denominator = rx * sy - ry * sx
            if abs(denominator) < 1e-18:
                continue
            dx, dy = c[0] - a[0], c[1] - a[1]
            t, u = (dx * sy - dy * sx) / denominator, (dx * ry - dy * rx) / denominator
            if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
                hits.append({"location": interpolate(a, b, t), "geometrySegmentIndex": index,
                    "segmentFraction": t, "distanceAlongLegMeters": distance + length * t})
        distance += length
    ordered = []
    for hit in sorted(hits, key=lambda h: h["distanceAlongLegMeters"]):
        if not ordered or hit["distanceAlongLegMeters"] - ordered[-1]["distanceAlongLegMeters"] > 0.05:
            ordered.append(hit)
    return ordered


def dense(line):
    for a, b in zip(line, line[1:]):
        count = max(1, ceil(meters(a, b) / 2))
        if count > 1000:
            raise ValueError("Unexpected pilot segment length")
        for i in range(count):
            yield interpolate(a, b, i / count)
    yield line[-1]


def corridor_matches(line, reference, tolerance):
    # Local metric projection for a roughly 100 m corridor, not route distance.
    origin = reference[0]
    mx = 111320 * cos(radians(origin[1]))
    def xy(p):
        return ((p[0] - origin[0]) * mx, (p[1] - origin[1]) * 111320)
    def station(p, path):
        x, y = xy(p)
        best, along, at = float("inf"), 0.0, 0.0
        for a, b in zip(path, path[1:]):
            ax, ay = xy(a)
            bx, by = xy(b)
            dx, dy = bx - ax, by - ay
            length = hypot(dx, dy)
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (length * length))) if length else 0
            gap = hypot(x - ax - t * dx, y - ay - t * dy)
            if gap < best:
                best, at = gap, along + t * length
            along += length
        return best, at
    progress = 0.0
    for point in dense(line):
        gap, at = station(point, reference)
        if gap > tolerance or at < progress - 1:
            return False
        progress = max(progress, at)
    return all(station(point, line)[0] <= tolerance for point in dense(reference))


def match_leg(leg, config):
    steps = leg.get("steps", [])
    if not steps or any(step.get("mode") != "cycling" for step in steps):
        return None
    line, step_locations = [], []
    for step in steps:
        part = points(step.get("geometry"))
        if not part or (line and line[-1] != part[0]):
            return None
        maneuver = step.get("maneuver", {})
        if maneuver.get("location") != part[0]:
            return None
        step_locations.append(part[0])
        line.extend(part if not line else part[1:])
    ring = config["polygon"]["coordinates"][0]
    if len(line) < 2 or inside(line[0], ring) or inside(line[-1], ring):
        return None
    hits = crossings(line, ring)
    if len(hits) != 2:
        return None
    entry, exit = hits
    if meters(entry["location"], config["entry"]) > 2.5 or meters(exit["location"], config["exit"]) > 2.5:
        return None
    total = sum(meters(a, b) for a, b in zip(line, line[1:]))
    if entry["distanceAlongLegMeters"] < 10 or total - exit["distanceAlongLegMeters"] < 10:
        return None
    if (not aligned(point_at(line, entry["distanceAlongLegMeters"] - 10), entry["location"], config["approach"])
        or not aligned(exit["location"], point_at(line, exit["distanceAlongLegMeters"] + 10), config["departure"])):
        return None
    start, end = entry["geometrySegmentIndex"], exit["geometrySegmentIndex"]
    traversed = [entry["location"], *line[start + 1:end + 1], exit["location"]]
    if not corridor_matches(traversed, config["corridor"], 2.5):
        return None
    contained = [i for i, location in enumerate(step_locations)
        if inside(location, ring) and steps[i]["maneuver"].get("type") not in ("depart", "arrive")]
    if not contained:
        return None
    return line, entry, exit, contained


def add_guidance(payload):
    """Return an enriched copy, or None; the caller retains the raw response."""
    if payload.get("code") != "Ok":
        return None
    config = pilot()
    result = None
    for route_index, route in enumerate(payload.get("routes", [])):
        try:
            whole = points(route.get("geometry"))
            # Metadata indices must address the unchanged response geometry.
            if len(whole) != len(route["geometry"]["coordinates"]):
                continue
            legs = route.get("legs", [])
            matches, reconstructed, offset, distance = [], [], 0, 0.0
            for leg_index, leg in enumerate(legs):
                # Build all leg geometries to establish unambiguous route indices.
                line = []
                for step in leg.get("steps", []):
                    part = points(step.get("geometry"))
                    if not part or (line and line[-1] != part[0]):
                        raise ValueError("Discontinuous leg")
                    line.extend(part if not line else part[1:])
                if not line or (reconstructed and reconstructed[-1] != line[0]):
                    raise ValueError("Discontinuous route")
                match = match_leg(leg, config)
                if match:
                    _, entry, exit, contained = match
                    for hit in (entry, exit):
                        hit["geometrySegmentIndex"] += offset
                        hit["distanceAlongRouteMeters"] = distance + hit["distanceAlongLegMeters"]
                    matches.append({"id": config["id"], "occurrenceId": f"{config['id']}:leg:{leg_index}",
                        "legIndex": leg_index, "movement": "left", "entryArm": "west", "exitArm": "north",
                        "entry": entry, "exit": exit, "polygon": deepcopy(config["polygon"]),
                        "suppressedStepIndices": contained})
                reconstructed.extend(line if not reconstructed else line[1:])
                offset += len(line) - 1
                distance += sum(meters(a, b) for a, b in zip(line, line[1:]))
            if reconstructed != whole or not matches:
                continue
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            continue
        if result is None:
            result = deepcopy(payload)
        result["routes"][route_index]["guidance"] = {"version": "big-junctions-v1",
            "catalogVersion": config["version"], "junctions": matches}
    return result
