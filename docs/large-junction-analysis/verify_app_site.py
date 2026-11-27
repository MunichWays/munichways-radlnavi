"""Technical check of ONE confirmed junction, started from the local review app.

Reuses the batch-12 district pipeline unchanged (frozen exact approval, real
Standard routes from the production API, directed OSM corridors, production
classification, right-turn and walking controls). Everything is written to
--out; the project itself is NOT changed here — the app server imports the
fingerprint-bound report under its own project lock.

Inner road connectors are admitted automatically only under strict rules:
every unsupported corridor point lies within 1.25 m of one legal cycling way
(allowed(): no access/bicycle restriction), only that way's segments fully
inside the approved polygon count, and direction stays enforced by the
directed graph. Admitted way IDs are listed in the result.
"""
import argparse
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

import verify_ba01_ba03_project as batch
from prepare_review_batch_routes import allowed

check = batch.checks.review.check
REPORT_NUMBER = 900  # Report-only; never a K number.
TOLERANCE = 1.25


def _segment_distance(p, a, b):
    mx, my = 111320 * math.cos(math.radians(p[1])), 110540
    ax, ay = (a[0]-p[0])*mx, (a[1]-p[1])*my
    bx, by = (b[0]-p[0])*mx, (b[1]-p[1])*my
    dx, dy = bx-ax, by-ay
    length = dx*dx + dy*dy
    t = 0 if not length else max(0, min(1, -(ax*dx + ay*dy) / length))
    return math.hypot(ax + t*dx, ay + t*dy)


def connector_candidates(site, report, fixtures, support):
    """Ways carrying the unsupported inner parts of real routes, or None if unclear."""
    ways = {w['id']: w for w in site['ways']}
    # Same graph as the check itself: approved road gates plus explicit lane continuations.
    graph_site = dict(site, number=REPORT_NUMBER, onRoadWayIds=support.get('onRoadWayIds', site['onRoadWayIds']))
    edges = check.corridor_graph(graph_site)
    found, shared = set(), []
    inside_ways = {wid for wid, way in ways.items() if allowed(way, [wid]) and any(
        check.inside([a['lon'], a['lat']], site['polygon']) and check.inside([b['lon'], b['lat']], site['polygon'])
        for a, b in zip(way['geometry'], way['geometry'][1:]))}
    record = next(r for r in report['junctions'] if r['id'] == site['id'])
    for move in record['movements']:
        if 'directed OSM support' not in move.get('reason', ''):
            continue
        path = fixtures / move['fixture']
        if not path.exists():
            return None
        line = json.loads(path.read_text(encoding='utf-8'))['routes'][0]['geometry']['coordinates']
        hits = check.crossings(line, site['polygon'])
        if len(hits) != 2:
            return None
        corridor = [hits[0]['location'], *line[hits[0]['geometrySegmentIndex']+1:hits[1]['geometrySegmentIndex']+1], hits[1]['location']]
        for point in corridor:
            if min((_segment_distance(point, a, b) for a, b, _ in edges), default=math.inf) <= TOLERANCE:
                continue
            near = {wid for wid, way in ways.items() if any(
                _segment_distance(point, [a['lon'], a['lat']], [b['lon'], b['lat']]) <= TOLERANCE
                for a, b in zip(way['geometry'], way['geometry'][1:]))}
            usable = near & inside_ways
            # Any nearby restricted way, or no legal inside way: leave for a human.
            if not usable or any(not allowed(ways[w], [w]) for w in near - usable if w not in inside_ways
                                 and ways[w]['tags'].get('highway') not in ('footway', 'path', 'steps')):
                return None
            if len(usable) == 1:
                found |= usable
            else:
                shared.append(usable)  # OSM node shared by several ways.
    for usable in shared:
        if not usable & found:
            return None  # Never guess between parallel legal ways.
    return sorted(found)


