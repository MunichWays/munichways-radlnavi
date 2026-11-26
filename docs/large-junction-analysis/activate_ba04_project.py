"""Explicitly activate the verified batch-14 BA04 relationships in the branch, no deployment."""
from datetime import datetime, timezone

import verify_ba04_project as ba04
from junction_review.store import ProjectStore, atomic_write
from src.big_junctions import validate_catalog

batch = ba04.batch
VERSION = '2.4.22'
CATALOG_VERSION = 'munich-big-junctions-v22'
MANIFEST = batch.ROOT / 'review-batch-14-activation.json'
AUTHORIZATION = 'Thomas: alle nur aktivieren, Commit und Deploy kommen später; 2026-11-26.'


def activate():
    read = batch.checks.review.read
    report = read(ba04.REPORT)
    proposal = read(batch.ROOT / (ba04.PREFIX + '-proposed-catalog.json'))
    if report['status'] != 'complete' or report['runtimeModified'] is not False:
        raise ValueError('Complete technical evidence required')
    records = {r['id']: r for r in report['junctions']}
    candidates = {j['id']: j for j in proposal['junctions'] if j['id'] in records}
    if set(candidates) != set(records):
        raise ValueError('Proposal and report differ')
    stores = {pid: ProjectStore(batch.PROJECTS / pid) for pid in {r['reviewProjectId'] for r in records.values()}}
    snapshots = {pid: store.snapshot() for pid, store in stores.items()}
    every = [s for p in batch.PROJECTS.iterdir() if (p / 'project.json').exists()
             for s in ProjectStore(p).snapshot()['sites']]
    next_number = max(s.get('number') or 0 for s in every) + 1
    assigned = {}
    for site_id, record in records.items():
        site = next(s for s in snapshots[record['reviewProjectId']]['sites'] if s['id'] == site_id)
        candidate = candidates[site_id]
        if (site['status'] != 'confirmed' or not site['decisionCurrent'] or not site['evidenceCurrent']
                or any(site[k] != v for k, v in record['reviewBinding'].items())
                or candidate['polygon']['coordinates'][0] != site['polygon']):
            raise ValueError('Stale review: ' + site_id)
        verified = {m['id'] for m in record['movements'] if m.get('enabled') and m.get('verified')}
        if not verified or verified != {m['id'] for m in candidate['movements'] if m.get('enabled')}:
            raise ValueError('Unverified activation: ' + site_id)
        if site.get('number') is None:
            assigned[site_id] = next_number
            next_number += 1
    current_path = batch.checks.REPO / 'backend/src/big_junctions.json'
    current = read(current_path)
    if any(j['id'] in records for j in current['junctions']):
        raise ValueError('Batch 14 already in runtime catalog')
    result = dict(current, version=CATALOG_VERSION,
                  junctions=current['junctions'] + [candidates[i] for i in records])
    validate_catalog(result)
    for pid, store in stores.items():
        if store.snapshot() != snapshots[pid]:
            raise ValueError('Concurrent review edit: ' + pid)
    atomic_write(current_path, result)
    (batch.checks.REPO / 'backend/VERSION').write_text(VERSION + '\n', encoding='utf-8')
    activated = []
    for pid, store in stores.items():
        state, dataset = store._read()
        if any(site['id'] in assigned for site in dataset['sites']):
            for site in dataset['sites']:
                site['number'] = assigned.get(site['id'], site.get('number'))
            store.import_dataset(dataset, refresh=True)  # Display metadata only; approval hashes stay exact.
        state, _ = store._read()
        for site_id, record in records.items():
            if record['reviewProjectId'] != pid:
                continue
            edit = state['sites'][site_id]
            count = sum(bool(m.get('enabled')) for m in candidates[site_id]['movements'])
            edit['technicalEvidence'].update(branchMovements=count, backendVersion=VERSION,
                deploymentStatus='branch-ready', deployment=f'Im Branch aktiviert; Backend {VERSION}; Deployment ausstehend')
            edit['version'] += 1
            edit.setdefault('history', []).append(dict(at=datetime.now(timezone.utc).isoformat(),
                action='branch-activation', backendVersion=VERSION, movements=count))
            activated.append(dict(id=site_id, projectId=pid, movements=count,
                reviewBinding=record['reviewBinding'], assignedNumber=assigned.get(site_id)))
        atomic_write(store.directory / 'project.json', state)
    enabled = [m for j in result['junctions'] if j['enabled'] for m in j['movements'] if m.get('enabled')]
    atomic_write(MANIFEST, dict(backendVersion=VERSION, catalogVersion=CATALOG_VERSION, status='branch-ready',
        authorization=AUTHORIZATION, activated=activated, assignedNumbers=assigned,
        activeJunctions=sum(j['enabled'] for j in result['junctions']), activeMovements=len(enabled)))
    print('Activated', len(records), 'cases;', sum(j['enabled'] for j in result['junctions']), 'junctions;',
          len(enabled), 'movements; numbers', assigned)


if __name__ == '__main__':
    activate()
