"""One-time offline import: python tools/import_districts.py INPUT OUTPUT."""
import hashlib
import json
import math
import sys
from pathlib import Path


def inside(point, rings):
    x, y = point
    result = False
    for ring in rings:
        for a, b in zip(ring, ring[1:]):
            if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                result = not result
    return result


def area(polygon):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon[0], polygon[0][1:])))


def label_point(polygon):
    # Search for an interior point far from edges, rather than a bbox centre
    # which can lie outside a concave district. Scale longitude to local metres.
    scale = math.cos(math.radians(48.14))
    rings = [[[x * scale, y] for x, y in ring] for ring in polygon]
    edges = [(a, b) for ring in rings for a, b in zip(ring, ring[1:])]
    xs, ys = zip(*rings[0])
    left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)

    def clearance(point):
        if not inside(point, rings):
            return -1
        distances = []
        for a, b in edges:
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = dx * dx + dy * dy
            t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) if length else 0
            distances.append((point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2)
        return min(distances)

    best = rings[0][0]
    for _ in range(5):
        sx, sy = (right - left) / 16, (top - bottom) / 16
        candidates = [(left + i * sx, bottom + j * sy) for i in range(17) for j in range(17)]
        best = max([best, *candidates], key=clearance)
        left, right, bottom, top = best[0] - sx, best[0] + sx, best[1] - sy, best[1] + sy
    result = [round(best[0] / scale, 7), round(best[1], 7)]
    assert inside(result, polygon), "Label must be inside its district"
    return result


def main():
    raw = Path(sys.argv[1]).read_bytes()
    source = json.loads(raw)
    districts = {}
    for feature in source['features']:
        p, geometry = feature['properties'], feature['geometry']
        number = p['bezirk_nummer']
        assert number in {f'BA{i:02}' for i in range(1, 26)}
        assert geometry['type'] == 'MultiPolygon'
        for polygon in geometry['coordinates']:
            for ring in polygon:
                assert len(ring) >= 4 and ring[0] == ring[-1]
                assert all(len(c) == 2 and 11 < c[0] < 12 and 47 < c[1] < 49 for c in ring)
        if number not in districts:
            districts[number] = {'type': 'Feature', 'id': number, 'properties': dict(p),
                                 'geometry': {'type': 'MultiPolygon', 'coordinates': []}}
        assert districts[number]['properties'] == p, "Parts must have identical metadata"
        districts[number]['geometry']['coordinates'].extend(geometry['coordinates'])
    assert len(districts) == 25
    features = [districts[key] for key in sorted(districts)]
    for feature in features:
        polygon = max(feature['geometry']['coordinates'], key=area)
        feature['properties']['label_coordinate'] = label_point(polygon)
    result = {'type': 'FeatureCollection', 'features': features}
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f"Imported {len(source['features'])} parts as {len(features)} districts; source SHA-256 {hashlib.sha256(raw).hexdigest()}")


if __name__ == '__main__':
    main()
