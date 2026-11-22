"""Frozen BA01–BA03 approvals, K89 and fresh K44/K46 routing rechecks.

Uses the existing directed-corridor and complete-catalog checks. No activation,
runtime writes or changes to approved geometry. --collect only fills this batch's
new fixture directory, so older routing results remain reproducible.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

import verify_munich_project as checks
from junction_review.store import ProjectStore, atomic_write

ROOT = checks.ROOT
PROJECTS = checks.PROJECT.parent
PREFIX = 'review-batch-12-ba01-ba03-project'
SOURCE = ROOT / (PREFIX + '-approved.json')
REPORT = ROOT / (PREFIX + '-routes.json')
FIXTURES = checks.FIXTURES.parent / 'batch-12'
TITLE = 'BA01–BA03, K89 und Wiedervorlagen K44/K46'
POLICIES = {}
SELECTED = {
    'area-603b6d7ec04db77e': ['osm-junction-13353278127'],
    'area-369e14ac688ef47e': ['osm-junction-20981714', 'osm-junction-1240216331'],
    'area-8c7276beba7eaf73': ['osm-junction-618702506', 'osm-junction-21632176',
                              'osm-junction-361803', 'osm-junction-361802'],
    'munich': ['lane-candidate-1954489', 'lane-candidate-361786', 'lane-candidate-428767'],
}
# Frozen legal road connectors diagnosed from unchanged reference routes.
# Existing corridor_graph admits ONLY segments with both ends inside the polygon.
INNER_ROADS = {
    'osm-junction-618702506': [968751243],
    'osm-junction-361802': [37342343, 456746076, 549021913],
    'lane-candidate-428767': [264964142],
}


def freeze():
    if SOURCE.exists():
        raise ValueError('Frozen batch exists; reproduce without --freeze')
    sites, blocked = [], []
    # Internal report numbers do not assign new K numbers in local projects.
    next_number = 101
    for project_id, identifiers in SELECTED.items():
        snapshot = ProjectStore(PROJECTS / project_id).snapshot()
        for site_id in identifiers:
            site = next(s for s in snapshot['sites'] if s['id'] == site_id)
            if site['status'] != 'confirmed' or not site['decisionCurrent']:
                raise ValueError('Exact current human approval required: ' + site_id)
            item = deepcopy(site)
            number = site.get('number')
            if number is None:
                number = next_number
                next_number += 1
            item.update(number=number, reportNumberOnly=site.get('number') is None,
                reviewProjectId=project_id, version=site['geometryRevision'], polygonApproved=True,
                reviewBinding={k: site[k] for k in ('geometryFingerprint', 'sourceFingerprint')})
            constraints = site.get('constraints') or {}
            item['onRoadWayIds'] = sorted(set(constraints.get('onRoadWayIds', [])) |
                                          {g['osmWayId'] for g in site['gates'] if g.get('onRoad')})
            item['normalGuidanceGates'] = constraints.get('normalGuidanceGates', [])
            try:
                if site_id == 'osm-junction-1240216331':
                    for gate in site['gates']:
                        checks.validate_direction(site, gate)
                    item['proposedLogicalArms'] = dict(zip(checks.review.check.ORDER, site['logicalArms'].values()))
                    item['angleClassification'] = True
                    item['technicalTopologyReview'] = ('Partial crossing: only Entry-1 to Exit-1 straight; '
                        'Exit-2 is an ordinary right-turn control. Use unchanged production angle checks; '
                        'no invented fourth direction or four-arm classification.')
                else:
                    item['proposedLogicalArms'] = checks.technical_arms(site)
                policy = POLICIES.get(site_id) or ((site.get('evidence') or {}).get('guidanceReview')
                                                 if site.get('evidenceCurrent') else None)
                if policy:
                    item['guidanceReview'] = deepcopy(policy)
                    item['normalGuidanceGates'] = sorted(set(item['normalGuidanceGates']) | set(policy.get('normalGuidanceGates', [])))
                    item['equivalentExitGroups'] = deepcopy(policy.get('equivalentExitGroups', []))
                    item['equivalentEntryGroups'] = deepcopy(policy.get('equivalentEntryGroups', []))
                    for labels in item['proposedLogicalArms'].values():
                        labels[:] = [label for label in labels if label not in item['normalGuidanceGates']]
                item['excludedMovements'] = checks.ambiguous_exits(item) + deepcopy(constraints.get('excludedMovements', []))
                for way in item['ways']:
                    way['geometry'] = [dict(lon=p[0], lat=p[1]) for p in way.pop('coordinates')]
                sites.append(item)
            except ValueError as error:
                blocked.append(dict(id=site_id, number=number, name=site['name'],
                    reviewProjectId=project_id, geometryRevision=site['geometryRevision'],
                    reviewBinding=item['reviewBinding'], reason=str(error),
                    logicalArms=site['logicalArms'], movements=[]))
    atomic_write(SOURCE, dict(project=dict(id='ba01-ba03-technical', city='München'),
        source=dict(frozenAt=datetime.now(timezone.utc).isoformat(),
                    note='Report-only numbers >=101; original project numbering unchanged.'),
        sites=sites, blocked=blocked))
    print(f'Frozen: {len(sites)} routable, {len(blocked)} topology checks pending.', flush=True)


def run(collect=False, import_results=False):
    with patch.multiple(checks, PREFIX=PREFIX, SOURCE=SOURCE, REPORT=REPORT,
            PROPOSAL=ROOT / (PREFIX + '-proposed-catalog.json'), FIXTURES=FIXTURES,
            SUMMARY=ROOT / (PREFIX + '-technical.md'), INNER_ROADS={**checks.INNER_ROADS, **INNER_ROADS}):
        checks.run(collect, review_date=checks.review.read(SOURCE)['source']['frozenAt'][:10])
    data = checks.review.read(SOURCE)
    report = checks.review.read(REPORT)
    by_id = {s['id']: s for s in data['sites'] + data['blocked']}
    equivalent_routes = 0
    for record in report['junctions']:
        record['reviewProjectId'] = by_id[record['id']]['reviewProjectId']
        record['reportNumberOnly'] = by_id[record['id']].get('reportNumberOnly', False)
        if by_id[record['id']].get('guidanceReview'):
            record['guidanceReview'] = by_id[record['id']]['guidanceReview']
        if by_id[record['id']].get('angleClassification'):
            record['classificationBasis'] = 'existing-runtime-angle-checks-straight-only'
        site = by_id[record['id']]
        gates = {g['label']: g for g in site.get('gates', [])}
        for move in record['movements']:
            if move.get('reason') != 'ValueError: Wrong entry gate':
                continue
            group = next((g for g in site.get('equivalentEntryGroups', []) if move['entryLabel'] in g), None)
            if not group:
                continue
            payload = checks.review.read(FIXTURES / move['fixture'])
            hits = checks.review.check.crossings(payload['routes'][0]['geometry']['coordinates'], site['polygon'])
            if len(hits) != 2:
                continue
            actual = min(group, key=lambda label: checks.review.check.meters(hits[0]['location'], gates[label]['location']))
            covered = next((m for m in record['movements'] if m.get('enabled') and
                (m['entryLabel'], m['exitLabel'], m['kind']) == (actual, move['exitLabel'], move['kind'])), None)
            if covered and checks.review.check.meters(hits[0]['location'], gates[actual]['location']) <= 2.5:
                move.update(coverageStatus='covered-equivalent-entry', coveredByEquivalentMovement=covered['id'],
                    reason=f'Standardrouting führt über den ausdrücklich gleichwertigen {actual}; '
                           'diese reale Route erhält die gleiche Kreuzungsansage über dessen geprüfte Beziehung.')
                equivalent_routes += 1
    if equivalent_routes:
        report['fullCatalogChecks']['equivalentEntryRoutesCovered'] = equivalent_routes
    atomic_write(REPORT, report)
    lines = ['# '+TITLE, '',
        'Prüfnummern ab 101 dienen nur diesem Bericht; die Projekte behalten ihre bisherigen P-Nummern.',
        'Unveränderte freigegebene Geometrien, aktuelle echte Standardrouten, gerichtete OSM-Korridore und Produktionsprüfung.',
        'Keine Aktivierung und kein Deployment. Neue Ergebnisse ersetzen keine Live-Verifikation.', '',
        '| Projekt / Kreuzung | Links / geradeaus bestanden | Rechtskontrollen bestanden |', '| --- | --- | --- |']
    for record in report['junctions']:
        moves = record['movements']
        left_straight = [m for m in moves if m['kind'] in ('left', 'straight')]
        right = [m for m in moves if m['kind'] == 'right']
        lines.append(f"| {record['reviewProjectId']} · {record['name']} | "
                     f"{sum(bool(m.get('enabled')) for m in left_straight)}/{len(left_straight)} | "
                     f"{sum(bool(m.get('verified')) for m in right)}/{len(right)} |")
    lines += ['', '## Ausgenommene oder nicht nachgewiesene Beziehungen', '']
    for record in report['junctions']:
        if record.get('reason'):
            lines.append(f"- {record['name']}: {record['reason']}")
        for move in record['movements']:
            if not move.get('verified'):
                lines.append(f"- {record['name']} · {move['entryLabel']} → {move['exitLabel']}: {move.get('reason', 'offen')}")
    lines += ['', '## Nachweise', '',
        '- Innere Straßenverbinder: exakte IDs im Supportbericht, nur erlaubte gerichtete Segmente vollständig innerhalb der freigegebenen Fläche.']
    if 'osm-junction-1240216331' in by_id:
        lines.append('- Stachus: ausschließlich Entry-1 → Exit-1 geradeaus; bestehende Winkelprüfung ohne Vierarm-Metadaten, rechte Beziehung als Kontrolle.')
    for site in data['sites']:
        if site.get('guidanceReview'):
            lines.append(f"- {site['name']}: {site['guidanceReview']['reason']}")
    (ROOT / (PREFIX + '-technical.md')).write_text('\n'.join(lines)+'\n', encoding='utf-8')
    if import_results:
        # Check every owner before changing any project. Do not partially import
        # an old batch if a human edited another project during route collection.
        for project_id in SELECTED:
            current = {s['id']: s for s in ProjectStore(PROJECTS / project_id).snapshot()['sites']}
            for record in report['junctions']:
                if record['reviewProjectId'] != project_id:
                    continue
                site = current[record['id']]
                if site['status'] != 'confirmed' or not site['decisionCurrent'] or any(
                        site[k] != v for k, v in record['reviewBinding'].items()):
                    raise ValueError('Approval changed since freeze: ' + site['id'])
        for project_id in SELECTED:
            store = ProjectStore(PROJECTS / project_id)
            records = [r for r in report['junctions'] if r['reviewProjectId'] == project_id]
            previous = {s['id']: deepcopy(s.get('evidence', {})) for s in store.snapshot()['sites']}
            store.import_technical(dict(report, junctions=records))
            with store.lock:
                state, _ = store._read()
                for record in records:
                    evidence = state['sites'][record['id']]['technicalEvidence']
                    if record.get('status') == 'blocked-topology':
                        evidence['technical'] = 'Technisch zurückgestellt: ' + record['reason']
                    old = previous[record['id']]
                    if old.get('deploymentStatus') == 'live':
                        for key in ('deployment', 'deploymentStatus', 'liveMovements', 'branchMovements',
                                    'backendVersion', 'fieldTests', 'rechecks'):
                            if key in old:
                                evidence[key] = old[key]
                        suffix = ' · neue technische Prüfung aktiviert keine weiteren Beziehungen'
                        if not evidence['deployment'].endswith(suffix):
                            evidence['deployment'] += suffix
                        for recheck in evidence.get('rechecks', []):
                            move = next((m for m in record['movements'] if
                                (m['entryLabel'], m['exitLabel']) == (recheck['entry'], recheck['exit'])), None)
                            if move and move.get('enabled'):
                                recheck.update(date=report['completedAt'][:10], checkedAt=report['completedAt'],
                                    technicalStatus='passed', reason='Erneut technisch bestanden; diese Beziehung ist noch nicht aktiviert.')
                atomic_write(store.directory / 'project.json', state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--import-results', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        freeze()
    run(args.collect, args.import_results)
