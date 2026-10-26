"""Reproduce issue #22 counts offline; no routing behavior is implemented here."""

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ATTRIBUTES = ("surface", "smoothness", "width")
SIDES = ("left", "right", "both")


def keys_for(attribute):
    return [
        key
        for side in SIDES
        for key in (
            f"cycleway:{side}:{attribute}",
            f"cycleway:{attribute}:{side}",
            f"{attribute}:{side}",
        )
    ]


def summarize(data):
    if data.get("remark"):
        raise ValueError(data["remark"])
    ways = [item for item in data["elements"] if item["type"] == "way"]
    counts = Counter(key for way in ways for key in way["tags"])
    attributes = {}
    for attribute in ATTRIBUTES:
        keys = keys_for(attribute)
        attributes[attribute] = {
            "ways": sum(any(key in way["tags"] for key in keys) for way in ways),
            "keys": {key: counts[key] for key in keys},
            "values": {
                key: dict(sorted(Counter(
                    way["tags"][key] for way in ways if key in way["tags"]
                ).items()))
                for key in keys if counts[key]
            },
        }
    return {
        "osm_timestamp": data["osm3s"]["timestamp_osm_base"],
        "area_timestamp": data["osm3s"]["timestamp_areas_base"],
        "unique_ways": len(ways),
        "attributes": attributes,
        "ways": [
            {
                "id": way["id"],
                "name": way["tags"].get("name", ""),
                "center": way["center"],
                "tags": {
                    key: value for key, value in sorted(way["tags"].items())
                    if key in {"highway", "bicycle", "oneway", "oneway:bicycle"}
                    or key.startswith("cycleway")
                    or any(key == attr or key.startswith(attr + ":") for attr in ATTRIBUTES)
                },
            }
            for way in sorted(ways, key=lambda item: item["id"])
        ],
    }


if __name__ == "__main__":
    data = json.loads((ROOT / "munich-side-tags.json").read_text(encoding="utf-8"))
    output = ROOT / "summary.json"
    output.write_text(
        json.dumps(summarize(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output.name}")
