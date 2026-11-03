"""Frozen Munich regression: Discovery prefers the legal parallel foot/cycle path."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from src.endpoint_routes import endpoint_route
from src.geo_store import __initialize_geo_store
from test_endpoint_access import fetcher, validate

FIXTURE = Path(__file__).with_name("fixtures") / "discovery-parallel-path-2026-11-03.osm"
COORDINATES = "11.520648,48.146644;11.516315,48.146799"
PARAMS = [("steps", "true"), ("overview", "full"), ("geometries", "geojson"),
          ("annotations", "true"), ("alternatives", "false")]


def map_edges():
    ways, forbidden = {}, set()
    for way in ET.parse(FIXTURE).getroot().findall("way"):
        refs = [int(n.get("ref")) for n in way.findall("nd")]
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        direction = tags.get("oneway:bicycle", tags.get("oneway"))
        counterflow = any(tags.get(key, "").startswith("opposite")
                          for key in ("cycleway", "cycleway:left", "cycleway:right"))
        for a, b in zip(refs, refs[1:]):
            ways[a, b] = ways[b, a] = int(way.get("id"))
            if direction in ("yes", "1", "true", "-1") and not counterflow:
                forbidden.add((a, b) if direction == "-1" else (b, a))
    return ways, forbidden


def check(db, standard, discovery):
    edge_ways, forbidden = map_edges()

    def route(endpoint, variant, text=COORDINATES):
        fetch = fetcher(endpoint)
        initial = fetch(text, PARAMS).json()
        payload = endpoint_route(db, "bike", text, PARAMS, initial, fetch, variant) or initial
        assert payload.get("code") == "Ok", payload
        result = validate(payload, 250, 1200)
        edges = {(a, b) for leg in result["legs"]
                 for a, b in zip(leg["annotation"]["nodes"], leg["annotation"]["nodes"][1:])}
        assert not edges.intersection(forbidden), "No shortcut against a cycling one-way"
        used_ways = {edge_ways[edge] for edge in edges if edge in edge_ways}
        return result, used_ways

    original, original_ways = route(standard, "standard")
    relaxed, relaxed_ways = route(discovery, "discovery")
    assert 153360599 in original_ways, "Standard must retain the Schlosschmidstrasse baseline"
    assert 5197210 not in original_ways, original_ways
    assert 5197210 in relaxed_ways, "Discovery must use the parallel shared foot/cycle path"
    assert 153360599 not in relaxed_ways, relaxed_ways
    assert original["weight_name"] == "cyclability"
    assert relaxed["weight_name"] == "relaxed_cycling"
    assert 0 < relaxed["distance"] - original["distance"] < 25
    assert any(s["mode"] == "pushing bike" for leg in relaxed["legs"] for s in leg["steps"])

    # Preserve the exact trip endpoints, legal reverse access and intermediate legs.
    reverse = ";".join(reversed(COORDINATES.split(";")))
    route(discovery, "discovery", reverse)
    stops, _ = route(discovery, "discovery",
                     "11.520648,48.146644;11.5175,48.14688;11.516315,48.146799")
    assert len(stops["legs"]) == 2

    # Preference changes must not inflate the physical speed or alter the ETA
    # on the very same mapped foot/cycle path in either direction.
    path = "11.520104,48.1467246;11.5169514,48.1468999"
    for text in (path, ";".join(reversed(path.split(";")))):
        a = fetcher(standard)(text, PARAMS).json()["routes"][0]
        b = fetcher(discovery)(text, PARAMS).json()["routes"][0]
        assert a["geometry"] == b["geometry"]
        assert abs(a["duration"] - b["duration"]) < 0.1

    print(f"Parallel path: Standard {original['distance']:.1f} m, "
          f"Discovery {relaxed['distance']:.1f} m; access, guidance, stops and ETA OK")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", default="http://localhost:18092")
    parser.add_argument("--discovery", default="http://localhost:18093")
    args = parser.parse_args()
    with closing(sqlite3.connect(":memory:")) as db:
        __initialize_geo_store(db, str(FIXTURE))
        check(db, args.standard, args.discovery)


if __name__ == "__main__":
    main()
