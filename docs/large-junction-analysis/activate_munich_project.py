"""Explicit activation of verified map cases; no push or deployment side effects."""
from copy import deepcopy
from datetime import datetime, timezone
import sys

import verify_munich_project as batch

sys.path.insert(0, str(batch.REPO / 'backend'))
from src.big_junctions import validate_catalog
from junction_review.store import ProjectStore, atomic_write


def activate(project=batch.PROJECT):
    store = ProjectStore(project)
    report = batch.review.read(batch.REPORT)
    proposal = batch.review.read(batch.PROPOSAL)
    if report['status'] != 'complete' or report['runtimeModified'] is not False:
        raise ValueError('Complete non-activating report required')
    snapshot = store.snapshot()
    sites = {s['id']: s for s in snapshot['sites']}
    additions, skipped = [], []
    for record in report['junctions']:
        site = sites[record['id']]
        if site['status'] != 'confirmed' or record.get('status') == 'blocked-topology':
            skipped.append(dict(id=site['id'], name=site['name'], status=site['status'],
                reason=record.get('reason') or 'Not currently confirmed'))
            continue
        if not site['decisionCurrent'] or not site['evidenceCurrent'] or any(
                record['reviewBinding'][k] != site[k] for k in ('geometryFingerprint','sourceFingerprint')):
            raise ValueError('Stale approval/evidence: ' + site['id'])
        candidate = deepcopy(next(j for j in proposal['junctions'] if j['id'] == site['id']))
        verified = {m['id'] for m in record['movements'] if m.get('enabled') and m.get('verified')}
        enabled = {m['id'] for m in candidate['movements'] if m.get('enabled')}
        if not enabled or enabled != verified or candidate['polygon']['coordinates'][0] != site['polygon']:
            raise ValueError('Unverified movement or geometry: ' + site['id'])
        additions.append(candidate)
    if not additions:
        raise ValueError('No currently approved verified movements')
    path = batch.REPO / 'backend/src/big_junctions.json'
    current = batch.review.read(path)
    ids = {j['id'] for j in additions}
    result = dict(current, version='munich-big-junctions-v20',
                  junctions=[j for j in current['junctions'] if j['id'] not in ids] + additions)
    validate_catalog(result)
    if any(j['id'] == 'lane-candidate-26823592' for j in result['junctions']):
        raise ValueError('Deferred Heidemannstrasse must not be active')
    with store.lock:
        # Recheck immediately before the release write; never transfer approval.
        for fresh in store.snapshot()['sites']:
            if fresh['id'] in ids and fresh != sites[fresh['id']]:
                raise ValueError('Concurrent review edit: ' + fresh['id'])
        atomic_write(path, result)
        (batch.REPO / 'backend/VERSION').write_text('2.4.20\n', encoding='utf-8')
        state, _ = store._read()
        for junction in additions:
            edit = state['sites'][junction['id']]
            count = sum(bool(m.get('enabled')) for m in junction['movements'])
            evidence = edit['technicalEvidence']
            if evidence.get('branchMovements') != count or evidence.get('backendVersion') != '2.4.20':
                evidence.update(branchMovements=count, backendVersion='2.4.20', deploymentStatus='branch-ready',
                    deployment='Im Branch aktiviert; Backend 2.4.20; noch nicht deployed')
                edit['version'] += 1
                edit.setdefault('history', []).append(dict(at=datetime.now(timezone.utc).isoformat(),
                    action='branch-activation', backendVersion='2.4.20', movements=count))
        atomic_write(store.directory / 'project.json', state)
    manifest = dict(backendVersion='2.4.20', catalogVersion=result['version'], status='branch-ready',
        authorization='Thomas requested activation of all verified cases, push and backend workflow on 2026-11-21.',
        activated=[dict(id=j['id'], name=j['name'], movements=sum(bool(m.get('enabled')) for m in j['movements']),
            reviewBinding={k:sites[j['id']][k] for k in ('geometryFingerprint','sourceFingerprint')}) for j in additions],
        skipped=skipped, projectDecisions=[{k:deepcopy(s[k]) for k in
            ('id','name','geometryRevision','status','decision','geometryFingerprint','sourceFingerprint')} for s in snapshot['sites']])
    atomic_write(batch.ROOT / (batch.PREFIX + '-activation.json'), manifest)
    print(f'Activated {len(additions)} junctions, {sum(m["movements"] for m in manifest["activated"])} movements. Backend 2.4.20; not deployed.')


if __name__ == '__main__':
    activate()
