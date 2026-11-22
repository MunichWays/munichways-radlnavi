"""Prepare K38-K41 from frozen OSM highway extracts. No runtime changes."""
import argparse
from datetime import datetime, timezone
import gzip
import html
import json
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from build_review_images import ROOT, prepare_site, draw, svg
from prepare_ba01_radlring import prepare as prepare_geometry

SOURCE = ROOT / 'review-batch-07-lanes-osm.json.gz'
DRAFTS = ROOT / 'review-batch-07-lanes-drafts.json'
OUT = ROOT / 'review-batch-07-lanes-images'
SELECTION = [(38, 'dachauer-georg-brauchle', 440646),
             (39, 'landsberger-fuerstenrieder', 444584),
             (40, 'innsbrucker-bad-schachener', 2386472481),
             (41, 'candid-gruenwalder', 21029425)]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def selection():
    inventory = json.loads((ROOT/'outgoing-lanes-munich-inventory.json').read_text(encoding='utf-8'))
    return [(number, identifier, next(g for g in inventory['candidates'] if node in g['nodeIds']))
            for number, identifier, node in SELECTION]


def collect():
    sites=[]
    for number, identifier, group in selection():
        lon, lat = group['origin']
        url=f'https://api.openstreetmap.org/api/0.6/map?bbox={lon-.0025},{lat-.0018},{lon+.0025},{lat+.0018}'
        with urlopen(Request(url, headers={'User-Agent':'MunichWays-Junction-Review/1.0'}), timeout=60) as response:
            root=ET.fromstring(response.read())
        nodes={int(n.attrib['id']): n for n in root.findall('node')}
        ways=[]
        for w in root.findall('way'):
            tags={t.attrib['k']:t.attrib['v'] for t in w.findall('tag')}
            if 'highway' not in tags:
                continue
            ids=[int(n.attrib['ref']) for n in w.findall('nd')]
            if any(n not in nodes for n in ids):
                raise ValueError('Incomplete map way')
            ways.append(dict(type='way', id=int(w.attrib['id']), tags=tags, nodes=ids,
                geometry=[dict(lon=float(nodes[n].attrib['lon']),lat=float(nodes[n].attrib['lat'])) for n in ids]))
        sites.append(dict(id=identifier, number=number, origin=group['origin'], url=url, elements=ways))
        print(f'Collected K{number}: {len(ways)} highway ways.', flush=True)
    SOURCE.write_bytes(gzip.compress(json.dumps(dict(retrievedAt=datetime.now(timezone.utc).isoformat(),sites=sites),ensure_ascii=False).encode(),mtime=0))


def prepare(record, ways):
    site=prepare_geometry(record,ways)
    site['district']='München · Priorität nach Fahrspuren'
    site['outgoingLaneTotal']=record['outgoingLaneTotal']
    site['excludedMovements']=record.get('excludedMovements', [])
    return site


def main(collect_source=False):
    if collect_source:
        collect()
    snapshot=json.loads(gzip.decompress(SOURCE.read_bytes()))
    sources={s['id']:s for s in snapshot['sites']}
    if not DRAFTS.exists():
        records=[]
        for number, identifier, group in selection():
            note=f'{group["taggedTotal"]} ausgehende Kfz-Fahrspuren laut OSM. Flächenentwurf; noch keine Freigabe oder Aktivierung.'
            feature=dict(geometry=dict(coordinates=group['origin']),properties=dict(id=identifier,
                name=' / '.join(group['roadNames']),reviewOrder=number,nextCheck=note))
            initial=prepare_site(feature,sources[identifier]['elements'])
            records.append(dict(id=identifier,number=number,version=1,name=initial['name'],origin=group['origin'],
                polygon=initial['polygon'],onRoadWayIds=[],candidateNodeIds=group['nodeIds'],
                proposedLogicalArms={},note=note,outgoingLaneTotal=group['taggedTotal']))
        write(DRAFTS,dict(version=1,enabled=False,sites=records))
    records=json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
    sites=[prepare(r,sources[r['id']]['elements']) for r in records]
    OUT.mkdir(exist_ok=True)
    data=OUT/'review-data.json'
    if data.exists():
        previous={s['id']:s for s in json.loads(data.read_text(encoding='utf-8'))['sites']}
        for site in sites:
            old=previous.get(site['id'])
            if old and site['version']<=old['version'] and any(site[k]!=old[k] for k in ('polygon','gates')):
                raise ValueError('Explicit geometry revision required: '+site['id'])
            if old and old.get('polygonApproved') and not site['polygonApproved']:
                raise ValueError('Existing approval cannot be dropped')
    cards=[]
    for site in sites:
        name=f'K{site["number"]:02d}-{site["id"]}'
        commands=draw(site)
        if site.get("review", {}).get("activationReview", {}).get("status") == "approved":
            for command in commands:
                if command["kind"] == "text":
                    command["text"] = command["text"].replace("NICHT AKTIV", "IM BRANCH; NICHT DEPLOYED")
        (OUT/f'{name}.drawing.json').write_text(json.dumps(commands,ensure_ascii=False),encoding='utf-8')
        (OUT/f'{name}.svg').write_text(svg(commands),encoding='utf-8')
        label=html.escape(f'K{site["number"]} v{site["version"]} · {site["name"]}')
        cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p><a href="{name}.png"><img src="{name}.svg" alt="{label}"></a></article>')
    (OUT/'index.html').write_text('<!doctype html><html lang="de"><meta charset="utf-8"><title>K38–K41 · Fahrspuren</title>'
        '<style>body{font:17px Arial;margin:24px;background:#f3f4f5}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}</style>'
        '<h1>K38–K41 · Größte neue Kandidaten nach Fahrspuren</h1><p>K38 und K40 mit je acht, K41 mit sechs Beziehungen technisch geprüft und im Branch aktiviert. K41 Entry-1 nach Exit-3/Exit-4 bleiben dauerhaft ausgeschlossen. K39 dauerhaft ausgeschlossen (komplexe Zweirichtungsradwege, Umbau 2026). Live-Stand siehe Gesamtübersicht.</p>'
        '<p><a href="../kreuzungspruefung/index.html">Gesamtübersicht</a> · <a href="overview.png">Kontaktübersicht</a></p><main>'+''.join(cards)+
        '</main><p>OSM '+snapshot['retrievedAt'][:10]+' · © OpenStreetMap-Mitwirkende, ODbL.</p></html>',encoding='utf-8')
    write(data,dict(version=1,enabled=False,osmRetrievedAt=snapshot['retrievedAt'],sites=sites))
    from organize_review_images import main as organize
    organize()
    from review_preflight import main as preflight
    preflight()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect',action='store_true')
    main(parser.parse_args().collect)
