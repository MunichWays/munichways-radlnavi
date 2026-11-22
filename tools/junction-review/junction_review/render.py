"""Repeatable standalone vector review images, independent of online map tiles."""
from html import escape
import math


def review_svg(site):
    origin = site['origin']
    if origin is None:
        raise ValueError('Kreuzung ohne Position.')
    polygon = site['polygon'] or [origin]
    scale = math.cos(math.radians(origin[1]))
    def metric(p):
        return [(p[0] - origin[0]) * scale * 111320, -(p[1] - origin[1]) * 111320]
    points = [metric(p) for p in polygon]
    extent = max(55, max(abs(v) for p in points for v in p) + 30)
    factor = 620 / (2 * extent)
    def xy(p):
        x, y = metric(p)
        return f'{500+x*factor:.2f},{420+y*factor:.2f}'
    def path(coords):
        return ' '.join(xy(p) for p in coords)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="800" viewBox="0 0 1000 800">',
             '<defs><clipPath id="map"><rect x="130" y="70" width="740" height="660"/></clipPath><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10Z" fill="#405f56"/></marker></defs>',
             '<rect width="1000" height="800" fill="white"/>',
             f'<text x="20" y="28" font-family="sans-serif" font-size="17">{escape(site["name"])} · v{site["geometryRevision"]}</text>',
             '<text x="945" y="65" font-family="sans-serif" font-size="18">N ↑</text><g clip-path="url(#map)">']
    for w in site['ways']:
        bike = w['tags'].get('highway') == 'cycleway' or w['tags'].get('bicycle') in ('yes', 'designated', 'permissive')
        color, width = ('#578375', 2) if bike else ('#d5d4d7', 8 if w['tags'].get('highway') in ('primary', 'secondary', 'tertiary') else 2)
        parts.append(f'<polyline points="{path(w["coordinates"])}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    if site['polygon']:
        parts.append(f'<polygon points="{path(site["polygon"])}" fill="#9654b3" fill-opacity=".13" stroke="#8734a5" stroke-width="2"/>')
    for g in site['gates']:
        p = g['location']
        v = g['forward']
        start = [p[0] - v[0] * 5 / (scale * 111320), p[1] - v[1] * 5 / 111320]
        end = [p[0] + v[0] * 5 / (scale * 111320), p[1] + v[1] * 5 / 111320]
        parts.append(f'<polyline points="{path([start, end])}" stroke="#405f56" stroke-width="1.4" marker-end="url(#arrow)"/>')
    parts.append('</g>')
    for side in (-1, 1):
        gates = sorted([g for g in site['gates'] if (g['location'][0] < origin[0]) == (side == -1)], key=lambda g: -g['location'][1])
        previous = 65
        for i, g in enumerate(gates):
            x, y = map(float, xy(g['location']).split(','))
            label_y = min(725 - (len(gates)-i-1)*22, max(y, previous+22))
            previous = label_y
            lx, anchor = (15, 'start') if side == -1 else (985, 'end')
            color = '#19785b' if g['kind'] == 'entry' else '#2466b5'
            parts.append(f'<path d="M{x},{y} L{lx},{label_y}" stroke="{color}" stroke-width=".7"/><circle cx="{x}" cy="{y}" r="5" fill="white" stroke="{color}"/><text x="{lx}" y="{label_y-4}" text-anchor="{anchor}" font-family="sans-serif" font-size="14" fill="{color}">{escape(g["label"])}</text>')
    parts.append('<text x="20" y="770" font-family="sans-serif" font-size="12">Grün: Entry · Blau: Exit · Violett: Entwurf · Pfeile: Fahrtrichtung · © OpenStreetMap-Mitwirkende, ODbL</text></svg>')
    return ''.join(parts)
