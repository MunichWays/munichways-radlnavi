"""Local OSM extract: one-time PBF import into SQLite and Overpass-compatible queries.

Standard library only. The import reads a Geofabrik ``.osm.pbf`` (protobuf decoded
by hand, zlib blobs, decoding spread over CPU cores), keeps every highway way, all
nodes of those ways with their tags and all ``type=restriction`` relations inside a
configurable region, and writes them to SQLite with an R-tree index.

``LocalOsm.query(selection)`` answers the same question as the Overpass query from
``discovery.selection_query``: highways in the selected area (``out ids`` markers),
highways within 130 m of them, their nodes and restriction relations, in Overpass
JSON layout. Ways whose geometry is not completely inside the extract are dropped
at import; selections outside the covered region are refused, never cut off.
"""
from array import array
from bisect import bisect_left
from datetime import datetime, timezone
import json
import math
from multiprocessing import Pool
import os
from pathlib import Path
import sqlite3
import struct
from threading import Lock
from urllib.request import Request, urlopen
import zlib

DEFAULT_URL = 'https://download.geofabrik.de/europe/germany/bayern/oberbayern-latest.osm.pbf'
# Munich city (all 25 districts) plus margin; nodes are kept in the wider box so
# that ways crossing the covered edge still have complete geometry.
DEFAULT_COVERAGE = (11.30, 48.02, 11.80, 48.29)
NODE_MARGIN = (0.07, 0.045)
AROUND_METERS = 130
SCHEMA = 1
USER_AGENT = 'JunctionReview/1.0 (local OSM extract import)'


class LocalUnavailable(ValueError):
    pass


def default_path():
    configured = os.environ.get('JUNCTION_REVIEW_OSM')
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / '.local/junction-review/osm/osm.sqlite'


# ---------------------------------------------------------------- protobuf --

def _varint(buf, pos):
    result = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7f) << shift
        if byte < 0x80:
            return result, pos
        shift += 7


def _fields(buf):
    pos, end = 0, len(buf)
    while pos < end:
        key, pos = _varint(buf, pos)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _varint(buf, pos)
        elif wire == 2:
            length, pos = _varint(buf, pos)
            value = buf[pos:pos + length]
            pos += length
        elif wire == 1:
            value, pos = buf[pos:pos + 8], pos + 8
        elif wire == 5:
            value, pos = buf[pos:pos + 4], pos + 4
        else:
            raise ValueError('Nicht unterstütztes Protobuf-Format in der PBF-Datei.')
        yield field, value


def _packed(buf):
    out, pos, end = [], 0, len(buf)
    append = out.append
    while pos < end:
        byte = buf[pos]
        pos += 1
        if byte < 0x80:
            append(byte)
            continue
        result, shift = byte & 0x7f, 7
        while True:
            byte = buf[pos]
            pos += 1
            result |= (byte & 0x7f) << shift
            if byte < 0x80:
                break
            shift += 7
        append(result)
    return out


def _delta(buf):
    total, out = 0, []
    append = out.append
    for value in _packed(buf):
        total += (value >> 1) ^ -(value & 1)
        append(total)
    return out


def _signed64(value):
    return value - (1 << 64) if value >= 1 << 63 else value


def _blob_data(blob):
    raw = compressed = None
    for field, value in _fields(blob):
        if field == 1:
            raw = value
        elif field == 3:
            compressed = value
    if raw is not None:
        return raw
    if compressed is not None:
        return zlib.decompress(compressed)
    raise ValueError('Nicht unterstützte PBF-Kompression (nur zlib).')


def blobs(path):
    with open(path, 'rb') as stream:
        while True:
            head = stream.read(4)
            if not head:
                return
            header = dict(_fields(stream.read(struct.unpack('>I', head)[0])))
            yield header[1].decode(), stream.read(header[3])


