"""Build a reproducible Lua way-ID lookup from one V20 snapshot (build time only)."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

V20_URL = "https://www.munichways.de/App/IST_RadlVorrangNetz_MunichWays_V20.geojson"


def lua_lookup(contents):
    data = json.loads(contents)
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("Expected V20 FeatureCollection")
    ids = set()
    for feature in data["features"]:
        props = feature.get("properties") or {}
        if str(props.get("munichways_neuralgic_point", "")).strip().casefold() != "geheimtipp":
            continue
        value = props.get("osm_id")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if str(value).isdigit() and int(value) > 0:
            ids.add(int(value))
    if not ids:
        raise ValueError("V20 contains no Geheimtipp with a usable OSM way ID")
    checksum = hashlib.sha256(contents).hexdigest()
    return "-- V20 sha256: " + checksum + "\nreturn {\n" + "".join(
        f"  [{way}]=true,\n" for way in sorted(ids)
    ) + "}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=V20_URL)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.source.startswith("https://"):
        with urlopen(args.source, timeout=60) as response:
            contents = response.read()
    else:
        contents = Path(args.source).read_bytes()
    Path(args.output).write_text(lua_lookup(contents), encoding="utf-8")


if __name__ == "__main__":
    main()
