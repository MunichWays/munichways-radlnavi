"""Fetch the frozen highway evidence for the inactive review batch."""

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def main():
    query = (ROOT / "review-batch-01.overpassql").read_text(encoding="utf-8")
    request = Request("https://overpass-api.de/api/interpreter",
                      data=urlencode({"data": query}).encode(),
                      headers={"User-Agent": "MunichWays-Junction-Catalog/1.0"})
    with urlopen(request, timeout=150) as response:
        value = json.load(response)
    if value.get("remark") or not value.get("elements"):
        raise ValueError("Incomplete Overpass response")
    snapshot = {"query": query, "retrievedAt": datetime.now(timezone.utc).isoformat(), "response": value}
    (ROOT / "review-batch-01-osm.json.gz").write_bytes(gzip.compress(
        json.dumps(snapshot, ensure_ascii=False).encode(), mtime=0))
    print(f"Saved {len(value['elements'])} highway elements; no runtime changes.")


if __name__ == "__main__":
    main()
