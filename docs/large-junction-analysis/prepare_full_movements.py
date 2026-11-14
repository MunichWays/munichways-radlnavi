"""Collect/check all left/straight routes for the two user-reviewed polygons.

Writes review evidence and a proposed catalog, never edits the runtime catalog.
All network requests are sequential. Coordinates are longitude/latitude.
"""

from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from math import ceil, cos, hypot, radians
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "backend"))
from src.big_junctions import (add_guidance, approved_movements, catalog, crossings,
    inside, meters, point_at, validate_catalog)
from unittest.mock import patch

SITES = {
    "arnulf-steuben": {
        "name": "Arnulfstraße / Steubenplatz",
        "source": "osm-examples.json",
        "gates": {"west": (61048818, 379393436), "north": (193876093, 71055915),
                  "east": (59454508, 61900266), "south": (61738273, 193876091)},
    },
    "balan-chiemgau": {
        "name": "Balanstraße / Chiemgaustraße",
        "source": "junction-detail.json.gz",
        "gates": {"west": (63534658, 63534665), "north": (341311854, 147718914),
                  "east": (52792924, 138347230), "south": (134138908, 138347229)},
    },
}
LEFT = {"west": "north", "north": "east", "east": "south", "south": "west"}
STRAIGHT = {"west": "east", "east": "west", "north": "south", "south": "north"}


def cycling_corridor(line, ways):
    """Independently check the entire inner route against directed cycling ways."""
    origin = line[0]
    mx = 111320 * cos(radians(origin[1]))
    xy = lambda p: ((p[0] - origin[0]) * mx, (p[1] - origin[1]) * 111320)
    segments = []
    for way in ways.values():
        tags = way.get("tags", {})
        if (tags.get("highway") not in ("cycleway", "path", "footway")
            or tags.get("bicycle") not in ("yes", "designated")
            or tags.get("access") in ("no", "private")):
            continue
        points = [[p["lon"], p["lat"]] for p in way.get("geometry", [])]
        direction = tags.get("oneway:bicycle", tags.get("oneway", "no"))
        for a, b in zip(points, points[1:]):
            if direction == "-1":
                a, b = b, a
            segments.append((xy(a), xy(b), direction in ("yes", "1", "-1"), way["id"]))
    used = set()
    for start, end in zip(line, line[1:]):
        a, b = xy(start), xy(end)
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = hypot(dx, dy)
        if length < .5:
            continue
        count = max(1, ceil(length / 2))
        for i in range(count):
            x, y = a[0] + dx * (i + .5) / count, a[1] + dy * (i + .5) / count
            best = None
            for c, d, oneway, identifier in segments:
                rx, ry = d[0] - c[0], d[1] - c[1]
                norm = hypot(rx, ry)
                if not norm:
                    continue
                dot = (dx * rx + dy * ry) / (length * norm)
                if (dot if oneway else abs(dot)) < .85:
                    continue
                t = max(0, min(1, ((x - c[0]) * rx + (y - c[1]) * ry) / (norm * norm)))
                gap = hypot(x - c[0] - t * rx, y - c[1] - t * ry)
                if best is None or gap < best[0]:
                    best = gap, identifier
            assert best is not None and best[0] <= 1.25, "Inner route lacks a matching permitted cycling segment/direction"
            used.add(best[1])
    return sorted(used)


def sample(line, station):
    total = sum(meters(a, b) for a, b in zip(line, line[1:]))
    if 0 <= station <= total:
        return point_at(line, station)
    a, b = (line[0], line[1]) if station < 0 else (line[-2], line[-1])
    fraction = station / meters(a, b) if station < 0 else 1 + (station - total) / meters(a, b)
    return [a[i] + (b[i] - a[i]) * fraction for i in (0, 1)]


