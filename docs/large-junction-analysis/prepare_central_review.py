"""Prepare K42-K46 from frozen OSM highway extracts. No runtime changes."""
import argparse
from datetime import datetime, timezone
import gzip
import html
import json
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from build_review_images import ROOT, prepare_site, draw, svg
from prepare_ba01_radlring import prepare as prepare_geometry

SOURCE = ROOT / 'review-batch-08-central-osm.json.gz'
DRAFTS = ROOT / 'review-batch-08-central-drafts.json'
OUT = ROOT / 'review-batch-08-central-images'
SELECTION = [(42, 'lane-candidate-363119', 363119),
             (43, 'lane-candidate-472070', 472070),
             (44, 'lane-candidate-361786', 361786),
             (45, 'lane-candidate-361790', 361790),
             (46, 'lane-candidate-428767', 428767)]


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
    site['district']='München · Zentrale Auswahl'
    site['outgoingLaneTotal']=record['outgoingLaneTotal']
    site['excludedMovements']=record.get('excludedMovements', [])
    return site


def main(collect_source=False, title='K42–K46 · Zentrale Kreuzungen', selection_label='Die fünf von Thomas ausgewählten Kreuzungen.'):
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
    report_path = DRAFTS.with_name(DRAFTS.name.replace('-drafts.json', '-routes.json'))
    technical = {s['id']: s for s in json.loads(report_path.read_text(encoding='utf-8'))['junctions']} if report_path.exists() else {}
    for site in sites:
        name=f'K{site["number"]:02d}-{site["id"]}'
        commands=draw(site)
        record = technical.get(site['id'], {})
        if record.get('geometryRevision') == site['version']:
            blocked = [m for m in record['movements'] if m['kind'] not in ('right', 'standard') and not m.get('enabled')]
            if blocked:
                labels = ', '.join(f'{m["entryLabel"]} → {m["exitLabel"]}' for m in blocked)
                dates = sorted({m['deferredUntil'] for m in blocked if m.get('deferredUntil')})
                notice = 'Ohne Kreuzungsansage: '+labels+'; normale Hinweise bleiben.'
                if dates:
                    notice += ' Wiedervorlage ab ' + '.'.join(reversed(dates[0].split('-'))) + '.'
                commands.append(dict(kind='text', text=notice,
                                     x=28, y=80, size=15, color='#616161'))
        if site.get("review", {}).get("activationReview", {}).get("status") == "approved":
            for command in commands:
                if command["kind"] == "text":
                    command["text"] = command["text"].replace("NICHT AKTIV", "IM BRANCH; NICHT DEPLOYED")
        (OUT/f'{name}.drawing.json').write_text(json.dumps(commands,ensure_ascii=False),encoding='utf-8')
        (OUT/f'{name}.svg').write_text(svg(commands),encoding='utf-8')
        label=html.escape(f'K{site["number"]} v{site["version"]} · {site["name"]}')
        cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p><a href="{name}.png"><img src="{name}.svg" alt="{label}"></a></article>')
    approved_count = sum(site['polygonApproved'] for site in sites)
    (OUT/'index.html').write_text(f'<!doctype html><html lang="de"><meta charset="utf-8"><title>{html.escape(title)}</title>'
        '<style>body{font:17px Arial;margin:24px;background:#f3f4f5;color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}</style>'
        f'<h1>{html.escape(title)}</h1><p>{approved_count} Geometrien freigegeben, {len(sites)-approved_count} noch zur Sichtprüfung offen. Technischer Stand und Live-Status siehe Gesamtübersicht. {html.escape(selection_label)} Bitte Umfang der Fläche, Entry-/Exit-Punkte, Fahrtrichtung und fehlende Anschlüsse prüfen. Benachbarte Einmündungen bleiben außerhalb. Radfahrstreifen werden anhand ihrer OSM-Fahrbahnmitte dargestellt; die seitliche Lage ist nicht vermessen. Eine Geometriefreigabe ist noch keine Aktivierung; Fahrbeziehungsprüfung und Live-Status werden getrennt dokumentiert.</p>'
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
