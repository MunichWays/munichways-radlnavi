"""Offline geometry-only pilot: Arnulfstrasse west to Steubenplatz north.

No routing/app changes or live API calls. The draft stays disabled.
"""

import json
from math import cos, hypot, radians
from pathlib import Path

from build_balan_pilot import inside, intersection, visits


ROOT = Path(__file__).resolve().parent
MX, MY = 111320 * cos(radians(48.15010)), 111320
CROSSINGS = {35218338, 35218359, 61048819, 379393437}


def project(point):
    return ((point[0] - 11.52030) * MX, (point[1] - 48.15010) * MY)


def main():
    polygon = json.loads((ROOT / "arnulf-steuben-draft.geojson").read_text(encoding="utf-8"))["features"][0]
    ring = polygon["geometry"]["coordinates"][0]
    assert polygon["properties"]["enabled"] is False
    assert ring[0] == ring[-1]
    for i, (a, b) in enumerate(zip(ring, ring[1:])):
        for j, (c, d) in enumerate(zip(ring, ring[1:])):
            if j > i + 1 and not (i == 0 and j == len(ring) - 2):
                assert intersection(a, b, c, d) is None, "Self-intersecting polygon"
    signed_area = sum(project(a)[0] * project(b)[1] - project(a)[1] * project(b)[0] for a, b in zip(ring, ring[1:])) / 2
    assert signed_area > 0, "Expected counterclockwise GeoJSON exterior"
    source = json.loads((ROOT / "arnulf-steuben-left.json").read_text(encoding="utf-8"))
    route = source["response"]["routes"][0]
    hits = visits(route["geometry"]["coordinates"], ring, projection=project)
    assert [hit["kind"] for hit in hits] == ["entry", "exit"]
    assert not inside(route["geometry"]["coordinates"][0], ring)
    assert not inside(route["geometry"]["coordinates"][-1], ring)
    features = [polygon, {"type": "Feature", "geometry": route["geometry"], "properties": {"name": "Pilot: links nach Steubenplatz", "stroke": "#1565c0", "stroke-width": 4}}]
    for hit in hits:
        hit["distanceAlongRouteMeters"] = round(hit["distanceAlongRouteMeters"], 2)
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": hit["location"]}, "properties": {"name": "Einfahrt West" if hit["kind"] == "entry" else "Ausfahrt Nord", **{k: v for k, v in hit.items() if k != "location"}}})
    at, maneuvers = 0.0, []
    for step in route["legs"][0]["steps"]:
        maneuver = step["maneuver"]
        if maneuver["type"] not in ("depart", "arrive"):
            assert inside(maneuver["location"], ring), "Internal maneuver outside polygon"
            maneuvers.append({"type": maneuver["type"], "modifier": maneuver.get("modifier"), "distanceFromStartApiMeters": round(at, 1)})
            features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": maneuver["location"]}, "properties": {"name": f"API: {maneuver['type']}/{maneuver.get('modifier')}", "marker-color": "#ef6c00"}})
        at += step["distance"]
    osm = json.loads((ROOT / "osm-examples.json").read_text(encoding="utf-8"))
    found = set()
    for way in osm["elements"]:
        if way["type"] != "way" or way["id"] not in CROSSINGS:
            continue
        coordinates = [[point["lon"], point["lat"]] for point in way["geometry"]]
        assert all(inside(point, ring) for point in coordinates)
        assert not visits(coordinates, ring, projection=project), "Crossing leaves polygon"
        found.add(way["id"])
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coordinates}, "properties": {"name": f"Querungsweg OSM {way['id']}", "stroke": "#777777", "stroke-width": 2}})
    assert found == CROSSINGS
    report = {
        "status": "draft-disabled", "movement": "west-to-north-left",
        "areaSquareMetersApprox": round(signed_area), "boundaryCrossings": hits,
        "insideRouteDistanceMetersApprox": round(hits[1]["distanceAlongRouteMeters"] - hits[0]["distanceAlongRouteMeters"], 1),
        "maneuvers": maneuvers, "crossingWayIds": sorted(found),
        "routeSourceUrl": source["url"], "routeRetrievedAtUtc": source["retrieved_at_utc"],
        "osmTimestamp": osm["osm3s"]["timestamp_osm_base"],
        "limitations": ["No other movement approved", "No 100m advance announcement replay: example starts too close to entry", "No phone, browser or on-site test", "No app/backend pilot behavior implemented"],
    }
    (ROOT / "arnulf-steuben-review.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "arnulf-steuben-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