def gate(way, polygon, kind, ways, distance=40):
    tags = way["tags"]
    assert tags.get("bicycle") in ("yes", "designated")
    assert tags.get("access") not in ("no", "private")
    assert tags.get("highway") in ("path", "cycleway", "footway")
    line = [[p["lon"], p["lat"]] for p in way["geometry"]]
    hits = crossings(line, polygon["coordinates"][0])
    assert len(hits) == 1
    forward_kind = "exit" if inside(line[0], polygon["coordinates"][0]) else "entry"
    if kind != forward_kind:
        assert tags.get("oneway:bicycle", tags.get("oneway", "no")) == "no"
        line.reverse()
        hits = crossings(line, polygon["coordinates"][0])
    hit = hits[0]
    # Follow the actual permitted continuation instead of extrapolating a short
    # gate way across bends (notably Arnulf's southern exit).
    if kind == "exit":
        used = {way["id"]}
        while sum(meters(a, b) for a, b in zip(line, line[1:])) < hit["distanceAlongLegMeters"] + distance:
            continuations = []
            for other in ways.values():
                t = other.get("tags", {})
                if other["id"] in used or t.get("bicycle") not in ("yes", "designated") or t.get("access") in ("no", "private"):
                    continue
                part = [[p["lon"], p["lat"]] for p in other.get("geometry", [])]
                if len(part) >= 2 and part[0] == line[-1]:
                    continuations.append((other["id"], part))
                elif len(part) >= 2 and part[-1] == line[-1] and t.get("oneway:bicycle", t.get("oneway", "no")) == "no":
                    continuations.append((other["id"], part[::-1]))
            if len(continuations) != 1:
                break
            identifier, part = continuations[0]
            used.add(identifier)
            line.extend(part[1:])
    position = sample(line, hit["distanceAlongLegMeters"] + (-distance if kind == "entry" else distance))
    assert not inside(position, polygon["coordinates"][0])
    return {"osmWayId": way["id"], "tags": tags, "location": hit["location"], "sample": position}


