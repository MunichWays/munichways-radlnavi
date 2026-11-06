"""Inspect frozen Overpass candidate queries; --refresh replaces their snapshots.

This validates Overpass QL against the server, not Turbo's MapCSS rendering.
The fixed test rectangle covers the five reported sites, not all of Munich.
"""

import argparse
from datetime import datetime, timezone
import gzip
import json
from math import cos, hypot, radians
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
QUERIES = (
    "candidates-primary-secondary", "candidates-major-road",
    "junction-detail", "candidates-four-way-points",
)
BBOX = "48.08,11.50,48.16,11.66"
SITES = (
    ("Thomasiusplatz", 48.1158, 11.6021),
    ("Balan / Chiemgau", 48.10845, 11.6040),
    ("Arnulf / Steuben", 48.1500, 11.5204),
    ("Staendler / Balan", 48.10445, 11.6053),
    ("Rudolf-Vogel / Otto-Hahn", 48.0921, 11.6453),
)


def refresh(name):
    template = (ROOT / f"{name}.overpassql").read_text(encoding="utf-8")
    query = re.sub(r"\{\{style:.*?\}\}", "", template, flags=re.DOTALL)
    bbox = "48.1078,11.6030,48.1090,11.6052" if name == "junction-detail" else BBOX
    query = query.replace("{{bbox}}", bbox)
    request = Request(
        "https://overpass-api.de/api/interpreter",
        data=urlencode({"data": query}).encode(),
        headers={"User-Agent": "MunichWays-Junction-Candidates/1.0"},
    )
    with urlopen(request, timeout=75) as response:
        payload = json.load(response)
    if payload.get("remark") or not payload.get("elements"):
        raise ValueError(f"{name}: incomplete response: {payload.get('remark')}")
    snapshot = {
        "query": query,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "response": payload,
    }
    (ROOT / f"{name}.json.gz").write_bytes(
        gzip.compress(
            (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            mtime=0,
        )
    )
    return name


def summarize(name):
    snapshot = json.loads(gzip.decompress((ROOT / f"{name}.json.gz").read_bytes()))
    elements = snapshot["response"]["elements"]
    nodes = [element for element in elements if element["type"] == "node"]
    ways = [element for element in elements if element["type"] == "way"]
    print(f"\n{name}: {len(nodes)} nodes, {len(ways)} ways")
    if name == "junction-detail":
        print("  signals:", sum(node.get("tags", {}).get("highway") == "traffic_signals" for node in nodes))
        return
    for label, lat, lon in SITES:
        nearby = []
        for node in nodes:
            distance = hypot(
                (node["lat"] - lat) * 111320,
                (node["lon"] - lon) * 111320 * cos(radians(lat)),
            )
            if distance <= 120:
                names = sorted({
                    way.get("tags", {}).get("name", "unnamed")
                    for way in ways if node["id"] in way.get("nodes", [])
                })
                nearby.append(
                    (round(distance, 1), node["id"], names) if ways
                    else (round(distance, 1), node["id"])
                )
        print(f"  {label}: {sorted(nearby)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh:
        # Keep only one public Overpass query in flight to avoid slot contention.
        for name in QUERIES:
            refresh(name)
            print(f"Saved {name}", flush=True)
    for name in QUERIES:
        summarize(name)


if __name__ == "__main__":
    main()
