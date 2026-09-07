"""Read-only analysis benchmark against a real geo.db; no network requests.

Run with the backend environment, --database PATH and optionally --fixture PATH.
Reports SQLite read-call bytes on Linux (rchar), not physical disk traffic.
Opening a new connection does NOT clear the operating system's file cache.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from time import perf_counter

os.environ.setdefault("OSRM_BACKEND_URL", "http://unused.invalid")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.encoders import jsonable_encoder
from src import app
from src.route_analysis import AnalysisLeg


def read_bytes():
    path = Path("/proc/self/io")
    if not path.exists():
        return 0
    return int(
        dict(line.split(": ") for line in path.read_text().splitlines())["rchar"]
    )


def measure(database, fixture):
    legs = [
        AnalysisLeg(
            nodes=leg["annotation"]["nodes"],
            distance=leg["annotation"]["distance"],
            start=fixture["waypoints"][i],
            end=fixture["waypoints"][i + 1],
        )
        for i, leg in enumerate(fixture["legs"])
    ]
    with sqlite3.connect(
        Path(database).resolve().as_uri() + "?mode=ro", uri=True
    ) as db:
        app.geo_store = db
        ids = [node for leg in legs for node in leg.nodes]
        sample = list(dict.fromkeys(ids))[:900]
        plan = list(
            db.execute(
                "EXPLAIN QUERY PLAN SELECT DISTINCT way_id FROM node_to_ways "
                f"WHERE node_id IN ({','.join('?' * len(sample))})",
                sample,
            )
        )
        start_bytes = read_bytes()
        start = perf_counter()
        nodes = app.retrieve_nodes_by_id(db, ids)
        nodes_done, node_bytes = perf_counter(), read_bytes()
        ways = app.retrieve_ways_by_node_ids(db, ids)
        ways_done, way_bytes = perf_counter(), read_bytes()
        segments = app.route_segments(legs, nodes, ways)
        segments_done = perf_counter()
        # Complete output, including highlight geometries, must stay identical.
        result = json.dumps(
            json.loads(
                json.dumps(jsonable_encoder(app.analyze_route(legs, details=True)))
            ),
            sort_keys=True,
        )
        digest = hashlib.sha256(result.encode()).hexdigest()
    app.geo_store = None
    return {
        "nodes": len(nodes),
        "ways": len(ways),
        "segments": len(segments),
        "nodes_ms": round((nodes_done - start) * 1000, 2),
        "ways_ms": round((ways_done - nodes_done) * 1000, 2),
        "segments_ms": round((segments_done - ways_done) * 1000, 2),
        "nodes_read_bytes": node_bytes - start_bytes,
        "ways_read_bytes": way_bytes - node_bytes,
        "result_sha256": digest,
        "query_plan": plan,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).with_name("munich-route-annotations.json"),
    )
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    for _ in range(args.repeat):
        print(json.dumps(measure(args.database, fixture)), flush=True)
