"""Rebuild the committed integration fixture from contracts and frozen OSM ways."""

from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent


def build():
    osm = ET.Element("osm", version="0.6", generator="RadlNavi issue 22 fixture")
    cases = json.loads((ROOT / "cycling-attribute-cases.json").read_text())
    for index, case in enumerate(cases):
        if "profile" not in case:
            continue
        node_id = 900000 + index * 10
        lat = 50 + index / 100
        for offset, lon in enumerate((11, 11.001)):
            ET.SubElement(osm, "node", id=str(node_id + offset), lat=f"{lat:.4f}", lon=str(lon))
        way = ET.SubElement(osm, "way", id=str(node_id))
        for offset in (0, 1):
            ET.SubElement(way, "nd", ref=str(node_id + offset))
        for key, value in {**case["tags"], "class:bicycle": "2", "name": case["id"]}.items():
            ET.SubElement(way, "tag", k=key, v=value)
    # A real choice: the surfaced cycleway wins forward, the paved detour
    # wins backward. Width is intentionally too small to be plausible, proving
    # that it cannot create a cost or access exclusion.
    for offset, (lon, lat) in enumerate(((11, 50.4), (11.002, 50.4), (11.001, 50.4006))):
        ET.SubElement(osm, "node", id=str(950000 + offset), lat=str(lat), lon=str(lon))
    for way_id, refs, tags in (
        (950000, (950000, 950001), {
            "highway": "residential", "cycleway:both": "track", "surface": "sett",
            "cycleway:right:surface": "asphalt", "cycleway:left:surface": "sett",
            "cycleway:both:width": "0.1", "name": "Directional shortcut",
        }),
        (950001, (950000, 950002, 950001), {
            "highway": "cycleway", "surface": "asphalt", "name": "Paved detour",
        }),
    ):
        way = ET.SubElement(osm, "way", id=str(way_id))
        for ref in refs:
            ET.SubElement(way, "nd", ref=str(ref))
        for key, value in {**tags, "class:bicycle": "2"}.items():
            ET.SubElement(way, "tag", k=key, v=value)
    snapshot = ET.parse(ROOT.parents[1] / "docs/issue-22-analysis/munich-examples.osm")
    for element in snapshot.getroot():
        if element.tag in {"node", "way"}:
            osm.append(deepcopy(element))
    # Keep every node before ways, including the original OSM nodes.
    osm[:] = sorted(osm, key=lambda element: element.tag != "node")
    ET.indent(osm)
    return ET.tostring(osm, encoding="utf-8", xml_declaration=True) + b"\n"


if __name__ == "__main__":
    target = ROOT / "fixtures/cycling-attributes.osm"
    target.write_bytes(build())
    print(f"Wrote {target.name}")
