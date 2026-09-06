"""Create the small analysis DB matching routing/tests/profile-fixture.osm."""

import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET


def build(source, destination):
    document = ET.parse(source).getroot()
    temporary = Path(str(destination) + ".new")
    with sqlite3.connect(temporary) as db:
        db.executescript(
            """
            CREATE TABLE nodes (id INTEGER PRIMARY KEY, lat FLOAT, lon FLOAT, tags TEXT);
            CREATE TABLE ways (id INTEGER PRIMARY KEY, node_list TEXT, tags TEXT);
            CREATE TABLE node_to_ways (node_id INTEGER, way_id INTEGER);
            CREATE INDEX node_to_ways_node_id ON node_to_ways(node_id);
        """
        )
        for element in document.findall("node"):
            tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
            db.execute(
                "INSERT INTO nodes VALUES (?, ?, ?, ?)",
                (
                    int(element.attrib["id"]),
                    float(element.attrib["lat"]),
                    float(element.attrib["lon"]),
                    json.dumps(tags),
                ),
            )
        for element in document.findall("way"):
            way = int(element.attrib["id"])
            nodes = [int(node.attrib["ref"]) for node in element.findall("nd")]
            tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
            db.execute(
                "INSERT INTO ways VALUES (?, ?, ?)",
                (way, json.dumps(nodes), json.dumps(tags)),
            )
            db.executemany(
                "INSERT INTO node_to_ways VALUES (?, ?)",
                [(node, way) for node in nodes],
            )
    db.close()
    temporary.replace(destination)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
