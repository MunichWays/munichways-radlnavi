"""Small geometry primitives; coordinates are always [longitude, latitude]."""
from copy import deepcopy
import math


def point(value):
    if (not isinstance(value, list) or len(value) != 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value)
            or not -180 <= value[0] <= 180 or not -85 <= value[1] <= 85):
        raise ValueError('Ungültige Koordinate [Längengrad, Breitengrad].')
    return value


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1]]


def intersection(a, b, c, d):
    r, s = sub(b, a), sub(d, c)
    den = cross(r, s)
    if abs(den) < 1e-18:
        return None
    t, u = cross(sub(c, a), s) / den, cross(sub(c, a), r) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return [a[0] + t * r[0], a[1] + t * r[1]]
    return None


def distance(a, b):
    return math.hypot((a[0] - b[0]) * math.cos(math.radians((a[1] + b[1]) / 2)), a[1] - b[1]) * 111320


def on_segment(p, a, b):
    r = sub(b, a)
    if abs(cross(sub(p, a), r)) > 1e-16:
        return False
    return all(min(a[i], b[i]) - 1e-12 <= p[i] <= max(a[i], b[i]) + 1e-12 for i in (0, 1))


def ring(value):
    if not isinstance(value, list) or not 4 <= len(value) <= 501:
        raise ValueError('Eine Fläche braucht 3 bis 500 Eckpunkte.')
    for p in value:
        point(p)
    if value[0] != value[-1]:
        raise ValueError('Die Polygonfläche muss geschlossen sein.')
    if len({tuple(p) for p in value[:-1]}) != len(value) - 1:
        raise ValueError('Doppelte Eckpunkte in der Fläche.')
    edges = list(zip(value, value[1:]))
    for i, (a, b) in enumerate(edges):
        if distance(a, b) < .05:
            raise ValueError('Zwei Eckpunkte liegen zu dicht beieinander.')
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            c, d = edges[j]
            if intersection(a, b, c, d) is not None or any((on_segment(a, c, d), on_segment(b, c, d), on_segment(c, a, b), on_segment(d, a, b))):
                raise ValueError('Die Fläche überschneidet sich selbst.')
    # Translate before area calculation to avoid cancellation at city coordinates.
    origin = value[0]
    area = abs(sum(cross(sub(a, origin), sub(b, origin)) for a, b in edges))
    if area < 1e-12:
        raise ValueError('Die Fläche ist zu klein oder liegt auf einer Linie.')
    return value


def inside(p, polygon):
    odd = False
    for a, b in zip(polygon, polygon[1:]):
        if (a[1] > p[1]) != (b[1] > p[1]):
            if p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]:
                odd = not odd
    return odd


def boundary_distance(p, polygon):
    best = math.inf
    for a, b in zip(polygon, polygon[1:]):
        r = sub(b, a)
        length_squared = sum(x * x for x in r)
        if length_squared == 0:
            best = min(best, distance(p, a))
            continue
        t = max(0, min(1, sum(x * y for x, y in zip(sub(p, a), r)) / length_squared))
        best = min(best, distance(p, [a[0] + t * r[0], a[1] + t * r[1]]))
    return best


def relocate_gates(site, polygon):
    """Keep stable gate identities/directions and intersect their evidenced ways.

    This first editor intentionally refuses ambiguous re-crossings. It does not
    invent new gates, cycling access or road-side positions from road centerlines.
    """
    ring(polygon)
    ways = {str(w['id']): w for w in site['ways']}
    result = []
    for gate in site['gates']:
        line = ways[str(gate['osmWayId'])]['coordinates']
        hits = []
        hit_segments = []
        for a, b in zip(line, line[1:]):
            for c, d in zip(polygon, polygon[1:]):
                p = intersection(a, b, c, d)
                if p is not None and all(distance(p, old) > .05 for old in hits):
                    hits.append(p)
                    hit_segments.append((a, b))
        if len(hits) != 1:
            # Direct OSM imports can contain an entire road through the junction,
            # with independently identified gates on both ends of the same way.
            known = {tuple(g['location']) for g in site['gates'] if str(g['osmWayId']) == str(gate['osmWayId'])}
            ordered = sorted(zip(hits, hit_segments), key=lambda item: distance(item[0], gate['location']))
            if len(known) > 1 and len(hits) == len(known) and distance(ordered[1][0], gate['location']) - distance(ordered[0][0], gate['location']) > .3:
                hits, hit_segments = [ordered[0][0]], [ordered[0][1]]
            else:
                raise ValueError(f"{gate['label']}: Weg schneidet die neue Fläche {len(hits)}-mal. Anschluss gezielt prüfen.")
        p = hits[0]
        if distance(p, gate['location']) > 80:
            raise ValueError(f"{gate['label']}: Verschiebung über 80 m erfordert eine neue Anschlussprüfung.")
        moved = deepcopy(gate)
        moved['location'] = p
        # Preserve the source-way travel direction, but update its local tangent.
        old_a, old_b = min(zip(line, line[1:]), key=lambda segment: boundary_distance(gate['location'], list(segment)))
        scale = math.cos(math.radians(p[1]))
        old_vector = [(old_b[0] - old_a[0]) * scale, old_b[1] - old_a[1]]
        sign = 1 if sum(x * y for x, y in zip(old_vector, gate['forward'])) >= 0 else -1
        a, b = hit_segments[0]
        vector = [(b[0] - a[0]) * scale, b[1] - a[1]]
        length = math.hypot(*vector)
        if length == 0:
            raise ValueError('Anschluss liegt auf einem Weg ohne Richtungsevidenz.')
        forward = [sign * v / length for v in vector]
        before = [p[0] - forward[0] * 1e-7 / scale, p[1] - forward[1] * 1e-7]
        after = [p[0] + forward[0] * 1e-7 / scale, p[1] + forward[1] * 1e-7]
        if (inside(before, polygon), inside(after, polygon)) != ((False, True) if gate['kind'] == 'entry' else (True, False)):
            raise ValueError(f"{gate['label']}: Die neue Grenze passt nicht zur belegten Fahrtrichtung auf OSM-Weg {gate['osmWayId']}. "
                             'Entry muss in die Fläche führen, Exit aus ihr heraus. Bei einem Wegende die passende Fortsetzung wählen.')
        moved['forward'] = forward
        result.append(moved)
    return result
