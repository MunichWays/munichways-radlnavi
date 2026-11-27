"""Local OSM extract: a tiny self-written PBF, imported and queried like Overpass."""
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from test_discovery import crossing
from junction_review import osm_local
from junction_review.discovery import discover, prepare


def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7f
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def zigzag(value):
    return (value << 1) ^ (value >> 63)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    return varint(number << 3 | 2) + varint(len(value)) + value


def packed(values):
    return b''.join(varint(v) for v in values)


def delta(values):
    out, previous = [], 0
    for value in values:
        out.append(zigzag(value - previous))
        previous = value
    return packed(out)


def blob(kind, payload):
    data = field(2, len(payload)) + field(3, zlib.compress(payload))
    header = field(1, kind.encode()) + field(3, len(data))
    return struct.pack('>I', len(header)) + header + data


def to_pbf(raw, path):
    strings = ['']
    def sid(text):
        if text not in strings:
            strings.append(text)
        return strings.index(text)
    nodes = sorted((e for e in raw['elements'] if e['type'] == 'node'), key=lambda e: e['id'])
    ways = sorted((e for e in raw['elements'] if e['type'] == 'way' and 'tags' in e), key=lambda e: e['id'])
    relations = [dict(type='relation', id=77, tags=dict(type='restriction', restriction='no_left_turn'),
                      members=[dict(type='way', ref=10, role='from'), dict(type='node', ref=1, role='via'),
                               dict(type='way', ref=20, role='to')])]
    keyvals = []
    for node in nodes:
        for key, value in node.get('tags', {}).items():
            keyvals += [sid(key), sid(value)]
        keyvals.append(0)
    dense = (field(1, delta([n['id'] for n in nodes])) + field(8, delta([round(n['lat'] * 1e7) for n in nodes]))
             + field(9, delta([round(n['lon'] * 1e7) for n in nodes])) + field(10, packed(keyvals)))
    way_messages = b''.join(field(3, field(1, w['id']) + field(2, packed([sid(k) for k in w['tags']]))
                                  + field(3, packed([sid(v) for v in w['tags'].values()])) + field(8, delta(w['nodes'])))
                            for w in ways)
    relation_messages = b''.join(field(4, field(1, r['id']) + field(2, packed([sid(k) for k in r['tags']]))
                                       + field(3, packed([sid(v) for v in r['tags'].values()]))
                                       + field(8, packed([sid(m['role']) for m in r['members']]))
                                       + field(9, delta([m['ref'] for m in r['members']]))
                                       + field(10, packed([{'node': 0, 'way': 1}[m['type']] for m in r['members']])))
                                 for r in relations)
    groups = field(2, field(2, dense)) + field(2, way_messages) + field(2, relation_messages)
    table = field(1, b''.join(field(1, s.encode()) for s in strings))
    header = field(4, b'OsmSchema-V0.6') + field(4, b'DenseNodes') + field(32, 1795000000)
    Path(path).write_bytes(blob('OSMHeader', header) + blob('OSMData', table + groups))


AREA = dict(type='Polygon', coordinates=[[[10.995, 47.995], [11.005, 47.995], [11.005, 48.005], [10.995, 48.005], [10.995, 47.995]]])


class LocalOsmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = crossing()
        self.pbf = Path(self.temp.name) / 'tiny.osm.pbf'
        self.db = Path(self.temp.name) / 'osm.sqlite'
        to_pbf(self.raw, self.pbf)
        osm_local.import_extract(self.pbf, self.db, coverage=(10.95, 47.95, 11.05, 48.05), workers=1, progress=lambda text: None)
        self.local = osm_local.LocalOsm(self.db)
        self.addCleanup(self.local.close)  # Windows: close before the temp folder is removed.

    def test_import_keeps_highways_nodes_restrictions_and_timestamp(self):
        info = self.local.info()
        self.assertEqual((info['ways'], info['restrictions']), (2, 1))
        self.assertEqual(info['timestamp'], '2026-11-18T11:06:40Z')

    def test_query_matches_overpass_layout_and_discovery_result(self):
        selection = dict(name='Test', area=AREA)
        raw = self.local.query(selection)
        roads = [e['id'] for e in raw['elements'] if set(e) == {'type', 'id'}]
        self.assertEqual(roads, [10, 20])
        way = next(e for e in raw['elements'] if e['type'] == 'way' and 'tags' in e and e['id'] == 10)
        self.assertEqual(way['nodes'], [3, 1, 2])
        self.assertEqual(way['geometry'][1], dict(lat=48.0, lon=11.0))
        relation = next(e for e in raw['elements'] if e['type'] == 'relation')
        self.assertEqual([(m['type'], m['ref'], m['role']) for m in relation['members']],
                         [('way', 10, 'from'), ('node', 1, 'via'), ('way', 20, 'to')])
        expected = dict(self.raw, elements=[dict(type='way', id=10), dict(type='way', id=20)] + self.raw['elements'])
        self.assertEqual([s['gates'] for s in prepare(raw, selection)[0]], [s['gates'] for s in prepare(expected, selection)[0]])

    def test_selection_outside_coverage_or_by_relation_is_not_answered_locally(self):
        outside = dict(type='Polygon', coordinates=[[[11.2, 48.2], [11.3, 48.2], [11.3, 48.3], [11.2, 48.2]]])
        self.assertFalse(self.local.supports(dict(area=outside)))
        self.assertFalse(self.local.supports(dict(relationId=123)))
        with self.assertRaises(osm_local.LocalUnavailable):
            self.local.query(dict(area=outside))

    def test_discover_prefers_local_extract_and_records_source(self):
        original = osm_local.default_path
        osm_local.default_path = lambda: self.db
        self.addCleanup(setattr, osm_local, 'default_path', original)
        osm_local._cached.clear()
        self.addCleanup(lambda: (osm_local._cached.pop('db').close() if 'db' in osm_local._cached else None, osm_local._cached.clear()))
        data, raw = discover(dict(name='Test', area=AREA))
        self.assertEqual(data['source']['osmSource']['kind'], 'local-extract')
        self.assertEqual(data['source']['osmRetrievedAt'], '2026-11-18T11:06:40Z')
        with self.assertRaises(ValueError):
            discover(dict(relationId=123, name='x'), source='local')


if __name__ == '__main__':
    unittest.main()
