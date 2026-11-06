"""Refresh city-wide candidate points. Never writes to the runtime catalog."""

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


def main():
    query = '''[out:json][timeout:120];
area[boundary=administrative][admin_level=6][name="München"]->.city;
way[highway~"^(primary|secondary|tertiary)(_link)?$"](area.city)->.roads;
node(way_link.roads:4)(area.city)->.fourWay;
way[junction~"^(roundabout|circular)$"] (area.city)->.roundabouts;
(node(w.roundabouts);node[highway=mini_roundabout](area.city);)->.excluded;
(.fourWay;- .excluded;)->.candidates;
.candidates out body;
'''
    request = Request("https://overpass-api.de/api/interpreter",
        data=urlencode({"data": query}).encode(),
        headers={"User-Agent": "MunichWays-Junction-Catalog/1.0"})
    with urlopen(request, timeout=150) as response:
        value = json.load(response)
    if value.get("remark") or not value.get("elements"):
        raise ValueError("Incomplete Overpass response")
    snapshot = {"query": query, "retrievedAt": datetime.now(timezone.utc).isoformat(), "response": value}
    (ROOT / "munich-candidates.json.gz").write_bytes(gzip.compress(
        json.dumps(snapshot, ensure_ascii=False, indent=2).encode(), mtime=0))
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
        "properties": {"osmNodeId": n["id"], "status": "unreviewed", "enabled": False,
            "note": "Candidate point only; polygon, logical arms and cycling movements require review."}}
        for n in value["elements"] if n["type"] == "node"]
    (ROOT / "munich-review-queue.geojson").write_text(json.dumps({"type": "FeatureCollection",
        "scope": "Munich administrative boundary; candidate nodes are not junction complexes",
        "attribution": "OpenStreetMap contributors, ODbL", "features": features}, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(features)} city-wide candidate points; no runtime activation.")


if __name__ == "__main__":
    main()
