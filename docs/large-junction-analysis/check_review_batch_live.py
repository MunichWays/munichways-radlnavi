"""Check the deployed catalog against cached real routes without changing routing."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent


def get(url):
    with urlopen(url,timeout=45) as response:return json.load(response)


def review_cases():
    cases=[]
    catalog=json.loads((ROOT.parents[1]/'backend/src/big_junctions.json').read_text(encoding='utf-8'))
    active={j['id'] for j in catalog['junctions'] if j.get('enabled')}
    updates=json.loads((ROOT/'review-updates-2026-11-14-routes.json').read_text(encoding='utf-8'))
    replaced={j['id'] for j in updates['junctions']}
    for name in ['full-movements-review.json','review-batch-01-routes.json','review-batch-02-ba09-routes.json','review-batch-03-ba09-routes.json']:
        report=json.loads((ROOT/name).read_text(encoding='utf-8'))
        for junction in report['junctions']:
            if junction['id'] in replaced:continue
            for item in junction['movements']:
                if 'url' in item:cases.append(dict(item,junctionId=junction['id'],expectGuidance=item['enabled'] and junction['id'] in active))
        for item in report.get('rightTurnChecks', []):
            if item.get('junctionId') in replaced:continue
            cases.append(dict(item,id=item.get('id',Path(item['fixture']).stem),expectGuidance=False))
    for junction in updates['junctions']:
        for item in junction['movements']:
            if item['kind'] == 'special':continue  # v2 sequences have separate contract tests.
            cases.append(dict(item,junctionId=junction['id'],expectGuidance=item['enabled']))
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    version=get('https://api.radlnavi.munichways.de/version')
    print(json.dumps(version),flush=True)
    if version.get('backendCommit') != args.commit:raise ValueError('Live version does not contain expected commit')
    cases=review_cases()
    checked=[]
    expected_catalog=json.loads((ROOT.parents[1]/'backend/src/big_junctions.json').read_text(encoding='utf-8'))['version']
    for item in cases:
        plain=get(item['url']);enriched=get(item['url']+'&junction_guidance=true')
        hits=[]
        for route in enriched['routes']:
            if 'guidance' in route:
                guidance=route.pop('guidance')
                if guidance['catalogVersion']!=expected_catalog:raise ValueError('Wrong catalog revision')
                hits.extend(guidance['junctions'])
        if enriched!=plain:raise ValueError('Guidance changed routing response: '+item['id'])
        if item['expectGuidance']:
            if len(hits)!=1 or hits[0]['id']!=item['junctionId'] or not hits[0]['occurrenceId'].startswith(item['junctionId']+':'+item['id']+':'):
                raise ValueError('Missing or wrong guidance: '+item['junctionId']+' '+item['id'])
        elif hits:raise ValueError('Unexpected guidance on excluded route: '+item['id'])
        checked.append({'junction':item.get('junctionId'),'id':item['id'],'guidance':bool(hits)})
        print(f'{len(checked)}/{len(cases)} {item.get("junctionId","")} {item["id"]}: OK',flush=True)
    Path(args.output).write_text(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),'version':version,'cases':checked},indent=2)+'\n',encoding='utf-8')
    print('All live controls passed; routing responses unchanged.',flush=True)


if __name__=='__main__':main()
