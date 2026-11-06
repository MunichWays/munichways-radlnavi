"""Additional metadata for reviewed crossing movements, never a routing change."""

from copy import deepcopy
from functools import lru_cache
import json
from math import asin, atan2, ceil, cos, degrees, hypot, isfinite, radians, sin, sqrt
from pathlib import Path


def validate_catalog(value):
    """Fail closed: an enabled movement requires explicit review and complete data."""
    if value.get("schemaVersion") != 1 or not isinstance(value.get("version"), str) or not value["version"]:
        raise ValueError("Invalid catalog version")
    identifiers = set()
    excluded = {item["id"] for item in value.get("excluded", [])}
    for junction in value["junctions"]:
        identifier = junction["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("Duplicate or invalid junction id")
        identifiers.add(identifier)
        if junction.get("enabled") is not True:
            continue
        if identifier in excluded or junction.get("review", {}).get("status") != "approved":
            raise ValueError("Junction requires review")
        if not junction["review"].get("evidence") or not junction["review"].get("date"):
            raise ValueError("Missing review evidence")
        shape = junction["polygon"]
        if shape.get("type") != "Polygon" or len(shape["coordinates"]) != 1:
            raise ValueError("Simple polygon required")
        ring = points({"type": "LineString", "coordinates": shape["coordinates"][0]})
        if not 4 <= len(ring) <= 64 or ring[0] != ring[-1] or not simple_ring(ring):
            raise ValueError("Invalid polygon ring")
        low = [min(p[i] for p in ring) for i in (0, 1)]
        high = [max(p[i] for p in ring) for i in (0, 1)]
        if meters(low, high) > 300:
            raise ValueError("Crossing polygon too large")
        movement_ids = set()
        for movement in junction["movements"]:
            if not isinstance(movement.get("id"), str) or not movement["id"] or movement["id"] in movement_ids:
                raise ValueError("Duplicate or invalid movement id")
            movement_ids.add(movement["id"])
            if movement.get("enabled") is not True:
                continue
            if movement.get("review", {}).get("status") != "approved" or not movement["review"].get("evidence"):
                raise ValueError("Movement requires review")
            if movement["movement"] not in ("left", "straight"):
                raise ValueError("Unsupported movement")
            if not all(isinstance(movement[k], str) and movement[k] for k in ("entryArm", "exitArm")):
                raise ValueError("Missing arms")
            if movement["entryArm"] == movement["exitArm"]:
                raise ValueError("Identical arms")
            for key in ("corridor", "approach", "departure"):
                path = points({"type": "LineString", "coordinates": movement[key]})
                if len(path) < 2 or path != movement[key]:
                    raise ValueError("Invalid reference path")
            for key in ("entry", "exit"):
                points({"type": "LineString", "coordinates": [movement[key]]})
            mx = cos(radians(movement["entry"][1]))
            def heading(path):
                return atan2(path[-1][1] - path[0][1], (path[-1][0] - path[0][0]) * mx)
            turn = (degrees(heading(movement["departure"]) - heading(movement["approach"])) + 180) % 360 - 180
            if ((movement["movement"] == "straight" and abs(turn) > 30)
                or (movement["movement"] == "left" and not 45 <= turn <= 135)):
                raise ValueError("Movement disagrees with approach/departure directions")
            if (meters(movement["entry"], movement["corridor"][0]) > .5
                or meters(movement["exit"], movement["corridor"][-1]) > .5
                or sum(meters(a, b) for a, b in zip(movement["corridor"], movement["corridor"][1:])) > 600):
                raise ValueError("Invalid corridor anchors or length")
            # The crossing of each approved reference must enter and leave this polygon.
            reference = [movement["approach"][0], *movement["corridor"], movement["departure"][-1]]
            hits = crossings(reference, ring)
            if (len(hits) != 2 or inside(reference[0], ring) or inside(reference[-1], ring)
                or meters(hits[0]["location"], movement["entry"]) > .5
                or meters(hits[1]["location"], movement["exit"]) > .5):
                raise ValueError("Reference does not cross approved gates")
    return value


@lru_cache(maxsize=1)
def catalog():
    return validate_catalog(json.loads(Path(__file__).with_name("big_junctions.json").read_text(encoding="utf-8")))


def approved_movements(value=None):
    value = catalog() if value is None else validate_catalog(value)
    return [dict(m, junctionId=j["id"], polygon=j["polygon"])
            for j in value["junctions"] if j.get("enabled") is True
            for m in j["movements"] if m.get("enabled") is True]


def simple_ring(ring):
    """Reject degenerate/self-intersecting polygons, including nonadjacent touches."""
    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    def on(a, b, c):
        return abs(orientation(a, b, c)) < 1e-16 and all(min(a[i], b[i]) <= c[i] <= max(a[i], b[i]) for i in (0, 1))
    edges = list(zip(ring, ring[1:]))
    if len(set(map(tuple, ring[:-1]))) != len(ring) - 1:
        return False
    if abs(sum((b[0] - a[0]) * (b[1] + a[1]) for a, b in edges)) < 1e-12:
        return False
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            c, d = edges[j]
            if (orientation(a, b, c) * orientation(a, b, d) < 0
                and orientation(c, d, a) * orientation(c, d, b) < 0) or any((on(a, b, c), on(a, b, d), on(c, d, a), on(c, d, b))):
                return False
    return True


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


def leg_geometry(leg):
    steps = leg.get("steps", [])
    if not steps or any(step.get("mode") != "cycling" for step in steps):
        return None
    line, step_locations, step_distances, distance = [], [], [], 0.0
    for step in steps:
        part = points(step.get("geometry"))
        if not part or (line and line[-1] != part[0]):
            return None
        maneuver = step.get("maneuver", {})
        if maneuver.get("location") != part[0]:
            return None
        step_locations.append(part[0])
        step_distances.append(distance)
        distance += sum(meters(a, b) for a, b in zip(part, part[1:]))
        line.extend(part if not line else part[1:])
    return line, step_locations, step_distances


def match_leg(leg, config, geometry=None):
    geometry = leg_geometry(leg) if geometry is None else geometry
    if geometry is None:
        return []
    line, step_locations, step_distances = geometry
    ring = config["polygon"]["coordinates"][0]
    if len(line) < 2 or inside(line[0], ring) or inside(line[-1], ring):
        return []
    # Broad phase only; geometric gate/corridor checks below remain authoritative.
    if any(max(p[i] for p in line) < min(p[i] for p in ring)
        or min(p[i] for p in line) > max(p[i] for p in ring) for i in (0, 1)):
        return []
    hits = crossings(line, ring)
    if len(hits) % 2:
        return []
    total = sum(meters(a, b) for a, b in zip(line, line[1:]))
    matches = []
    for entry, exit in zip(hits[::2], hits[1::2]):
        if meters(entry["location"], config["entry"]) > 2.5 or meters(exit["location"], config["exit"]) > 2.5:
            continue
        if entry["distanceAlongLegMeters"] < 10 or total - exit["distanceAlongLegMeters"] < 10:
            continue
        if (not aligned(point_at(line, entry["distanceAlongLegMeters"] - 10), entry["location"], config["approach"])
            or not aligned(exit["location"], point_at(line, exit["distanceAlongLegMeters"] + 10), config["departure"])):
            continue
        start, end = entry["geometrySegmentIndex"], exit["geometrySegmentIndex"]
        traversed = [entry["location"], *line[start + 1:end + 1], exit["location"]]
        if not corridor_matches(traversed, config["corridor"], 2.5):
            continue
        contained = [i for i, location in enumerate(step_locations)
            if inside(location, ring) and steps_type(leg, i) not in ("depart", "arrive")
            and entry["distanceAlongLegMeters"] <= step_distances[i] <= exit["distanceAlongLegMeters"]]
        if contained:
            matches.append((entry, exit, contained))
    return matches


def steps_type(leg, index):
    return leg["steps"][index]["maneuver"].get("type")


def add_guidance(payload):
    """Return an enriched copy, or None; the caller retains the raw response."""
    if payload.get("code") != "Ok":
        return None
    data = catalog()
    configs = approved_movements()
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
                geometry = leg_geometry(leg)
                if geometry is not None:
                    for config in configs:
                        for visit, (entry, exit, contained) in enumerate(match_leg(leg, config, geometry)):
                            for hit in (entry, exit):
                                hit["geometrySegmentIndex"] += offset
                                hit["distanceAlongRouteMeters"] = distance + hit["distanceAlongLegMeters"]
                            matches.append({"id": config["junctionId"],
                                "occurrenceId": f"{config['junctionId']}:{config['id']}:leg:{leg_index}:visit:{visit}",
                                "legIndex": leg_index, "movement": config["movement"],
                                "entryArm": config["entryArm"], "exitArm": config["exitArm"],
                                "entry": entry, "exit": exit, "polygon": deepcopy(config["polygon"]),
                                "suppressedStepIndices": contained})
                reconstructed.extend(line if not reconstructed else line[1:])
                offset += len(line) - 1
                distance += sum(meters(a, b) for a, b in zip(line, line[1:]))
            matches.sort(key=lambda m: m["entry"]["distanceAlongRouteMeters"])
            # Ambiguous/overlapping matches fall back to ordinary guidance for this route.
            if any(a["exit"]["distanceAlongRouteMeters"] >= b["entry"]["distanceAlongRouteMeters"]
                for a, b in zip(matches, matches[1:])):
                continue
            if reconstructed != whole or not matches:
                continue
        except (ValueError, TypeError, KeyError, IndexError, OverflowError):
            continue
        if result is None:
            result = deepcopy(payload)
        result["routes"][route_index]["guidance"] = {"version": "big-junctions-v1",
            "catalogVersion": data["version"], "junctions": matches}
    return result
