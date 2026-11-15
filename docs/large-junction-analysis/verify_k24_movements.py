"""Technical K24 draft with agreed left-side templates; never activates runtime data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from verify_ba01_movements import ROOT, read, write, configure
import verify_ba09_movements as check

FIXTURES = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/k24-two-way'
CONTRACTS = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/k24-instructions'
MANIFEST = ROOT / 'review-k24-route-requests.json'
REPORT = ROOT / 'review-k24-v1-draft-technical.json'
PROPOSAL = ROOT / 'review-k24-proposed-catalog.json'
# Reviewed meaning: only these outgoing directions use the left-hand side
# against the adjacent normal carriageway flow. Exit-1 remains standard.
REVERSE_SIDE_EXITS = {'Exit-3', 'Exit-6'}


def run(collect=False):
    site = next(s for s in read(ROOT / 'review-batch-04-ba01-radlring-images/review-data.json')['sites'] if s['number'] == 24)
    configure([site])
    check.FIXTURES = FIXTURES
    FIXTURES.mkdir(exist_ok=True)
    CONTRACTS.mkdir(exist_ok=True)
    tasks, samples = check.plan(site, draft=True)
    # At 45m the west reference starts before Herzog-Rudolf-Strasse and
    # Standard routing bypasses K24. At 25m both legal points belong to K24.
    gates = {g['label']: g for g in site['gates']}
    edges = check.graph(site['ways'], site['onRoadWayIds'])
    for item in tasks:
        if (item['entryLabel'], item['exitLabel']) == ('Entry-4', 'Exit-6'):
            item['rejectedReference'] = {
                'fixture': 'k24-two-way-detours/'+item['fixture'], 'url': item['url'],
                'reason': '45m reference route bypasses K24 via Herzog-Rudolf-Strasse; retained as a negative control.'}
            start = check.endpoint(gates['Entry-4'], edges, 'entry', site['polygon'], 25)
            end = check.endpoint(gates['Exit-6'], edges, 'exit', site['polygon'], 25)
            coord = lambda p: f'{p[0]:.9f},{p[1]:.9f}'
            item['url'] = ('https://api.radlnavi.munichways.de/route/v1/bike/' + coord(start) + ';' + coord(end)
                + '?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false&variant=standard')
            item['sampleDistanceMeters'] = {'entry': 25, 'exit': 25}
    base = deepcopy(check.catalog())
    base['junctions'] = [j for j in base['junctions'] if j['id'] != site['id']]
    candidate = dict(id=site['id'], name=site['name'], enabled=True,
        polygon={'type': 'Polygon', 'coordinates': [site['polygon']]},
        armTopology=check.arm_topology(site), movements=[],
        review=dict(status='approved', date='2026-11-15',
                    evidence='Technical test proposal only; geometry/activation approval pending.'))
    candidate['armTopology']['review']['evidence'] = 'K24 draft clockwise arm membership; target-side semantics explicitly clarified by Thomas.'
    manifest = read(MANIFEST) if MANIFEST.exists() else {}
    def fetch(item):
        try:
            return check.collect(item, manifest, collect)
        except Exception as error:
            return error
    pending = [m for m in tasks if 'url' in m]
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
                    movement['review'] = dict(status='approved', date='2026-11-15', evidence=
                        'Technical draft: legal directed Standard route; agreed target-side semantics; no runtime activation.')
                    if item['exitLabel'] in REVERSE_SIDE_EXITS:
                        movement.update(instructionTemplate='two-way-left-near' if item['kind'] == 'left'
                            else 'two-way-straight-opposite', targetCyclingSide='left-against-traffic',
                            targetWayType='two-way-cycleway')
                        item['instructionTemplate'] = movement['instructionTemplate']
                    candidate['movements'].append(movement)
            except Exception as error:
                item['reason'] = str(error)
            print(item['entryLabel'], '->', item['exitLabel'], item['kind'],
                  'PASS' if item.get('verified') else item.get('reason'), flush=True)
    proposal = dict(base, junctions=base['junctions']+[candidate], activationApproved=False,
                    scope='K24 technical test proposal only; human geometry/activation approval pending')
    check.validate_catalog(proposal)
    with patch('src.big_junctions.catalog', return_value=proposal):
        for item in tasks:
            path = FIXTURES / item['fixture']
            if not path.exists():
                continue
            payload = read(path)
            modern = check.add_guidance(payload, instruction_guidance=True)
            if item.get('enabled'):
                if modern is None:
                    raise ValueError('Full catalog rejects '+item['fixture'])
                hit, = modern['routes'][0]['guidance']['junctions']
                if bool(hit.get('instruction')) != bool(item.get('instructionTemplate')):
                    raise ValueError('Wrong target-side template')
                write(CONTRACTS / item['fixture'], modern)
                if item.get('instructionTemplate'):
                    if check.add_guidance(payload, sequence_guidance=True) is not None:
                        raise ValueError('Legacy app must retain ordinary instructions')
            elif item['kind'] == 'right' and modern is not None:
                raise ValueError('Right-turn control triggers macro')
    write(MANIFEST, manifest)
    write(PROPOSAL, proposal)
    write(REPORT, dict(id=site['id'], number=24, geometryRevision=site['version'],
        status='draft-technical-check', runtimeModified=False, checkedAt=datetime.now(timezone.utc).isoformat(),
        gateEvidence=samples, fixtureDirectory='k24-two-way', movements=tasks))
    print('K24 draft:', sum(bool(m.get('enabled')) for m in tasks), 'passed; runtime unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
