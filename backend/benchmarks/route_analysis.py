"""Offline before/after benchmark of route segment analysis.

Run from the repository root with the backend environment:
  backend/.venv/Scripts/python.exe backend/benchmarks/route_analysis.py

Uses synthetic SQLite data and the original implementation from commit f05172e.
Verifies ordinary-route comfort, distances and highlight geometries match.
The annotated path uses precomputed lengths as supplied by OSRM; it is reported
separately from legacy node-only clients. No network, OSRM or production load.
"""

import argparse
import asyncio
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
    db.executescript(
        """
        CREATE TABLE nodes (id INTEGER PRIMARY KEY, lat FLOAT, lon FLOAT, tags TEXT);
        CREATE TABLE ways (id INTEGER PRIMARY KEY, node_list TEXT, tags TEXT);
        CREATE TABLE node_to_ways (node_id INTEGER, way_id INTEGER);
        CREATE INDEX node_to_ways_node_id ON node_to_ways(node_id);
        CREATE INDEX node_to_ways_way_id ON node_to_ways(way_id);
    """
    )
    ids = list(range(1, count + 1))
    db.executemany(
        "INSERT INTO nodes VALUES (?, ?, ?, ?)",
        [(node, 48.1, 11.4 + node * 0.0001, "{}") for node in ids],
    )
    way_count = 0
    for start in range(0, count - 1, 8):
        way_count += 1
        nodes = ids[start : start + 9]
        tags = {
            "class:bicycle": str(way_count % 3 + 1),
            "surface": "asphalt",
            "lit": "yes",
            "name": "Fixture",
        }
        db.execute(
            "INSERT INTO ways VALUES (?, ?, ?)",
            (way_count, json.dumps(nodes), json.dumps(tags)),
        )
        db.executemany(
            "INSERT INTO node_to_ways VALUES (?, ?)",
            [(node, way_count) for node in nodes],
        )
    return db, ids, way_count


def load_baseline():
    """Use the reviewed pre-change implementation as an independent reference."""
    import subprocess
    import types

    source = subprocess.check_output(
        ["git", "show", "f05172e:backend/src/app.py"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        encoding="utf-8",
    )
    module = types.ModuleType("radlnavi_analysis_baseline")
    module.__file__ = str(Path(app.__file__))
    sys.modules[module.__name__] = module
    exec(compile(source, "baseline/app.py", "exec"), module.__dict__)
    return module


def median_ms(action, repeat):
    samples = []
    for _ in range(repeat):
        start = perf_counter()
        action()
        samples.append((perf_counter() - start) * 1000)
    return round(statistics.median(samples), 3)


def benchmark(count, repeat, baseline):
    db, ids, way_count = fixture(count)
    try:
        with patch.object(app, "geo_store", db), patch.object(
            baseline, "geo_store", db
        ):
            nodes = app.retrieve_nodes_by_id(db, ids)
            # Preparation is outside measurement, as OSRM supplies these lengths.
            distances = [
                app.distance.distance(nodes[a].location, nodes[b].location).meters
                for a, b in zip(ids, ids[1:])
            ]
            legs = [
                app.AnalysisLeg(
                    nodes=ids,
                    distance=distances,
                    start=nodes[ids[0]].coord,
                    end=nodes[ids[-1]].coord,
                )
            ]
            legacy_request = app.NodeList(node_ids=ids)
            old_payload = asyncio.run(
                baseline.tag_distribution(baseline.NodeList(node_ids=ids))
            )
            payload = asyncio.run(app.tag_distribution(legacy_request))
            annotated = app.analyze_route(legs, details=True)
            assert payload["comfort"] == old_payload["comfort"] == annotated["comfort"]
            for tag, values in old_payload["tag_distribution"].items():
                for value, info in values.items():
                    assert (
                        abs(
                            info.distance
                            - payload["tag_distribution"][tag][value].distance
                        )
                        < 1e-6
                    )
                    old_lines = [way.geometry.coordinates for way in info.ways.values()]
                    new_lines = [
                        way.geometry.coordinates
                        for way in payload["tag_distribution"][tag][value].ways.values()
                    ]
                    assert old_lines == new_lines, "Ordinary route geometry changed"
            result = {
                "nodes": count,
                "ways": way_count,
                "ways_sql_before_ms": median_ms(
                    lambda: baseline.retrieve_ways_by_node_ids(db, ids), repeat
                ),
                "ways_sql_after_ms": median_ms(
                    lambda: app.retrieve_ways_by_node_ids(db, ids), repeat
                ),
                "comfort_before_ms": median_ms(
                    lambda: baseline.calculate_comfort_for_node_ids(ids), repeat
                ),
                "comfort_nodes_after_ms": median_ms(
                    lambda: app.calculate_comfort_for_node_ids(ids), repeat
                ),
                "comfort_annotations_after_ms": median_ms(
                    lambda: app.analyze_route(legs), repeat
                ),
                "details_before_ms": median_ms(
                    lambda: asyncio.run(
                        baseline.tag_distribution(baseline.NodeList(node_ids=ids))
                    ),
                    repeat,
                ),
                "details_nodes_after_ms": median_ms(
                    lambda: asyncio.run(app.tag_distribution(legacy_request)), repeat
                ),
                "details_annotations_after_ms": median_ms(
                    lambda: app.analyze_route(legs, details=True), repeat
                ),
                "encode_and_json_ms": median_ms(
                    lambda: json.dumps(
                        jsonable_encoder(payload), separators=(",", ":")
                    ),
                    repeat,
                ),
                "payload_bytes": len(
                    json.dumps(
                        jsonable_encoder(payload), separators=(",", ":")
                    ).encode()
                ),
            }
            return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nodes", type=int, nargs="+", default=[1000, 2000, 4000, 8000]
    )
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if args.repeat < 1 or any(count < 2 for count in args.nodes):
        parser.error("repeat must be positive; node counts must be at least two")
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "repeat": args.repeat,
                "fixture": "synthetic, in-memory, 8 edges per way",
            }
        )
    )
    baseline = load_baseline()
    for count in args.nodes:
        print(json.dumps(benchmark(count, args.repeat, baseline)), flush=True)


if __name__ == "__main__":
    main()
