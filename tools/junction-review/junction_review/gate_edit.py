"""Joint boundary/gate edits; stable labels, evidenced OSM ways and direction."""
from copy import deepcopy
import math
import re

from .cycling import direction
from .geometry import boundary_distance, distance, inside, point, relocate_gates, ring
from .model import validate_site


def geometry_of(site):
    return {k: deepcopy(site[k]) for k in ('polygon', 'gates', 'logicalArms')}


def movement_changed(before, after):
    return (before is None or str(before['osmWayId']) != str(after['osmWayId'])
            or distance(before['location'], after['location']) > .01
            or sum((a-b)**2 for a,b in zip(before['forward'],after['forward'])) > 1e-8)


def draft_geometry(current, geometry):
    if not isinstance(geometry, dict) or set(geometry) != {'polygon', 'gates', 'logicalArms'}:
        raise ValueError('Fläche, Anschlüsse und Straßenarmzuordnung müssen gemeinsam vorliegen.')
    candidate = deepcopy(current)
    candidate.update(deepcopy(geometry))
    original = {g['id']: g for g in current['gates']}
    if not isinstance(candidate['gates'], list):
        raise ValueError('Ungültige Anschlussliste.')
    for gate in candidate['gates']:
        previous = original.get(gate.get('id'))
        if previous is None:
            kind = gate.get('kind')
            label = gate.get('label', '')
            match = re.fullmatch(r'(Entry|Exit)-([1-9][0-9]*)', label)
            if (kind not in ('entry','exit') or not match or match[1].lower()!=kind
                    or gate.get('id') != f'manual-{kind}-{match[2]}'
                    or label in reserved_labels(current)
                    or sum(label in labels for labels in candidate['logicalArms'].values()) != 1):
                raise ValueError('Ungültige Identität oder Straßenarmzuordnung des neuen Anschlusses.')
        elif any(gate.get(k) != previous[k] for k in ('label', 'kind')):
            raise ValueError('Bestehende Anschluss-IDs, Beschriftungen und Typen bleiben erhalten.')
    ring(candidate['polygon'])
    if any(boundary_distance(g['location'], candidate['polygon']) > .1 for g in candidate['gates']):
        candidate['gates'] = relocate_gates(candidate, candidate['polygon'])
    validate_site(candidate)
    # A submitted staged draft must meet the same movement checks as a move.
    for gate in candidate['gates']:
        if movement_changed(original.get(gate['id']),gate):
            validate_direction(candidate, gate)
    return candidate


def validate_direction(site, gate):
    ways = {str(w['id']): w for w in site['ways']}
    way = ways[str(gate['osmWayId'])]
    scale = math.cos(math.radians(gate['location'][1]))
    a, b = min(zip(way['coordinates'], way['coordinates'][1:]),
               key=lambda ab: boundary_distance(gate['location'], list(ab)))
    raw = [(b[0]-a[0])*scale, b[1]-a[1]]
    length = math.hypot(*raw)
    alignment = sum(x*y for x,y in zip(raw, gate['forward'])) / length if length else 0
    sign = 1 if alignment >= 0 else -1
    if abs(alignment) < .98 or sign not in direction(way['tags']):
        raise ValueError(f"{gate['label']}: Die Richtung ist auf diesem OSM-Weg nicht belegt oder nicht erlaubt.")
    p, v = gate['location'], gate['forward']
    before = [p[0]-v[0]*.1/(111320*scale), p[1]-v[1]*.1/111320]
    after = [p[0]+v[0]*.1/(111320*scale), p[1]+v[1]*.1/111320]
    if (inside(before,site['polygon']),inside(after,site['polygon'])) != ((False,True) if gate['kind']=='entry' else (True,False)):
        raise ValueError(f"{gate['label']}: Fahrtrichtung und Flächengrenze passen nicht zusammen.")


