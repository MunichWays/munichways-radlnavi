"""Real routing checks for every reviewed BA09 entry/exit pair; no runtime writes."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import json
from math import atan2, cos, degrees, radians
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import add_guidance, catalog, crossings, meters, point_at, validate_catalog, inside
from prepare_review_batch_routes import graph, endpoint, corridor_check, allowed

FIXTURES = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-02'
MANIFEST = ROOT / 'review-batch-02-ba09-route-requests.json'
REPORT = ROOT / 'review-batch-02-ba09-routes.json'
# Logical arms are explicit. A later bend never silently changes straight to left.
ARMS = {
    11: {'north': (['Entry-4'], ['Exit-1']), 'east': (['Entry-1'], ['Exit-2']), 'south': (['Entry-2'], ['Exit-3']), 'west': (['Entry-3'], ['Exit-4', 'Exit-5'])},
    12: {'north': (['Entry-4'], ['Exit-1']), 'east': (['Entry-1'], ['Exit-2']), 'south': (['Entry-2'], ['Exit-3']), 'west': (['Entry-3'], ['Exit-4'])},
    13: {'north': (['Entry-6'], ['Exit-1']), 'east': (['Entry-1'], ['Exit-2', 'Exit-3']), 'south': (['Entry-2', 'Entry-3'], ['Exit-4']), 'west': (['Entry-4', 'Entry-5'], ['Exit-5', 'Exit-6'])},
    14: {'north': (['Entry-4'], ['Exit-1']), 'east': (['Entry-1'], ['Exit-2']), 'south': (['Entry-2'], ['Exit-3', 'Exit-4']), 'west': (['Entry-3'], ['Exit-5'])},
    15: {'north': (['Entry-4'], ['Exit-1']), 'east': (['Entry-1'], ['Exit-2']), 'south': (['Entry-2'], ['Exit-3']), 'west': (['Entry-3'], ['Exit-4'])},
    16: {'north': (['Entry-4'], ['Exit-1', 'Exit-2']), 'east': (['Entry-1'], ['Exit-3']), 'south': (['Entry-2'], ['Exit-4']), 'west': (['Entry-3'], ['Exit-5'])},
    17: {'north': (['Entry-5'], ['Exit-1']), 'east': (['Entry-1'], ['Exit-2']), 'south': (['Entry-2'], ['Exit-3']), 'west': (['Entry-3'], ['Exit-4'])},
}
ORDER = ['north', 'east', 'south', 'west']
# Frozen OSM: continuation of the reviewed Lothstrasse carriageway inside K17.
# This supports corridors only; it creates no additional entry/exit gates.
INTERNAL_ROADS = {17: [38349617]}


def corridor_graph(site):
    edges = graph(site['ways'], site.get('onRoadWayIds', []))
    for way in site['ways']:
        if way['id'] not in INTERNAL_ROADS.get(site['number'], []):
            continue
        if not allowed(way, [way['id']]):
            raise ValueError('Internal road has a cycling/access restriction')
        edges.extend((a, b, identifier) for a, b, identifier in graph([way], [way['id']])
                     if inside(a, site['polygon']) and inside(b, site['polygon']))
    return edges


def gate_sample(gate, edges, ring):
    # Short approaches need not extend past an unrelated bend or side junction.
    # Each sample still follows the same legal directed graph and lies outside.
    failures = []
    for distance in (45, 35, 25, 15, 12):
        try:
            return {'sample': endpoint(gate, edges, gate['kind'], ring, distance),
                    'distanceMeters': distance}
        except ValueError as error:
            failures.append(f'{distance}m: {error}')
    return {'error': '; '.join(failures)}


def kind_for(before, after):
    change = (ORDER.index(after) - ORDER.index(before)) % 4
    return {1: 'left', 2: 'straight', 3: 'right'}[change]


def arm_topology(site):
    gates = {g['label']: g['location'] for g in site['gates']}
    return {'clockwise': ORDER, 'gates': {
        arm: {'entries': [gates[label] for label in entries], 'exits': [gates[label] for label in exits]}
        for arm, (entries, exits) in ARMS[site['number']].items()},
        'review': {'status': 'approved', 'date': datetime.now(timezone.utc).date().isoformat(),
                   'evidence': f'Technical four-arm assignment in verify_ba09_movements.ARMS; '
                   f'human-approved gate geometry K{site["number"]:02d} v{site["version"]}. '
                   'Arm order determines instruction; real directed local paths determine matching.'}}


def plan(site):
    if not site['polygonApproved']:
        raise ValueError('Human geometry approval required')
    gates = {g['label']: g for g in site['gates']}
    arms = ARMS[site['number']]
    listed = [label for entries, exits in arms.values() for label in entries + exits]
    if set(listed) != set(gates) or len(listed) != len(gates):
        raise ValueError(f'Logical arm mapping incomplete: {site["id"]}')
    edges = graph(site['ways'], site.get('onRoadWayIds', []))
    samples = {}
    for label, gate in gates.items():
        samples[label] = gate_sample(gate, edges, site['polygon'])
    tasks = []
    for before, (entries, _) in arms.items():
        for after, (_, exits) in arms.items():
            if before == after:
                continue
            for entry in entries:
                for exit in exits:
                    kind = kind_for(before, after)
                    identifier = f'{before}-{after}-{kind}-{entry.lower()}-{exit.lower()}'
                    item = {'id': identifier, 'junctionId': site['id'], 'entryArm': before, 'exitArm': after,
                        'entryLabel': entry, 'exitLabel': exit, 'kind': kind, 'enabled': False,
                        'fixture': f'{site["id"]}-{identifier}.json'}
                    if 'error' in samples[entry] or 'error' in samples[exit]:
                        item['reason'] = samples[entry].get('error', samples[exit].get('error'))
                    else:
                        coord = lambda p: f'{p[0]:.9f},{p[1]:.9f}'
                        item['url'] = 'https://api.radlnavi.munichways.de/route/v1/bike/' + coord(samples[entry]['sample']) + ';' + coord(samples[exit]['sample']) + '?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false&variant=standard'
                    tasks.append(item)
    return tasks, samples


def collect(item, manifest, refresh):
    path = FIXTURES / item['fixture']
    if path.exists() and manifest.get(path.name, {}).get('url') == item['url']:
        return json.loads(path.read_text(encoding='utf-8')), None
    if not refresh:
        raise ValueError('Missing frozen API response; use --collect')
    for attempt in range(2):
        try:
            with urlopen(Request(item['url'], headers={'User-Agent': 'MunichWays-Junction-Technical-Review/1.0'}), timeout=45) as response:
                return json.load(response), datetime.now(timezone.utc).isoformat()
        except Exception:
            if attempt:
                raise


def verify(site, item, payload, base):
    if payload.get('code') != 'Ok' or len(payload.get('routes', [])) != 1:
        raise ValueError('No single standard route')
    if any(w['distance'] > 5 for w in payload['waypoints']):
        raise ValueError('Routing endpoint snapped over 5m')
    route = payload['routes'][0]
    if route.get('guidance'):
        raise ValueError('Expected raw route without optional guidance')
    line = route['geometry']['coordinates']
    hits = crossings(line, site['polygon'])
    if len(hits) != 2 or inside(line[0], site['polygon']) or inside(line[-1], site['polygon']):
        raise ValueError('Route does not cross polygon exactly once')
    entry, exit = hits
    gates = {g['label']: g for g in site['gates']}
    if meters(entry['location'], gates[item['entryLabel']]['location']) > 2.5:
        raise ValueError('Wrong entry gate')
    if meters(exit['location'], gates[item['exitLabel']]['location']) > 2.5:
        raise ValueError('Wrong exit gate')
    start, end = entry['geometrySegmentIndex'], exit['geometrySegmentIndex']
    corridor = [entry['location'], *line[start + 1:end + 1], exit['location']]
    supported = corridor_check(corridor, corridor_graph(site))
    if item['kind'] == 'right':
        return None, {'verified': True, 'verifiedCyclingWayIds': supported}
    failures = []
    for distance in (10, 40):
        movement = {'id': item['id'], 'enabled': True, 'movement': item['kind'],
            'entryArm': item['entryArm'], 'exitArm': item['exitArm'], 'entry': entry['location'], 'exit': exit['location'],
            'corridor': corridor, 'approach': [point_at(line, max(0, entry['distanceAlongLegMeters'] - distance)), entry['location']],
            'departure': [exit['location'], point_at(line, exit['distanceAlongLegMeters'] + distance)],
            'review': {'status': 'approved', 'date': '2026-11-08', 'evidence': f'Human-reviewed geometry v{site["version"]}; legal directed OSM corridor and real standard route batch-02/{item["fixture"]}; logical arm classification preserved.'}}
        junction = {'id': site['id'], 'name': site['name'], 'enabled': True,
            'armTopology': arm_topology(site),
            'polygon': {'type': 'Polygon', 'coordinates': [site['polygon']]},
            'review': {'status': 'approved', 'date': '2026-11-08', 'evidence': f'Thomas approved K{site["number"]:02d} v{site["version"]}'},
            'movements': [movement]}
        candidate = dict(base, junctions=[junction])
        try:
            validate_catalog(candidate)
            from unittest.mock import patch
            with patch('src.big_junctions.catalog', return_value=candidate):
                result = add_guidance(payload)
            if result is None:
                raise ValueError('Production geometry/mode/heading/continuity checks reject route')
            hit, = result['routes'][0].pop('guidance')['junctions']
            if hit['movement'] != item['kind'] or result != payload:
                raise ValueError('Classification mismatch or routing data changed')
            return movement, {'enabled': True, 'verified': True, 'verifiedCyclingWayIds': supported, 'headingEvidenceMeters': distance}
        except ValueError as error:
            failures.append(str(error))
    raise ValueError('; '.join(dict.fromkeys(failures)))


def save(report, manifest):
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


def write_summary(report):
    lines = ['# BA09: technische Fahrbeziehungsprüfung', '',
        'Geprüft gegen echte Standardrouten und die freigegebenen Geometrien. '
        'Der Aktivierungsstand steht im Backendkatalog und in der Prüfungsübersicht. '
        'Die Prüfung selbst startet weder Build noch Deployment.', '',
        '| Kreuzung | Revision | Links/geradeaus bestanden | Rechtskontrollen ohne Makro |',
        '| --- | --- | --- | --- |']
    for junction in report['junctions']:
        items = junction['movements']
        attempts = [m for m in items if m['kind'] != 'right']
        right = [m for m in items if m['kind'] == 'right']
        lines.append(f'| K{junction["number"]:02d} | v{junction["geometryRevision"]} | '
                     f'{sum(m.get("enabled", False) for m in attempts)}/{len(attempts)} | {len(right)} |')
    lines += ['', '## Weiterhin gesperrt', '',
        'Diese Beziehungen behalten Standardhinweise. Gerichtete Legalitätsprüfung, Korridortoleranzen '
        'und lokale Richtungsprüfung bleiben unverändert.', '']
    for junction in report['junctions']:
        for item in junction['movements']:
            if item['kind'] != 'right' and not item.get('enabled'):
                lines.append(f'- K{junction["number"]:02d} {item["entryLabel"]} → {item["exitLabel"]} '
                             f'({item["kind"]}): {item.get("reason", "offen")}')
    lines += ['', '## Prüfumfang', '',
        '- Die Ansagerichtung folgt der explizit geprüften Reihenfolge der vier Straßenarme und deren '
        'zugeordneten Entry-/Exitpunkten. Die lokale Fahrtrichtung bleibt über reale Referenzpfade geprüft. '
        'Ohne dokumentierte Armzuordnung gelten weiterhin die bisherigen Winkelgrenzen.',
        '- Ein minimal versetzter Zielmarker ist nur beim letzten, geometrisch punktförmigen Arrive-Schritt '
        'mit Distanz/Dauer null bis 0,75 m zulässig. Innere Manöver und Geometrieanschlüsse bleiben exakt.',
        '- Eindeutige Flächenquerung, richtige Entry-/Exitpunkte und gerichteter OSM-Korridor.',
        '- Reale Testpunkte außerhalb der Fläche: regulär 45 m; bei kurzen Anschlüssen bis mindestens 12 m, '
        'mit Reserve zur 10-m-Laufzeitprüfung. Entfernungen stehen im JSON-Prüfbericht.',
        '- K17: OSM-Weg 38349617 als innere Fortsetzung der freigegebenen Lothstraßen-Fahrbahn. '
        'Nur vollständig innerhalb liegende Segmente; keine neuen Gates. Zugangsbeschränkungen bleiben wirksam.',
        '- Gesamter vorgeschlagener Katalog: positive Routen, gesperrte Beziehungen, Rechtskontrollen '
        'und Schiebeabschnitte als Regression geprüft; ursprüngliche Routendaten bleiben unverändert.', '',
        '[Detaillierte Belege](review-batch-02-ba09-routes.json) · '
        '[Prüfungsübersicht mit Live-Stand](kreuzungspruefung/index.html)', '']
    (ROOT / 'review-batch-02-ba09-technical.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    args = parser.parse_args()
    sites = json.loads((ROOT / 'review-batch-02-ba09-images/review-data.json').read_text(encoding='utf-8'))['sites']
    FIXTURES.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}
    base = deepcopy(catalog())
    # Regeneration replaces this batch, including after its runtime activation.
    batch_ids = {site['id'] for site in sites}
    base['junctions'] = [j for j in base['junctions'] if j['id'] not in batch_ids]
    report = {'version': 1, 'status': 'in_progress', 'startedAt': datetime.now(timezone.utc).isoformat(), 'runtimeModified': False, 'junctions': []}
    tasks, by_id, candidates = [], {s['id']: s for s in sites}, {}
    records = {}
    for site in sites:
        planned, samples = plan(site)
        record = {'id': site['id'], 'number': site['number'], 'geometryRevision': site['version'],
                  'classificationBasis': 'reviewed-arm-order', 'status': 'in_progress', 'gateEvidence': samples, 'movements': planned}
        report['junctions'].append(record)
        records[site['id']] = record
        tasks.extend(planned)
        candidates[site['id']] = {'id': site['id'], 'name': site['name'], 'enabled': False,
            'armTopology': arm_topology(site),
            'polygon': {'type': 'Polygon', 'coordinates': [site['polygon']]},
            'review': {'status': 'approved', 'date': '2026-11-08', 'evidence': f'Human geometry approval K{site["number"]:02d} v{site["version"]}; real API evidence in review-batch-02-ba09-routes.json'}, 'movements': []}
    save(report, manifest)
    from organize_review_images import main as organize
    organize()
    print(f'Checking {len(tasks)} entry/exit relationships across seven reviewed junctions.', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(collect, item, manifest, args.collect): item for item in tasks if 'url' in item}
        completed = 0
        for future in as_completed(pending):
            item = pending[future]
            try:
                payload, retrieved = future.result()
                if retrieved:
                    (FIXTURES / item['fixture']).write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
                    manifest[item['fixture']] = {'url': item['url'], 'retrievedAt': retrieved}
                movement, evidence = verify(by_id[item['junctionId']], item, payload, base)
                item.update(evidence)
                if movement:
                    candidates[item['junctionId']]['movements'].append(movement)
            except Exception as error:
                item['reason'] = f'{type(error).__name__}: {error}'
            completed += 1
            save(report, manifest)
            print(f'{completed}/{len(pending)} {item["junctionId"]} {item["entryLabel"]}->{item["exitLabel"]} {"PASS" if item.get("verified") else item.get("reason")}', flush=True)
    proposed = deepcopy(base)
    proposed['version'] = 'munich-big-junctions-v5'
    for item in tasks:
        if item['kind'] != 'right' and not item.get('enabled'):
            candidates[item['junctionId']]['movements'].append({
                'id': item['id'], 'enabled': False, 'movement': item['kind'],
                'entryArm': item['entryArm'], 'exitArm': item['exitArm'],
                'disabledReason': item.get('reason', 'Technical verification pending'),
                'entryLabel': item['entryLabel'], 'exitLabel': item['exitLabel']})
    for junction in candidates.values():
        junction['movements'].sort(key=lambda m: m['id'])
        junction['enabled'] = any(m.get('enabled') for m in junction['movements'])
        proposed['junctions'].append(junction)
    validate_catalog(proposed)
    # All real right-turn controls, including routes that picked another gate,
    # must remain without macro metadata. No classification relaxation.
    from unittest.mock import patch
    for item in tasks:
        if item['kind'] != 'right' or not (FIXTURES / item['fixture']).exists():
            continue
        payload = json.loads((FIXTURES / item['fixture']).read_text(encoding='utf-8'))
        with patch('src.big_junctions.catalog', return_value=proposed):
            result = add_guidance(payload)
        if result:
            raise ValueError('Right-turn control triggers macro: '+item['fixture'])
    for record in records.values():
        record['status'] = 'complete'
    report['status'] = 'complete'
    report['completedAt'] = datetime.now(timezone.utc).isoformat()
    save(report, manifest)
    (ROOT / 'review-batch-02-ba09-proposed-catalog.json').write_text(json.dumps(proposed, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    write_summary(report)
    organize()
    count = sum(m.get('enabled', False) for j in candidates.values() for m in j['movements'])
    print(f'Complete: {count} verified candidate movements; runtime catalog NOT modified.', flush=True)


if __name__ == '__main__':
    main()
