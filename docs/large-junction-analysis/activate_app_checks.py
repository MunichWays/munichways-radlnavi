"""Activate junctions finished as "Standardfall" by the review app's technical check.

Branch only, no deployment. Selected are all sites of the given projects that are
confirmed, have CURRENT evidence from an app check with standard=True and are not
yet in the runtime catalog. Each site's own app-check folder supplies the
fingerprint-bound report and the proposed junction (report number K900 is
replaced by the newly assigned K number).

Before anything is written, every real Standard route is replayed with the
production add_guidance against the merged catalog: an enabled movement yields
exactly its macro, the walking variant none, every other route no macro of this
junction. Reports and routes are copied into the repository so the activation
stays reproducible offline (test_review_app_activation.py).

--replace <site id> re-activates a junction that is already in the runtime
catalog after its geometry was changed and re-approved and re-checked in the
app: the runtime entry is replaced in place and the site keeps its K number.
Only explicitly named sites are replaced.

--accept-special <site id> activates a special case (standard=False) that Thomas
released with its individual failures: every issue must concern a movement that
stays disabled (normal guidance there); the enabled movements must all be
verified, and the replay still proves no failed route gets a macro.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
from unittest.mock import patch

import verify_munich_project as checks
from junction_review.store import ProjectStore, atomic_write
from src.big_junctions import add_guidance, validate_catalog

ROOT = checks.ROOT
REPO = checks.REPO
PROJECTS = checks.PROJECT.parent
CATALOG = REPO / 'backend/src/big_junctions.json'
REPORT_LABEL = 'K900'
EVIDENCE_FILES = ('check-approved.json', 'check-routes.json', 'check-technical.md', 'result.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _renumber(value, label):
    if isinstance(value, str):
        return value.replace(REPORT_LABEL, label)
    if isinstance(value, list):
        return [_renumber(v, label) for v in value]
    if isinstance(value, dict):
        return {k: _renumber(v, label) for k, v in value.items()}
    return value


def _special_ok(record, issues):
    moves = {(m['entryLabel'], m['exitLabel']): m for m in record['movements']}
    return bool(issues) and all((i.get('entryLabel'), i.get('exitLabel')) in moves
                                and not moves[(i['entryLabel'], i['exitLabel'])].get('enabled') for i in issues)


def collect(store, snapshot, runtime_ids, replace=(), special=()):
    """(site, folder, record, candidate) for every activatable app-checked site."""
    found = []
    for site in snapshot['sites']:
        check = (site.get('evidence') or {}).get('appCheck') if site.get('evidenceCurrent') else None
        if site['id'] in replace and not (check and check.get('standard')):
            raise ValueError('Replacement needs a current standard app check: ' + site['id'])
        accepted = site['id'] in special and check is not None
        if (site['id'] in runtime_ids and site['id'] not in replace) or not check or not (check.get('standard') or accepted):
            continue
        if site['status'] != 'confirmed' or not site['decisionCurrent']:
            raise ValueError('Exact current human approval required: ' + site['id'])
        folder = store.directory / check['folder'].replace('\\', '/')
        report = read(folder / 'check-routes.json')
        if report['status'] != 'complete' or report['runtimeModified'] is not False:
            raise ValueError('Complete technical evidence required: ' + site['id'])
        record = next(r for r in report['junctions'] if r['id'] == site['id'])
        binding = {k: site[k] for k in ('geometryFingerprint', 'sourceFingerprint')}
        if record['reviewBinding'] != binding or record['geometryRevision'] != site['geometryRevision']:
            raise ValueError('Stale app check: ' + site['id'])
        result = read(folder / 'result.json')
        if not result['standard'] and not (accepted and _special_ok(record, result['issues'])):
            raise ValueError('Not a standard case (or an issue touches an enabled movement): ' + site['id'])
        candidate = next(j for j in read(folder / 'check-proposed-catalog.json')['junctions'] if j['id'] == site['id'])
        if candidate['polygon']['coordinates'][0] != site['polygon']:
            raise ValueError('Polygon differs from approval: ' + site['id'])
        verified = {m['id'] for m in record['movements'] if m.get('enabled') and m.get('verified')}
        if not verified or verified != {m['id'] for m in candidate['movements'] if m.get('enabled')}:
            raise ValueError('Unverified activation: ' + site['id'])
        found.append((site, folder, record, candidate))
    return found


GATE_MATCH_M = 2.0


def _dist(a, b):
    return math.hypot((a[0] - b[0]) * 111320 * math.cos(math.radians(a[1])), (a[1] - b[1]) * 110540)


def _matches_enabled(junction, hit):
    """A macro on another real route is correct only where that route really takes an enabled,
    verified movement: same kind, entering and leaving at that movement's gates."""
    return any(m.get('enabled') and m['movement'] == hit['movement']
               and _dist(m['entry'], hit['entry']['location']) <= GATE_MATCH_M
               and _dist(m['exit'], hit['exit']['location']) <= GATE_MATCH_M for m in junction['movements'])


