"""Real Munich regression: no implicit pushing against mapped cycling one-ways."""

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from test_direct_profile import successful


def forbidden_edges():
    root = ET.parse(Path(__file__).with_name("fixtures") / "munich-oneway.osm")
    edges = {}
    for way in root.findall("way"):
        tags = {tag.get("k"): tag.get("v") for tag in way.findall("tag")}
        direction = tags.get("oneway:bicycle", tags.get("oneway"))
        if direction not in ("yes", "1", "true", "-1"):
            continue
        if any(
            tags.get(key, "").startswith("opposite")
            for key in ("cycleway", "cycleway:left", "cycleway:right")
        ):
            continue
        nodes = [int(node.get("ref")) for node in way.findall("nd")]
        for a, b in zip(nodes, nodes[1:]):
            edges[(a, b) if direction == "-1" else (b, a)] = way.get("id")
    return edges


def check(endpoint):
    forbidden = forbidden_edges()
    for name, coordinates in (
        ("Arnulfstrasse", "11.554569,48.142131;11.562248,48.141745"),
        ("Lenbachplatz", "11.565394,48.140805;11.571082,48.141976"),
    ):
        route = successful(endpoint, coordinates)
        violations = []
        for leg in route["legs"]:
            nodes = leg["annotation"]["nodes"]
            violations.extend(
                forbidden[a, b] for a, b in zip(nodes, nodes[1:]) if (a, b) in forbidden
            )
        assert not violations, (name, sorted(set(violations)))
        print(name, round(route["distance"], 1), "metres; no forbidden reverse edges")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    check(parser.parse_args().endpoint)