def read_header(path):
    for kind, blob in blobs(path):
        if kind != 'OSMHeader':
            continue
        info = {}
        for field, value in _fields(_blob_data(blob)):
            if field == 4:
                info.setdefault('required', []).append(value.decode())
            elif field == 5:
                info.setdefault('optional', []).append(value.decode())
            elif field == 32:
                info['timestamp'] = datetime.fromtimestamp(value, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            elif field == 34:
                info['replication'] = value.decode()
        unknown = set(info.get('required', [])) - {'OsmSchema-V0.6', 'DenseNodes'}
        if unknown:
            raise ValueError('PBF braucht nicht unterstützte Merkmale: ' + ', '.join(sorted(unknown)))
        return info
    raise ValueError('PBF-Datei ohne OSMHeader.')


def decode_block(args):
    """Worker: one OSMData blob -> nodes in box, highway ways, restriction relations."""
    blob, box = args
    west, south, east, north = box
    block = _blob_data(blob)
    strings, groups, granularity, lat_offset, lon_offset = [], [], 100, 0, 0
    for field, value in _fields(block):
        if field == 1:
            strings = [s.decode('utf-8') for f, s in _fields(value) if f == 1]
        elif field == 2:
            groups.append(value)
        elif field == 17:
            granularity = value
        elif field == 19:
            lat_offset = _signed64(value)
        elif field == 20:
            lon_offset = _signed64(value)
    index = {s: i for i, s in enumerate(strings)}
    highway, kind_key, restriction = index.get('highway'), index.get('type'), index.get('restriction')
    nodes, ways, relations = [], [], []

    def to7(value, offset):  # nanodegrees -> 1e-7 degree integers (granularity 100)
        return (offset + granularity * value) // 100

    def tags(keys, values):
        return {strings[k]: strings[v] for k, v in zip(keys, values)}

    for group in groups:
        for field, value in _fields(group):
            if field == 2:  # DenseNodes
                ids = lats = lons = None
                keyvals = []
                for f, v in _fields(value):
                    if f == 1:
                        ids = _delta(v)
                    elif f == 8:
                        lats = _delta(v)
                    elif f == 9:
                        lons = _delta(v)
                    elif f == 10:
                        keyvals = _packed(v)
                position = 0
                for i, identifier in enumerate(ids):
                    pairs = None
                    if keyvals:
                        start = position
                        while keyvals[position]:
                            position += 2
                        if position > start:
                            pairs = keyvals[start:position]
                        position += 1
                    lat, lon = to7(lats[i], lat_offset), to7(lons[i], lon_offset)
                    if south <= lat <= north and west <= lon <= east:
                        nodes.append((identifier, lat, lon, tags(pairs[0::2], pairs[1::2]) if pairs else None))
            elif field == 1:  # plain Node
                data = dict(_fields(value))
                keys, values = _packed(data.get(2, b'')), _packed(data.get(3, b''))
                identifier = (data[1] >> 1) ^ -(data[1] & 1)
                lat = to7((data[8] >> 1) ^ -(data[8] & 1), lat_offset)
                lon = to7((data[9] >> 1) ^ -(data[9] & 1), lon_offset)
                if south <= lat <= north and west <= lon <= east:
                    nodes.append((identifier, lat, lon, tags(keys, values) if keys else None))
            elif field == 3 and highway is not None:  # Way
                identifier, keys, values, refs = 0, [], [], b''
                for f, v in _fields(value):
                    if f == 1:
                        identifier = v
                    elif f == 2:
                        keys = _packed(v)
                    elif f == 3:
                        values = _packed(v)
                    elif f == 8:
                        refs = v
                if highway in keys:
                    ways.append((identifier, tags(keys, values), _delta(refs)))
            elif field == 4 and kind_key is not None and restriction is not None:  # Relation
                identifier, keys, values, roles, members, types = 0, [], [], [], [], []
                for f, v in _fields(value):
                    if f == 1:
                        identifier = v
                    elif f == 2:
                        keys = _packed(v)
                    elif f == 3:
                        values = _packed(v)
                    elif f == 8:
                        roles = _packed(v)
                    elif f == 9:
                        members = _delta(v)
                    elif f == 10:
                        types = _packed(v)
                found = dict(zip(keys, values))
                if found.get(kind_key) == restriction:
                    names = ('node', 'way', 'relation')
                    ways_or_nodes = [dict(type=names[t], ref=m, role=strings[r]) for t, m, r in zip(types, members, roles)]
                    relations.append((identifier, tags(keys, values), ways_or_nodes))
    return nodes, ways, relations


# ------------------------------------------------------------------ import --

def download(url, target, progress=print):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    request = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(request, timeout=60) as response, open(partial, 'wb') as out:
        total, done, last = int(response.headers.get('Content-Length') or 0), 0, 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if done - last >= 25 << 20:
                last = done
                progress(f'Download {done >> 20} MB' + (f' von {total >> 20} MB' if total else ''))
    os.replace(partial, target)
    return target


def import_extract(pbf, database=None, coverage=DEFAULT_COVERAGE, workers=None, progress=print):
    """PBF -> SQLite. Writes to a temporary file and replaces the database atomically."""
    pbf, database = Path(pbf), Path(database or default_path())
    header = read_header(pbf)
    west, south, east, north = coverage
    box7 = tuple(round(v * 1e7) for v in (west - NODE_MARGIN[0], south - NODE_MARGIN[1],
                                          east + NODE_MARGIN[0], north + NODE_MARGIN[1]))
    node_ids, node_lat, node_lon = array('q'), array('i'), array('i')
    node_tags, ways, relations = {}, [], []
    ordered, blocks, started = True, 0, datetime.now()
    tasks = ((blob, box7) for kind, blob in blobs(pbf) if kind == 'OSMData')
    with Pool(workers or os.cpu_count()) as pool:
        for found_nodes, found_ways, found_relations in pool.imap(decode_block, tasks, chunksize=2):
            blocks += 1
            for identifier, lat, lon, tags in found_nodes:
                if node_ids and identifier < node_ids[-1]:
                    ordered = False
                node_ids.append(identifier)
                node_lat.append(lat)
                node_lon.append(lon)
                if tags:
                    node_tags[identifier] = json.dumps(tags, ensure_ascii=False, separators=(',', ':'))
            ways.extend(found_ways)
            relations.extend(found_relations)
            if blocks % 500 == 0:
                progress(f'{blocks} Datenblöcke gelesen · {len(node_ids):,} Knoten im Bereich · {len(ways):,} Straßenwege')
    if not ordered:
        order = sorted(range(len(node_ids)), key=node_ids.__getitem__)
        node_ids = array('q', (node_ids[i] for i in order))
        node_lat = array('i', (node_lat[i] for i in order))
        node_lon = array('i', (node_lon[i] for i in order))
    progress(f'Gelesen in {(datetime.now() - started).seconds} s; schreibe SQLite …')

    def locate(identifier):
        i = bisect_left(node_ids, identifier)
        return i if i < len(node_ids) and node_ids[i] == identifier else -1

    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_name(database.name + '.tmp')
    if temporary.exists():
        temporary.unlink()
    con = sqlite3.connect(temporary)
    con.executescript('''
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE nodes(id INTEGER PRIMARY KEY, lat INTEGER, lon INTEGER, tags TEXT);
        CREATE TABLE ways(id INTEGER PRIMARY KEY, tags TEXT, refs TEXT);
        CREATE VIRTUAL TABLE way_box USING rtree(id, min_lon, max_lon, min_lat, max_lat);
        CREATE TABLE relations(id INTEGER PRIMARY KEY, tags TEXT, members TEXT);
        CREATE TABLE relation_ways(way INTEGER, relation INTEGER);
    ''')
    kept, needed, incomplete = set(), set(), 0
    batch_ways, batch_boxes = [], []
    for identifier, tags, refs in ways:
        positions = [locate(r) for r in refs]
        if len(refs) < 2 or min(positions) < 0:
            if any(p >= 0 for p in positions):
                incomplete += 1  # Crosses the extract edge: drop, never truncate.
            continue
        lats = [node_lat[p] for p in positions]
        lons = [node_lon[p] for p in positions]
        kept.add(identifier)
        needed.update(refs)
        batch_ways.append((identifier, json.dumps(tags, ensure_ascii=False, separators=(',', ':')), json.dumps(refs)))
        batch_boxes.append((identifier, min(lons) / 1e7, max(lons) / 1e7, min(lats) / 1e7, max(lats) / 1e7))
    con.executemany('INSERT INTO ways VALUES (?,?,?)', batch_ways)
    con.executemany('INSERT INTO way_box VALUES (?,?,?,?,?)', batch_boxes)
    restriction_rows, member_rows = [], []
    for identifier, tags, members in relations:
        way_refs = {m['ref'] for m in members if m['type'] == 'way'}
        if not way_refs & kept:
            continue
        restriction_rows.append((identifier, json.dumps(tags, ensure_ascii=False, separators=(',', ':')), json.dumps(members, ensure_ascii=False)))
        member_rows.extend((w, identifier) for w in way_refs)
        needed.update(m['ref'] for m in members if m['type'] == 'node' and locate(m['ref']) >= 0)
    con.executemany('INSERT INTO relations VALUES (?,?,?)', restriction_rows)
    con.executemany('INSERT INTO relation_ways VALUES (?,?)', member_rows)
    con.executemany('INSERT INTO nodes VALUES (?,?,?,?)', ((n, node_lat[locate(n)], node_lon[locate(n)], node_tags.get(n))
                                                          for n in sorted(needed)))
    con.execute('CREATE INDEX relation_ways_way ON relation_ways(way)')
    meta = dict(schema=str(SCHEMA), source=pbf.name, sourceBytes=str(pbf.stat().st_size),
                timestamp=header.get('timestamp', ''), replication=header.get('replication', ''),
                importedAt=datetime.now(timezone.utc).isoformat(), coverage=json.dumps(list(coverage)),
                ways=str(len(kept)), nodes=str(len(needed)), restrictions=str(len(restriction_rows)),
                droppedEdgeWays=str(incomplete))
    con.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
    con.commit()
    con.close()
    os.replace(temporary, database)
    progress(f"Fertig: {len(kept):,} Straßenwege, {len(needed):,} Knoten, {len(restriction_rows):,} Abbiegeverbote · OSM-Stand {meta['timestamp'] or 'unbekannt'}")
    return meta


# ------------------------------------------------------------------- query --

def _meters(lat):
    return 111320 * math.cos(math.radians(lat)), 110540


def _inside(point, ring):
    x, y = point
    result = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            result = not result
    return result


def _crosses(a, b, c, d):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (side(a, b, c) > 0) != (side(a, b, d) > 0) and (side(c, d, a) > 0) != (side(c, d, b) > 0)


def _segment_distance(p, a, b, scale):
    ax, ay = (a[0] - p[0]) * scale[0], (a[1] - p[1]) * scale[1]
    bx, by = (b[0] - p[0]) * scale[0], (b[1] - p[1]) * scale[1]
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0 if not length else max(0, min(1, -(ax * dx + ay * dy) / length))
    return math.hypot(ax + t * dx, ay + t * dy)


def _segments_distance(a, b, c, d, scale):
    if _crosses(a, b, c, d):
        return 0
    return min(_segment_distance(a, c, d, scale), _segment_distance(b, c, d, scale),
               _segment_distance(c, a, b, scale), _segment_distance(d, a, b, scale))


class _Ring:
    """Polygon ring with horizontal bands of edges for fast inside/crossing tests."""
    def __init__(self, points, bands=256):
        self.edges = [(a, b) for a, b in zip(points, points[1:] + points[:1]) if a != b]
        self.south, north = min(p[1] for p in points), max(p[1] for p in points)
        self.height = (north - self.south) / bands or 1e-9
        self.bands = [[] for _ in range(bands)]
        for edge in self.edges:
            low, high = sorted((edge[0][1], edge[1][1]))
            for band in range(self._band(low), self._band(high) + 1):
                self.bands[band].append(edge)

    def _band(self, y):
        return max(0, min(len(self.bands) - 1, int((y - self.south) / self.height)))

    def inside(self, point):
        x, y = point
        result = False
        for (x1, y1), (x2, y2) in self.bands[self._band(y)]:
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                result = not result
        return result

    def crosses(self, a, b):
        seen = set()
        low, high = sorted((a[1], b[1]))
        for band in range(self._band(low), self._band(high) + 1):
            for edge in self.bands[band]:
                if id(edge) not in seen:
                    seen.add(id(edge))
                    if _crosses(a, b, *edge):
                        return True
        return False


class LocalOsm:
    def __init__(self, path=None):
        self.path = Path(path or default_path())
        if not self.path.exists():
            raise LocalUnavailable('Kein lokaler OSM-Auszug vorhanden. Einmalig „run.py osm-import“ ausführen.')
        self.con = sqlite3.connect(f'file:{self.path.as_posix()}?mode=ro', uri=True, check_same_thread=False)
        self.lock = Lock()
        self.meta = dict(self.con.execute('SELECT key, value FROM meta'))
        if self.meta.get('schema') != str(SCHEMA):
            raise LocalUnavailable('Lokaler OSM-Auszug hat ein altes Format. Bitte „run.py osm-import“ erneut ausführen.')
        self.coverage = tuple(json.loads(self.meta['coverage']))

    def close(self):
        self.con.close()

    def info(self):
        return dict(available=True, timestamp=self.meta.get('timestamp'), source=self.meta.get('source'),
                    importedAt=self.meta.get('importedAt'), coverage=list(self.coverage),
                    ways=int(self.meta.get('ways', 0)), restrictions=int(self.meta.get('restrictions', 0)))

    def rings(self, selection):
        from .districts import district_feature
        if selection.get('districtId'):
            return [polygon[0] for polygon in district_feature(selection['districtId'])['geometry']['coordinates']]
        if selection.get('area'):
            return [selection['area']['coordinates'][0]]
        raise LocalUnavailable('Gesuchte Verwaltungsgebiete brauchen die Grenze von Overpass; '
                               'Stadtbezirk wählen oder Fläche einzeichnen, oder Overpass verwenden.')

    def supports(self, selection):
        try:
            rings = self.rings(selection)
        except LocalUnavailable:
            return False
        west, south, east, north = self.coverage
        margin_lon, margin_lat = AROUND_METERS / 111320 / math.cos(math.radians(48.1)) * 2, AROUND_METERS / 110540 * 2
        return all(west + margin_lon <= x <= east - margin_lon and south + margin_lat <= y <= north - margin_lat
                   for ring in rings for x, y in ring)

    def _ways_in_box(self, west, south, east, north):
        rows = self.con.execute('SELECT id FROM way_box WHERE max_lon >= ? AND min_lon <= ? AND max_lat >= ? AND min_lat <= ?',
                                (west, east, south, north))
        return [r[0] for r in rows]

    def _load_ways(self, ids):
        ways = {}
        ids = list(ids)
        for i in range(0, len(ids), 900):
            chunk = ids[i:i + 900]
            for identifier, tags, refs in self.con.execute(
                    f'SELECT id, tags, refs FROM ways WHERE id IN ({",".join("?" * len(chunk))})', chunk):
                ways[identifier] = dict(id=identifier, tags=json.loads(tags), refs=json.loads(refs))
        need = sorted({r for w in ways.values() for r in w['refs']})
        nodes = self._load_nodes(need)
        for way in ways.values():
            way['coords'] = [(nodes[r]['lon'], nodes[r]['lat']) for r in way['refs']]
        return ways, nodes

    def _load_nodes(self, ids):
        nodes = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i:i + 900]
            for identifier, lat, lon, tags in self.con.execute(
                    f'SELECT id, lat, lon, tags FROM nodes WHERE id IN ({",".join("?" * len(chunk))})', chunk):
                nodes[identifier] = dict(lat=lat / 1e7, lon=lon / 1e7, tags=json.loads(tags) if tags else None)
        return nodes

    def query(self, selection):
        if not self.supports(selection):
            raise LocalUnavailable('Die Auswahl liegt nicht vollständig im lokalen OSM-Auszug. Overpass verwenden.')
        rings = [[tuple(p) for p in ring[:-1] if p] if ring[0] == ring[-1] else [tuple(p) for p in ring] for ring in self.rings(selection)]
        with self.lock:
            xs = [p[0] for ring in rings for p in ring]
            ys = [p[1] for ring in rings for p in ring]
            candidates, _ = self._load_ways(self._ways_in_box(min(xs), min(ys), max(xs), max(ys)))
            indexed = [_Ring(ring) for ring in rings]
            roads = set()
            for way in candidates.values():
                coords = way['coords']
                if any(r.inside(p) for p in coords for r in indexed) or any(
                        r.crosses(a, b) for a, b in zip(coords, coords[1:]) for r in indexed):
                    roads.add(way['id'])
            scale = _meters(sum(ys) / len(ys))
            dx, dy = AROUND_METERS / scale[0], AROUND_METERS / scale[1]
            nearby, _ = self._load_ways(self._ways_in_box(min(xs) - dx, min(ys) - dy, max(xs) + dx, max(ys) + dy))
            # Grid of road segments for the 130 m "around" test.
            cell = 0.002
            grid = {}
            for identifier in roads:
                coords = nearby[identifier]['coords']
                for a, b in zip(coords, coords[1:]):
                    for gx in range(int(math.floor((min(a[0], b[0]) - dx) / cell)), int(math.floor((max(a[0], b[0]) + dx) / cell)) + 1):
                        for gy in range(int(math.floor((min(a[1], b[1]) - dy) / cell)), int(math.floor((max(a[1], b[1]) + dy) / cell)) + 1):
                            grid.setdefault((gx, gy), []).append((a, b))
            selected = set(roads)
            for identifier, way in nearby.items():
                if identifier in selected:
                    continue
                coords = way['coords']
                found = False
                for a, b in zip(coords, coords[1:]):
                    keys = {(gx, gy) for gx in range(int(math.floor(min(a[0], b[0]) / cell)), int(math.floor(max(a[0], b[0]) / cell)) + 1)
                            for gy in range(int(math.floor(min(a[1], b[1]) / cell)), int(math.floor(max(a[1], b[1]) / cell)) + 1)}
                    if any(_segments_distance(a, b, c, d, scale) <= AROUND_METERS for key in keys for c, d in grid.get(key, ())):
                        found = True
                        break
                if found:
                    selected.add(identifier)
            ways = {i: nearby[i] for i in selected}
            relation_ids = set()
            ids = sorted(selected)
            for i in range(0, len(ids), 900):
                chunk = ids[i:i + 900]
                relation_ids.update(r[0] for r in self.con.execute(
                    f'SELECT relation FROM relation_ways WHERE way IN ({",".join("?" * len(chunk))})', chunk))
            relations = []
            for identifier in sorted(relation_ids):
                tags, members = self.con.execute('SELECT tags, members FROM relations WHERE id = ?', (identifier,)).fetchone()
                relations.append(dict(id=identifier, tags=json.loads(tags), members=json.loads(members)))
            node_ids = sorted({r for w in ways.values() for r in w['refs']} |
                              {m['ref'] for rel in relations for m in rel['members'] if m['type'] == 'node'})
            nodes = self._load_nodes(node_ids)
        return self._overpass_json(sorted(roads), ways, nodes, relations)

    def _overpass_json(self, roads, ways, nodes, relations):
        elements = [dict(type='way', id=i) for i in roads]
        for identifier in sorted(nodes):
            node = nodes[identifier]
            element = dict(type='node', id=identifier, lat=node['lat'], lon=node['lon'])
            if node['tags']:
                element['tags'] = node['tags']
            elements.append(element)
        for identifier in sorted(ways):
            way = ways[identifier]
            lats = [nodes[r]['lat'] for r in way['refs']]
            lons = [nodes[r]['lon'] for r in way['refs']]
            elements.append(dict(type='way', id=identifier,
                                 bounds=dict(minlat=min(lats), minlon=min(lons), maxlat=max(lats), maxlon=max(lons)),
                                 nodes=way['refs'], geometry=[dict(lat=nodes[r]['lat'], lon=nodes[r]['lon']) for r in way['refs']],
                                 tags=way['tags']))
        for relation in relations:
            members = []
            for m in relation['members']:
                member = dict(m)
                if m['type'] == 'way' and m['ref'] in ways:
                    member['geometry'] = [dict(lat=nodes[r]['lat'], lon=nodes[r]['lon']) for r in ways[m['ref']]['refs']]
                elif m['type'] == 'node' and m['ref'] in nodes:
                    member.update(lat=nodes[m['ref']]['lat'], lon=nodes[m['ref']]['lon'])
                members.append(member)
            elements.append(dict(type='relation', id=relation['id'], members=members, tags=relation['tags']))
        return dict(version=0.6, generator='JunctionReview local OSM extract',
                    osm3s=dict(timestamp_osm_base=self.meta.get('timestamp'),
                               copyright='The data included in this document is from www.openstreetmap.org. '
                                         'The data is made available under ODbL.'),
                    elements=elements)


_cached = {}


def open_default():
    """Shared read-only handle, reopened when the database file changes; None if absent."""
    path = default_path()
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return None
    if _cached.get('stamp') != stamp:
        try:
            _cached.update(stamp=stamp, db=LocalOsm(path))
        except LocalUnavailable:
            return None
    return _cached['db']
