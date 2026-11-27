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

Road/cycleway variants (reviewed case Arcisstraße, BA05 P8 Balanstraße): where
a cycleway is NOT compulsory, cyclists freely choose road or cycleway, so two
neighbouring gates of the same arm and kind — exactly one on a legally cyclable
road (no bicycle=use_sidepath), one on a cycling path, at most 15 m apart and
running the same way — are treated as one exit/entry with identical guidance.

A right-turn control whose real Standard route never touches the polygon is a
valid negative control (precedent: Wilram): no junction macro can fire there.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

import verify_ba01_ba03_project as batch
from prepare_review_batch_routes import allowed
from junction_review.split_entries import _m, is_path, is_road
from junction_review.store import ProjectStore

check = batch.checks.review.check
REPORT_NUMBER = 900  # Report-only; never a K number.
TOLERANCE = 1.25
VARIANT_GAP = 15
VARIANT_ANGLE = 45
VARIANT_REASON = ('Nicht benutzungspflichtiger Radweg neben der Fahrbahn: Radfahrende wählen frei zwischen '
                  'Radweg und Straße, daher gleiche Ansage für beide Anschlüsse (Regel der Kreuzungsapp, '
                  'wie Arcisstraße).')


def road_path_variants(site):
    """{'exit': [[a, b], ...], 'entry': [...]}: same-arm road/cycleway pairs with equal guidance.

    A human decision always wins: gates marked for normal guidance (constraint or
    reviewed policy, e.g. Maximilianstraße Exit-1) are never paired.
    """
    ways = {w['id']: w for w in site['ways']}
    gates = {g['label']: g for g in site['gates']}
    normal = set((site.get('constraints') or {}).get('normalGuidanceGates', [])) | set(
        ((site.get('evidence') or {}).get('guidanceReview') or {}).get('normalGuidanceGates', []))
    groups = {'exit': [], 'entry': []}
    for labels in site['logicalArms'].values():
        for kind, found in groups.items():
            pair = [gates[label] for label in labels if label in gates and gates[label]['kind'] == kind]
            if len(pair) != 2 or any(g['label'] in normal for g in pair):
                continue
            tags = [ways.get(g['osmWayId'], {}).get('tags', {}) for g in pair]
            if sorted((is_road(t), is_path(t)) for t in tags) != [(False, True), (True, False)]:
                continue
            if _m(pair[0]['location'], pair[1]['location']) > VARIANT_GAP:
                continue
            a, b = (math.atan2(g['forward'][1], g['forward'][0]) for g in pair)
            if abs((math.degrees(a - b) + 180) % 360 - 180) > VARIANT_ANGLE:
                continue
            found.append(sorted(g['label'] for g in pair))
    return groups


def variant_policy(project, site_id):
    """Batch policy with the rule's groups merged into any existing reviewed policy, or None."""
    site = next(s for s in ProjectStore(project).snapshot()['sites'] if s['id'] == site_id)
    groups = road_path_variants(site)
    if not any(groups.values()):
        return None, groups
    policy = deepcopy((site.get('evidence') or {}).get('guidanceReview') or {}) if site.get('evidenceCurrent') else {}
    for kind, field in (('exit', 'equivalentExitGroups'), ('entry', 'equivalentEntryGroups')):
        known = policy.setdefault(field, [])
        known += [g for g in groups[kind] if not any(set(g) <= set(k) for k in known)]
    policy.setdefault('reviewer', 'Kreuzungsapp')
    policy['reason'] = ' '.join(filter(None, [policy.get('reason'), VARIANT_REASON]))
    return policy, groups


