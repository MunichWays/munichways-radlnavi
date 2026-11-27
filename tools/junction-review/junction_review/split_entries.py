"""Entries before a road-to-cycleway split belong on the road carriageway.

Pattern (reviewed cases K108 Hohenzollernstraße, BA05 P4 Ohlmüllerstraße):
cyclists ride on the carriageway; shortly before the junction a short diagonal
cycleway leaves the road onto a separate path beside it. A gate placed on that
diagonal piece (or on the road just after the split) is wrong — the entry is on
the road a few metres BEFORE the split, and the split node lies inside the area.

Conservative rule, applied only when all conditions hold:
* an entry lies on a cycling path whose upstream end (against travel) is a node
  N at most MAX_APPROACH metres away;
* exactly one legally cyclable road arrives at N, and no cycling path arrives;
* entries of the same arm starting at N are merged into ONE entry 5 m before N
  on that road (an entry already on the road keeps its label);
* every other gate keeps its exact position; otherwise nothing is changed.
"""
from copy import deepcopy
import math

from .cycling import direction
from .gate_edit import edit_gate

ROADS = {'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link',
         'tertiary', 'tertiary_link', 'residential', 'unclassified', 'living_street'}
MAX_APPROACH = 25
BEFORE_SPLIT = 5


def _m(a, b):
    scale = math.cos(math.radians(a[1]))
    return math.hypot((b[0] - a[0]) * 111320 * scale, (b[1] - a[1]) * 110540)


def _key(p):
    return (round(p[0], 7), round(p[1], 7))


def is_road(tags):
    return (tags.get('highway') in ROADS and tags.get('bicycle') not in ('no', 'use_sidepath', 'dismount')
            and tags.get('access') not in ('no', 'private'))


def is_path(tags):
    return tags.get('highway') == 'cycleway' or (
        tags.get('highway') in ('path', 'footway', 'track') and tags.get('bicycle') in ('yes', 'designated', 'permissive'))


def _upstream_end(gate, way):
    """Upstream endpoint of the gate's way and the distance to it, or None."""
    coords = way['coordinates']
    index = min(range(len(coords) - 1), key=lambda i: _segment_distance(gate['location'], coords[i], coords[i + 1]))
    a, b = coords[index], coords[index + 1]
    scale = math.cos(math.radians(a[1]))
    along = (b[0] - a[0]) * scale * gate['forward'][0] + (b[1] - a[1]) * gate['forward'][1]
    if along > 0:  # travel follows coordinate order: upstream is the start
        path = [gate['location']] + coords[index::-1]
    else:
        path = [gate['location']] + coords[index + 1:]
    return path[-1], sum(_m(p, q) for p, q in zip(path, path[1:]))


def _segment_distance(p, a, b):
    scale = math.cos(math.radians(p[1]))
    ax, ay = (a[0] - p[0]) * 111320 * scale, (a[1] - p[1]) * 110540
    bx, by = (b[0] - p[0]) * 111320 * scale, (b[1] - p[1]) * 110540
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0 if not length else max(0, min(1, -(ax * dx + ay * dy) / length))
    return math.hypot(ax + t * dx, ay + t * dy)


def _arrivals(node, ways, exclude):
    """Ways on which cycling legally arrives at ``node``: (way, coordinates towards node)."""
    result = []
    for way in ways:
        if way['id'] in exclude:
            continue
        keys = [_key(p) for p in way['coordinates']]
        for i, key in enumerate(keys):
            if key != node:
                continue
            signs = direction(way['tags'])
            if i > 0 and 1 in signs:
                result.append((way, way['coordinates'][:i + 1]))
            if i < len(keys) - 1 and -1 in signs:
                result.append((way, way['coordinates'][i:][::-1]))
    return result


def _point_before(path, meters):
    """Point ``meters`` before the end of ``path`` (which ends at the split node)."""
    remaining = meters
    for a, b in zip(path[::-1], path[-2::-1]):
        length = _m(a, b)
        if length >= remaining:
            t = remaining / length
            return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
        remaining -= length
    return None


def corrections(site):
    """Proposed (keep, remove, road way, target) per split; nothing is applied."""
    ways = {w['id']: w for w in site['ways']}
    arm_of = {label: arm for arm, labels in site['logicalArms'].items() for label in labels}
    groups = {}
    for gate in site['gates']:
        way = ways.get(gate['osmWayId'])
        if gate['kind'] != 'entry' or way is None:
            continue
        node, distance = _upstream_end(gate, way)
        if distance > MAX_APPROACH:
            continue
        groups.setdefault((arm_of.get(gate['label']), _key(node)), []).append(gate)
    proposals = []
    for (arm, node), gates in groups.items():
        if arm is None or not any(is_path(ways[g['osmWayId']]['tags']) for g in gates):
            continue  # Only a cycleway split triggers the rule.
        arriving = _arrivals(node, site['ways'], {g['osmWayId'] for g in gates})
        roads = [(w, path) for w, path in arriving if is_road(w['tags'])]
        if len(roads) != 1 or any(is_path(w['tags']) for w, _ in arriving):
            continue
        road, path = roads[0]
        target = _point_before(path, BEFORE_SPLIT)
        if target is None:
            continue
        keep = next((g for g in gates if is_road(ways[g['osmWayId']]['tags'])), min(gates, key=lambda g: int(g['label'].split('-')[1])))
        proposals.append(dict(keep=keep['id'], remove=[g['id'] for g in gates if g is not keep], wayId=road['id'],
                              target=target, label=keep['label'], removedLabels=[g['label'] for g in gates if g is not keep]))
    return proposals


def apply(site):
    """Apply all safe corrections; returns (site, notes). Unsafe ones are skipped."""
    notes = []
    for proposal in corrections(site):
        before = {g['id']: g['location'] for g in site['gates']}
        try:
            result = deepcopy(site)
            for gate_id in proposal['remove']:
                result = edit_gate(result, dict(action='delete', gateId=gate_id))
            result = edit_gate(result, dict(action='move', gateId=proposal['keep'], wayId=proposal['wayId'],
                                            location=proposal['target']))
        except ValueError:
            continue
        moved = [g['label'] for g in result['gates'] if g['id'] != proposal['keep'] and _m(g['location'], before[g['id']]) > .05]
        if moved:
            continue
        site = result
        removed = ', '.join(proposal['removedLabels'])
        notes.append(f"{proposal['label']} auf Fahrbahn OSM {proposal['wayId']} {BEFORE_SPLIT} m vor Radweg-Abzweig gelegt"
                     + (f"; {removed} entfällt" if removed else ''))
    return site, notes