def replay(catalog, records, fixtures):
    """Production add_guidance on every real route; returns (positive, others) or raises.

    Enabled: exactly its own macro (walking: none). Disabled: no macro of this junction,
    unless the real route actually enters/leaves through the gates of another enabled,
    verified movement of the same kind (equivalent entry/exit in the same arm).
    """
    positive = others = 0
    with patch('src.big_junctions.catalog', return_value=catalog):
        for record in records:
            for move in record['movements']:
                path = Path(fixtures(record)) / move['fixture']
                if not path.exists():
                    if move.get('explicitlyExcluded'):
                        continue
                    raise ValueError('Missing route: ' + move['fixture'])
                payload = read(path)
                before = deepcopy(payload)
                result = add_guidance(payload)
                if payload != before:
                    raise ValueError('Route payload mutated: ' + move['fixture'])
                raw = (result or {}).get('routes', [{}])[0].get('guidance', {}).get('junctions', [])
                hits = [(h['id'], h['movement']) for h in raw]
                if move.get('enabled'):
                    if hits != [(record['id'], move['kind'])]:
                        raise ValueError(f"Wrong macro {hits} for {move['fixture']}")
                    walking = deepcopy(payload)
                    for leg in walking['routes'][0]['legs']:
                        for step in leg['steps']:
                            step['mode'] = 'walking'
                    if add_guidance(walking) is not None:
                        raise ValueError('Walking route gets a macro: ' + move['fixture'])
                    positive += 1
                else:
                    junction = next(j for j in catalog['junctions'] if j['id'] == record['id'])
                    for hit in (h for h in raw if h['id'] == record['id']):
                        if not _matches_enabled(junction, hit):
                            raise ValueError('Disabled movement gets a macro: ' + move['fixture'])
                    others += 1
    return positive, others


