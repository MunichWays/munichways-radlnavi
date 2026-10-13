"""Attach real walking paths only at the outer endpoints of an OSRM route."""

from copy import deepcopy
from dataclasses import replace
from itertools import product
from math import isfinite

from src.endpoint_access import AccessGraph, MAX_ACCESS_METERS, bearing, meters


MAX_ROUTE_QUERIES = 6
JOIN_TOLERANCE_METERS = 0.75


def encode_geometry(points, format):
    if format == "geojson":
        return {"type": "LineString", "coordinates": [list(p) for p in points]}
    factor = 1_000_000 if format == "polyline6" else 100_000
    previous = [0, 0]
    result = []
    for lon, lat in points:
        for axis, value in enumerate((lat, lon)):
            rounded = int(round(value * factor))
            delta = rounded - previous[axis]
            previous[axis] = rounded
            encoded = ~(delta << 1) if delta < 0 else delta << 1
            while encoded >= 32:
                result.append(chr(((encoded & 31) | 32) + 63))
                encoded >>= 5
            result.append(chr(encoded + 63))
    return "".join(result)


def coordinates(text):
    try:
        points = [tuple(map(float, p.split(","))) for p in text.split(";")]
        if len(points) < 2 or any(len(p) != 2 or not all(map(isfinite, p)) or
            not (-180 <= p[0] <= 180 and -85 <= p[1] <= 85) for p in points):
            return None
        return points
    except (ValueError, TypeError):
        return None


def waypoint(connection, requested, *, last=False):
    point = connection.coordinates[-1 if last else 0]
    return {"location": list(point), "distance": meters(requested, point),
            "name": connection.edges[-1 if last else 0].name}


def walking_leg(connection, variant):
    weight_factor = 1 if variant == "direct" else 1 / 0.55
    steps = []
    first = 0
    groups = []
    for index, edge in enumerate(connection.edges):
        if index == len(connection.edges) - 1 or (
            edge.name, edge.speed) != (connection.edges[index + 1].name, connection.edges[index + 1].speed):
            groups.append((first, index + 1))
            first = index + 1
    for first, last in groups:
        edge = connection.edges[first]
        geometry = connection.coordinates[first:last + 1]
        start, end = geometry[0], geometry[-1]
        heading = bearing(start, end)
        length = sum(e.distance for e in connection.edges[first:last])
        seconds = sum(e.distance / (e.speed / 3.6) for e in connection.edges[first:last])
        steps.append({"name": edge.name, "mode": "pushing bike",
            "driving_side": "right", "distance": length, "duration": seconds,
            "weight": seconds * weight_factor,
            "geometry": encode_geometry(geometry, "geojson"),
            "maneuver": {"type": "depart" if not first else "continue",
                         "modifier": "straight", "location": list(start),
                         "bearing_before": bearing(*connection.coordinates[first - 1:first + 1]) if first else 0,
                         "bearing_after": heading},
            "intersections": [{"location": list(start), "bearings": [heading],
                               "entry": [True], "out": 0}]})
    final = connection.coordinates[-1]
    steps.append({"name": connection.edges[-1].name, "mode": "pushing bike",
        "driving_side": "right", "distance": 0, "duration": 0, "weight": 0,
        "geometry": encode_geometry((final, final), "geojson"),
        "maneuver": {"type": "arrive", "location": list(final),
                     "bearing_before": bearing(*connection.coordinates[-2:]), "bearing_after": 0},
        "intersections": [{"location": list(final), "bearings": [], "entry": []}]})
    lengths = [e.distance for e in connection.edges]
    seconds = [e.distance / (e.speed / 3.6) for e in connection.edges]
    return {"distance": connection.distance, "duration": connection.duration,
            "weight": connection.duration * weight_factor, "summary": "", "steps": steps,
            "annotation": {"nodes": list(connection.nodes), "distance": lengths,
                "duration": seconds, "weight": [s * weight_factor for s in seconds],
                "speed": [e.speed / 3.6 for e in connection.edges],
                "datasources": [0] * len(lengths)}}


def trim_zero_edge(leg, *, first):
    annotation = leg["annotation"]
    distances = annotation["distance"]
    index = 0 if first else -1
    if not distances or distances[index] > 0.05:
        return False
    annotation["nodes"].pop(index)
    for key, values in annotation.items():
        if key != "nodes" and isinstance(values, list):
            values.pop(index)
    return True


