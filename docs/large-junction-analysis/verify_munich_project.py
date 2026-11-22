"""Frozen, repeatable technical checks for newly approved Munich map cases.

No runtime writes, activation or geometry changes. Only exact current approvals
receive the resulting evidence. Run --freeze once, --collect for real routes.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
from unittest.mock import patch

import verify_ba01_movements as review

ROOT = review.ROOT
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'tools/junction-review'))
from junction_review.store import ProjectStore
from junction_review.gate_edit import validate_direction

PREFIX = 'review-batch-11-munich-project'
SOURCE = ROOT / (PREFIX + '-approved.json')
REPORT = ROOT / (PREFIX + '-routes.json')
PROPOSAL = ROOT / (PREFIX + '-proposed-catalog.json')
FIXTURES = REPO / 'backend/tests/fixtures/big-junctions/batch-11'
SUMMARY = ROOT / (PREFIX + '-technical.md')
PROJECT = REPO / '.local/junction-review/munich'
# Diagnosed from the unchanged real routes and frozen access/oneway tags.
# Only edges with BOTH endpoints inside the approved polygon are admitted.
INNER_ROADS = {
    'lane-candidate-1506641801': [169254469, 169254470, 371151395, 371151398, 410466890, 593148775],
    'lane-candidate-1956160': [26824141, 26825752, 1453301341],
    'lane-candidate-21029419': [33531622],
}


def technical_arms(site):
    """Unambiguous outward gate headings, never positional quadrant guesses.

    A strict four-cluster test rejects a missing or fifth direction. Existing
    discovery bearings can split opposite sides of the same wide street or put
    an exit on the next arm. Directions are independently checked against OSM.
    """
    values = []
    for gate in site['gates']:
        validate_direction(site, gate)
        sign = -1 if gate['kind'] == 'entry' else 1
        angle = math.degrees(math.atan2(sign*gate['forward'][0], sign*gate['forward'][1])) % 360
        values.append((angle, gate['label']))
    values.sort()
    groups = []
    for value in values:
        if not groups or value[0] - groups[-1][-1][0] > 40:
            groups.append([value])
        else:
            groups[-1].append(value)
    if len(groups) > 1 and (groups[0][0][0] + 360 - groups[-1][-1][0]) <= 40:
        groups[0] = groups.pop() + groups[0]
    if len(groups) != 4:
        raise ValueError(f'{len(groups)} eindeutige Radverkehrsrichtungen statt vier; keine automatische Makrofreigabe')
    def center(group):
        return math.degrees(math.atan2(sum(math.sin(math.radians(a)) for a, _ in group),
                                      sum(math.cos(math.radians(a)) for a, _ in group))) % 360
    groups.sort(key=center)
    first = min(range(4), key=lambda i: min(center(groups[i]), 360-center(groups[i])))
    groups = groups[first:] + groups[:first]
    angles = [center(g) for g in groups]
    gaps = [(angles[(i+1)%4]-angles[i]) % 360 for i in range(4)]
    if any(not 45 <= gap <= 135 for gap in gaps):
        raise ValueError('Strassenrichtungen nicht eindeutig als vierarmige Kreuzung zuordenbar')
    return dict(zip(review.check.ORDER, [[label for _, label in g] for g in groups]))


def ambiguous_exits(site):
    excluded = []
    kinds = {g['label']: g['kind'] for g in site['gates']}
    arms = site['proposedLogicalArms']
    for before, labels in arms.items():
        for after, targets in arms.items():
            if before == after or review.check.kind_for(before, after) == 'right':
                continue
            exits = [label for label in targets if kinds[label] == 'exit']
            if len(exits) > 1:
                for entry in labels:
                    if kinds[entry] != 'entry':
                        continue
                    for exit in exits:
                        excluded.append(dict(entryLabel=entry, exitLabel=exit,
                            reason='Mehrere Ausfahrten desselben Strassenarms: dieselbe Links-/Geradeausansage '
                                   'waere nicht eindeutig. Normale Hinweise beibehalten.'))
    return excluded


def freeze(project):
    if SOURCE.exists():
        raise ValueError('Frozen approval batch exists; reproduce it without --freeze')
    snapshot = ProjectStore(project).snapshot()
    sites, blocked = [], []
    pending = [s for s in snapshot['sites'] if s['status'] == 'confirmed' and s['decisionCurrent']
               and not s['evidenceCurrent'] and s.get('geometryMode') == 'editable']
    for number, site in enumerate(pending, 54):
        item = deepcopy(site)
        item.update(number=number, version=site['geometryRevision'], polygonApproved=True,
            reviewBinding={k: site[k] for k in ('geometryFingerprint','sourceFingerprint')},
            onRoadWayIds=sorted({g['osmWayId'] for g in site['gates'] if g.get('onRoad')}))
        try:
            item['proposedLogicalArms'] = technical_arms(site)
            item['excludedMovements'] = ambiguous_exits(item) + deepcopy(site.get('constraints', {}).get('excludedMovements', []))
            for way in item['ways']:
                way['geometry'] = [dict(lon=p[0], lat=p[1]) for p in way.pop('coordinates')]
            sites.append(item)
        except ValueError as error:
            blocked.append(dict(id=site['id'], number=number, name=site['name'], geometryRevision=site['geometryRevision'],
                reviewBinding=item['reviewBinding'], reason=str(error), logicalArms=site['logicalArms'], movements=[]))
    if not pending:
        raise ValueError('No pending current approvals')
    review.write(SOURCE, dict(project=snapshot['project'], source=snapshot['source'], sites=sites, blocked=blocked))
    print(f'Frozen: {len(sites)} routable cases, {len(blocked)} topology-blocked; runtime unchanged.', flush=True)


def run(collect=False, import_project=None):
    data = review.read(SOURCE)
    sites = data['sites']
    # Explicit cycling lanes continue across OSM way splits outside a gate.
    # This is graph evidence only, never a new gate or access override.
    from prepare_review_batch_routes import allowed
    support = {}
    for site in sites:
        lanes = [w['id'] for w in site['ways'] if allowed(w, [w['id']]) and any(
            'lane' in str(v) for k, v in w['tags'].items() if k.startswith('cycleway'))]
        site['onRoadWayIds'] = sorted(set(site['onRoadWayIds']) | set(lanes))
        site['internalRoads'] = INNER_ROADS.get(site['id'], [])
        # A reviewed carriageway gate can end on a short OSM split. Follow only
        # legally cycling, connected, same-named road pieces for sampling; do
        # not admit these whole roads as inner-corridor evidence.
        ways = {w['id']: w for w in site['ways']}
        names = {ways[g['osmWayId']]['tags'].get('name') for g in site['gates'] if g.get('onRoad')}
        names.discard(None)
        roads = {w['id'] for w in site['ways'] if w['tags'].get('name') in names and allowed(w, [w['id']])}
        selected = {g['osmWayId'] for g in site['gates'] if g.get('onRoad')}
        while True:
            nodes = {(p['lon'], p['lat']) for wid in selected for p in ways[wid]['geometry']}
            extra = {wid for wid in roads if any((p['lon'],p['lat']) in nodes for p in ways[wid]['geometry'])}
            if extra <= selected:
                break
            selected |= extra
        site['sampleRoadWayIds'] = sorted(selected)
        support[site['id']] = dict(onRoadWayIds=site['onRoadWayIds'], internalRoads=site['internalRoads'], sampleRoadWayIds=site['sampleRoadWayIds'])
    review.write(ROOT / (PREFIX + '-support.json'), support)
    original_read = review.read
    original_plan = review.check.plan
    def plan_with_continuations(site):
        sampling = dict(site, onRoadWayIds=sorted(set(site['onRoadWayIds']) | set(site['sampleRoadWayIds'])))
        return original_plan(sampling)
    internal = {**review.check.INTERNAL_ROADS, **{s['number']:s.get('internalRoads',[]) for s in sites}}
    with patch.object(review, 'read', side_effect=lambda path: deepcopy(data) if path == SOURCE else original_read(path)), \
            patch.object(review.check, 'plan', side_effect=plan_with_continuations), \
            patch.object(review.check, 'INTERNAL_ROADS', internal), patch.multiple(review,
            NUMBERS={s['number'] for s in sites}, SOURCE=SOURCE, FIXTURES=FIXTURES,
            REPORT=REPORT, MANIFEST=ROOT / (PREFIX + '-route-requests.json'), PROPOSAL=PROPOSAL,
            SUMMARY=SUMMARY, TITLE='Neue bestaetigte Muenchner Kartenfaelle',
            REGION='Projekt Muenchen', REVIEW_DATE='2026-11-21'):
        review.run(collect)
    report = review.read(REPORT)
    proposal = review.read(PROPOSAL)
    by_id = {s['id']: s for s in sites}
    for record in report['junctions']:
        record['reviewBinding'] = by_id[record['id']]['reviewBinding']
        record['name'] = by_id[record['id']]['name']
        record['graphSupport'] = support[record['id']]
        record['classificationBasis'] = 'validated-outward-directions-four-arm-order'
        for move in record['movements']:
            reason = move.get('reason', '')
            if move.get('enabled'):
                continue
            move['failureStage'] = ('instruction-clarity' if move.get('explicitlyExcluded') else
                'reference-sampling' if 'legal gate continuation' in reason else
                'gate-matching' if 'Wrong entry' in reason or 'Wrong exit' in reason else
                'polygon-crossing' if 'cross polygon' in reason else
                'directed-corridor' if 'directed OSM support' in reason else 'runtime-matching')
            if 'Production geometry' in reason:
                payload = review.read(FIXTURES / move['fixture'])
                for leg in payload['routes'][0]['legs']:
                    terminal = leg['steps'][-1]
                    if terminal['maneuver'].get('type') == 'arrive':
                        offset = review.check.meters(terminal['maneuver']['location'], terminal['geometry']['coordinates'][0])
                        if offset > .75:
                            move.update(failureStage='response-continuity', arrivalMarkerOffsetMeters=offset,
                                reason=f'OSRM-Ankunftsmarker {offset:.3f} m von der Geometrie entfernt; '
                                       'oberhalb der bestehenden 0.75-m-Grenze. Rohroute und Laufzeitgrenze unveraendert.')
                            for junction in proposal['junctions']:
                                if junction['id'] == record['id']:
                                    for configured in junction['movements']:
                                        if configured['id'] == move['id'] and not configured['enabled']:
                                            configured['disabledReason'] = move['reason']
    for blocked in data['blocked']:
        report['junctions'].append(dict(blocked, status='blocked-topology'))
    transport = [m for j in report['junctions'] for m in j['movements'] if any(
        token in m.get('reason', '') for token in ('Missing frozen API', 'URLError', 'HTTPError', 'TimeoutError', 'ConnectionError'))]
    if transport:
        report['status'] = 'incomplete'
    review.write(REPORT, report)
    review.write(PROPOSAL, proposal)
    with SUMMARY.open('a', encoding='utf-8') as file:
        file.write('\n## Nicht automatisch zuordenbare Topologie\n\n')
        for blocked in data['blocked']:
            file.write(f'- {blocked["name"]}: {blocked["reason"]}. Geometriefreigabe bleibt erhalten.\n')
        file.write('\nKeine Aktivierung oder Laufzeitaenderung. Exakte Fingerprint-Bindung an die Kartenfreigaben.\n')
        file.write('\n## Fallnamen\n\n')
        for record in report['junctions']:
            file.write(f'- K{record["number"]}: {record["name"]}\n')
        file.write('\nRadfahrstreifen-Fortsetzungen und freigegebene Strassenanschluesse werden '
            'getrennt fuer aeussere Referenzpunkte und innere Korridore nachgewiesen. '
            'Die konkreten OSM-Weg-IDs stehen im Supportbericht; keine pauschale Strassenfreigabe.\n')
        file.write('\nReichenbachbruecke: Zwei Referenzrouten zu Exit-6 haben einen um 0.893 m '
            'versetzten OSRM-Ankunftsmarker. Die bestehende Grenze betraegt 0.75 m; '
            'diese Beziehungen bleiben gesperrt. Keine Reparatur der Rohantwort und keine Lockerung der Laufzeitpruefung.\n')
    if transport:
        raise ValueError(f'{len(transport)} Routen noch ohne Transportnachweis; Ergebnisse nicht importiert')
    if import_project:
        store = ProjectStore(import_project)
        store.import_technical(report)
        # A completed rejection is evidence, not an unperformed 0/0 route check.
        with store.lock:
            state, _ = store._read()
            for blocked in data['blocked']:
                state['sites'][blocked['id']]['technicalEvidence']['technical'] = 'Technisch zurueckgestellt: ' + blocked['reason']
            from junction_review.store import atomic_write
            atomic_write(store.directory / 'project.json', state)
    print('Complete:', len(report['junctions']), 'cases;', report['fullCatalogChecks'], 'runtime unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PROJECT)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--import-results', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        freeze(args.project)
    run(args.collect, args.project if args.import_results else None)