STAGES = {
    'instruction-clarity': 'Bewusst ausgeschlossen bzw. mehrdeutige Ausfahrt',
    'reference-sampling': 'Kein eindeutiger Referenzpunkt auf dem Zufahrtsweg',
    'gate-matching': 'Route trifft einen anderen Anschluss',
    'polygon-crossing': 'Route führt nicht genau einmal durch die Fläche',
    'directed-corridor': 'Innerer Weg ohne legale gerichtete OSM-Unterstützung',
    'response-continuity': 'Routenantwort mit versetztem Ankunftspunkt',
    'runtime-matching': 'Produktionsprüfung erkennt die Route nicht',
}


def summarize(report, site_id, connectors):
    record = next(r for r in report['junctions'] if r['id'] == site_id)
    if record.get('status') == 'blocked-topology':
        return dict(standard=False, passed=0, attempted=0, rightVerified=0, rightAttempted=0, connectors=connectors,
                    issues=[dict(stage='topology', text='Straßenarme nicht automatisch als Vierarmkreuzung zuordenbar: ' + record['reason'])])
    moves = record['movements']
    attempts = [m for m in moves if m['kind'] in ('left', 'straight')]
    rights = [m for m in moves if m['kind'] == 'right']
    issues = []
    for move in moves:
        if move.get('enabled') or move.get('verified') or move.get('explicitlyExcluded'):
            continue
        stage = move.get('failureStage', 'runtime-matching')
        issues.append(dict(stage=stage, entryLabel=move['entryLabel'], exitLabel=move['exitLabel'], kind=move['kind'],
                           text=STAGES.get(stage, stage), reason=move.get('reason', '')))
    return dict(standard=not issues, passed=sum(bool(m.get('enabled')) for m in attempts), attempted=len(attempts),
                rightVerified=sum(bool(m.get('verified')) for m in rights), rightAttempted=len(rights),
                excluded=[dict(entryLabel=m['entryLabel'], exitLabel=m['exitLabel'], reason=m.get('reason', ''))
                          for m in moves if m.get('explicitlyExcluded')],
                connectors=connectors, issues=issues)


def run(project, site_id, out):
    out.mkdir(parents=True, exist_ok=False)
    prefix = str(out / 'check')
    fixtures = out / 'routes'
    settings = dict(PREFIX=prefix, SOURCE=Path(prefix + '-approved.json'), REPORT=Path(prefix + '-routes.json'),
                    FIXTURES=fixtures, SELECTED={project.name: [site_id]}, POLICIES={},
                    FIRST_REPORT_NUMBER=REPORT_NUMBER, TITLE='Technische Prüfung aus der Kreuzungsapp')
    connectors = []
    with patch.multiple(batch, PROJECTS=project.parent, INNER_ROADS=dict(batch.INNER_ROADS), **settings):
        print('PHASE Freigabe einfrieren', flush=True)
        batch.freeze()
        print('PHASE Echte Standardrouten abrufen und prüfen', flush=True)
        batch.run(collect=True)
    data = json.loads(settings['SOURCE'].read_text(encoding='utf-8'))
    report = json.loads(settings['REPORT'].read_text(encoding='utf-8'))
    if data['sites']:
        support = json.loads(Path(prefix + '-support.json').read_text(encoding='utf-8')).get(site_id, {})
        candidates = connector_candidates(data['sites'][0], report, fixtures, support)
        if candidates:
            connectors = candidates
            print('PHASE Innere Verbinder zulassen: ' + ', '.join(map(str, connectors)), flush=True)
            with patch.multiple(batch, PROJECTS=project.parent,
                                INNER_ROADS={**batch.INNER_ROADS, site_id: connectors}, **settings):
                batch.run(collect=False)
            report = json.loads(settings['REPORT'].read_text(encoding='utf-8'))
    if report.get('status') != 'complete':
        raise SystemExit('Prüfbericht unvollständig (Netzwerk?). Nichts übernommen.')
    result = summarize(report, site_id, connectors)
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('RESULT ' + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--site', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.project.resolve(), args.site, args.out.resolve())
