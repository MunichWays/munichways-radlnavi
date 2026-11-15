"""Verify K30's three-arm geometry using existing angle checks, never runtime writes."""
import argparse
import gzip
import json
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

import verify_ba09_movements as check
from verify_ba01_movements import read, write, ROOT

FIXTURES = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/k30'
REPORT = ROOT / 'review-k30-v3-draft-technical.json'
MANIFEST = ROOT / 'review-k30-route-requests.json'
PROPOSAL = ROOT / 'review-k30-proposed-catalog.json'
# Explicit intended actions; no fabricated fourth arm or relaxed angle limits.
PAIRS = [('Entry-1', 'Exit-3', 'left'), ('Entry-2', 'Exit-1', 'straight'),
         ('Entry-4', 'Exit-2', 'left'), ('Entry-1', 'Exit-1', 'right'),
         ('Entry-2', 'Exit-2', 'right'), ('Entry-4', 'Exit-3', 'straight')]


def run(collect=False):
    site = read(ROOT / 'review-batch-05-ba01-remaining-images/review-data.json')['sites'][0]
    if not site['polygonApproved'] or site['version'] != 3:
        raise ValueError('Exact approved K30 v3 required')
    gates = {g['label']: g for g in site['gates']}
    arms = {label: arm for arm, labels in site['proposedLogicalArms'].items() for label in labels}
    supplement = read_connector_snapshot()
    replaced = {1127704280, 1265305106, 1265305108, 67562511}
    evidence_ways = [w for w in site['ways'] if w['id'] not in replaced]
    evidence_ways += [w for w in supplement['response']['elements'] if w['id'] in replaced]
    edges = check.graph(evidence_ways, site['onRoadWayIds'])
    samples = {label: check.gate_sample(g, edges, site['polygon']) for label, g in gates.items()}
    check.FIXTURES = FIXTURES
    FIXTURES.mkdir(exist_ok=True)
    manifest = read(MANIFEST) if MANIFEST.exists() else {}
    base = deepcopy(check.catalog())
    base['junctions'] = [j for j in base['junctions'] if j['id'] != site['id']]
    candidate = dict(id=site['id'], name=site['name'], enabled=True,
        polygon=dict(type='Polygon', coordinates=[site['polygon']]), movements=[],
        review=dict(status='approved', date='2026-11-15', evidence='Thomas approved K30 v3; real Standard routes and unchanged production angle checks.'))
    tasks = []
    excluded = {(m['entryLabel'], m['exitLabel']): m['reason'] for m in site['excludedMovements']}
    for entry_label, exit_label, kind in PAIRS:
        identifier = f'{entry_label.lower()}-{exit_label.lower()}-{kind}'
        item = dict(id=identifier, kind=kind, entryLabel=entry_label, exitLabel=exit_label,
            entryArm=arms[entry_label], exitArm=arms[exit_label], enabled=False,
            fixture=f'lenbach-pacelli-{identifier}.json')
        tasks.append(item)
        try:
            coord = lambda p: f'{p[0]:.9f},{p[1]:.9f}'
            item['url'] = ('https://api.radlnavi.munichways.de/route/v1/bike/'
                +coord(samples[entry_label]['sample'])+';'+coord(samples[exit_label]['sample'])
                +'?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false&variant=standard')
            payload, retrieved = check.collect(item, manifest, collect)
            if retrieved:
                write(FIXTURES / item['fixture'], payload)
                manifest[item['fixture']] = dict(url=item['url'], retrievedAt=retrieved)
            if (entry_label, exit_label) in excluded:
                item['reason'] = excluded[entry_label, exit_label]
                item['explicitlyExcluded'] = True
                continue
            line = payload['routes'][0]['geometry']['coordinates']
            if payload.get('code') != 'Ok' or len(payload['routes']) != 1 or payload['routes'][0].get('guidance'):
                raise ValueError('Expected one raw Standard route')
            if any(w['distance'] > 5 for w in payload['waypoints']):
                raise ValueError('Endpoint snapped over 5m')
            hits = check.crossings(line, site['polygon'])
            if len(hits) != 2 or check.inside(line[0], site['polygon']) or check.inside(line[-1], site['polygon']):
                raise ValueError('Route does not cross polygon exactly once')
            entry, exit = hits
            if any(check.meters(hit['location'], gates[label]['location']) > 2.5
                   for hit, label in [(entry, entry_label), (exit, exit_label)]):
                raise ValueError('Wrong entry or exit gate')
            corridor = [entry['location'], *line[entry['geometrySegmentIndex']+1:exit['geometrySegmentIndex']+1], exit['location']]
            item['verifiedCyclingWayIds'] = check.corridor_check(corridor, edges)
            if kind == 'right':
                item['verified'] = True
                continue
            failures = []
            for distance in (10, 40):
                movement = dict(id=identifier, enabled=True, movement=kind,
                    entryArm=arms[entry_label], exitArm=arms[exit_label],
                    entryLabel=entry_label, exitLabel=exit_label, entry=entry['location'], exit=exit['location'],
                    corridor=corridor,
                    approach=[check.point_at(line, max(0, entry['distanceAlongLegMeters']-distance)), entry['location']],
                    departure=[exit['location'], check.point_at(line, exit['distanceAlongLegMeters']+distance)],
                    review=dict(status='approved', date='2026-11-15', evidence='K30 v3 human approval; legal frozen OSM corridor and real Standard route; unchanged angle validation.'))
                trial = dict(base, junctions=[dict(candidate, movements=[movement])])
                try:
                    check.validate_catalog(trial)
                    with patch('src.big_junctions.catalog', return_value=trial):
                        result = check.add_guidance(payload)
                    if result is None or result['routes'][0].pop('guidance')['junctions'][0]['movement'] != kind or result != payload:
                        raise ValueError('Production matcher rejected route')
                    candidate['movements'].append(movement)
                    item.update(enabled=True, verified=True, headingEvidenceMeters=distance)
                    break
                except ValueError as error:
                    failures.append(str(error))
            if not item['enabled']:
                raise ValueError('; '.join(failures))
        except Exception as error:
            item['reason'] = str(error)
        finally:
            print(entry_label, '->', exit_label, kind, 'PASS' if item.get('verified') else item.get('reason'), flush=True)
            write(MANIFEST, manifest)
    for item in tasks:
        if item['kind'] != 'right' and not item['enabled']:
            candidate['movements'].append(dict(id=item['id'], enabled=False, movement=item['kind'],
                entryArm=item['entryArm'], exitArm=item['exitArm'], entryLabel=item['entryLabel'],
                exitLabel=item['exitLabel'], disabledReason=item.get('reason', 'Unverified')))
    candidate['enabled'] = any(m['enabled'] for m in candidate['movements'])
    proposal = dict(base, junctions=base['junctions']+[candidate])
    check.validate_catalog(proposal)
    with patch('src.big_junctions.catalog', return_value=proposal):
        for item in tasks:
            path = FIXTURES / item['fixture']
            if not path.exists():
                continue
            payload = read(path)
            result = check.add_guidance(payload)
            if bool(result) != item['enabled']:
                raise ValueError('Full catalog positive/negative mismatch: '+item['fixture'])
            if result:
                result['routes'][0].pop('guidance')
                if result != payload:
                    raise ValueError('Raw route changed')
                walking = deepcopy(payload)
                for leg in walking['routes'][0]['legs']:
                    for step in leg['steps']:
                        step['mode'] = 'walking'
                if check.add_guidance(walking):
                    raise ValueError('Walking route triggers macro')
    write(PROPOSAL, proposal)
    write(REPORT, dict(id=site['id'], number=30, geometryRevision=3, status='complete',
        checkedAt=datetime.now(timezone.utc).isoformat(), runtimeModified=False,
        fixtureDirectory='k30', classificationBasis='existing-approach-departure-angle-checks',
        gateEvidence=samples, movements=tasks,
        connectorEvidence=dict(snapshot='review-k30-internal-connector-osm.json.gz',
            retrievedAt=supplement['retrievedAt'], replacedWayIds=sorted(replaced),
            scope='Current internal cycling connector; approved polygon and gates unchanged.')))


def read_connector_snapshot():
    return json.loads(gzip.decompress(
        (ROOT / 'review-k30-internal-connector-osm.json.gz').read_bytes()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
