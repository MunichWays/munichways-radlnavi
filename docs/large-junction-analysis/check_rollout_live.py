"""Verify K18/K34-K41 on production against the exact local catalog and routes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from check_junction_release_live import fetch, read, ROOT

sys.path.insert(0, str(ROOT.parents[1] / 'backend'))
from src.big_junctions import add_guidance, catalog


def run(commit):
    version = fetch('https://api.radlnavi.munichways.de/version')
    if version['backendCommit'] != commit or version['backend'] != '2.4.16':
        raise ValueError('Expected release is not live')
    tasks = []
    for filename in ('review-batch-06-primary-routes.json', 'review-batch-07-lanes-routes.json', 'review-k18-v5-routes.json'):
        report = read(ROOT / filename)
        for record in report['junctions']:
            for item in record['movements']:
                tasks.append(dict(item, fixtureDirectory=record['fixtureDirectory'], expectedJunction=record['id']))
        if filename == 'review-batch-06-primary-routes.json':
            manifest = read(ROOT / 'review-batch-06-primary-route-requests.json')
            for item in report['combinedRouteChecks']:
                tasks.append(dict(item, url=manifest[item['fixture']]['url'], fixtureDirectory='batch-06'))

    def check(item):
        raw = fetch(item['url'])
        frozen = read(ROOT.parents[1] / 'backend/tests/fixtures/big-junctions' / item['fixtureDirectory'] / item['fixture'])
        if raw['routes'][0]['geometry'] != frozen['routes'][0]['geometry']:
            raise ValueError('Routing geometry changed: ' + item['fixture'])
        expected = add_guidance(raw)
        live = fetch(item['url'] + '&junction_guidance=true', 3)
        if live != (expected if expected is not None else raw):
            raise ValueError('Live response differs from exact local catalog: ' + item['fixture'])
        if item.get('enabled'):
            hits = live['routes'][0]['guidance']['junctions']
            if not any(h['id'] == item['expectedJunction'] and h['movement'] == item['kind']
                       and h['entryArm'] == item['entryArm'] and h['exitArm'] == item['exitArm'] for h in hits):
                raise ValueError('Expected reviewed pair absent: '+item['fixture'])
        return dict(fixture=item['fixture'], passed=True,
                    macroCount=len(live['routes'][0].get('guidance', {}).get('junctions', [])))

    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(check, tasks))
    output = ROOT / 'review-release-2.4.16-rollout-live-checks.json'
    output.write_text(json.dumps(dict(checkedAt=datetime.now(timezone.utc).isoformat(),
        version=version, catalogVersion=catalog()['version'], status='passed', checks=checks),
        ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(checks)} live routes passed; enriched responses match exact local catalog, ordinary routes unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    run(parser.parse_args().expected_commit)