def join_legs(a, b):
    """Keep the public leg/waypoint count and real adjacent annotation nodes."""
    left, right = a["annotation"], b["annotation"]
    while left["nodes"][-1] != right["nodes"][0]:
        if trim_zero_edge(a, first=False) or trim_zero_edge(b, first=True):
            continue
        raise ValueError("Walking and cycling annotations do not meet")
    annotation = {"nodes": left["nodes"] + right["nodes"][1:]}
    for key in ("distance", "duration", "weight", "speed", "datasources"):
        annotation[key] = left[key] + right[key]
    if "metadata" in right:
        annotation["metadata"] = right["metadata"]
    elif "metadata" in left:
        annotation["metadata"] = left["metadata"]
    steps = a["steps"][:-1] + b["steps"]
    transition = steps[len(a["steps"]) - 1]
    transition["maneuver"]["type"] = "notification"
    transition["maneuver"]["modifier"] = "straight"
    return {"distance": a["distance"] + b["distance"],
            "duration": a["duration"] + b["duration"],
            "weight": a["weight"] + b["weight"],
            "summary": b.get("summary") or a.get("summary", ""),
            "steps": steps, "annotation": annotation}


def finish(payload, params):
    """Honor response format/options after composing the canonical full route."""
    result = deepcopy(payload)
    format = params.get("geometries", "polyline")
    keep = {v.strip() for v in params.get("annotations", "false").split(",")}
    for route in result["routes"]:
        if params.get("overview") == "false":
            route.pop("geometry", None)
        else:
            points = route["geometry"]["coordinates"]
            distinct = [p for i, p in enumerate(points) if not i or p != points[i - 1]]
            route["geometry"] = encode_geometry(distinct if len(distinct) > 1 else points, format)
        for leg in route["legs"]:
            if params.get("steps", "false") == "false":
                leg.pop("steps", None)
            else:
                for step in leg["steps"]:
                    step["geometry"] = encode_geometry(step["geometry"]["coordinates"], format)
            if keep == {"false"}:
                leg.pop("annotation", None)
            elif keep != {"true"}:
                leg["annotation"] = {key: value for key, value in leg["annotation"].items()
                    if key in keep or (key == "metadata" and "datasources" in keep)}
    if params.get("skip_waypoints") == "true":
        result.pop("waypoints", None)
    return result


