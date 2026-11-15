"""Verify K23/K25/K28 against frozen real Standard routes; --collect fills missing fixtures.

Writes a proposal only. Activation is a separate, explicitly authorized operation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from unittest.mock import patch

import verify_ba09_movements as check

ROOT = check.ROOT
FIXTURES = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-04'
REPORT = ROOT / 'review-batch-04-ba01-routes.json'
MANIFEST = ROOT / 'review-batch-04-ba01-route-requests.json'
PROPOSAL = ROOT / 'review-batch-04-ba01-proposed-catalog.json'
NUMBERS = {23, 25, 28}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def configure(sites):
    check.FIXTURES = FIXTURES
    for site in sites:
        # The names denote clockwise slots; K28 is rotated northeast/southeast.
        check.ARMS[site['number']] = {
            arm: ([g for g in labels if g.startswith('Entry-')],
                  [g for g in labels if g.startswith('Exit-')])
            for arm, labels in zip(check.ORDER, site['proposedLogicalArms'].values())}


def run(collect=False):
    sites = [s for s in read(ROOT / 'review-batch-04-ba01-radlring-images/review-data.json')['sites']
             if s['number'] in NUMBERS]
    if len(sites) != 3 or any(not s['polygonApproved'] for s in sites):
        raise ValueError('Exact human geometry approval required for all three sites')
    configure(sites)
    FIXTURES.mkdir(exist_ok=True)
    manifest = read(MANIFEST) if MANIFEST.exists() else {}
    base = deepcopy(check.catalog())
    identifiers = {s['id'] for s in sites}
    base['junctions'] = [j for j in base['junctions'] if j['id'] not in identifiers]
    records, candidates = [], []
    for site in sites:
        tasks, samples = check.plan(site)
        topology = check.arm_topology(site)
        topology['review']['evidence'] = (
            f'Thomas approved K{site["number"]} v{site["version"]}; clockwise gate membership '
            'in review-batch-04-ba01-radlring-drafts.json; verified Standard routes.')
        candidate = dict(id=site['id'], name=site['name'], enabled=False,
            polygon={'type': 'Polygon', 'coordinates': [site['polygon']]},
            armTopology=topology, movements=[], review=dict(status='approved', date='2026-11-15',
            evidence=f'Thomas approved K{site["number"]} v{site["version"]}; review-batch-04-ba01-routes.json'))
        record = dict(id=site['id'], number=site['number'], geometryRevision=site['version'],
            status='complete', fixtureDirectory='batch-04', classificationBasis='reviewed-arm-order',
            logicalArms=site['proposedLogicalArms'], gateEvidence=samples, movements=tasks)

        def fetch(item):
            try:
                return check.collect(item, manifest, collect)
            except Exception as error:
                return error

        pending = [item for item in tasks if 'url' in item]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for item, result in zip(pending, pool.map(fetch, pending)):
                try:
                    if isinstance(result, Exception):
                        raise result
                    payload, retrieved = result
                    if retrieved:
                        write(FIXTURES / item['fixture'], payload)
                        manifest[item['fixture']] = dict(url=item['url'], retrievedAt=retrieved)
                    movement, evidence = check.verify(site, item, payload, base)
                    item.update(evidence)
                    if movement:
                        movement['review'] = dict(status='approved', date='2026-11-15',
                            evidence=f'Thomas approved K{site["number"]} v{site["version"]}; '
                            f'legal directed frozen OSM corridor, batch-04/{item["fixture"]}; '
                            'unchanged Standard response passes production matching.')
                        candidate['movements'].append(movement)
                except Exception as error:
                    item['reason'] = f'{type(error).__name__}: {error}'
                print(f'K{site["number"]} {item["entryLabel"]} -> {item["exitLabel"]} '
                      f'{item["kind"]}: '+('PASS' if item.get('verified') else item.get('reason', 'unchecked')), flush=True)
        for item in tasks:
            if item['kind'] != 'right' and not item.get('enabled'):
                candidate['movements'].append(dict(id=item['id'], enabled=False, movement=item['kind'],
                    entryArm=item['entryArm'], exitArm=item['exitArm'], entryLabel=item['entryLabel'],
                    exitLabel=item['exitLabel'], disabledReason=item.get('reason', 'Unverified')))
        candidate['enabled'] = any(m.get('enabled') for m in candidate['movements'])
        candidates.append(candidate)
        records.append(record)
        write(MANIFEST, manifest)
        write(REPORT, dict(version=1, status='in_progress', runtimeModified=False, junctions=records))
    proposal = dict(base, version='munich-big-junctions-v10', junctions=base['junctions']+candidates)
    check.validate_catalog(proposal)
    positive = right = walking = 0
    with patch('src.big_junctions.catalog', return_value=proposal):
        for record in records:
            for item in record['movements']:
                path = FIXTURES / item['fixture']
                if not path.exists():
                    continue
                payload = read(path)
                result = check.add_guidance(payload)
                if item.get('enabled'):
                    if result is None:
                        raise ValueError('Full catalog rejects verified movement: '+item['fixture'])
                    hits = result['routes'][0].pop('guidance')['junctions']
                    if len(hits) != 1 or hits[0]['movement'] != item['kind'] or result != payload:
                        raise ValueError('Wrong full-catalog classification or changed route')
                    positive += 1
                    on_foot = deepcopy(payload)
                    for leg in on_foot['routes'][0]['legs']:
                        for step in leg['steps']:
                            step['mode'] = 'walking'
                    if check.add_guidance(on_foot):
                        raise ValueError('Walking route triggers macro')
                    walking += 1
                elif item['kind'] == 'right':
                    if result is not None:
                        raise ValueError('Right-turn control triggers macro: '+item['fixture'])
                    right += 1
    write(PROPOSAL, proposal)
    report = dict(version=1, status='complete', completedAt=datetime.now(timezone.utc).isoformat(),
        runtimeModified=False, junctions=records, fullCatalogChecks=dict(
            positive=positive, rightTurnControls=right, walkingControls=walking))
    write(REPORT, report)
    lines = ['# BA01 · Technische Prüfung K23, K25, K28', '',
        'Echte Standardrouten, unveränderte freigegebene Flächen, gerichtete OSM-Korridore und '
        'Laufzeitprüfung. Aktivierungs-/Live-Stand siehe zentrale Übersicht.', '',
        '| Fall | Links/geradeaus bestanden | Rechtskontrollen |', '| --- | --- | --- |']
    for record in records:
        moves = record['movements']
        passed = sum(bool(m.get('enabled')) for m in moves)
        total = sum(m['kind'] != 'right' for m in moves)
        lines.append(f'| K{record["number"]} v{record["geometryRevision"]} | {passed}/{total} | '
                     f'{sum(m["kind"] == "right" and bool(m.get("verified")) for m in moves)}/4 |')
    lines += ['', f'Gesamtkatalog: {positive} positive Routen, {right} Rechts- und {walking} Fußkontrollen.', '', '## Gesperrte Beziehungen', '']
    for record in records:
        for item in record['movements']:
            if not item.get('verified'):
                lines.append(f'- K{record["number"]} {item["entryLabel"]} → {item["exitLabel"]}: {item.get("reason", "offen")}')
    if all(item.get('verified') for record in records for item in record['movements']):
        lines.append('Keine; alle geprüften Beziehungen bestanden.')
    (ROOT / 'review-batch-04-ba01-technical.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(f'Proposal: {positive} active movements; {right} right controls; {walking} walking controls. Runtime unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