def activate(project_ids, batch, prefix, version, catalog_version, authorization, replace=(), special=()):
    current = read(CATALOG)
    runtime_ids = {j['id'] for j in current['junctions']}
    replace = set(replace)
    if replace - runtime_ids:
        raise ValueError('Not in the runtime catalog: ' + ', '.join(sorted(replace - runtime_ids)))
    stores = {pid: ProjectStore(PROJECTS / pid) for pid in project_ids}
    snapshots = {pid: store.snapshot() for pid, store in stores.items()}
    found = [(pid, *item) for pid in project_ids for item in collect(stores[pid], snapshots[pid], runtime_ids, replace, set(special))]
    if not found:
        raise ValueError('Nothing to activate')
    if replace - {site['id'] for _, site, *_ in found}:
        raise ValueError('Replacement not found in the given projects: ' + ', '.join(sorted(replace - {s['id'] for _, s, *_ in found})))
    every = [s for p in PROJECTS.iterdir() if (p / 'project.json').exists() for s in ProjectStore(p).snapshot()['sites']]
    next_number = max(s.get('number') or 0 for s in every) + 1
    assigned, candidates, records = {}, [], []
    for pid, site, folder, record, candidate in found:
        number = site.get('number')
        if number is None:
            number = assigned[site['id']] = next_number
            next_number += 1
        candidates.append(_renumber(candidate, f'K{number}'))
        records.append(dict(record, number=number, reportNumberOnly=False, appCheckFolder=folder.name))
    new = {c['id']: c for c in candidates}
    kept = [new.pop(j['id']) if j['id'] in replace else j for j in current['junctions']]
    result = dict(current, version=catalog_version, junctions=kept + [c for c in candidates if c['id'] in new])
    validate_catalog(result)
    folders = {r['id']: f for (_, _, f, r, _) in found}
    positive, others = replay(result, records, lambda r: folders[r['id']] / 'routes')
    print(f'Replay: {positive} macros exact, {others} other routes without a foreign macro, walking rejected.', flush=True)

    for pid, store in stores.items():
        if store.snapshot() != snapshots[pid]:
            raise ValueError('Concurrent review edit: ' + pid)
    target_fixtures = REPO / 'backend/tests/fixtures/big-junctions' / batch
    target_reports = ROOT / prefix
    if target_fixtures.exists() or target_reports.exists():
        raise ValueError(f'{batch} evidence already exists')
    for record in records:
        folder = folders[record['id']]
        (target_reports / folder.name).mkdir(parents=True)
        for name in EVIDENCE_FILES:
            shutil.copy2(folder / name, target_reports / folder.name / name)
        target_fixtures.mkdir(parents=True, exist_ok=True)
        for move in record['movements']:
            if (folder / 'routes' / move['fixture']).exists():
                shutil.copy2(folder / 'routes' / move['fixture'], target_fixtures / move['fixture'])
    atomic_write(ROOT / (prefix + '-catalog.json'), dict(junctions=candidates))
    atomic_write(CATALOG, result)
    (REPO / 'backend/VERSION').write_text(version + '\n', encoding='utf-8')

    activated = []
    for pid, store in stores.items():
        state, dataset = store._read()
        if any(site['id'] in assigned for site in dataset['sites']):
            for site in dataset['sites']:
                site['number'] = assigned.get(site['id'], site.get('number'))
            store.import_dataset(dataset, refresh=True)  # Display metadata only; approval hashes stay exact.
        state, _ = store._read()
        for (fpid, site, folder, record, _), candidate in zip(found, candidates):
            if fpid != pid:
                continue
            edit = state['sites'][site['id']]
            count = sum(bool(m.get('enabled')) for m in candidate['movements'])
            edit['technicalEvidence'].update(branchMovements=count, backendVersion=version,
                deploymentStatus='branch-ready', deployment=f'Im Branch aktiviert; Backend {version}; Deployment ausstehend')
            edit['version'] += 1
            edit.setdefault('history', []).append(dict(at=datetime.now(timezone.utc).isoformat(),
                action='branch-activation', backendVersion=version, movements=count))
            activated.append(dict(id=site['id'], projectId=pid, number=assigned.get(site['id'], site.get('number')),
                movements=count, appCheckFolder=folder.name, reviewBinding=record['reviewBinding'],
                geometryRevision=record['geometryRevision']))
        atomic_write(store.directory / 'project.json', state)
    enabled = [m for j in result['junctions'] if j['enabled'] for m in j['movements'] if m.get('enabled')]
    atomic_write(ROOT / (prefix + '-activation.json'), dict(backendVersion=version, catalogVersion=catalog_version,
        status='branch-ready', authorization=authorization, batch=batch, activated=activated, assignedNumbers=assigned,
        replaced=sorted(replace), acceptedSpecialCases=sorted(set(special)),
        replay=dict(positive=positive, others=others),
        activeJunctions=sum(j['enabled'] for j in result['junctions']), activeMovements=len(enabled)))
    print('Activated', len(candidates), 'cases;', sum(j['enabled'] for j in result['junctions']), 'junctions;',
          len(enabled), 'movements; numbers', assigned)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project', action='append', required=True)
    parser.add_argument('--batch', required=True, help='e.g. batch-15 (fixture folder)')
    parser.add_argument('--prefix', required=True, help='e.g. review-batch-15-ba05-app')
    parser.add_argument('--version', required=True)
    parser.add_argument('--catalog-version', required=True)
    parser.add_argument('--authorization', required=True)
    parser.add_argument('--replace', action='append', default=[], help='site id already live, re-approved and re-checked')
    parser.add_argument('--accept-special', action='append', default=[], help='site id released by Thomas with its failed movements disabled')
    args = parser.parse_args()
    activate(args.project, args.batch, args.prefix, args.version, args.catalog_version, args.authorization, args.replace, args.accept_special)