def snap_to_way(location, ways, way_id=None):
    point(location)
    scale = math.cos(math.radians(location[1]))
    choices = []
    for way in ways:
        if way_id is not None and str(way['id']) != str(way_id):
            continue
        if not direction(way['tags']):
            continue
        for a,b in zip(way['coordinates'],way['coordinates'][1:]):
            v = [(b[0]-a[0])*scale,b[1]-a[1]]
            length2 = sum(x*x for x in v)
            if not length2:
                continue
            rel = [(location[0]-a[0])*scale,location[1]-a[1]]
            t = max(0,min(1,sum(x*y for x,y in zip(rel,v))/length2))
            p = [a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]
            choices.append((distance(location,p),way,p,v))
    if not choices or min(c[0] for c in choices) > 12:
        raise ValueError('Kein erlaubter Radweg/Straßenabschnitt innerhalb von 12 m. Bitte näher an den gewünschten Weg klicken.')
    choices.sort(key=lambda c:(c[0],c[1]['id']))
    best = choices[0]
    if way_id is None and any(c[1]['id'] != best[1]['id'] and abs(c[0]-best[0]) < .3 for c in choices):
        raise ValueError('Mehrere OSM-Wege liegen am Zielpunkt. Bitte den gewünschten Zielweg in der Liste auswählen.')
    return best[1:]


def move_boundary(polygon, previous, target):
    polygon = deepcopy(polygon)
    near = min(range(len(polygon)-1),key=lambda i:distance(previous,polygon[i]))
    if distance(previous,polygon[near]) < .3:
        polygon[near] = target
        if near == 0:
            polygon[-1] = target
    else:
        edge = min(range(len(polygon)-1),key=lambda i:boundary_distance(previous,polygon[i:i+2]))
        polygon.insert(edge+1,target)
    ring(polygon)
    return polygon


def perpendicular_boundary(polygon, previous, target, vector, half_width=2.5):
    """Boundary through ``target`` as a short edge across the way (no spike).

    Used when moving a gate outward along a road: a single inserted vertex makes
    a narrow spike that the road may not enter cleanly. The old gate vertex (or
    its edge) is replaced by two points ``half_width`` metres either side.
    """
    polygon = deepcopy(polygon)
    scale = math.cos(math.radians(target[1]))
    length = math.hypot(*vector) or 1
    nx, ny = -vector[1] / length, vector[0] / length
    offset = half_width / 111320
    side = [[target[0] + sign * nx * offset / scale, target[1] + sign * ny * offset] for sign in (1, -1)]
    near = min(range(len(polygon) - 1), key=lambda i: distance(previous, polygon[i]))
    if distance(previous, polygon[near]) < .3:
        before = polygon[near - 1] if near else polygon[-2]
        first, second = sorted(side, key=lambda q: distance(before, q))
        polygon[near:near + 1] = [first, second]
        if near == 0:
            polygon[-1] = first
    else:
        edge = min(range(len(polygon) - 1), key=lambda i: boundary_distance(previous, polygon[i:i + 2]))
        first, second = sorted(side, key=lambda q: distance(polygon[edge], q))
        polygon[edge + 1:edge + 1] = [first, second]
    ring(polygon)
    return polygon


def reserved_labels(site):
    gates = list(site['gates'])
    for event in site.get('history', []):
        gates.extend((event.get('previousGeometry') or {}).get('gates', []))
    return {g['label'] for g in gates} | {m['label'] for g in gates for m in g.get('mergedFrom', [])}


def add_gate(site, operation):
    result = deepcopy(site)
    kind, arm = operation.get('kind'), operation.get('arm')
    if kind not in ('entry','exit') or arm not in result['logicalArms']:
        raise ValueError('Bitte Entry/Exit und einen vorhandenen Straßenarm auswählen.')
    way, target, _ = snap_to_way(operation['location'],result['ways'],operation.get('wayId'))
    if any(g['kind']==kind and str(g['osmWayId'])==str(way['id']) and distance(g['location'],target)<.3 for g in result['gates']):
        raise ValueError('Hier existiert bereits ein gleichartiger Anschluss auf diesem Weg.')
    _, anchor, _ = snap_to_way(target,[dict(id=0,tags=dict(highway='cycleway'),coordinates=result['polygon'])])
    prefix = kind.title()+'-'
    number = max([int(label.split('-')[-1]) for label in reserved_labels(site) if re.fullmatch(prefix+r'[0-9]+',label)]+[0])+1
    gate = dict(id=f'manual-{kind}-{number}',label=f'{prefix}{number}',kind=kind,
                location=anchor,osmWayId=way['id'],forward=[1,0])
    result['gates'].append(gate)
    result['logicalArms'][arm].append(gate['label'])
    return edit_gate(result,dict(action='move',gateId=gate['id'],wayId=way['id'],location=target))