def endpoint_route(db, profile, text, query, original, fetch, variant):
    """Return an augmented payload, or None for unchanged ordinary bike routes.

The bicycle graph and its cost model are always used unchanged between the
chosen walking exits. Intermediate waypoints stay in that same bicycle route.
"""
    points = coordinates(text)
    params = dict(query)
    if db is None or profile != "bike" or points is None:
        return None
    # Subset waypoint output/explicit snapping hints are advanced caller-selected
    # snaps. Forward those unchanged instead of silently overriding their intent.
    if params.get("waypoints") or params.get("hints", "").replace(";", ""):
        return None
    if original.get("code") not in {"Ok", "NoRoute", "NoSegment"}:
        return None
    graphs, options, changed = [], [], []
    for side, point in enumerate((points[0], points[-1])):
        graph = AccessGraph(db, point, 21)
        nearest = graph.nearest(point)
        # Classify from the map, not from optional upstream steps/waypoints.
        # This also works for steps=false and for a point already snapped to
        # an ordinary pushing edge whose terminal cost still needs separating.
        affected = (nearest is not None and
            nearest[0] + JOIN_TOLERANCE_METERS < graph.cycling_gap(point))
        radius = params.get("radiuses", "").split(";")
        if affected and radius != [""]:
            try:
                requested = radius[0 if not side else -1]
                affected = requested == "unlimited" or nearest[0] <= float(requested)
            except ValueError:
                return None
        if affected:
            graph = AccessGraph(db, point, MAX_ACCESS_METERS + 1)
            candidates = graph.connections(point, incoming=bool(side))
        else:
            candidates = [None]
        graphs.append(graph)
        options.append(candidates)
        changed.append(affected)
    if not any(changed):
        return None
    choices = []
    # A wholly walked journey is meaningful only when both original endpoints
    # belong to the same bounded pedestrian network; never extend this through
    # the bicycle graph or across intermediate stops.
    if all(changed) and len(points) == 2:
        connection = graphs[0].walking_route(points[0], points[-1])
        if connection:
            leg = walking_leg(connection, variant)
            payload = {"code": "Ok", "waypoints": [waypoint(connection, points[0]),
                waypoint(connection, points[-1], last=True)], "routes": [{
                    "weight_name": "fast_cycling" if variant == "direct" else "cyclability",
                    "distance": leg["distance"], "duration": leg["duration"], "weight": leg["weight"],
                    "legs": [leg], "geometry": encode_geometry(connection.coordinates, "geojson")}]}
            choices.append(payload)
    def estimate(pair):
        start, end = pair
        a = start.coordinates[-1] if start else points[0]
        b = end.coordinates[0] if end else points[-1]
        core = [a] + points[1:-1] + [b]
        return ((start.duration if start else 0) + (end.duration if end else 0)
                + sum(meters(x, y) for x, y in zip(core, core[1:])) / (20 / 3.6))
    pairs = sorted(product(*options), key=estimate)[:MAX_ROUTE_QUERIES]
    for start, end in pairs:
        core_points = list(points)
        if start:
            core_points[0] = start.coordinates[-1]
        if end:
            core_points[-1] = end.coordinates[0]
        core_params = dict(params)
        core_params.update(geometries="geojson", overview="full", steps="true",
                           annotations="true", alternatives="false", skip_waypoints="false")
        for key in ("bearings", "approaches", "radiuses"):
            values = params.get(key, "").split(";") if key in params else [""] * len(points)
            if len(values) != len(points):
                return None
            for index, connection in ((0, start), (-1, end)):
                if connection:
                    values[index] = "0.75" if key == "radiuses" else "unrestricted" if key == "approaches" else ""
            if key == "radiuses":
                values = [v or "unlimited" for v in values]
            if key in params or key == "radiuses":
                core_params[key] = ";".join(values)
        core_text = ";".join(f"{p[0]},{p[1]}" for p in core_points)
        response = fetch(core_text, list(core_params.items()))
        if response.status_code != 200:
            continue
        payload = deepcopy(response.json())
        if payload.get("code") != "Ok" or not payload.get("routes"):
            continue
        route = payload["routes"][0]
        if len(route.get("legs", [])) != len(points) - 1 or len(payload.get("waypoints", [])) != len(points):
            continue
        geometry = route["geometry"]["coordinates"]
        steps = [s for leg in route["legs"] for s in leg["steps"] if s.get("distance", 0) > 0]
        if (start and meters(start.coordinates[-1], geometry[0]) > JOIN_TOLERANCE_METERS or
            end and meters(end.coordinates[0], geometry[-1]) > JOIN_TOLERANCE_METERS or
            start and steps and steps[0]["mode"] != "cycling" or
            end and steps and steps[-1]["mode"] != "cycling"):
            continue
        try:
            if start:
                # OSRM rounds coordinates to six decimals. Use its exact join
                # coordinate in BOTH step and overview geometry, so clients can
                # match mode sections without nearest-point guesses.
                start = replace(start, coordinates=start.coordinates[:-1] + (tuple(geometry[0]),))
                leg = walking_leg(start, variant)
                route["legs"][0] = join_legs(leg, route["legs"][0])
                geometry = [list(p) for p in start.coordinates[:-1]] + geometry
                payload["waypoints"][0] = waypoint(start, points[0])
            if end:
                end = replace(end, coordinates=(tuple(geometry[-1]),) + end.coordinates[1:])
                leg = walking_leg(end, variant)
                # Cycling -> pushing retains the shared mode-change search cost.
                leg["weight"] += 30
                leg["steps"][0]["weight"] += 30
                route["legs"][-1] = join_legs(route["legs"][-1], leg)
                geometry = geometry + [list(p) for p in end.coordinates[1:]]
                payload["waypoints"][-1] = waypoint(end, points[-1], last=True)
        except (KeyError, ValueError, IndexError):
            continue  # Never fabricate an annotation edge across mismatched maps.
        for key in ("distance", "duration", "weight"):
            route[key] = sum(leg[key] for leg in route["legs"])
        route["geometry"] = {"type": "LineString", "coordinates": geometry}
        choices.append(payload)
    if not choices:
        return None
    selected = min(choices, key=lambda p:p["routes"][0]["weight"])
    return finish(selected, params)
