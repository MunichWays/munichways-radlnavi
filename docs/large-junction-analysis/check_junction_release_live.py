"""Read-only live regression for the K24/K30/K33 release and legacy fallback."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fetch(url, protocol=None):
    headers = {'User-Agent': 'MunichWays-Junction-Release-Check/1.0'}
    if protocol is not None:
        headers['X-Junction-Guidance-Version'] = str(protocol)
    with urlopen(Request(url, headers=headers), timeout=45) as response:
        return json.load(response)


def run(commit, version):
    deployed = fetch('https://api.radlnavi.munichways.de/version')
    if deployed.get('backendCommit') != commit or deployed.get('backend') != version:
        raise ValueError('Expected backend commit/version is not live')
    records = [read(ROOT / 'review-k24-v1-draft-technical.json'),
               read(ROOT / 'review-k30-v3-draft-technical.json'),
               read(ROOT / 'review-batch-05-k33-routes.json')['junctions'][0]]
    tasks = []
    for record in records:
        for item in record['movements']:
            tasks.append((record, item, 3))
            if item.get('instructionTemplate'):
                tasks.append((record, item, 2))

    def verify(task):
        record, item, protocol = task
        payload = fetch(item['url']+'&junction_guidance=true', protocol)
        raw = fetch(item['url'])
        frozen = read(ROOT.parents[1] / 'backend/tests/fixtures/big-junctions'
                      / record['fixtureDirectory'] / item['fixture'])
        if raw['routes'][0]['geometry'] != frozen['routes'][0]['geometry']:
            raise ValueError('Live route geometry differs from verified evidence: '+item['fixture'])
        guidance = payload['routes'][0].pop('guidance', None)
        expected = bool(item.get('enabled')) and (protocol == 3 or not item.get('instructionTemplate'))
        if expected:
            if not guidance or len(guidance.get('junctions', [])) != 1:
                raise ValueError('Missing unique live macro: '+item['fixture'])
            hit, = guidance['junctions']
            if hit['id'] != record['id'] or hit['movement'] != item['kind']:
                raise ValueError('Wrong live classification: '+item['fixture'])
            if bool(hit.get('instruction')) != bool(item.get('instructionTemplate')):
                raise ValueError('Wrong special-template response: '+item['fixture'])
        elif guidance and guidance.get('junctions'):
            raise ValueError('Excluded/right/legacy route has a macro: '+item['fixture'])
        if payload != raw:
            raise ValueError('Optional junction metadata changes ordinary live route: '+item['fixture'])
        return dict(junctionId=record['id'], fixture=item['fixture'], protocol=protocol,
                    expectedMacro=expected, result='passed')

    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(verify, tasks))
    report = dict(checkedAt=datetime.now(timezone.utc).isoformat(), version=deployed,
                  status='passed', requests=len(checks), checks=checks)
    (ROOT / f'review-release-{version}-live-checks.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'LIVE {version} {commit}: {len(checks)} checks passed; ordinary route data unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-version', required=True)
    args = parser.parse_args()
    run(args.expected_commit, args.expected_version)
