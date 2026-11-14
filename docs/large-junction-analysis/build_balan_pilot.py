"""Rebuild the draft review data and inline map from frozen OSM/API evidence.

This is an offline analysis utility, not production guidance code.
Coordinates are longitude/latitude; distances use a local metric projection.
"""

import gzip
import json
from math import cos, hypot, radians
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LON0, LAT0 = 11.60407, 48.10856
MX, MY = 111320 * cos(radians(LAT0)), 111320
CROSSINGS = {52792925, 138347215, 147718922, 380171576}
ROUTES = ("balan-chiemgau-left", "balan-chiemgau-straight")


def project(p):
    return ((p[0] - LON0) * MX, (p[1] - LAT0) * MY)


def interpolate(a, b, fraction):
    return [round(a[i] + (b[i] - a[i]) * fraction, 9) for i in (0, 1)]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def intersection(a, b, c, d):
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    delta = (c[0] - a[0], c[1] - a[1])
    denominator = cross(r, s)
    if abs(denominator) < 1e-18:
        return None
    t, u = cross(delta, s) / denominator, cross(delta, r) / denominator
    return t if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9 else None


def inside(point, ring):
    x, y = point
    result = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            result = not result
    return result


def visits(coordinates, ring, projection=project):
    hits, distance = [], 0.0
    for index, (a, b) in enumerate(zip(coordinates, coordinates[1:])):
        pa, pb = projection(a), projection(b)
        length = hypot(pb[0] - pa[0], pb[1] - pa[1])
        fractions = sorted({
            round(t, 10) for c, d in zip(ring, ring[1:])
            if (t := intersection(a, b, c, d)) is not None
        })
        for t in fractions:
            if any(abs(distance + t * length - hit["distanceAlongRouteMeters"]) < 0.01 for hit in hits):
                continue
            hits.append({
                "kind": "exit" if inside([a[i] + (b[i] - a[i]) * (t - 1e-5) for i in (0, 1)], ring) else "entry",
                "location": interpolate(a, b, t),
                "segmentIndex": index,
                "segmentFraction": round(t, 8),
                "distanceAlongRouteMeters": distance + t * length,
            })
        distance += length
    return hits


