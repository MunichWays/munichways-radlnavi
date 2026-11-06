"""Capture the six reported routes, or summarize frozen responses (stdlib only).

Inputs in cases.json use latitude/longitude; OSRM requests use longitude/latitude.
Run without --refresh to inspect the committed evidence without network access.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
API = "https://api.radlnavi.munichways.de"


def capture(item):
    filename, url = item
    request = Request(url, headers={"User-Agent": "MunichWays-Large-Junction-Analysis/1.0"})
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if filename != "version" and payload.get("code") != "Ok":
        raise ValueError(f"{filename}: {payload}")
    snapshot = {
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "response": payload,
    }
    (ROOT / f"{filename}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return filename


def summarize(cases):
    for case in cases:
        payload = json.loads((ROOT / f"{case['id']}.json").read_text(encoding="utf-8"))["response"]
        route = payload["routes"][0]
        print(f"\n{case['id']}: {route['distance']} m")
        print("  snap distances:", [point.get("distance") for point in payload["waypoints"]])
        at = 0.0
        for leg in route["legs"]:
            for step in leg["steps"]:
                maneuver = step["maneuver"]
                print(
                    f"  {at:6.1f} m: {maneuver['type']}/{maneuver.get('modifier', '-')} "
                    f"{step.get('name', '')!r}; next {step['distance']} m; "
                    f"{step.get('mode')}; {maneuver['location']}"
                )
                at += step["distance"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Replace snapshots using seven public GET requests")
    parser.add_argument("--osm", action="store_true", help="Replace the five-site OSM snapshot using one Overpass request")
    args = parser.parse_args()
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    if args.osm:
        query = (ROOT / "examples.overpassql").read_text(encoding="utf-8")
        request = Request(
            "https://overpass-api.de/api/interpreter",
            data=urlencode({"data": query}).encode(),
            headers={"User-Agent": "MunichWays-Large-Junction-Analysis/1.0"},
        )
        with urlopen(request, timeout=45) as response:
            payload = json.load(response)
        if payload.get("remark") or not payload.get("elements"):
            raise ValueError(f"Incomplete Overpass response: {payload.get('remark')}")
        (ROOT / "osm-examples.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Saved {len(payload['elements'])} OSM elements")
    if args.refresh:
        query = urlencode({
            "steps": "true", "geometries": "geojson", "overview": "full",
            "annotations": "nodes,distance", "alternatives": "false",
            "continue_straight": "default", "variant": "standard",
        })
        requests = [("version", f"{API}/version")]
        for case in cases:
            coordinates = ";".join(f"{lon},{lat}" for lat, lon in (case["start"], case["end"]))
            requests.append((case["id"], f"{API}/route/v1/bike/{coordinates}?{query}"))
        with ThreadPoolExecutor(max_workers=3) as pool:
            for filename in pool.map(capture, requests):
                print(f"Saved {filename}")
    summarize(cases)


if __name__ == "__main__":
    main()
