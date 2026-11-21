"""Reproduce the three approved drawn-area cases; activation is explicit."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import patch

import verify_ba01_movements as review

ROOT = review.ROOT
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'tools/junction-review'))
from junction_review.store import ProjectStore, atomic_write

PREFIX = 'review-batch-10-drawn-six'
SOURCE = ROOT / (PREFIX + '-approved.json')
REPORT = ROOT / (PREFIX + '-routes.json')
PROPOSAL = ROOT / (PREFIX + '-proposed-catalog.json')
PROJECT = REPO / '.local/junction-review/area-d8cedf2a8d9e717e'
# Logical street continuations, clockwise; split automatic bearings are paired.
# Gate positions and the approved geometry fingerprint remain untouched.
CASES = {
    'osm-junction-2041371': (51, {
        'north': ['Entry-6', 'Exit-1'], 'east': ['Entry-1', 'Exit-2'],
        'south': ['Entry-2', 'Exit-3'], 'west': ['Entry-4', 'Entry-5', 'Exit-4']}),
    'osm-junction-14658540': (52, {
        'north': ['Entry-4', 'Exit-1'], 'east': ['Entry-1', 'Exit-4'],
        'south': ['Entry-2', 'Exit-2'], 'west': ['Entry-3', 'Exit-3']}),
    'osm-junction-2041368': (53, {
        'north': ['Entry-4', 'Exit-1'], 'east': ['Entry-1', 'Exit-2'],
        'south': ['Entry-2', 'Exit-3'], 'west': ['Entry-3', 'Exit-4']})}


def freeze(project):
    snapshot = ProjectStore(project).snapshot()
    sites = []
    for site in snapshot['sites']:
        if site['id'] not in CASES:
            continue
        if site['status'] != 'confirmed' or not site['decisionCurrent']:
            raise ValueError('Current human approval required: ' + site['id'])
        number, arms = CASES[site['id']]
        item = deepcopy(site)
        item.update(number=number, version=site['geometryRevision'], polygonApproved=True,
                    proposedLogicalArms=arms,
                    reviewBinding={k: site[k] for k in ('geometryFingerprint', 'sourceFingerprint')},
                    onRoadWayIds=[g['osmWayId'] for g in site['gates'] if g.get('onRoad')])
        for way in item['ways']:
            way['geometry'] = [dict(lon=p[0], lat=p[1]) for p in way.pop('coordinates')]
        sites.append(item)
    if len(sites) != 3:
        raise ValueError('Expected exactly P3, P5, P6')
    review.write(SOURCE, dict(project=snapshot['project'], source=snapshot['source'], sites=sites))


def run(collect=False):
    sites = review.read(SOURCE)['sites']
    # The reviewed road exit at P5 is reached through the short legal inner
    # Blankbauerstrasse connector. Admit only its wholly internal segments.
    internal = {**review.check.INTERNAL_ROADS, 52: [3302000]}
    with patch.object(review.check, 'INTERNAL_ROADS', internal), patch.multiple(review, NUMBERS={51, 52, 53}, SOURCE=SOURCE,
            FIXTURES=REPO / 'backend/tests/fixtures/big-junctions/batch-10', REPORT=REPORT,
            MANIFEST=ROOT / (PREFIX + '-route-requests.json'), PROPOSAL=PROPOSAL,
            SUMMARY=ROOT / (PREFIX + '-technical.md'), TITLE='P3 / K51, P5 / K52, P6 / K53',
            REGION='Gezeichnete 6 Faelle', REVIEW_DATE='2026-11-21'):
        review.run(collect)
    report = review.read(REPORT)
    by_id = {s['id']: s for s in sites}
    for record in report['junctions']:
        record['reviewBinding'] = by_id[record['id']]['reviewBinding']
        record['projectLabel'] = 'P' + str(by_id[record['id']]['priorityRank'])
    review.write(REPORT, report)
    summary = ROOT / (PREFIX + '-technical.md')
    with summary.open('a', encoding='utf-8') as file:
        file.write('\n## Zuordnung und Diagnose\n\n'
            '- P3 = K51, P5 = K52, P6 = K53. Die P-Nummern im lokalen Projekt bleiben erhalten.\n'
            '- P3 Entry-5: Die echten Referenzrouten werden auf den benachbarten Entry-4 verlegt. '
            'Entry-5 nach Exit-1/Exit-2 bleibt deshalb deaktiviert; keine Aenderung der freigegebenen Geometrie. '
            'Die Rechtsroute ist ebenfalls kein Nachweis fuer Entry-5, bleibt aber ohne Makro.\n'
            '- P5: Der gerichtete innere Abschnitt von Blankbauerstrasse, OSM 3302000, '
            'verbindet die Radwege mit dem freigegebenen Strassen-Exit auf OSM 3302001. '
            'Nur vollstaendig innere Segmente werden zur Korridorpruefung zugelassen.\n'
            '- Armzuordnung: P5 automatische Arm-1/2 = Nord, Arm-3 = Ost, Arm-4/5 = Sued, Arm-6 = West; '
            'P6 Arm-1 = Nord, Arm-2 = Ost, Arm-3/4 = Sued, Arm-5 = West. '
            'Die technische Zuordnung liegt separat zur unveraenderten Geometriefreigabe.\n'
            '- Aktivierungsstand steht in der lokalen Kartenuebersicht; kein Deployment durch dieses Pruefkommando.\n')


def activate(project):
    store = ProjectStore(project)
    report, proposal = review.read(REPORT), review.read(PROPOSAL)
    snapshot = {s['id']: s for s in store.snapshot()['sites']}
    if report['status'] != 'complete' or len(report['junctions']) != 3:
        raise ValueError('Complete technical report required')
    additions = []
    for record in report['junctions']:
        site = snapshot[record['id']]
        if site['status'] != 'confirmed' or not site['decisionCurrent'] or any(
                site[k] != record['reviewBinding'][k] for k in ('geometryFingerprint', 'sourceFingerprint')):
            raise ValueError('Approval changed: ' + site['id'])
        junction = deepcopy(next(j for j in proposal['junctions'] if j['id'] == site['id']))
        if junction['polygon']['coordinates'][0] != site['polygon']:
            raise ValueError('Polygon mismatch')
        verified = {m['id'] for m in record['movements'] if m.get('enabled') and m.get('verified')}
        enabled = {m['id'] for m in junction['movements'] if m.get('enabled')}
        if not enabled or enabled != verified:
            raise ValueError('No verified movement set: ' + site['id'])
        additions.append(junction)
    path = REPO / 'backend/src/big_junctions.json'
    current = review.read(path)
    ids = {j['id'] for j in additions}
    result = dict(current, version='munich-big-junctions-v19',
                  junctions=[j for j in current['junctions'] if j['id'] not in ids] + additions)
    review.check.validate_catalog(result)
    store.import_technical(report)
    atomic_write(path, result)
    (REPO / 'backend/VERSION').write_text('2.4.19\n', encoding='utf-8')
    with store.lock:
        state, _ = store._read()
        for junction in additions:
            edit = state['sites'][junction['id']]
            count = sum(bool(m.get('enabled')) for m in junction['movements'])
            edit['technicalEvidence'].update(branchMovements=count, backendVersion='2.4.19',
                deploymentStatus='branch-ready', deployment='Im Branch aktiviert; noch nicht deployed')
            edit['version'] += 1
            edit.setdefault('history', []).append(dict(at=datetime.now(timezone.utc).isoformat(),
                action='branch-activation', backendVersion='2.4.19', movements=count))
        atomic_write(store.directory / 'project.json', state)
    print('P3/P5/P6 activated in branch; not deployed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=PROJECT)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        freeze(args.project)
    run(args.collect)
    if args.activate:
        activate(args.project)
