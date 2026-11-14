"""Snapshot the actual production version and its exact committed catalog."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id')
    args = parser.parse_args()
    with urlopen('https://api.radlnavi.munichways.de/version', timeout=30) as response:
        version = json.load(response)
    commit = version['backendCommit']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Unexpected production commit')
    source = subprocess.run(['git', 'show', f'{commit}:backend/src/big_junctions.json'],
        check=True, capture_output=True, encoding='utf-8').stdout
    catalog = json.loads(source)
    state = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'version': version,
        'catalogVersion': catalog['version'], 'source': 'Production /version plus catalog from exact backendCommit',
        'junctions': [{k: j[k] for k in ('id', 'enabled', 'polygon', 'movements')} for j in catalog['junctions']]}
    if args.run_id:
        result = subprocess.run(['gh', 'run', 'view', args.run_id, '--repo', 'MunichWays/munichways-radlnavi',
            '--json', 'status,conclusion,headSha,url'], check=True, capture_output=True, encoding='utf-8')
        state['deploymentRun'] = json.loads(result.stdout)
    (ROOT / 'review-deployment-state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('Production:', version['backend'], commit, catalog['version'])
    from organize_review_images import main as organize
    organize()


if __name__ == '__main__':
    main()
