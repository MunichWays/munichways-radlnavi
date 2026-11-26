"""Deterministic OSM discovery and conservative, routing-neutral review drafts."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import re

from .geometry import distance, inside, intersection, point
from .model import digest, validate_area, validate_dataset
from .osm_client import query_osm
from .districts import district_feature
from .cycling import direction

ALGORITHM = 'osm-four-arm-v1'
MAJOR = {'primary', 'secondary', 'tertiary', 'primary_link', 'secondary_link', 'tertiary_link'}


def search_areas(name, fetch=query_osm):
    if not isinstance(name, str):
        raise ValueError('Bitte einen Stadt- oder Stadtteilnamen eingeben.')
    name = name.strip()
    if not 2 <= len(name) <= 100:
        raise ValueError('Bitte einen Stadt- oder Stadtteilnamen mit 2–100 Zeichen eingeben.')
    # JSON quoting also safely quotes an Overpass QL string (no query interpolation).
    data = fetch('[out:json][timeout:25];rel[boundary=administrative][name~' + json.dumps('^' + re.escape(name) + '$', ensure_ascii=False) + ',i];out tags bb;')
    return area_results(data)


def areas_at(location, fetch=query_osm):
    point(location)
    lon, lat = location
    return area_results(fetch(f'[out:json][timeout:25];is_in({lat:.7f},{lon:.7f})->.a;'
                              'rel(pivot.a)[boundary=administrative][admin_level~"^(6|7|8|9|10|11)$"][name];out tags bb;'))


def area_boundary(relation_id, fetch=query_osm):
    if type(relation_id) is not int or relation_id <= 0:
        raise ValueError('Ungültige Gebietsrelation.')
    results = area_results(fetch(f'[out:json][timeout:35];rel({relation_id})[boundary=administrative];out geom;'))
    if not results or not results[0]['outlines']:
        raise ValueError('Für dieses Gebiet wurde keine Grenze gefunden. Bitte eine Fläche einzeichnen.')
    return results[0]


def area_results(data):
    return [dict(id=e['id'], name=e['tags'].get('name', 'Gebiet'),
                 level=e['tags'].get('admin_level'), bounds=e.get('bounds'),
                 outlines=[[[p['lon'], p['lat']] for p in m['geometry']] for m in e.get('members', []) if m.get('role') == 'outer' and m.get('geometry')],
                 description=', '.join(filter(None, [e['tags'].get('name'), e['tags'].get('is_in'), e['tags'].get('ref')])))
            for e in sorted(data['elements'], key=lambda e: (-int(e.get('tags', {}).get('admin_level', '0')) if str(e.get('tags', {}).get('admin_level', '0')).isdigit() else 0, e['id']))
            if e['type'] == 'relation' and e.get('bounds')]


def selection_query(selection):
    if selection.get('districtId'):
        feature = district_feature(selection['districtId'])
        queries = []
        for polygon in feature['geometry']['coordinates']:
            poly = ' '.join(f'{p[1]:.7f} {p[0]:.7f}' for p in polygon[0][:-1])
            queries.append(f'way[highway](poly:"{poly}");')
        scope = '(' + ''.join(queries) + ')->.roads;'
    elif selection.get('relationId'):
        rid = selection['relationId']
        if type(rid) is not int or rid <= 0:
            raise ValueError('Ungültige Gebietsrelation.')
        # buffer around all selected highways keeps complete junctions at the border.
        scope = f'rel({rid});out geom;map_to_area->.a;way[highway](area.a)->.roads;'
    else:
        area = selection.get('area')
        validate_area(area)
        if area is None:
            raise ValueError('Stadt/Stadtteil oder gezeichnete Fläche auswählen.')
        coords = area['coordinates'][0]
        west, east = min(p[0] for p in coords), max(p[0] for p in coords)
        south, north = min(p[1] for p in coords), max(p[1] for p in coords)
        if distance([west, south], [east, north]) > 35000:
            raise ValueError('Zum Testen bitte eine Fläche mit höchstens 35 km Diagonale wählen.')
        poly = ' '.join(f'{p[1]:.7f} {p[0]:.7f}' for p in coords[:-1])
        scope = f'way[highway](poly:"{poly}")->.roads;'
    return ('[out:json][timeout:150];' + scope +
            '(way.roads;way[highway](around.roads:130);)->.all;'
            '.roads out ids;(.all;node(w.all);rel(bw.all)[type=restriction];);out body geom;')


def bearing(p, origin):
    return math.atan2((p[0] - origin[0]) * math.cos(math.radians(origin[1])), p[1] - origin[1]) % (2 * math.pi)


def cluster_bearings(items, origin, tolerance=32):
    groups = []
    for item in sorted(items, key=lambda x: bearing(x['point'], origin)):
        angle = bearing(item['point'], origin)
        nearest = next((g for g in groups if abs(math.atan2(math.sin(angle - g['angle']), math.cos(angle - g['angle']))) < math.radians(tolerance)), None)
        if nearest:
            nearest['items'].append(item)
        else:
            groups.append(dict(angle=angle, items=[item]))
    return sorted(groups, key=lambda g: g['angle'])


def describe_arms(site):
    """Describe stable source arms, independently of later moved gate positions."""
    preparation = site.get('preparation') or {}
    if preparation.get('armEvidence'):
        return preparation['armEvidence']
    if preparation.get('algorithm') != ALGORITHM or not site.get('polygon'):
        return {}
    hits = [dict(point=p, way=w) for w in site['ways'] if w['tags'].get('highway') in MAJOR
            for p, _, _ in crossings(w, site['polygon'])]
    arms = cluster_bearings(hits, site['origin'])
    if len(arms) != len(site['logicalArms']):
        return {}
    return {f'Arm-{i+1}': dict(bearing=math.degrees(arm['angle']),
                names=sorted({h['way']['tags']['name'] for h in arm['items'] if h['way']['tags'].get('name')}),
                wayIds=sorted({h['way']['id'] for h in arm['items']})) for i, arm in enumerate(arms)}


def crossings(way, polygon):
    found = []
    for a, b in zip(way['coordinates'], way['coordinates'][1:]):
        for c, d in zip(polygon, polygon[1:]):
            p = intersection(a, b, c, d)
            if p and all(distance(p, old[0]) > .1 for old in found):
                found.append((p, a, b))
    return found


def lane_count(tags, sign):
    raw = tags.get('lanes:forward' if sign == 1 else 'lanes:backward')
    try:
        if raw is not None:
            return int(raw) if 0 < int(raw) < 15 else None
        total = int(tags.get('lanes', ''))
        if tags.get('oneway') in ('yes', '1', '-1'):
            return total if 0 < total < 15 else None
        # Odd totals may include a shared/turn lane; never silently round them up.
        both = int(tags.get('lanes:both_ways', '0'))
        return (total - both) // 2 if total > both and (total - both) % 2 == 0 else None
    except (ValueError, TypeError):
        return None


def departure_lanes(hit, origin, ways):
    """Sample after the junction, not an inbound turn-lane fan at the signal."""
    way = hit['way']
    sign = 1 if distance(hit['b'], origin) > distance(hit['a'], origin) else -1
    initial_sign = sign
    one = way['tags'].get('oneway', 'no')
    if one in ('yes', '1') and sign == -1 or one == '-1' and sign == 1:
        return None  # inbound-only carriageway, not a missing lane count
    index = next(i for i, (a, b) in enumerate(zip(way['coordinates'], way['coordinates'][1:])) if a == hit['a'] and b == hit['b'])
    index = index + 1 if sign == 1 else index
    seen = set()
    while (way['id'], index, sign) not in seen:
        seen.add((way['id'], index, sign))
        p = way['coordinates'][index]
        if distance(p, origin) >= 80:
            return dict(wayId=way['id'], direction=sign, lanes=lane_count(way['tags'], sign), sample=p,
                        boundaryWayId=hit['way']['id'], boundaryDirection=initial_sign)
        next_index = index + sign
        if 0 <= next_index < len(way['nodes']):
            index = next_index
            continue
        nid = way['nodes'][index]
        candidates = []
        for other in ways:
            if other['id'] == way['id'] or other['tags'].get('name') != way['tags'].get('name') or other['tags']['highway'] not in MAJOR:
                continue
            for j in (0, len(other['nodes'])-1):
                if other['nodes'][j] != nid:
                    continue
                step = 1 if j == 0 else -1
                one = other['tags'].get('oneway', 'no')
                if one in ('yes', '1') and step == -1 or one == '-1' and step == 1:
                    continue
                q = other['coordinates'][j+step]
                if distance(q, origin) > distance(p, origin):
                    candidates.append((other, j+step, step))
        if len(candidates) != 1:
            break
        way, index, sign = candidates[0]
    return dict(wayId=way['id'], direction=sign, lanes=None, sample=None,
                boundaryWayId=hit['way']['id'], boundaryDirection=initial_sign)


def administrative_rings(relation, role):
    segments = [[[p['lon'], p['lat']] for p in m['geometry']]
                for m in relation.get('members', []) if m.get('type') == 'way' and m.get('role', 'outer') == role and m.get('geometry')]
    rings = []
    while segments:
        chain = segments.pop(0)
        while chain[0] != chain[-1]:
            match = next(((i, s if chain[-1] == s[0] else list(reversed(s))) for i, s in enumerate(segments) if chain[-1] in (s[0], s[-1])), None)
            if match is None:
                raise ValueError('Verwaltungsgrenze ist unvollständig. Bitte eine Fläche einzeichnen.')
            i, segment = match
            chain.extend(segment[1:])
            segments.pop(i)
        rings.append(chain)
    return rings


def prepare(raw, selection):
    """Pure function: frozen OSM + selection => same proposals and ordering."""
    district = district_feature(selection['districtId']) if selection.get('districtId') else None
    elements = raw['elements']
    outer, inner = [], []
    if selection.get('relationId'):
        relation = next((e for e in elements if e['type'] == 'relation' and e['id'] == selection['relationId']), None)
        if relation is None:
            raise ValueError('Die gewählte Verwaltungsgrenze fehlt in der OSM-Antwort.')
        outer, inner = administrative_rings(relation, 'outer'), administrative_rings(relation, 'inner')
        if not outer:
            raise ValueError('Die gewählte Verwaltungsgrenze hat keine vollständige Außenfläche.')
    # Only Overpass ``out ids`` records select the discovery scope. Untagged
    # ordinary OSM ways (with nodes/version metadata) are not scope markers.
    selected_way_ids = {e['id'] for e in elements if e['type'] == 'way' and set(e) == {'type', 'id'}}
    nodes = {e['id']: e for e in elements if e['type'] == 'node'}
    ways = []
    for e in elements:
        if e['type'] != 'way' or 'highway' not in e.get('tags', {}):
            continue
        coords = [[p['lon'], p['lat']] for p in e.get('geometry', []) if p and 'lon' in p]
        if len(coords) != len(e.get('nodes', [])) or len(coords) < 2:
            raise ValueError('Unvollständige OSM-Weggeometrie; keine Teilvorschläge erzeugt.')
        ways.append(dict(id=e['id'], tags=e['tags'], nodes=e['nodes'], coordinates=coords))
    adjacency = defaultdict(list)
    bounds = {w['id']: (min(p[0] for p in w['coordinates']), min(p[1] for p in w['coordinates']),
                        max(p[0] for p in w['coordinates']), max(p[1] for p in w['coordinates'])) for w in ways}
    for w in ways:
        if w['tags']['highway'] not in MAJOR:
            continue
        for i, nid in enumerate(w['nodes']):
            for j in (i - 1, i + 1):
                if 0 <= j < len(w['nodes']):
                    adjacency[nid].append(dict(way=w, point=w['coordinates'][j]))
    seeds, roundabouts = [], []
    for nid, edges in sorted(adjacency.items()):
        if len({e['way']['id'] for e in edges}) < 2 or len(edges) < 3 or nid not in nodes:
            continue
        if selected_way_ids and not any(e['way']['id'] in selected_way_ids for e in edges):
            continue
        origin = [nodes[nid]['lon'], nodes[nid]['lat']]
        if outer and (not any(inside(origin, r) for r in outer) or any(inside(origin, r) for r in inner)):
            continue
        if selection.get('area') and not inside(origin, selection['area']['coordinates'][0]):
            continue
        if district and not any(inside(origin, polygon[0]) and not any(inside(origin, hole) for hole in polygon[1:])
                                for polygon in district['geometry']['coordinates']):
            continue
        # Do not combine roads on different levels merely because they cross visually.
        if any(e['way']['tags'].get('junction') in ('roundabout', 'circular') for e in edges):
            if all(distance(origin, r['origin']) > 100 for r in roundabouts):
                roundabouts.append(dict(name=' / '.join(sorted({e['way']['tags'].get('name', 'Kreisverkehr') for e in edges})), origin=origin, reason='Kreisverkehr'))
            continue
        names = {e['way']['tags'].get('name', str(e['way']['id'])) for e in edges}
        if len(names) < 2:
            continue
        seeds.append(dict(id=nid, origin=origin, names=names))
    # Bounded groups: no transitive chain joining a whole road corridor.
    groups = []
    for seed in seeds:
        group = next((g for g in groups if all(distance(seed['origin'], s['origin']) < 65 for s in g)
                      and any(len(seed['names'] & s['names']) >= 2 for s in g)), None)
        if group is None:
            groups.append([seed])
        else:
            group.append(seed)
    sites, rejected = [], roundabouts
    for group in groups:
        origin = [sum(s['origin'][i] for s in group) / len(group) for i in (0, 1)]
        spread = max(distance(origin, s['origin']) for s in group)
        radius = max(32, spread + 22)
        scale = math.cos(math.radians(origin[1]))
        polygon = [[origin[0] + math.sin(i * math.tau / 16) * radius / (111320 * scale),
                    origin[1] + math.cos(i * math.tau / 16) * radius / 111320] for i in range(16)]
        polygon.append(polygon[0])
        dx, dy = (radius + 100) / (111320 * scale), (radius + 100) / 111320
        local = [w for w in ways if bounds[w['id']][0] <= origin[0] + dx and bounds[w['id']][2] >= origin[0] - dx
                 and bounds[w['id']][1] <= origin[1] + dy and bounds[w['id']][3] >= origin[1] - dy]
        road_hits = []
        for w in local:
            if w['tags']['highway'] not in MAJOR:
                continue
            for p, a, b in crossings(w, polygon):
                road_hits.append(dict(point=p, way=w, a=a, b=b))
        arms = cluster_bearings(road_hits, origin)
        name = ' / '.join(sorted(set().union(*(s['names'] for s in group))))
        if len(arms) < 4:
            rejected.append(dict(name=name, origin=origin, reason='T-Kreuzung / weniger als vier Straßenarme'))
            continue
        warnings = []
        if len(arms) != 4:
            warnings.append(f'{len(arms)} Straßenarme: komplexe Topologie')
        if spread > 22:
            warnings.append('Versetzte / breite Kreuzung: Nachbarknoten und Flächengrenze prüfen')
        if any(distance(origin, s['origin']) < radius + 40 for other in groups if other is not group for s in other):
            warnings.append('Benachbarte Kreuzung: Flächentrennung prüfen')
        if any(w['tags'].get('junction') in ('roundabout', 'circular') and crossings(w, polygon) for w in local):
            rejected.append(dict(name=name, origin=origin, reason='Kreisverkehr'))
            continue
        gates = []
        for w in local:
            hits = crossings(w, polygon)
            if not hits:
                continue
            t = w['tags']
            dedicated = t['highway'] == 'cycleway' or t.get('bicycle') in ('yes', 'designated', 'permissive')
            lane = any('lane' in str(v) for k, v in t.items() if k.startswith('cycleway'))
            # Ordinary roads are included as explicitly marked on-road proposals.
            road = t['highway'] in MAJOR | {'residential', 'unclassified', 'living_street'}
            if not (dedicated or lane or road):
                continue
            for p, a, b in hits:
                dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
                length = math.hypot(dx, dy)
                if not length:
                    continue
                for sign in direction(t):
                    vector = [sign * dx / length, sign * dy / length]
                    after = [p[0] + vector[0] * .5 / (111320 * scale), p[1] + vector[1] * .5 / 111320]
                    kind = 'entry' if inside(after, polygon) else 'exit'
                    gates.append(dict(kind=kind, location=p, osmWayId=w['id'], forward=vector,
                                      shared=len(direction(t)) == 2, onRoad=not dedicated, lane=lane))
        # Prefer mapped separate cycleways on an arm; do not duplicate a road's sidepath.
        for arm in arms:
            assigned = [g for g in gates if abs(math.atan2(math.sin(bearing(g['location'], origin) - arm['angle']), math.cos(bearing(g['location'], origin) - arm['angle']))) < math.radians(38)]
            if any(not g['onRoad'] for g in assigned):
                gates = [g for g in gates if g not in assigned or not g['onRoad'] or g['lane']]
        gates.sort(key=lambda g: (bearing(g['location'], origin), g['kind'] != 'exit', g['osmWayId']))
        counters = dict(entry=0, exit=0)
        logical = {f'Arm-{i+1}': [] for i in range(len(arms))}
        for g in gates:
            counters[g['kind']] += 1
            g['label'] = f"{g['kind'].title()}-{counters[g['kind']]}"
            g['id'] = g['label'].lower()
            if arms:
                nearest = min(range(len(arms)), key=lambda i: abs(math.atan2(math.sin(bearing(g['location'], origin) - arms[i]['angle']), math.cos(bearing(g['location'], origin) - arms[i]['angle']))))
                logical[f'Arm-{nearest+1}'].append(g['label'])
        if any(g['onRoad'] for g in gates):
            warnings.append('Fahren auf Straße / Radfahrstreifen: Lage schematisch auf Straßenmitte prüfen')
        if any(g['shared'] for g in gates):
            warnings.append('Zweirichtungsweg / gemeinsame Entry-Exit-Positionen prüfen')
        if any('conditional' in key for w in local for key in w['tags']):
            warnings.append('Bedingte Verkehrsregel: Fahrtrichtungen / Zugänglichkeit technisch prüfen')
        if len(gates) > 12:
            warnings.append('Viele Grenzquerungen: interne Anschlüsse / Flächengröße prüfen')
        if any(not any(label.startswith('Entry') for label in labels) or not any(label.startswith('Exit') for label in labels) for labels in logical.values()):
            warnings.append('Mindestens ein Straßenarm ohne vollständige Radverkehrsanschlüsse')
        outgoing, lane_evidence = 0, []
        for arm in arms:
            counts = []
            for hit in arm['items']:
                evidence = departure_lanes(hit, origin, local)
                if evidence is None:
                    continue
                counts.append(evidence['lanes'])
                lane_evidence.append(evidence)
            if not counts or any(c is None for c in counts):
                outgoing = None
                break
            outgoing += sum(counts)
        if outgoing is None:
            warnings.append('Ausgehende Fahrspuren teilweise unbekannt; keine erfundene Spurzahl')
        local_ids = {w['id'] for w in local}
        local_nodes = {n for w in local for n in w['nodes']}
        restrictions = [e for e in elements if e['type'] == 'relation' and e.get('tags', {}).get('type') == 'restriction' and any(m['type'] == 'way' and m['ref'] in local_ids for m in e.get('members', []))]
        site = dict(id='osm-junction-' + str(min(s['id'] for s in group)), number=None, name=name,
                    origin=origin, geometryRevision=1, polygon=polygon if gates else [], gates=gates,
                    geometryMode='editable' if gates else 'none', logicalArms=logical,
                    ways=[{k: w[k] for k in ('id', 'tags', 'coordinates')} for w in local],
                    outgoingLanes=outgoing, note=' · '.join(warnings),
                    preparation=dict(algorithm=ALGORITHM, warnings=warnings, complexity=len(warnings),
                                     laneEvidence=lane_evidence, candidateNodes=sorted(s['id'] for s in group)),
                    provenance=dict(adapter=ALGORITHM), sourceFingerprint=digest(dict(group=group_signature(group), ways=local,
                        nodes=[nodes[n] for n in sorted(local_nodes) if n in nodes], restrictions=restrictions)))
        sites.append(site)
    sites.sort(key=lambda s: (-(s['outgoingLanes'] or 0), s['preparation']['complexity'], s['id']))
    for rank, site in enumerate(sites, 1):
        site['priorityRank'] = rank
    return sites, rejected


def group_signature(group):
    return [dict(id=s['id'], origin=s['origin'], names=sorted(s['names'])) for s in group]


def discover(selection, fetch=query_osm):
    query = selection_query(selection)
    raw = fetch(query)
    sites, rejected = prepare(raw, selection)
    if not sites:
        raise ValueError(f'Keine geeigneten Vierarm-Kandidaten gefunden ({len(rejected)} T-/Kreisverkehrsfälle aussortiert). Bestehendes Projekt bleibt unverändert.')
    identity = 'area-' + digest(selection)[:16]
    data = dict(schemaVersion=1, project=dict(id=identity, city=selection.get('name') or 'Gezeichnetes Gebiet', area=selection.get('area')),
                source=dict(adapter=ALGORITHM, sha256=digest(raw), osmRetrievedAt=raw.get('osm3s', {}).get('timestamp_osm_base'),
                            retrievedAt=datetime.now(timezone.utc).isoformat(), attribution='© OpenStreetMap-Mitwirkende, ODbL',
                            query=query, selection=selection, rejected=rejected), sites=sites)
    validate_dataset(data)
    return data, raw