def edit_gate(site, operation):
    if operation.get('action') == 'add':
        return add_gate(site, operation)
    result = deepcopy(site)
    gate = next((g for g in result['gates'] if g['id']==operation.get('gateId')),None)
    if gate is None:
        raise ValueError('Bitte einen vorhandenen Anschluss auswählen.')
    action = operation.get('action')
    if action not in ('move','delete','merge'):
        raise ValueError('Unbekannte Anschlussbearbeitung.')
    remove = {gate['id']} if action=='delete' else set(operation.get('mergeIds',[])) if action=='merge' else set()
    if action=='merge':
        partners = [g for g in result['gates'] if g['id'] in remove]
        if not remove or len(partners)!=len(remove) or gate['id'] in remove or any(g['kind']!=gate['kind'] for g in partners):
            raise ValueError('Nur verschiedene Entry-Punkte oder verschiedene Exit-Punkte können zusammengelegt werden.')
        arms = {label:arm for arm,labels in result['logicalArms'].items() for label in labels}
        if any(arms.get(g['label']) != arms.get(gate['label']) for g in partners):
            raise ValueError('Diese Anschlüsse gehören zu verschiedenen Straßenarmen. Straßenarme zuerst fachlich prüfen.')
        gate['mergedFrom'] = gate.get('mergedFrom',[]) + [
            {k:deepcopy(g[k]) for k in ('id','label','osmWayId','location')} for g in partners]
    removed_labels = {g['label'] for g in result['gates'] if g['id'] in remove}
    result['gates'] = [g for g in result['gates'] if g['id'] not in remove]
    result['logicalArms'] = {arm:[label for label in labels if label not in removed_labels] for arm,labels in result['logicalArms'].items()}
    if action != 'delete':
        way,p,vector = snap_to_way(operation['location'],result['ways'],operation.get('wayId'))
        if distance(p,gate['location']) > 80:
            raise ValueError('Bitte den Anschluss höchstens 80 m pro Bearbeitung verschieben.')
        previous = gate['location']
        result['polygon'] = move_boundary(result['polygon'],previous,p)
        gate['location'],gate['osmWayId'] = p,way['id']
        length = math.hypot(*vector)

        def directions():
            found = []
            for sign in direction(way['tags']):
                candidate = deepcopy(gate)
                candidate['forward'] = [sign*v/length for v in vector]
                try:
                    validate_direction(result,candidate)
                    found.append(candidate)
                except ValueError:
                    pass
            return found
        candidates = directions()
        if len(candidates) != 1:
            # A spike vertex can leave the way outside its own tip; try a short cross edge.
            try:
                result['polygon'] = perpendicular_boundary(site['polygon'],previous,p,vector)
                candidates = directions()
            except ValueError:
                candidates = []
        if len(candidates) != 1:
            raise ValueError('An dieser Stelle ist keine eindeutige passende Ein-/Ausfahrtrichtung belegt. Bitte einen Punkt vor der Verzweigung wählen.')
        gate.update(candidates[0])
        gate['onRoad'] = way['tags'].get('highway') != 'cycleway' and way['tags'].get('bicycle') not in ('yes','designated','permissive')
        gate['lane'] = any('lane' in str(v) for k,v in way['tags'].items() if k.startswith('cycleway'))
        gate['shared'] = any(g['id']!=gate['id'] and distance(g['location'],p)<.3 for g in result['gates'])
        result['gates'] = relocate_gates(result,result['polygon'])
    for g in result['gates']:
        g['shared'] = any(other['id']!=g['id'] and distance(g['location'],other['location'])<.3 for other in result['gates'])
    validate_site(result)
    for g in result['gates']:
        old = next((old for old in site['gates'] if old['id']==g['id']),None)
        if movement_changed(old,g):
            validate_direction(result,g)
    return result
