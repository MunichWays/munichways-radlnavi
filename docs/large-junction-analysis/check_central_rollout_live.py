"""Read-only 2.4.17 production verification; never marks a started build live."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import sys

from check_junction_release_live import ROOT, fetch, read
from check_rollout_live import equivalent_metadata

sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import add_guidance, catalog


def run(commit):
    version = fetch('https://api.radlnavi.munichways.de/version')
    if version.get('backendCommit') != commit or version.get('backend') != '2.4.17':
        raise ValueError('Expected backend 2.4.17/commit is not live')
    report = read(ROOT / 'review-batch-08-central-routes.json')
    tasks = [(site, item) for site in report['junctions'] for item in site['movements']
             if not item.get('explicitlyExcluded')]

    def verify(task):
        site, item = task
        raw = fetch(item['url'])
        frozen = read(ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-08' / item['fixture'])
        if raw['routes'][0]['geometry'] != frozen['routes'][0]['geometry']:
            raise ValueError('Routing geometry changed; recheck required: ' + item['fixture'])
        expected = add_guidance(raw)
        expected_metadata = expected['routes'][0].pop('guidance', None) if expected else None
        live = fetch(item['url'] + '&junction_guidance=true', 3)
        metadata = live['routes'][0].pop('guidance', None)
        if live != raw or not equivalent_metadata(metadata, expected_metadata):
            raise ValueError('Live guidance differs from exact local catalog: ' + item['fixture'])
        if item.get('enabled') and not any(
                h['id'] == site['id'] and h['movement'] == item['kind']
                and h['entryArm'] == item['entryArm'] and h['exitArm'] == item['exitArm']
                for h in (metadata or {}).get('junctions', [])):
            raise ValueError('Enabled relationship missing: ' + item['fixture'])
        return dict(fixture=item['fixture'], passed=True,
                    macroCount=len((metadata or {}).get('junctions', [])))

    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(verify, tasks))
    output = ROOT / 'review-release-2.4.17-central-live-checks.json'
    output.write_text(json.dumps(dict(checkedAt=datetime.now(timezone.utc).isoformat(),
        version=version, catalogVersion=catalog()['version'], status='passed', checks=checks),
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(checks)} real live routes match the exact local catalog; raw routes unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    run(parser.parse_args().expected_commit)