def main():
    proposed = deepcopy(catalog())
    proposed["version"] = "munich-big-junctions-v2"
    proposed["junctions"] = []
    with urlopen("https://api.radlnavi.munichways.de/version", timeout=60) as response:
        api_version = json.load(response)
    report = {"retrievedAt": datetime.now(timezone.utc).isoformat(), "apiVersion": api_version, "junctions": []}
    fixture_root = ROOT.parents[1] / "backend/tests/fixtures/big-junctions"
    fixture_root.mkdir(parents=True, exist_ok=True)
    for identifier, site in SITES.items():
        polygon = json.loads((ROOT / f"{identifier}-draft.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"]
        source = ROOT / site["source"]
        snapshot = json.loads(gzip.decompress(source.read_bytes())) if source.suffix == ".gz" else json.loads(source.read_text(encoding="utf-8"))
        osm = snapshot.get("response", snapshot)
        ways = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
        gates = {arm: {kind: gate(ways[way], polygon, kind, ways,
                                70 if identifier == "balan-chiemgau" and arm == "north" and kind == "entry" else 40)
                       for kind, way in zip(("entry", "exit"), ids)}
                 for arm, ids in site["gates"].items()}
        junction = {"id": identifier, "name": site["name"], "enabled": True, "polygon": polygon,
            "review": {"status": "approved", "date": "2026-11-07",
                "evidence": "User approved polygon and requested all left/straight movements; directed cycling gates and live reference routes checked."},
            "movements": []}
        evidence = {"id": identifier, "osmSnapshot": site["source"],
            "osmTimestamp": osm.get("osm3s", {}).get("timestamp_osm_base"), "gates": gates, "movements": []}
        for arm in ("west", "north", "east", "south"):
            for kind, target in (("left", LEFT[arm]), ("straight", STRAIGHT[arm])):
                movement_id = f"{arm}-{target}-{kind}"
                before, after = gates[arm]["entry"], gates[target]["exit"]
                coord = lambda p: f"{p[0]:.9f},{p[1]:.9f}"
                url = ("https://api.radlnavi.munichways.de/route/v1/bike/" + coord(before["sample"]) + ";" + coord(after["sample"])
                    + "?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false")
                with urlopen(url, timeout=90) as response:
                    payload = json.load(response)
                fixture = f"{identifier}-{movement_id}.json"
                (fixture_root / fixture).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                item = {"id": movement_id, "url": url, "fixture": fixture, "enabled": False}
                try:
                    assert payload["code"] == "Ok"
                    assert all(w["distance"] <= 5 for w in payload["waypoints"]), "Endpoint snap exceeds 5m"
                    route = payload["routes"][0]
                    line = route["geometry"]["coordinates"]
                    hits = crossings(line, polygon["coordinates"][0])
                    assert len(hits) == 2, "Route does not visit polygon exactly once"
                    entry, exit = hits
                    assert meters(entry["location"], before["location"]) < 2.5, "Wrong entry gate"
                    assert meters(exit["location"], after["location"]) < 2.5, "Wrong exit gate"
                    start, end = entry["geometrySegmentIndex"], exit["geometrySegmentIndex"]
                    corridor = [entry["location"], *line[start + 1:end + 1], exit["location"]]
                    cycling_ways = cycling_corridor(corridor, ways)
                    movement = {"id": movement_id, "enabled": True, "movement": kind,
                        "entryArm": arm, "exitArm": target, "entry": entry["location"], "exit": exit["location"],
                        "corridor": corridor,
                        "approach": [point_at(line, entry["distanceAlongLegMeters"] - 10), entry["location"]],
                        "departure": [exit["location"], point_at(line, exit["distanceAlongLegMeters"] + 10)],
                        "review": {"status": "approved", "date": "2026-11-07",
                            "evidence": f"Reviewed polygon; directed OSM gates {before['osmWayId']} -> {after['osmWayId']}; live route {fixture}."}}
                    test_catalog = dict(proposed, junctions=[dict(junction, movements=[movement])])
                    validate_catalog(test_catalog)
                    with patch("src.big_junctions.catalog", return_value=test_catalog):
                        matched = add_guidance(payload)
                    assert matched is not None, "Route fails production corridor/mode/continuity checks"
                    hit = matched["routes"][0]["guidance"]["junctions"][0]
                    junction["movements"].append(movement)
                    item.update(enabled=True, entry=entry["location"], exit=exit["location"],
                        internalMeters=exit["distanceAlongLegMeters"] - entry["distanceAlongLegMeters"],
                        suppressedSteps=hit["suppressedStepIndices"], verifiedCyclingWayIds=cycling_ways)
                except (AssertionError, KeyError, ValueError, IndexError, TypeError) as error:
                    item["reason"] = str(error)
                    junction["movements"].append({"id": movement_id, "enabled": False, "movement": kind,
                        "entryArm": arm, "exitArm": target, "review": {"status": "unverified", "evidence": str(error)}})
                evidence["movements"].append(item)
                print(f"{identifier} {movement_id}: {'verified' if item['enabled'] else item['reason']}", flush=True)
        proposed["junctions"].append(junction)
        report["junctions"].append(evidence)
    validate_catalog(proposed)
    report["rightTurnChecks"] = []
    for junction in report["junctions"]:
        for arm in ("west", "north", "east", "south"):
            target = next(source for source, destination in LEFT.items() if destination == arm)
            before = junction["gates"][arm]["entry"]["sample"]
            after = junction["gates"][target]["exit"]["sample"]
            url = ("https://api.radlnavi.munichways.de/route/v1/bike/" + coord(before) + ";" + coord(after)
                + "?steps=true&overview=full&geometries=geojson&alternatives=false")
            with urlopen(url, timeout=90) as response:
                payload = json.load(response)
            fixture = f"{junction['id']}-{arm}-{target}-right.json"
            (fixture_root / fixture).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            with patch("src.big_junctions.catalog", return_value=proposed):
                assert add_guidance(payload) is None, "Right turn unexpectedly matches an approved movement"
            report["rightTurnChecks"].append({"fixture": fixture, "url": url, "guidance": False})
    (ROOT / "full-movements-proposed-catalog.json").write_text(json.dumps(proposed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "full-movements-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    features = []
    for junction in proposed["junctions"]:
        features.append({"type": "Feature", "geometry": junction["polygon"],
            "properties": {"name": junction["name"], "kind": "approved_polygon", "fill-opacity": .08}})
        for movement in junction["movements"]:
            if movement.get("enabled") is not True:
                continue
            features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": movement["corridor"]},
                "properties": {"name": f"{junction['id']} {movement['id']}", "movement": movement["movement"],
                    "stroke": "#1565c0" if movement["movement"] == "left" else "#2e7d32", "stroke-width": 3}})
    for junction in report["junctions"]:
        for arm, gates in junction["gates"].items():
            for kind, gate_data in gates.items():
                features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": gate_data["location"]},
                    "properties": {"name": f"{junction['id']} {arm} {kind}", "osmWayId": gate_data["osmWayId"]}})
    (ROOT / "full-movements-review.geojson").write_text(json.dumps({"type": "FeatureCollection",
        "attribution": "OpenStreetMap contributors, ODbL", "features": features}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(approved_movements(proposed))}/16 movements; runtime catalog unchanged.")


if __name__ == "__main__":
    main()
