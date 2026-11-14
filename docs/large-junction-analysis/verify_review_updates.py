"""Check approved K07/K10/K19 revisions; freeze real routes, never activate them."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from unittest.mock import patch

import verify_ba09_movements as check
from src.big_junctions import leg_geometry

ROOT = check.ROOT
FIXTURES = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/review-updates-2026-11-14'
REPORT = ROOT / 'review-updates-2026-11-14-routes.json'
MANIFEST = ROOT / 'review-updates-2026-11-14-route-requests.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def prepare(site):
    """Four-arm macros and the separately specified Wilram connector cases."""
    standard = deepcopy(site)
    if site['number'] == 10:
        standard['gates'] = [g for g in standard['gates'] if g['label'] not in ('Entry-5', 'Exit-5')]
    check.ARMS[site['number']] = {arm: (v['entries'], v['exits'])
        for arm, v in site['review']['proposedLogicalArms'].items()}
    tasks, samples = check.plan(standard)
    for task in tasks:
        task['scope'] = 'standard-four-arm'
    if site['number'] == 10:
        edges = check.corridor_graph(site)
        for gate in site['gates']:
            if gate['label'] not in samples:
                samples[gate['label']] = check.gate_sample(gate, edges, site['polygon'])
        for instruction in read(ROOT / 'review-k10-wilram-plan.json')['relationships']:
            entry, exit = instruction['entry'], instruction['exit']
            identifier = f'wilram-{entry.lower()}-{exit.lower()}'
            item = dict(id=identifier, junctionId=site['id'], entryLabel=entry,
                exitLabel=exit, kind='special' if instruction.get('advance') else 'right',
                scope='wilram', enabled=False,
                fixture=f'{site["id"]}-{identifier}.json', requestedGuidance=instruction)
            if 'error' in samples[entry] or 'error' in samples[exit]:
                item['reason'] = samples[entry].get('error', samples[exit].get('error'))
            else:
                coord = lambda p: f'{p[0]:.9f},{p[1]:.9f}'
                item['url'] = ('https://api.radlnavi.munichways.de/route/v1/bike/'
                    + coord(samples[entry]['sample'])+';'+coord(samples[exit]['sample'])
                    + '?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false&variant=standard')
            tasks.append(item)
    return standard, tasks, samples


def verify_wilram(site, item, payload):
    """Evidence for the legal path is distinct from executable special guidance."""
    if payload.get('code') != 'Ok' or len(payload.get('routes', [])) != 1:
        raise ValueError('No single standard route')
    if any(w['distance'] > 5 for w in payload['waypoints']):
        raise ValueError('Routing endpoint snapped over 5m')
    route = payload['routes'][0]
    if any(leg_geometry(leg) is None for leg in route['legs']):
        raise ValueError('Production step continuity checks reject route')
    line = route['geometry']['coordinates']
    hits = check.crossings(line, site['polygon'])
    if item['kind'] == 'right' and not hits and not any(check.inside(p, site['polygon']) for p in line):
        # Wilram -> east uses the expressly excluded Thomasiusplatz side street.
        # A legal route outside the macro is the desired negative control.
        roads = site.get('onRoadWayIds', []) + [145178206]
        supported = check.corridor_check(line, check.graph(site['ways'], roads))
        return dict(verified=True, geometryVerified=True, bypassesPolygon=True,
            verifiedCyclingWayIds=supported, implementationPending=False,
            reason='Legal standard right turn outside the polygon; no macro intended')
    if len(hits) != 2 or check.inside(line[0], site['polygon']) or check.inside(line[-1], site['polygon']):
        raise ValueError('Route does not cross polygon exactly once')
    gates = {g['label']: g for g in site['gates']}
    entry, exit = hits
    for hit, label in ((entry, item['entryLabel']), (exit, item['exitLabel'])):
        if check.meters(hit['location'], gates[label]['location']) > 2.5:
            raise ValueError('Wrong '+label+' gate')
    start, end = entry['geometrySegmentIndex'], exit['geometrySegmentIndex']
    corridor = [entry['location'], *line[start+1:end+1], exit['location']]
    supported = check.corridor_check(corridor, check.corridor_graph(site))
    steps = [dict(location=s['maneuver']['location'], type=s['maneuver']['type'],
                  modifier=s['maneuver'].get('modifier'), name=s.get('name', ''),
                  mode=s.get('mode')) for leg in route['legs'] for s in leg['steps']
             if s['maneuver']['type'] not in ('depart', 'arrive')]
    return dict(geometryVerified=True, verifiedCyclingWayIds=supported,
        observedInstructions=steps, implementationPending=item['kind'] == 'special',
        reason=('Special sequence/internal checkpoints/alternative crossing require backend and app support'
                if item['kind'] == 'special' else 'Standard right turn; no macro intended'))


def run(collect=False):
    numbers = {7, 10, 19}
    all_sites = []
    for batch in ('review-batch-01-images', 'review-batch-03-ba09-remaining-images'):
        all_sites += read(ROOT / batch / 'review-data.json')['sites']
    sites = [s for s in all_sites if s['number'] in numbers]
    if len(sites) != len(set(numbers)) or any(not s['polygonApproved'] for s in sites):
        raise ValueError('Every requested site requires exact human geometry approval')
    FIXTURES.mkdir(exist_ok=True)
    check.FIXTURES = FIXTURES
    manifest = read(MANIFEST) if MANIFEST.exists() else {}
    report = read(REPORT) if REPORT.exists() else {'junctions': []}
    base = deepcopy(check.catalog())
    base['junctions'] = [j for j in base['junctions'] if j['id'] not in {s['id'] for s in sites}]
    candidates, records = [], []
    for site in sites:
        standard, tasks, samples = prepare(site)
        candidate = dict(id=site['id'], name=site['name'], enabled=True,
            polygon={'type': 'Polygon', 'coordinates': [site['polygon']]},
            armTopology=check.arm_topology(standard),
            review={'status': 'approved', 'date': '2026-11-14',
                    'evidence': f'Thomas approved K{site["number"]} v{site["version"]}; technical proposal only.'},
            movements=[])

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
                    if item['scope'] == 'wilram':
                        item.update(verify_wilram(site, item, payload))
                    else:
                        movement, evidence = check.verify(standard, item, payload, base)
                        item.update(evidence)
                        if movement:
                            movement['review'] = dict(status='approved', date='2026-11-14',
                                evidence=f'Human-approved K{site["number"]} v{site["version"]}; directed legal corridor and unchanged real Standard response review-updates-2026-11-14/{item["fixture"]}; runtime checks passed.')
                            candidate['movements'].append(movement)
                except Exception as error:
                    item['reason'] = str(error)
                print(f'K{site["number"]} {item["entryLabel"]} -> {item["exitLabel"]}: '
                      + ('PASS' if item.get('verified') else 'PATH OK; '+item['reason']
                         if item.get('geometryVerified') else item.get('reason', 'unchecked')), flush=True)
        candidate['enabled'] = bool(candidate['movements'])
        candidates.append(candidate)
        records.append(dict(id=site['id'], number=site['number'], geometryRevision=site['version'],
            status='complete', fixtureDirectory=FIXTURES.name, gateEvidence=samples, movements=tasks,
            runtimeModified=False, specialGuidanceImplemented=False if site['number'] == 10 else None))
    proposed = dict(base, version='munich-reviewed-updates-2026-11-14-proposed',
                    junctions=base['junctions']+candidates)
    check.validate_catalog(proposed)
    with patch('src.big_junctions.catalog', return_value=proposed):
        for record in records:
            for item in record['movements']:
                if not item.get('verified') and not item.get('geometryVerified'):
                    continue
                payload = read(FIXTURES / item['fixture'])
                result = check.add_guidance(payload)
                if bool(result) != bool(item.get('enabled')):
                    raise ValueError('Whole-catalog classification differs: '+item['id'])
                if result:
                    result['routes'][0].pop('guidance')
                    if result != payload:
                        raise ValueError('Raw route changed')
                    walking = deepcopy(payload)
                    for leg in walking['routes'][0]['legs']:
                        for step in leg['steps']:
                            step['mode'] = 'pushing bike'
                    if check.add_guidance(walking):
                        raise ValueError('Walking route triggered guidance')
    report['junctions'] = [j for j in report['junctions'] if j['number'] not in numbers]+records
    report.update(status='complete', checkedAt=datetime.now(timezone.utc).isoformat(), runtimeModified=False,
                  wholeCatalogVerified=True,
                  walkingControlsPassed=sum(m.get('enabled', False) for r in records for m in r['movements']))
    write(MANIFEST, manifest)
    write(REPORT, report)
    write(ROOT / 'review-updates-2026-11-14-proposed-catalog.json', proposed)
    print('Technical review finished; runtime catalog unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    args = parser.parse_args()
    run(args.collect)
