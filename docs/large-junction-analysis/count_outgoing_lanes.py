"""Rank provisional Munich primary/secondary junctions by outgoing tagged lanes.

Offline by default. --collect freezes the city-wide Overpass response first.
This inventory is neither a polygon approval nor an activation proposal.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import html
import json
from math import atan2, cos, degrees, radians
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from count_primary_primary import distance

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'outgoing-lanes-munich-osm.json.gz'
QUERY = '''[out:json][timeout:180];
area[boundary=administrative][admin_level=6][name="München"]->.city;
way[highway~"^(primary|secondary)(_link)?$"](area.city)->.roads;
node(way_link.roads:3-)(area.city)->.contacts;
.contacts out body;
.roads out body geom;
'''


def integer(value):
    return int(value) if isinstance(value, str) and value.isdigit() else None


def lane_count(tags, forward):
    """Return explicit directional evidence, or an explicitly labelled estimate."""
    direction = 'forward' if forward else 'backward'
    one = tags.get('oneway')
    if one in ('yes', '1', 'true', '-1'):
        if forward != (one != '-1'):
            return None  # incoming carriageway, never an outgoing arm
        directional = integer(tags.get('lanes:' + direction))
        total = integer(tags.get('lanes'))
        if directional is not None and total is not None and directional != total:
            return dict(count=None, estimated=None, basis='conflicting one-way lane tags')
        count = directional if directional is not None else total
        return dict(count=count, estimated=None, basis='lanes:'+direction if directional is not None else 'oneway + lanes')
    directional = integer(tags.get('lanes:' + direction))
    total = integer(tags.get('lanes'))
    other = integer(tags.get('lanes:' + ('backward' if forward else 'forward')))
    centre = integer(tags.get('lanes:both_ways', '0'))
    if (directional is not None and total is not None and centre is not None
            and (directional + centre > total
                 or other is not None and directional + other + centre != total)):
        return dict(count=None, estimated=None, basis='conflicting directional lane tags')
    if directional is not None:
        return dict(count=directional, estimated=None, basis='lanes:' + direction)
    if total is not None and other is not None and centre is not None and total >= other + centre:
        return dict(count=total-other-centre, estimated=None, basis='lanes minus opposite and both_ways')
    # Equal division is plausible but is not evidence for a directional count.
    estimate = (total-centre)//2 if total is not None and centre is not None and total > centre and (total-centre)%2 == 0 else None
    return dict(count=None, estimated=estimate, basis='direction missing; equal split estimate' if estimate is not None else 'directional lane count missing')


def surface(way):
    tags = way.get('tags', {})
    return (tags.get('layer', '0') == '0' and tags.get('bridge') not in ('yes', 'viaduct')
            and tags.get('tunnel') not in ('yes', 'building_passage')
            and tags.get('junction') not in ('roundabout', 'circular')
            and tags.get('access') not in ('no', 'private')
            and tags.get('motor_vehicle') != 'no')


def inside(point, bounds):
    return bounds[0] < point[0] < bounds[2] and bounds[1] < point[1] < bounds[3]


def crossing(a, b, bounds):
    """One boundary hit on a directed segment whose endpoint membership differs."""
    for axis, edge in ((0, bounds[0]), (0, bounds[2]), (1, bounds[1]), (1, bounds[3])):
        if a[axis] == b[axis]:
            continue
        fraction = (edge-a[axis])/(b[axis]-a[axis])
        point = [a[i]+fraction*(b[i]-a[i]) for i in (0, 1)]
        if (0 <= fraction <= 1 and bounds[1-axis]-1e-10 <= point[1-axis]
                <= bounds[3-axis]+1e-10):
            return point
    raise ValueError('Boundary crossing missing')


def group_contacts(nodes, ways):
    names = defaultdict(set)
    for way in ways:
        if way['tags']['highway'] not in ('primary', 'secondary') or not way['tags'].get('name'):
            continue
        for node in way['nodes']:
            names[node].add(way['tags']['name'])
    groups = []
    for node in sorted(nodes, key=lambda n: n['id']):
        if len(names[node['id']]) < 2:
            continue
        point = [node['lon'], node['lat']]
        group = next((g for g in groups if len(set(g['roadNames']) & names[node['id']]) >= 2
                      and all(distance(point, p) <= 80 for p in g['locations'])), None)
        if group is None:
            group = dict(roadNames=[], nodeIds=[], locations=[])
            groups.append(group)
        group['roadNames'] = sorted(set(group['roadNames']) | names[node['id']])
        group['nodeIds'].append(node['id'])
        group['locations'].append(point)
    return groups


def exits_for(group, ways):
    points = group['locations']
    origin = [sum(p[i] for p in points)/len(points) for i in (0, 1)]
    mx = 111320*cos(radians(origin[1]))
    bounds = [min(p[0] for p in points)-12/mx, min(p[1] for p in points)-12/111320,
              max(p[0] for p in points)+12/mx, max(p[1] for p in points)+12/111320]
    exits, approaches, warnings = [], [], []
    for way in ways:
        coords = [[p['lon'], p['lat']] for p in way['geometry']]
        for index, (a, b) in enumerate(zip(coords, coords[1:])):
            if inside(a, bounds) == inside(b, bounds):
                continue
            outward = inside(a, bounds)
            hit = crossing(a, b, bounds)
            outside = b if outward else a
            bearing = (degrees(atan2((outside[0]-hit[0])*mx, (outside[1]-hit[1])*111320))+360)%360
            approaches.append(bearing)
            evidence = lane_count(way['tags'], outward)
            if evidence is None:
                continue
            tags = way['tags']
            exit = dict(osmWayId=way['id'], segment=index, name=tags.get('name', '(ohne Namen)'),
                        roadClass=tags['highway'], location=hit, bearing=round(bearing, 1),
                        osmForward=outward, laneTags={k:v for k,v in tags.items() if k.startswith(('lanes', 'turn:lanes')) or k=='oneway'}, **evidence)
            exits.append(exit)
            if tags['highway'].endswith('_link'):
                warnings.append('Verbindungsrampe am Suchrand; mögliche Doppelzählung prüfen')
            if tags.get('name') not in group['roadNames']:
                warnings.append('Zusätzlicher Straßenname am Suchrand')
    # Group separated incoming/outgoing carriageways into geometric arms.
    clusters = []
    for bearing in sorted(approaches):
        def delta(other):
            return abs((bearing-other+180)%360-180)
        cluster = next((c for c in clusters if all(delta(b) < 35 for b in c)), None)
        if cluster is None:
            clusters.append([bearing])
        else:
            cluster.append(bearing)
    count = len(clusters)
    if count != 4:
        warnings.append(f'{count} geometrische Arme statt vier; kein automatisch bestätigter Vierarmknoten')
    if any(e['count'] == 0 for e in exits):
        warnings.append('Ausgehende Richtung mit null Fahrspuren; Tagging prüfen')
    exact = bool(exits) and all(e['count'] is not None and e['count'] > 0 for e in exits)
    estimated = bool(exits) and all(e['count'] is not None or e['estimated'] is not None for e in exits)
    return dict(origin=origin, searchBounds=bounds, geometricArms=count, outgoing=exits,
                taggedTotal=sum(e['count'] for e in exits) if exact else None,
                estimatedTotal=sum(e['count'] if e['count'] is not None else e['estimated'] for e in exits) if estimated else None,
                knownSubtotal=sum(e['count'] or 0 for e in exits),
                unknownExits=sum(e['count'] is None for e in exits), warnings=sorted(set(warnings)))


def reviewed_sites():
    result = []
    runtime = json.loads((ROOT.parents[1]/'backend/src/big_junctions.json').read_text(encoding='utf-8'))
    active = {j['id'] for j in runtime['junctions'] if j.get('enabled')}
    for path in ROOT.glob('review-batch-*-images/review-data.json'):
        for site in json.loads(path.read_text(encoding='utf-8'))['sites']:
            result.append(dict(id=site['id'], label=f'K{site["number"]:02d}', name=site['name'],
                polygon=site['polygon'], nodes=site.get('candidateNodeIds', []),
                status='aktiv im Branch' if site['id'] in active else site['status']))
    known = {s['id'] for s in result}
    supplemental = json.loads((ROOT/'review-supplemental-sites.json').read_text(encoding='utf-8'))['sites']
    decisions = json.loads((ROOT/'junction-review-decisions.json').read_text(encoding='utf-8'))['decisions']
    for site in supplemental:
        if site['id'] in known:
            continue
        junction = next((j for j in runtime['junctions'] if j['id']==site['id']), None)
        decision = next((d for d in decisions if d['junctionId']==site['id']), {})
        result.append(dict(id=site['id'], label='Pilot' if junction else 'Früherer Ausschluss', name=site['name'],
            polygon=junction['polygon']['coordinates'][0] if junction else [],
            nodes=[decision['referenceNodeId']] if 'referenceNodeId' in decision else [],
            status='aktiv im Branch' if junction else 'ausgeschlossen'))
    return result


def main(collect=False):
    if collect:
        request = Request('https://overpass-api.de/api/interpreter',
            data=urlencode({'data': QUERY}).encode(), headers={'User-Agent': 'MunichWays-Lane-Inventory/1.0'})
        with urlopen(request, timeout=210) as response:
            value = json.load(response)
        if value.get('remark') or not value.get('elements'):
            raise ValueError('Incomplete Overpass response')
        snapshot = dict(query=QUERY, retrievedAt=datetime.now(timezone.utc).isoformat(), response=value)
        SOURCE.write_bytes(gzip.compress(json.dumps(snapshot, ensure_ascii=False).encode(), mtime=0))
    snapshot = json.loads(gzip.decompress(SOURCE.read_bytes()))
    elements = snapshot['response']['elements']
    ways = [w for w in elements if w['type']=='way' and surface(w)]
    nodes = [n for n in elements if n['type']=='node' and n.get('tags', {}).get('highway') != 'mini_roundabout']
    groups = group_contacts(nodes, ways)
    reviewed = reviewed_sites()
    from src.big_junctions import inside as in_polygon
    for group in groups:
        group.update(exits_for(group, ways))
        matches = [s for s in reviewed if set(s['nodes']) & set(group['nodeIds'])
                   or bool(s['polygon']) and any(in_polygon(p, s['polygon']) for p in group['locations'])]
        group['reviewMatches'] = [{k:s[k] for k in ('id','label','name','status')} for s in matches]
        group['priorityEligible'] = group['geometricArms']==4 and not group['warnings']
    groups.sort(key=lambda g: (g['taggedTotal'] is None, -(g['taggedTotal'] or 0), g['roadNames']))
    distribution = Counter(g['taggedTotal'] for g in groups if g['priorityEligible'] and g['taggedTotal'] is not None)
    report = dict(sourceRetrievedAt=snapshot['retrievedAt'], scope='Munich primary/secondary, including same-class intersections; four-arm candidates only in priority groups.',
        method='Outgoing motor-traffic directions at a provisional rectangle 12m beyond grouped contact nodes. '
               'Surface roads only. Explicit lanes:forward/backward, or oneway lanes; opposing and both_ways lanes excluded. '
               'Equal splits are estimates only. No defaults for missing lanes. Lane totals may include bus lanes. '
               'Grouping <=80m with two common street names is provisional; unnamed, grade-separated or atypical junctions may be missed. '
               'Search rectangles are not navigation polygons; manual geometry/road-arm review remains required.',
        rawContactNodes=len(nodes), surfaceWays=len(ways), provisionalComplexes=len(groups),
        taggedFourArmDistribution={str(k):v for k,v in sorted(distribution.items(), reverse=True)}, candidates=groups)
    (ROOT/'outgoing-lanes-munich-inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    render(report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('candidates','method')}, ensure_ascii=True))


def render(report):
    esc = html.escape
    lines = ['# München: Kreuzungen nach ausgehenden Fahrspuren', '',
             'OSM-Stand: '+report['sourceRetrievedAt'][:10]+'. Primary/Primary, Primary/Secondary und Secondary/Secondary.', '',
             'Gezählt werden die **ausgehenden Kfz-Fahrspuren aller vier Arme**; eingehende Abbiegespuren zählen nicht. '
             '2 Spuren je ausgehendem Arm ergeben 8. Busspuren können in den OSM-Spurzahlen enthalten sein.', '',
             'Die Zahlen sind OSM-Angaben, keine Vor-Ort-Bestätigung. Fehlende Richtungsangaben werden nicht als exakte Zahl ausgegeben. '
             'Die automatische Knotengruppierung und die Straßenarme müssen vor der Kreuzungsbearbeitung geprüft werden.', '',
             '| Ausgehende Fahrspuren | Kandidaten mit vollständigen Spurangaben | Davon noch ohne Prüfungszuordnung |', '| --- | --- | --- |']
    sections = []
    details_lines = []
    for count in sorted((int(n) for n in report['taggedFourArmDistribution']), reverse=True):
        sites = [g for g in report['candidates'] if g['priorityEligible'] and g['taggedTotal']==count]
        new = [g for g in sites if not g['reviewMatches']]
        lines.append(f'| {count} | {len(sites)} | {len(new)} |')
        rows=[]
        for group in sorted(sites,key=lambda g:(bool(g['reviewMatches']),g['roadNames'])):
            details='; '.join(f'{e["name"]} ({e["bearing"]:.0f}°): {e["count"]}' for e in group['outgoing'])
            state=', '.join(m['label']+' '+m['status'] for m in group['reviewMatches']) or 'noch nicht zugeordnet'
            name=' / '.join(group['roadNames'])
            link=f'https://www.openstreetmap.org/node/{group["nodeIds"][0]}'
            rows.append(f'<tr><td><a href="{link}">{esc(name)}</a></td><td>{esc(details)}</td><td>{esc(state)}</td></tr>')
        sections.append(f'<h2>{count} ausgehende Fahrspuren · {len(sites)} Kandidaten</h2><table><tr><th>Kreuzung</th><th>Ausgänge (0° Nord, 90° Ost)</th><th>Prüfstand</th></tr>'+''.join(rows)+'</table>')
        details_lines += ['', f'## {count} ausgehende Fahrspuren', '', '| Kreuzung | Ausgehende Spuren | Prüfstand |', '| --- | --- | --- |']
        for g in sorted(sites,key=lambda g:(bool(g['reviewMatches']),g['roadNames'])):
            state=', '.join(m['label']+' '+m['status'] for m in g['reviewMatches']) or 'noch nicht zugeordnet'
            details_lines.append('| '+ ' / '.join(g['roadNames'])+' | '+' + '.join(str(e['count']) for e in g['outgoing'])+' | '+state+' |')
    lines += details_lines
    unknown = [g for g in report['candidates'] if g['priorityEligible'] and g['taggedTotal'] is None]
    uncertain = [g for g in report['candidates'] if not g['priorityEligible']]
    lines += ['', f'## Fehlende Richtungs-Spurzahlen: {len(unknown)} Kandidaten', '',
              'Diese Fälle sind nicht zuverlässig einsortierbar. Schätzungen aus gleichmäßiger Aufteilung stehen separat im JSON.', '',
              f'Weitere {len(uncertain)} Kontaktgruppen mit unklarer Geometrie/Armen/Rampen werden nicht automatisch priorisiert.', '']
    rows=[]
    for g in unknown:
        estimate=f'; Schätzung {g["estimatedTotal"]}' if g['estimatedTotal'] is not None else ''
        rows.append('<tr><td>'+esc(' / '.join(g['roadNames']))+'</td><td>'+str(g['knownSubtotal'])+' sicher getaggte Spuren; '+str(g['unknownExits'])+' Ausgänge unklar'+estimate+'</td></tr>')
    intro='<p>OSM '+report['sourceRetrievedAt'][:10]+'. Ausgehende Kfz-Spuren; keine eingehenden Abbiegespuren. Größte zuerst. '
    intro+='Busspuren können enthalten sein. Vollständige OSM-Zahlen sind noch keine geprüfte Kreuzungsgeometrie. '
    intro+='Fehlende Richtungsspuren werden nicht stillschweigend halbiert. Bereits bearbeitete Fälle sind gekennzeichnet.</p>'
    body='<!doctype html><html lang="de"><meta charset="utf-8"><title>Priorität nach Fahrspuren</title><style>body{font:16px Arial;margin:28px;color:#263238}table{border-collapse:collapse;width:100%}td,th{padding:9px;border:1px solid #ddd;text-align:left}th{background:#eee}h2{margin-top:35px}</style><h1>Münchner Kreuzungen nach ausgehenden Fahrspuren</h1>'+intro
    body+='<p><a href="kreuzungspruefung/index.html">Kreuzungsprüfung</a> · <a href="outgoing-lanes-munich-inventory.json">Alle Daten und Geometriehinweise</a></p>'
    body+=''.join(sections)+f'<h2>Nicht sicher einsortierbar · {len(unknown)}</h2><table>'+''.join(rows)+'</table>'
    body+=f'<p>{len(uncertain)} weitere Kontaktgruppen wegen unklarer Arme, Rampen oder Zusatzstraßen nicht in der Rangliste. Details im JSON.</p><p>© OpenStreetMap-Mitwirkende, ODbL. Keine Änderungen am Backendkatalog.</p></html>'
    (ROOT/'outgoing-lanes-munich.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'outgoing-lanes-munich.html').write_text(body,encoding='utf-8')


if __name__=='__main__':
    import sys
    sys.path.insert(0, str(ROOT.parents[1]/'backend'))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect',action='store_true')
    main(parser.parse_args().collect)
