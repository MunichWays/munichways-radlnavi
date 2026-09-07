import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.geo_store import __initialize_geo_store as initialize_geo_store


class GeoStoreBuildTest(unittest.TestCase):
    def test_import_retains_occurrences_and_uses_covering_lookup(self):
        # A closed way and a second way share the same node: lookup must retain
        # every candidate, while the ordered way payload retains the loop.
        fixture = """<osm version="0.6">
          <node id="1" lat="48" lon="11"/>
          <node id="2" lat="48.001" lon="11.001"/>
          <way id="10"><nd ref="1"/><nd ref="2"/><nd ref="1"/>
            <tag k="highway" v="cycleway"/></way>
          <way id="20"><nd ref="1"/><nd ref="2"/>
            <tag k="surface" v="gravel"/></way>
        </osm>"""
        with tempfile.TemporaryDirectory() as folder, sqlite3.connect(":memory:") as db:
            path = Path(folder) / "fixture.osm"
            path.write_text(fixture)
            initialize_geo_store(db, str(path))
            query = "SELECT DISTINCT way_id FROM node_to_ways WHERE node_id IN (?, ?)"
            self.assertEqual({10, 20}, {row[0] for row in db.execute(query, (1, 2))})
            self.assertEqual(
                "[1, 2, 1]",
                db.execute("SELECT node_list FROM ways WHERE id=10").fetchone()[0],
            )
            self.assertEqual(
                5, db.execute("SELECT COUNT(*) FROM node_to_ways").fetchone()[0]
            )
            plan = " ".join(
                row[3] for row in db.execute("EXPLAIN QUERY PLAN " + query, (1, 2))
            )
            self.assertIn("COVERING INDEX", plan)
