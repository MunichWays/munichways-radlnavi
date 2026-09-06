"""Sequential, low-volume measurements of the user's four-point example route.

This sends real routing requests to the deployed API, including comfort analysis.
It records client-observed timings, not internal server spans or Flutter frames.
Run with the backend Python environment; --output writes the measurement JSON.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import requests


COORDINATES = [
    [48.156304, 11.540013],
    [48.102548, 11.568796],
    [48.120477, 11.655645],
    [47.991860, 11.828568],
]
PARAMS = {
    "alternatives": "false",
    "steps": "true",
    "annotations": "false",
    "geometries": "geojson",
    "overview": "full",
    "continue_straight": "default",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://api.radlnavi.munichways.de")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "coordinates_lat_lon": COORDINATES,
        "method": "Sequential requests from Windows; first route is excluded warmup; 3 samples per main variant; no intentional concurrency or server cache control",
        "samples": records,
    }
    path = "/route/v1/bike/" + ";".join(
        f"{lon},{lat}" for lat, lon in COORDINATES
    )

    def measure(session, label, endpoint, params=None, payload=None):
        started = perf_counter()
        record = {"label": label, "started_at_utc": datetime.now(timezone.utc).isoformat()}
        data = None
        try:
            response = session.request(
                "POST" if payload is not None else "GET",
                args.base_url + endpoint,
                params=params,
                json=payload,
                timeout=(10, 65),
                stream=True,
            )
            with response:
                headers_s = perf_counter() - started
                content = response.content
                total_s = perf_counter() - started
                record.update({
                    "http_status": response.status_code,
                    "headers_s": round(headers_s, 4),
                    "total_s": round(total_s, 4),
                    "decoded_response_bytes": len(content),
                    "content_encoding": response.headers.get("Content-Encoding"),
                    "server_timing": response.headers.get("Server-Timing"),
                })
                parse_started = perf_counter()
                try:
                    data = response.json()
                except ValueError:
                    record["non_json_response"] = True
                record["python_json_parse_s"] = round(perf_counter() - parse_started, 4)
                if isinstance(data, dict):
                    if endpoint == "/version":
                        record["versions"] = data
                    elif data.get("routes"):
                        route = data["routes"][0]
                        legs = route.get("legs", [])
                        record.update({
                            "code": data.get("code"),
                            "data_version": data.get("data_version"),
                            "distance_m": route.get("distance"),
                            "duration_s": route.get("duration"),
                            "leg_distances_m": [leg.get("distance") for leg in legs],
                            "legs": len(legs),
                            "steps": sum(len(leg.get("steps", [])) for leg in legs),
                            "geometry_points": len(route.get("geometry", {}).get("coordinates", [])),
                            "geometry_sha256": hashlib.sha256(json.dumps(route.get("geometry"), sort_keys=True).encode()).hexdigest(),
                            "annotation_node_counts": [len(leg.get("annotation", {}).get("nodes", [])) for leg in legs],
                            "comfort": route.get("comfort"),
                        })
                    elif endpoint == "/tag_distribution":
                        record["ok"] = data.get("ok")
                        record["comfort"] = data.get("comfort")
                        record["tag_categories"] = list(data.get("tag_distribution", {}))
        except requests.RequestException as error:
            record.update({"error": str(error), "total_s": round(perf_counter() - started, 4)})
        records.append(record)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record), flush=True)
        return data

    with requests.Session() as session:
        session.headers.update({"Accept": "application/json", "User-Agent": "com.munichways.app/flutter"})
        measure(session, "version_before", "/version")
        measure(session, "first_route_warmup", path, PARAMS)
        for label in ["without_comfort_1", "with_comfort_1", "with_comfort_2",
                      "without_comfort_2", "without_comfort_3", "with_comfort_3"]:
            params = dict(PARAMS)
            if label.startswith("with_comfort"):
                params["comfort"] = "true"
            measure(session, label, path, params)
        annotated = measure(session, "route_with_node_annotations", path,
                            {**PARAMS, "annotations": "nodes"})
        if isinstance(annotated, dict) and annotated.get("routes"):
            nodes = []
            for leg in annotated["routes"][0].get("legs", []):
                part = leg.get("annotation", {}).get("nodes", [])
                nodes.extend(part[1:] if nodes and part and nodes[-1] == part[0] else part)
            if nodes:
                report["analysis_node_count"] = len(nodes)
                measure(session, "tag_distribution", "/tag_distribution", payload={"node_ids": nodes})
        measure(session, "version_after", "/version")


if __name__ == "__main__":
    main()
