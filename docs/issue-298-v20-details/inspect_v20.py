"""Inspect a downloaded V20 snapshot without changing application data.

Run from the repository root:
python docs/issue-298-v20-details/inspect_v20.py SOURCE.geojson --output REPORT.json
"""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


SOURCE_URL = "https://www.munichways.de/App/IST_RadlVorrangNetz_MunichWays_V20.geojson"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sizes(raw):
    return {"bytes": len(raw), "gzip_bytes": len(gzip.compress(raw, mtime=0))}


def inspect(source):
    raw = source.read_bytes()
    collection = json.loads(raw)
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")
    features = collection["features"]
    if not features:
        raise ValueError("No features")
    properties = [feature.get("properties") or {} for feature in features]

    def ids(field):
        counts = Counter(
            str(p[field]).strip()
            for p in properties
            if p.get(field) is not None and str(p[field]).strip() not in ("", "-")
        )
        return {
            "populated_features": sum(counts.values()),
            "unique_values": len(counts),
            "duplicate_groups": sum(count > 1 for count in counts.values()),
        }

    osm_ids = ids("osm_id")
    if osm_ids["populated_features"] != len(features) or osm_ids["duplicate_groups"]:
        raise ValueError("Snapshot needs an explicit policy for absent/duplicate OSM IDs")

    geometries = []
    details = {}
    vertices = 0
    bounds = [180, 90, -180, -90]
    for feature in features:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "LineString":
            raise ValueError("This snapshot inspector currently expects LineString")
        coordinates = geometry["coordinates"]
        if len(coordinates) < 2:
            raise ValueError("LineString has fewer than two coordinates")
        for coordinate in coordinates:
            lon, lat = coordinate[:2]
            if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                raise ValueError("Coordinate outside WGS84 range")
            bounds = [min(bounds[0], lon), min(bounds[1], lat),
                      max(bounds[2], lon), max(bounds[3], lat)]
        vertices += len(coordinates)
        feature_id = "osm_" + str(feature["properties"]["osm_id"]).strip()
        geometries.append({"type": "Feature", "id": feature_id,
                           "properties": {}, "geometry": geometry})
        details[feature_id] = feature["properties"]

    return {
        "source_url": SOURCE_URL,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source_size": sizes(raw),
        "features": len(features),
        "geometry_types": dict(Counter(f["geometry"]["type"] for f in features)),
        "vertices": vertices,
        "bbox_lon_lat": bounds,
        "property_presence": dict(sorted(Counter(k for p in properties for k in p).items())),
        "osm_id": osm_ids,
        "munichways_id": ids("munichways_id"),
        "osm_class_bicycle": dict(sorted(Counter(str(p.get("osm_class_bicycle")) for p in properties).items())),
        "color": dict(sorted(Counter(str(p.get("color")) for p in properties).items())),
        "proposed_geometry_size": sizes(encoded({"type": "FeatureCollection", "features": geometries})),
        "proposed_unsplit_details_size": sizes(encoded(details)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(inspect(args.source), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
