"""Record "Live" for every reviewed junction that production actually serves.

Run after every successful backend deployment (Thomas, 2026-11-27: deployed
junctions are factually live, even if bugs are found later):

    python docs/large-junction-analysis/mark_deployed_live.py --run-id <backend run>

Production /version names the exact backend commit; the catalog is read from
that commit. A site becomes live only if it is confirmed with current evidence
and production serves exactly the junction activated in the branch (same
polygon and movements as the working catalog). A site whose newer geometry is
only in the branch (e.g. replaced via --replace) stays "branch-ready" until its
own deployment. Afterwards review-deployment-state.json is refreshed.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROJECTS = REPO / '.local/junction-review'
sys.path.insert(0, str(REPO / 'tools/junction-review'))
from junction_review.store import ProjectStore, atomic_write  # noqa: E402

REPOSITORY = 'MunichWays/munichways-radlnavi'


def production():
    with urlopen('https://api.radlnavi.munichways.de/version', timeout=30) as response:
        version = json.load(response)
    source = subprocess.run(['git', 'show', version['backendCommit'] + ':backend/src/big_junctions.json'],
                            check=True, capture_output=True, encoding='utf-8', cwd=REPO).stdout
    return version, {j['id']: j for j in json.loads(source)['junctions'] if j.get('enabled')}


def check_run(run_id, commit):
    result = subprocess.run(['gh', 'run', 'view', run_id, '-R', REPOSITORY, '--json',
                             'status,conclusion,headSha,workflowName,url'],
                            check=True, capture_output=True, encoding='utf-8')
    run = json.loads(result.stdout)
    if run['status'] != 'completed' or run['conclusion'] != 'success':
        raise SystemExit(f"Deployment run not successful: {run['status']}/{run['conclusion']}")
    if run['headSha'] != commit:
        raise SystemExit(f"Production commit {commit[:7]} is not the run's commit {run['headSha'][:7]}")
    return run


def live_candidates(snapshot, served, branch):
    """(site, movements) for each site whose activated junction production serves unchanged."""
    for site in snapshot['sites']:
        if site['status'] != 'confirmed' or not site['evidenceCurrent'] or site['deploymentStatus'] == 'live':
            continue
        junction = served.get(site['id'])
        if junction is None or junction != branch.get(site['id']):
            continue
        if junction['polygon']['coordinates'][0] != site['polygon']:
            continue
        yield site, sum(bool(m.get('enabled')) for m in junction['movements'])


def mark(run_id=None, dry_run=False):
    version, served = production()
    commit = version['backendCommit']
    run = check_run(run_id, commit) if run_id else None
    branch = {j['id']: j for j in json.loads((REPO / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))['junctions']}
    now = datetime.now(timezone.utc)
    marked = []
    for path in sorted(PROJECTS.iterdir()):
        if not (path / 'project.json').exists():
            continue
        store = ProjectStore(path)
        with store.lock:
            found = list(live_candidates(store.snapshot(), served, branch))
            if not found or dry_run:
                marked += [(path.name, s['number'], s['name'], n) for s, n in found]
                continue
            state, _ = store._read()
            for site, count in found:
                edit = state['sites'][site['id']]
                evidence = edit['technicalEvidence']
                evidence.update(deploymentStatus='live', liveMovements=count, branchMovements=count,
                    backendVersion=version['backend'], deploymentRun=run and run['url'],
                    deployment=f"LIVE · Backend {version['backend']} · Commit {commit[:7]} · {count} Fahrbeziehungen"
                               f" · abgeglichen {now.date().isoformat()}")
                edit['version'] += 1
                edit.setdefault('history', []).append(dict(at=now.isoformat(), action='live-verified',
                    backendVersion=version['backend'], backendCommit=commit, liveMovements=count,
                    deploymentRun=run and run['url']))
                marked.append((path.name, site['number'], site['name'], count))
            atomic_write(path / 'project.json', state)
    for project, number, name, count in marked:
        print(f"{'würde' if dry_run else ''} LIVE K{number} {name} ({count} Beziehungen) [{project}]".strip())
    print(f"Production {version['backend']} {commit[:7]}: {len(marked)} Kreuzung(en) {'gefunden' if dry_run else 'auf Live gesetzt'}.")
    if not dry_run:
        args = ['--run-id', run_id] if run_id else []
        subprocess.run([sys.executable, str(ROOT / 'update_review_deployment_state.py'), *args], check=True, cwd=REPO)
    return marked


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-id', help='successful backend deployment run (checked against production commit)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    mark(args.run_id, args.dry_run)
