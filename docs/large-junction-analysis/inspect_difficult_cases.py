"""Freeze four difficult OSM examples and inspect the existing degree-four filter.

Offline by default. --refresh makes one public Overpass request per case.
This is diagnostic evidence, not a bicycle-access resolver or release gate.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from math import atan2, cos, degrees, hypot, radians
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RADIUS = 180
ROAD_PATTERN = re.compile(r"^(primary|secondary|tertiary)(_link)?$")
CAR_ROADS = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service"}


def distance(point, case):
    return hypot(
        (point[1] - case["lat"]) * 111320,
        (point[0] - case["lon"]) * 111320 * cos(radians(case["lat"])),
    )


def refresh(case):
    center = f"{case['lat']},{case['lon']}"
    query = f'''[out:json][timeout:40];
node(id:{case['nodeId']})->.seed;
way(bn.seed)[highway]->.incident;
way[highway](around:{RADIUS},{center})->.nearby;
(
  .seed;
  .incident;
  .nearby;
  node[highway](around:{RADIUS},{center});
  node[barrier](around:{RADIUS},{center});
  rel(bw.incident)[type=restriction];
);
out body geom;
'''
    request = Request(
        "https://overpass-api.de/api/interpreter",
        data=urlencode({"data": query}).encode(),
        headers={"User-Agent": "MunichWays-Difficult-Junction-Analysis/1.0"},
    )
    for attempt in range(2):
        try:
            with urlopen(request, timeout=55) as response:
                payload = json.load(response)
            break
        except HTTPError as error:
            if error.code not in (502, 503, 504) or attempt:
                raise
    if payload.get("remark") or not payload.get("elements"):
        raise ValueError(f"Incomplete OSM response for {case['id']}")
    assert any(e["type"] == "node" and e["id"] == case["nodeId"] for e in payload["elements"])
    snapshot = {"case": case, "query": query, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "response": payload}
    (ROOT / f"difficult-{case['id']}.json.gz").write_bytes(
        gzip.compress((json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0)
    )


def inspect(case):
    snapshot = json.loads(gzip.decompress((ROOT / f"difficult-{case['id']}.json.gz").read_bytes()))
    elements = snapshot["response"]["elements"]
    ways = [e for e in elements if e["type"] == "way" and "highway" in e.get("tags", {})]
    nodes = {e["id"]: e for e in elements if e["type"] == "node"}
    coordinates = {}
    selected_degree = Counter()
    car_degree = Counter()
    for way in ways:
        coordinates.update({node: [point["lon"], point["lat"]] for node, point in zip(way["nodes"], way["geometry"])})
        if ROAD_PATTERN.fullmatch(way["tags"]["highway"]):
            for a, b in zip(way["nodes"], way["nodes"][1:]):
                selected_degree[a] += 1
                selected_degree[b] += 1
        if way["tags"]["highway"] in CAR_ROADS:
            for a, b in zip(way["nodes"], way["nodes"][1:]):
                car_degree[a] += 1
                car_degree[b] += 1
    excluded = {e["id"] for e in nodes.values() if e.get("tags", {}).get("highway") == "mini_roundabout"}
    excluded.update(node for way in ways if way["tags"].get("junction") in ("roundabout", "circular") for node in way["nodes"])
    candidates = sorted((node for node, degree in selected_degree.items() if degree == 4 and node not in excluded and distance(coordinates[node], case) <= RADIUS), key=lambda node: distance(coordinates[node], case))
    keep = {"name", "highway", "ref", "oneway", "bicycle", "bicycle:forward", "bicycle:backward", "access", "vehicle", "motorroad", "tunnel", "bridge", "layer", "junction", "cycleway", "cycleway:left", "cycleway:right", "cycleway:both", "sidewalk", "foot", "footway"}
    incident = []
    for way in ways:
        if case["nodeId"] not in way["nodes"]:
            continue
        arms = []
        for i, node in enumerate(way["nodes"]):
            if node != case["nodeId"]:
                continue
            for j in (i - 1, i + 1):
                if 0 <= j < len(way["nodes"]):
                    p = coordinates[way["nodes"][j]]
                    dx = (p[0] - case["lon"]) * cos(radians(case["lat"]))
                    dy = p[1] - case["lat"]
                    arms.append({"nextNode": way["nodes"][j], "bearingAway": round(degrees(atan2(dx, dy)) % 360, 1)})
        endpoints = []
        for endpoint in (way["nodes"][0], way["nodes"][-1]):
            if endpoint == case["nodeId"] or distance(coordinates[endpoint], case) > RADIUS:
                continue
            endpoints.append({
                "nodeId": endpoint,
                "distanceFromSeedMeters": round(distance(coordinates[endpoint], case), 1),
                "otherCarWays": [{"id": other["id"], "tags": {k: v for k, v in other["tags"].items() if k in keep}} for other in ways if other["id"] != way["id"] and endpoint in other["nodes"] and other["tags"]["highway"] in CAR_ROADS],
            })
        incident.append({"id": way["id"], "tags": {k: v for k, v in way["tags"].items() if k in keep or k.startswith("cycleway:") or k.startswith("bicycle:")}, "segments": arms, "nearbyEndpoints": endpoints})
    report = {
        "id": case["id"], "name": case["name"], "nodeId": case["nodeId"],
        "osmTimestamp": snapshot["response"]["osm3s"]["timestamp_osm_base"],
        "inputCoordinateErrorMeters": round(distance([nodes[case["nodeId"]]["lon"], nodes[case["nodeId"]]["lat"]], case), 3),
        "selectedDegreeAtSeed": selected_degree[case["nodeId"]],
        "allMotorTrafficRoadDegreeAtSeed": car_degree[case["nodeId"]],
        "seedPassesFourWayFilter": case["nodeId"] in candidates,
        "candidateNodesWithin180m": [{"id": n, "distanceMeters": round(distance(coordinates[n], case), 1)} for n in candidates],
        "incidentWays": incident,
        "specialCarWaysWithin180m": [{"id": w["id"], "tags": {k: v for k, v in w["tags"].items() if k in keep}} for w in ways if w["tags"]["highway"] in CAR_ROADS and any(k in w["tags"] and w["tags"][k] not in ("no", "0") for k in ("tunnel", "bridge", "layer", "motorroad")) or w["tags"]["highway"] in ("motorway", "motorway_link", "trunk", "trunk_link")],
        "explicitCyclingPathsWithin180m": [{"id": w["id"], "highway": w["tags"]["highway"], "bicycle": w["tags"].get("bicycle"), "oneway": w["tags"].get("oneway"), "cycleway": w["tags"].get("cycleway")} for w in ways if w["tags"]["highway"] == "cycleway" or (w["tags"]["highway"] in ("path", "footway") and w["tags"].get("bicycle") in ("yes", "designated"))],
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--case", help="Inspect or refresh only the named case")
    args = parser.parse_args()
    cases = json.loads((ROOT / "difficult-cases.json").read_text(encoding="utf-8"))
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
        if not cases:
            parser.error("Unknown case ID")
    reports = []
    for case in cases:
        if args.refresh:
            refresh(case)
            print(f"Saved {case['id']}", flush=True)
        report = inspect(case)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not args.case:
        (ROOT / "difficult-cases-report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
