"""Explicitly activate the latest approved batch-12/13 relationships, no deployment."""
from copy import deepcopy
from datetime import datetime, timezone

import verify_ba01_ba03_project as batch
import verify_guidance_followups as followups
from junction_review.store import ProjectStore, atomic_write
from src.big_junctions import validate_catalog

VERSION = '2.4.21'
MANIFEST = batch.ROOT / 'review-batch-12-13-activation.json'


def activate():
    records, candidates = {}, {}
    for prefix in (batch.PREFIX, followups.PREFIX):
        report = batch.checks.review.read(batch.ROOT / (prefix+'-routes.json'))
        proposal = batch.checks.review.read(batch.ROOT / (prefix+'-proposed-catalog.json'))
        if report['status'] != 'complete' or report['runtimeModified'] is not False:
            raise ValueError('Complete technical evidence required')
        for record in report['junctions']:
            records[record['id']] = record
            candidates[record['id']] = deepcopy(next(j for j in proposal['junctions'] if j['id']==record['id']))
    stores = {r['reviewProjectId']: ProjectStore(batch.PROJECTS/r['reviewProjectId']) for r in records.values()}
    snapshots = {pid: store.snapshot() for pid, store in stores.items()}
    current_path = batch.checks.REPO / 'backend/src/big_junctions.json'
    current = batch.checks.review.read(current_path)
    assigned = batch.checks.review.read(MANIFEST).get('assignedNumbers', {}) if MANIFEST.exists() else {}
    historical = {j['id']: j for j in batch.checks.review.read(
        batch.ROOT/(followups.PREFIX+'-proposed-catalog.json'))['junctions']}
    historical['nymphenburger-waisenhaus'] = next(j for j in batch.checks.review.read(
        batch.ROOT/(batch.PREFIX+'-proposed-catalog.json'))['junctions'] if j['id']=='nymphenburger-waisenhaus')
    next_number = max(s.get('number') or 0 for snap in snapshots.values() for s in snap['sites']) + 1
    for site_id, record in records.items():
        site = next(s for s in snapshots[record['reviewProjectId']]['sites'] if s['id']==site_id)
        # Retain explicit legacy scope metadata such as excludedApproaches.
        candidate = candidates[site_id] = dict(deepcopy(historical.get(site_id, {})), **candidates[site_id])
        candidate = candidates[site_id] = dict(deepcopy(historical.get(site_id, {})), **candidate)
        if (site['status'] != 'confirmed' or not site['decisionCurrent'] or not site['evidenceCurrent']
                or any(site[k] != v for k,v in record['reviewBinding'].items())
                or candidate['polygon']['coordinates'][0] != site['polygon']):
            raise ValueError('Stale review: '+site_id)
        verified = {m['id'] for m in record['movements'] if m.get('enabled') and m.get('verified')}
        if not verified or verified != {m['id'] for m in candidate['movements'] if m.get('enabled')}:
            raise ValueError('Unverified activation: '+site_id)
        if record.get('guidanceReview'):
            candidate['review']['guidancePolicy'] = record['guidanceReview']
        if site_id == 'lane-candidate-428767':
            movement_id = 'east-south-left-entry-2-exit-3'
            previous = next(m for m in historical[site_id]['movements'] if m['id']==movement_id)
            movement = next(m for m in candidate['movements'] if m['id']==movement_id)
            if previous['corridor'] != movement['corridor']:
                movement['alternateCorridors'] = [dict(coordinates=previous['corridor'], review=dict(
                    status='approved', evidence='Previously verified unchanged batch-08 real route: '
                    'lane-candidate-428767-east-south-left-entry-2-exit-3.json; retain alongside current batch-12 route.'))]
        if site.get('number') is None:
            assigned[site_id] = next_number
            next_number += 1
    result = dict(current, version='munich-big-junctions-v21', junctions=[
        j for j in current['junctions'] if j['id'] not in records] + list(candidates.values()))
    validate_catalog(result)
    for pid, store in stores.items():
        if store.snapshot() != snapshots[pid]:
            raise ValueError('Concurrent review edit: '+pid)
    atomic_write(current_path, result)
    (batch.checks.REPO/'backend/VERSION').write_text(VERSION+'\n', encoding='utf-8')
    activated = []
    for pid, store in stores.items():
        state, dataset = store._read()
        renumbered = False
        for site in dataset['sites']:
            if site['id'] in assigned:
                site['number'] = assigned[site['id']]
                renumbered = True
        if renumbered:
            store.import_dataset(dataset, refresh=True)  # Display metadata only; approval hashes stay exact.
        state, _ = store._read()
        for site_id, record in records.items():
            if record['reviewProjectId'] != pid:
                continue
            edit = state['sites'][site_id]
            evidence = edit['technicalEvidence']
            count = sum(bool(m.get('enabled')) for m in candidates[site_id]['movements'])
            evidence.update(branchMovements=count, backendVersion=VERSION, deploymentStatus='branch-ready',
                deployment=f'Im Branch aktiviert; Backend {VERSION}; Deployment ausstehend')
            edit['version'] += 1
            edit.setdefault('history', []).append(dict(at=datetime.now(timezone.utc).isoformat(),
                action='branch-activation', backendVersion=VERSION, movements=count))
            activated.append(dict(id=site_id, projectId=pid, movements=count,
                reviewBinding=record['reviewBinding'], assignedNumber=assigned.get(site_id)))
        atomic_write(store.directory/'project.json', state)
    atomic_write(MANIFEST, dict(backendVersion=VERSION, catalogVersion=result['version'], status='branch-ready',
        authorization='Thomas: alles aktivieren, commit, push und Workflow zum Live-Setzen; 2026-11-22.',
        activated=activated, assignedNumbers=assigned,
        activeJunctions=sum(j['enabled'] for j in result['junctions']),
        activeMovements=sum(bool(m.get('enabled')) for j in result['junctions'] if j['enabled'] for m in j['movements'])))
    print('Activated',len(records),'cases;',sum(j['enabled'] for j in result['junctions']),'junctions;',
          sum(bool(m.get('enabled')) for j in result['junctions'] if j['enabled'] for m in j['movements']),'movements')


if __name__=='__main__':
    activate()
