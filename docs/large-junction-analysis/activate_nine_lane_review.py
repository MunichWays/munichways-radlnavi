"""Explicitly activate the verified K48-K50 proposal; never pushes or deploys."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / 'tools/junction-review'), str(REPO / 'backend')]
from junction_review.store import ProjectStore, atomic_write
from src.big_junctions import validate_catalog


def activate(project):
    store = ProjectStore(project)
    snapshot = {s['number']: s for s in store.snapshot()['sites'] if s['number'] in (47, 48, 49, 50)}
    report = json.loads((ROOT / 'review-batch-09-nine-lanes-routes.json').read_text(encoding='utf-8'))
    proposal = json.loads((ROOT / 'review-batch-09-nine-lanes-proposed-catalog.json').read_text(encoding='utf-8'))
    path = REPO / 'backend/src/big_junctions.json'
    current = json.loads(path.read_text(encoding='utf-8'))
    additions = []
    assert snapshot[47]['status'] == 'excluded'
    for record in report['junctions']:
        site = snapshot[record['number']]
        assert site['status'] == 'confirmed' and site['decisionCurrent'] and site['evidenceCurrent']
        assert all(record['reviewBinding'][k] == site[k] for k in ('geometryFingerprint', 'sourceFingerprint'))
        junction = deepcopy(next(j for j in proposal['junctions'] if j['id'] == site['id']))
        assert junction['polygon']['coordinates'][0] == site['polygon']
        assert sum(bool(m.get('enabled')) for m in junction['movements']) == 8
        additions.append(junction)
    ids = {j['id'] for j in additions}
    assert len(ids) == 3 and snapshot[47]['id'] not in ids
    result = dict(current, version='munich-big-junctions-v18',
                  junctions=[j for j in current['junctions'] if j['id'] not in ids] + additions)
    validate_catalog(result)
    atomic_write(path, result)
    (REPO / 'backend/VERSION').write_text('2.4.18\n', encoding='utf-8')
    drafts_path = ROOT / 'review-batch-09-nine-lanes-drafts.json'
    drafts = json.loads(drafts_path.read_text(encoding='utf-8'))
    for record in drafts['sites']:
        if record['id'] in ids:
            record['reviewDecision']['activationReview'] = dict(status='approved', date='2026-11-21',
                evidence='Thomas explicitly requested activation and commit; push/deployment reserved for later.')
    atomic_write(drafts_path, drafts)
    # Bind the local card's preparation status to the same untouched approval.
    with store.lock:
        state, _ = store._read()
        for site in snapshot.values():
            if site['id'] not in ids:
                continue
            edit = state['sites'][site['id']]
            evidence = edit['technicalEvidence']
            if evidence.get('branchMovements') != 8:
                evidence.update(branchMovements=8, deploymentStatus='branch-ready', backendVersion='2.4.18',
                    deployment='Im Branch aktiviert · Backend 2.4.18 · noch nicht deployed')
                edit['version'] += 1
        atomic_write(store.directory / 'project.json', state)
    print('K48-K50: 24 neue Beziehungen im Branch aktiviert; Backend 2.4.18. Nicht deployed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=REPO / '.local/junction-review/munich')
    activate(parser.parse_args().project)