def main():
    feature_collection = json.loads((ROOT / "balan-chiemgau-draft.geojson").read_text(encoding="utf-8"))
    polygon = feature_collection["features"][0]
    ring = polygon["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    for i, (a, b) in enumerate(zip(ring, ring[1:])):
        for j, (c, d) in enumerate(zip(ring, ring[1:])):
            if j <= i + 1 or (i == 0 and j == len(ring) - 2):
                continue
            assert intersection(a, b, c, d) is None, "Draft polygon self-intersects"
    assert sum(cross(project(a), project(b)) for a, b in zip(ring, ring[1:])) > 0, "GeoJSON exterior must be counterclockwise"
    area = abs(sum(cross(project(a), project(b)) for a, b in zip(ring, ring[1:]))) / 2
    osm = json.loads(gzip.decompress((ROOT / "junction-detail.json.gz").read_bytes()))["response"]
    ways, markers, gates = [], [], []
    for element in osm["elements"]:
        tags = element.get("tags", {})
        if element["type"] == "node":
            markers.append({"id": element["id"], "location": [element["lon"], element["lat"]], "kind": tags.get("highway")})
            continue
        coordinates = [[p["lon"], p["lat"]] for p in element.get("geometry", [])]
        if len(coordinates) < 2:
            continue
        properties = {k: v for k, v in tags.items() if k in ("highway", "name", "bicycle", "oneway", "footway", "cycleway", "access", "lanes", "area")}
        properties.update({"id": element["id"], "crossing": element["id"] in CROSSINGS})
        ways.append({"type": "Feature", "properties": properties, "geometry": {"type": "LineString", "coordinates": coordinates}})
        if element["id"] in CROSSINGS:
            assert all(inside(p, ring) for p in coordinates), f"Crossing {element['id']} extends outside draft"
        if tags.get("highway") in ("path", "cycleway") and tags.get("bicycle") in ("yes", "designated"):
            for hit in visits(coordinates, ring):
                hit.update({"osmWayId": element["id"], "directionBasis": "OSM way order; oneway=yes" if tags.get("oneway") == "yes" else "not direction-validated"})
                gates.append(hit)
    gates.sort(key=lambda hit: (hit["location"][1], hit["location"][0]))
    for index, gate in enumerate(gates, 1):
        gate["id"] = f"G{index}"
        x, y = project(gate["location"])
        gate["arm"] = ("east" if x > 0 else "west") if abs(x) > abs(y) else ("north" if y > 0 else "south")
    assert {(gate["arm"], gate["kind"]) for gate in gates} == {
        (arm, kind) for arm in ("north", "east", "south", "west") for kind in ("entry", "exit")
    }
    assert len(gates) == 8, f"Expected eight cycling path boundary crossings, got {len(gates)}"

    routes = []
    for name in ROUTES:
        payload = json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))["response"]
        route = payload["routes"][0]
        coordinates = route["geometry"]["coordinates"]
        hits = visits(coordinates, ring)
        assert [hit["kind"] for hit in hits] == ["entry", "exit"]
        maneuvers, at = [], 0.0
        for step in route["legs"][0]["steps"]:
            maneuver = step["maneuver"]
            if maneuver["type"] not in ("depart", "arrive"):
                assert inside(maneuver["location"], ring), f"Maneuver outside draft: {maneuver}"
                maneuvers.append({"location": maneuver["location"], "type": maneuver["type"], "modifier": maneuver.get("modifier"), "at": at})
            at += step["distance"]
        for hit in hits:
            gate = min(gates, key=lambda gate: hypot(*[a - b for a, b in zip(project(gate["location"]), project(hit["location"]))]))
            assert hypot(*[a - b for a, b in zip(project(gate["location"]), project(hit["location"]))]) < 0.5
            hit["gateId"] = gate["id"]
            hit["distanceAlongRouteMeters"] = round(hit["distanceAlongRouteMeters"], 2)
        routes.append({"id": name, "label": "Links abbiegen" if name.endswith("left") else "Geradeaus", "geometry": route["geometry"], "boundaryCrossings": hits, "maneuvers": maneuvers})

    data = {
        "polygon": polygon, "osm": {"type": "FeatureCollection", "features": ways},
        "markers": markers, "gates": gates, "routes": routes,
        "areaSquareMetersApprox": round(area),
        "osmTimestamp": osm["osm3s"]["timestamp_osm_base"],
        "closeBounds": [[11.60320, 48.10798], [11.60497, 48.10901]],
        "routeBounds": [[11.60315, 48.10748], [11.60620, 48.10953]],
    }
    (ROOT / "balan-chiemgau-review.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_features = [polygon]
    for route in routes:
        left = route["id"].endswith("left")
        review_features.append({
            "type": "Feature", "geometry": route["geometry"],
            "properties": {"name": route["label"], "kind": "example_route", "stroke": "#1565c0" if left else "#ef6c00", "stroke-width": 4, "status": "draft_review"},
        })
    for gate in gates:
        review_features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": gate["location"]},
            "properties": {"name": gate["id"], "kind": gate["kind"], "arm": gate["arm"], "osmWayId": gate["osmWayId"], "status": "draft", "marker-color": "#7b1fa2"},
        })
    review_features.extend(feature for feature in ways if feature["properties"]["crossing"])
    (ROOT / "balan-chiemgau-review.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": review_features}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    template = (ROOT / "balan-chiemgau-map.template.html").read_text(encoding="utf-8")
    assert template.count("__PILOT_DATA__") == 1
    rendered = template.replace("__PILOT_DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))
    (ROOT / "balan-chiemgau-map.html").write_text(rendered, encoding="utf-8")
    print(json.dumps({"area_m2_approx": round(area), "gates": gates, "routes": [{"id": r["id"], "boundaryCrossings": r["boundaryCrossings"]} for r in routes]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
