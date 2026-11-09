"""Focused offline/recollectable technical review; never modifies runtime catalog."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from unittest.mock import patch

import verify_ba09_movements as check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--number', type=int, default=19)
    parser.add_argument('--collect', action='store_true')
    args = parser.parse_args()
    root = check.ROOT
    site = next(s for s in json.loads((root / 'review-batch-03-ba09-remaining-images/review-data.json').read_text(encoding='utf-8'))['sites'] if s['number'] == args.number)
    if not site['polygonApproved']:
        raise ValueError('Only explicitly approved geometry may be tested for activation')
    check.ARMS[site['number']] = {arm: (g['entries'], g['exits']) for arm, g in site['review']['proposedLogicalArms'].items()}
    check.FIXTURES = root.parents[1] / 'backend/tests/fixtures/big-junctions/batch-03'
    check.FIXTURES.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'review-batch-03-ba09-route-requests.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    tasks, samples = check.plan(site)
    base = deepcopy(check.catalog())
    base['junctions'] = [j for j in base['junctions'] if j['id'] != site['id']]
    candidate = {'id': site['id'], 'name': site['name'], 'enabled': True,
                 'polygon': {'type': 'Polygon', 'coordinates': [site['polygon']]},
                 'armTopology': check.arm_topology(site),
                 'review': {'status': 'approved', 'date': datetime.now(timezone.utc).date().isoformat(),
                            'evidence': f'Human geometry approval K{site["number"]} v{site["version"]}; focused real route checks.'},
                 'movements': []}
    def fetch(item):
        try:
            return check.collect(item, manifest, args.collect)
        except Exception as error:
            return error
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [item for item in tasks if 'url' in item]
        for item, result in zip(pending, pool.map(fetch, pending)):
            try:
                if isinstance(result, Exception):
                    raise result
                payload, retrieved = result
                if retrieved:
                    (check.FIXTURES / item['fixture']).write_text(json.dumps(payload, ensure_ascii=False)+'\n', encoding='utf-8')
                    manifest[item['fixture']] = {'url': item['url'], 'retrievedAt': retrieved}
                movement, evidence = check.verify(site, item, payload, base)
                item.update(evidence)
                if movement:
                    candidate['movements'].append(movement)
            except Exception as error:
                item['reason'] = str(error)
            print(item['entryLabel'], item['exitLabel'], item['kind'], 'PASS' if item.get('verified') else item.get('reason'), flush=True)
    proposed = deepcopy(base)
    proposed['version'] = 'munich-big-junctions-v6-proposed'
    candidate['enabled'] = bool(candidate['movements'])
    candidate['movements'].sort(key=lambda m: m['id'])
    proposed['junctions'].append(candidate)
    check.validate_catalog(proposed)
    with patch('src.big_junctions.catalog', return_value=proposed):
        for item in tasks:
            path = check.FIXTURES / item['fixture']
            if not path.exists() or 'url' not in item:
                continue
            payload = json.loads(path.read_text(encoding='utf-8'))
            result = check.add_guidance(payload)
            if bool(result) != bool(item.get('enabled')):
                raise ValueError('Whole-catalog result differs from individual review: '+item['id'])
            if result:
                result['routes'][0].pop('guidance')
                if result != payload:
                    raise ValueError('Routing changed')
                walking = deepcopy(payload)
                for leg in walking['routes'][0]['legs']:
                    for step in leg['steps']:
                        step['mode'] = 'pushing bike'
                if check.add_guidance(walking):
                    raise ValueError('Walking control triggered guidance')
    record = {'id': site['id'], 'number': site['number'], 'geometryRevision': site['version'],
              'status': 'complete', 'gateEvidence': samples, 'movements': tasks}
    report_path = root / 'review-batch-03-ba09-routes.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'junctions': []}
    report['junctions'] = [j for j in report['junctions'] if j['id'] != site['id']] + [record]
    report.update(status='complete', checkedAt=datetime.now(timezone.utc).isoformat(), runtimeModified=False)
    for path, value in [(manifest_path, manifest), (report_path, report),
                        (root / f'review-k{site["number"]}-proposed-catalog.json', proposed)]:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    from organize_review_images import main as organize
    organize()
    print('Verified:', len(candidate['movements']), '; runtime catalog unchanged.')


if __name__ == '__main__':
    main()