def accept_bypasses(report, site, fixtures):
    """Real routes that stay completely outside the polygon.

    Right control → verified negative control. Left/straight → covered only if the
    exit has an equivalent road/cycleway partner whose movement from the same
    entry passed; it stays disabled (normal guidance), but is no open issue.
    """
    rights, covered = [], []
    for record in report['junctions']:
        enabled = {(m['entryLabel'], m['exitLabel']): m for m in record['movements'] if m.get('enabled')}
        for move in record['movements']:
            if move.get('verified') or move.get('enabled') or move.get('failureStage') != 'polygon-crossing':
                continue
            path = fixtures / move['fixture']
            if not path.exists():
                continue
            line = json.loads(path.read_text(encoding='utf-8'))['routes'][0]['geometry']['coordinates']
            if check.crossings(line, site['polygon']) or any(check.inside(p, site['polygon']) for p in line):
                continue
            pair = dict(entryLabel=move['entryLabel'], exitLabel=move['exitLabel'])
            if move['kind'] == 'right':
                move.update(verified=True, bypassesPolygon=True,
                            reason='Standardroute umfährt die Kreuzung vollständig; kein Kreuzungsmakro möglich '
                                   '(gültige Negativkontrolle).')
                rights.append(pair)
            else:
                group = next((g for g in site.get('equivalentExitGroups', []) if move['exitLabel'] in g), [])
                partner = next((enabled[(move['entryLabel'], label)] for label in group
                                if (move['entryLabel'], label) in enabled), None)
                if partner is None:
                    continue
                move.update(bypassesPolygon=True, coverageStatus='covered-equivalent-exit',
                            coveredByEquivalentMovement=partner['id'],
                            reason=f"Standardroute umfährt die Kreuzung; die gleichwertige Ausfahrt {partner['exitLabel']} "
                                   'ist geprüft und erhält die Kreuzungsansage.')
                covered.append(dict(pair, partner=partner['exitLabel']))
            move.pop('failureStage', None)
    return rights, covered


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
            gaps = {wid: min(_segment_distance(point, [a['lon'], a['lat']], [b['lon'], b['lat']])
                             for a, b in zip(way['geometry'], way['geometry'][1:])) for wid, way in ways.items()}
            near = {wid for wid, gap in gaps.items() if gap <= TOLERANCE}
            usable = near & inside_ways
            if not usable:
                return None
            # A restricted way only vetoes when it is clearly CLOSER to the route than
            # every legal way (the route may have used it). Sharing a node does not.
            best = min(gaps[w] for w in usable)
            if any(not allowed(ways[w], [w]) and gaps[w] < best - .3 for w in near - usable
                   if ways[w]['tags'].get('highway') not in ('footway', 'path', 'steps')):
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


def summarize(report, site_id, connectors, variants=None, bypasses=(), covered=()):
    record = next(r for r in report['junctions'] if r['id'] == site_id)
    extra = dict(variants=variants or {'exit': [], 'entry': []}, bypassingRights=list(bypasses),
                 coveredByVariant=list(covered))
    if record.get('status') == 'blocked-topology':
        return dict(standard=False, passed=0, attempted=0, rightVerified=0, rightAttempted=0, connectors=connectors, **extra,
                    issues=[dict(stage='topology', text='Straßenarme nicht automatisch als Vierarmkreuzung zuordenbar: ' + record['reason'])])
    moves = record['movements']
    attempts = [m for m in moves if m['kind'] in ('left', 'straight')]
    rights = [m for m in moves if m['kind'] == 'right']
    issues = []
    for move in moves:
        if move.get('enabled') or move.get('verified') or move.get('explicitlyExcluded') or move.get('coverageStatus'):
            continue
        stage = move.get('failureStage', 'runtime-matching')
        issues.append(dict(stage=stage, entryLabel=move['entryLabel'], exitLabel=move['exitLabel'], kind=move['kind'],
                           text=STAGES.get(stage, stage), reason=move.get('reason', '')))
    return dict(standard=not issues, passed=sum(bool(m.get('enabled')) for m in attempts), attempted=len(attempts),
                rightVerified=sum(bool(m.get('verified')) for m in rights), rightAttempted=len(rights),
                excluded=[dict(entryLabel=m['entryLabel'], exitLabel=m['exitLabel'], reason=m.get('reason', ''))
                          for m in moves if m.get('explicitlyExcluded')],
                connectors=connectors, issues=issues, **extra)


def run(project, site_id, out):
    out.mkdir(parents=True, exist_ok=False)
    prefix = str(out / 'check')
    fixtures = out / 'routes'
    policy, variants = variant_policy(project, site_id)
    if policy:
        print('PHASE Gleichwertige Radweg-/Fahrbahnvarianten: ' + ', '.join(
            '/'.join(g) for kind in ('exit', 'entry') for g in variants[kind]), flush=True)
    settings = dict(PREFIX=prefix, SOURCE=Path(prefix + '-approved.json'), REPORT=Path(prefix + '-routes.json'),
                    FIXTURES=fixtures, SELECTED={project.name: [site_id]}, POLICIES={site_id: policy} if policy else {},
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
    rights, covered = accept_bypasses(report, data['sites'][0], fixtures) if data['sites'] else ([], [])
    if rights or covered:
        settings['REPORT'].write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    result = summarize(report, site_id, connectors, variants, rights, covered)
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('RESULT ' + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--site', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.project.resolve(), args.site, args.out.resolve())
