"""Count named primary/primary contacts; not geometry or activation approval."""
import gzip
import json
from math import cos, hypot, radians
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def distance(a, b):
    return hypot((a[0]-b[0])*111320*cos(radians((a[1]+b[1])/2)), (a[1]-b[1])*111320)


def main():
    snapshot = json.loads(gzip.decompress((ROOT / 'primary-primary-munich-osm.json.gz').read_bytes()))
    elements = snapshot['response']['elements']
    ways = [w for w in elements if w['type'] == 'way']
    nodes = [n for n in elements if n['type'] == 'node']
    groups = []
    ignored = []
    for node in nodes:
        names = sorted({w['tags']['name'] for w in ways
                        if node['id'] in w['nodes'] and w['tags'].get('name')})
        if len(names) < 2:
            ignored.append(node['id'])
            continue
        point = [node['lon'], node['lat']]
        # Merge near nodes sharing at least two primary road names. Different
        # names on opposite sides (Ampfingstrasse) can belong to the same complex.
        group = next((g for g in groups if len(set(names) & set(g['roadNames'])) >= 2
                      and all(distance(point, p) <= 80 for p in g['locations'])), None)
        if group is None:
            group = dict(roadNames=[], locations=[], nodeIds=[])
            groups.append(group)
        group['roadNames'] = sorted(set(group['roadNames']) | set(names))
        group['locations'].append(point)
        group['nodeIds'].append(node['id'])
    catalog = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
    state = json.loads((ROOT / 'review-deployment-state.json').read_text(encoding='utf-8'))
    for group in groups:
        origin = [sum(p[i] for p in group['locations'])/len(group['locations']) for i in (0, 1)]
        group['origin'] = origin
        found = []
        for junction in catalog['junctions']:
            ring = junction['polygon']['coordinates'][0][:-1]
            center = [sum(p[i] for p in ring)/len(ring) for i in (0, 1)]
            if distance(origin, center) < 100:
                found.append(junction['id'])
        group['nearbyCatalogIds'] = found
        group['alreadyLive'] = any(j['id'] in found and j.get('enabled') for j in state['junctions'])
    report = dict(sourceRetrievedAt=snapshot['retrievedAt'], rawNodes=len(nodes),
        namedContactNodes=sum(len(g['nodeIds']) for g in groups), namedComplexCandidates=len(groups),
        alreadyLive=sum(g['alreadyLive'] for g in groups),
        newCandidates=sum(not g['alreadyLive'] for g in groups),
        omittedNodesWithoutTwoNamedPrimaryRoads=ignored,
        policy='Strict highway=primary; primary_link and trunk excluded. At least two distinct named primary roads; '
               'nearby contacts sharing two names grouped within 80m. Splits, unnamed connectors and ramps are not named crossings. '
               'Four cycling arms, grade separation and suitability require individual review. No completeness claim for unnamed primary roads.',
        candidates=groups)
    (ROOT / 'primary-primary-munich-inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('candidates', 'policy', 'omittedNodesWithoutTwoNamedPrimaryRoads')}))


if __name__ == '__main__':
    main()
