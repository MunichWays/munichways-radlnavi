"""Refresh the public Overpass snapshots for RadlNavi issue #22 (stdlib only)."""

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://overpass-api.de/api/interpreter"


def fetch(query):
    request = Request(
        ENDPOINT,
        data=urlencode({"data": query}).encode(),
        headers={"User-Agent": "MunichWays-RadlNavi-Issue22-Analysis/1.0"},
    )
    with urlopen(request, timeout=150) as response:
        return response.read()


def json_snapshot(query_name, output_name):
    data = json.loads(fetch((ROOT / query_name).read_text(encoding="utf-8")))
    if data.get("remark"):
        raise RuntimeError(data["remark"])
    (ROOT / output_name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


def main():
    data = json_snapshot("munich-side-tags.overpassql", "munich-side-tags.json")
    ids = sorted(item["id"] for item in data["elements"] if item["type"] == "way")
    timestamp = data["osm3s"]["timestamp_osm_base"]
    if ids:
        # Freeze geometries at the same OSM timestamp as the tag inventory.
        query = (
            f'[out:xml][timeout:120][date:"{timestamp}"];\n'
            f'way(id:{",".join(map(str, ids))});\n(._;>;);out meta;\n'
        )
        (ROOT / "munich-examples.overpassql").write_text(query, encoding="utf-8")
        import xml.etree.ElementTree as ET

        raw = fetch(query)
        osm = ET.fromstring(raw)
        if osm.tag != "osm" or osm.find("remark") is not None:
            raise RuntimeError("Incomplete Overpass XML response")
        found = {int(way.attrib["id"]) for way in osm.findall("way")}
        nodes = {node.attrib["id"] for node in osm.findall("node")}
        if found != set(ids) or any(
            nd.attrib["ref"] not in nodes for nd in osm.findall("way/nd")
        ):
            raise RuntimeError("Missing ways or geometry nodes")
        # Contributor names/IDs are unnecessary for routing acceptance fixtures.
        for element in osm:
            element.attrib.pop("user", None)
            element.attrib.pop("uid", None)
        ET.ElementTree(osm).write(
            ROOT / "munich-examples.osm", encoding="utf-8", xml_declaration=True
        )
    print(f"Saved {len(ids)} ways at OSM timestamp {timestamp}")


if __name__ == "__main__":
    main()
