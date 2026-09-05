"""Offline microbenchmark of the current analysis and a pair-index prototype.

Run from the repository root with the backend environment:
  backend/.venv/Scripts/python.exe backend/benchmarks/route_analysis.py

Uses a synthetic SQLite database in memory, never calls OSRM or production.
The prototype intentionally preserves the current way-grouping behavior; it
does not address missing nodes, disconnected way visits or ambiguous OSM ways.
Times are not end-to-end route latency predictions.
"""

import argparse
import asyncio
from collections import defaultdict
import importlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import sys
from time import perf_counter
from unittest.mock import patch

from fastapi.encoders import jsonable_encoder

os.environ.setdefault("OSRM_BACKEND_URL", "http://unused.invalid")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
app = importlib.import_module("src.app")


def fixture(count):
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE nodes (id INTEGER PRIMARY KEY, lat FLOAT, lon FLOAT, tags TEXT);
        CREATE TABLE ways (id INTEGER PRIMARY KEY, node_list TEXT, tags TEXT);
        CREATE TABLE node_to_ways (node_id INTEGER, way_id INTEGER);
        CREATE INDEX node_to_ways_node_id ON node_to_ways(node_id);
        CREATE INDEX node_to_ways_way_id ON node_to_ways(way_id);
    """)
    ids = list(range(1, count + 1))
    db.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?)", [
        (node, 48.1, 11.4 + node * 0.0001, "{}") for node in ids
    ])
    way_count = 0
    for start in range(0, count - 1, 8):
        way_count += 1
        nodes = ids[start:start + 9]
        tags = {"class:bicycle": str(way_count % 3 + 1),
                "surface": "asphalt", "lit": "yes", "name": "Fixture"}
        db.execute("INSERT INTO ways VALUES (?, ?, ?)",
                   (way_count, json.dumps(nodes), json.dumps(tags)))
        db.executemany("INSERT INTO node_to_ways VALUES (?, ?)",
                       [(node, way_count) for node in nodes])
    return db, ids, way_count


def indexed_route_ways(node_ids):
    nodes = app.retrieve_nodes_by_id(app.geo_store, node_ids)
    ways = app.retrieve_ways_by_node_ids(app.geo_store, node_ids)
    by_pair = defaultdict(list)
    for way in ways.values():
        for a, b in zip(way.nodes, way.nodes[1:]):
            by_pair[(a, b)].append(way.id)
            by_pair[(b, a)].append(way.id)
    ordered = [nodes[node] for node in node_ids if node in nodes]
    result = defaultdict(list)
    for a, b in zip(ordered, ordered[1:]):
        for way_id in by_pair.get((a.id, b.id), ()):
            way_nodes = result[way_id]
            if way_nodes and way_nodes[-1] == a:
                way_nodes.append(b)
            else:
                way_nodes.extend((a, b))
    return result, ways


def median_ms(action, repeat):
    samples = []
    for _ in range(repeat):
        start = perf_counter()
        action()
        samples.append((perf_counter() - start) * 1000)
    return round(statistics.median(samples), 3)


def benchmark(count, repeat):
    db, ids, way_count = fixture(count)
    try:
        with patch.object(app, "geo_store", db):
            original = app.retrieve_route_ways(ids)
            candidate = indexed_route_ways(ids)
            assert original == candidate, "Prototype changed the synthetic mapping"
            payload = asyncio.run(app.tag_distribution(app.NodeList(node_ids=ids)))
            encoded = jsonable_encoder(payload)
            result = {
                "nodes": count,
                "ways": way_count,
                "mapping_current_ms": median_ms(lambda: app.retrieve_route_ways(ids), repeat),
                "mapping_pair_index_ms": median_ms(lambda: indexed_route_ways(ids), repeat),
                "comfort_current_ms": median_ms(lambda: app.calculate_comfort_for_node_ids(ids), repeat),
                "all_tags_current_ms": median_ms(lambda: asyncio.run(app.tag_distribution(app.NodeList(node_ids=ids))), repeat),
                "encode_and_json_ms": median_ms(lambda: json.dumps(jsonable_encoder(payload), separators=(",", ":")), repeat),
                "payload_bytes": len(json.dumps(encoded, separators=(",", ":")).encode()),
                "comfort_arithmetic_ms": median_ms(lambda: app.calculate_comfort_index(payload["tag_distribution"]["class:bicycle"]), 101),
            }
            with patch.object(app, "retrieve_route_ways", indexed_route_ways):
                assert app.calculate_comfort_for_node_ids(ids) == payload["comfort"]
                result["comfort_pair_index_ms"] = median_ms(lambda: app.calculate_comfort_for_node_ids(ids), repeat)
            return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=int, nargs="+", default=[1000, 2000, 4000, 8000])
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if args.repeat < 1 or any(count < 2 for count in args.nodes):
        parser.error("repeat must be positive; node counts must be at least two")
    print(json.dumps({"python": platform.python_version(), "platform": platform.platform(),
                      "repeat": args.repeat, "fixture": "synthetic, in-memory, 8 edges per way"}))
    for count in args.nodes:
        print(json.dumps(benchmark(count, args.repeat)), flush=True)


if __name__ == "__main__":
    main()
