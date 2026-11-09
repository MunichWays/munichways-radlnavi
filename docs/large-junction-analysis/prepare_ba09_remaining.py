"""Prepare all remaining sites from the frozen BA09 degree-four inventory; no runtime writes."""

import gzip
import html
import json
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from build_review_images import prepare_site, apply_review, draw, svg, status_text

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'review-batch-03-ba09-remaining-images'
SELECTION = [
    (18, 'romanplatz-sued', 'Romanplatz Süd / Arnulfstraße / Wotanstraße / Guntherstraße', 11.51138, 48.15444,
     [444564, 1719145060, 12288734444], 'Vier Straßenarme am südlichen Romanplatz prüfen; nördliche Teilkreuzung separat halten. Tram-/Haltestellenbereiche und Radwegverzweigungen nicht als zusätzliche Arme zählen.'),
    (19, 'romanplatz-nord', 'Romanplatz Nord / Notburgastraße / Romanstraße', 11.5118756, 48.1557525,
     [297265251], 'Prüffrage: Gibt es einen eigenständigen vierten Radverkehrsarm oder nur eine dreiarme Einmündung mit Abbiegeverbindung? Ohne belegten vierten Arm zurückgestellt.'),
    (20, 'menzinger-schragenhof', 'Menzinger Straße / Schragenhofstraße', 11.4926049, 48.1657687,
     [26085228], 'Prüffrage: Vier eigenständige Arme oder T-Kreuzung mit getrennten Fahrbahnen? Radverkehr auf der Schragenhofstraße und seitliche Anschlüsse gesondert prüfen.'),
    (21, 'schwere-reiter-ackermann', 'Schwere-Reiter-Straße / Ackermannstraße / Infanteriestraße', 11.5528417, 48.1615241,
     [21035971], 'Prüffrage: Ist die Aufteilung der Ackermannstraße lediglich eine dreiarme Einmündung? Bei drei logischen Armen bleibt dieser Fall außerhalb der Aktivierung.'),
    (22, 'dachauer-landshuter', 'Dachauer Straße / Landshuter Allee', 11.5380883, 48.1655284,
     [1371997712], 'Tunnel-/Brückenkomplex: nur oberirdische Radverkehrsverbindungen zählen. Prüfen, ob vier zusammenhängende Arme in eine einzige überschaubare Kreuzungsfläche passen; andernfalls zurückgestellt.'),
]
EXISTING = {
    'leonrod-landshuter': [236849, 401307391, 21039238],
    'arnulf-landshuter': [245339, 245353],
    'menzinger-wintrich': [245415, 564080, 11840625],
    'dachauer-leonrod': [363211, 16259472, 363219, 16259287],
    'dachauer-loth': [20980542],
    'nymphenburger-waisenhaus': [27590215, 3008660221, 3008660224],
    'nymphenburger-landshuter': [29004859, 29004860, 333992516, 333992518],
    'wintrich-allacher': [2467495003],
    'arnulf-steuben': [6564938024, 6564938032, 6564938025, 6564938026],
}


def load_snapshot(name):
    return json.loads(gzip.decompress((ROOT / name).read_bytes()))


def collect():
    """Small official OSM map extracts; retain only complete highway ways."""
    urls = [f'https://api.openstreetmap.org/api/0.6/map?bbox={lon-.0029:.7f},{lat-.0020:.7f},{lon+.0029:.7f},{lat+.0020:.7f}'
            for _, _, _, lon, lat, _, _ in SELECTION]
    def fetch(url):
        with urlopen(Request(url, headers={'User-Agent': 'MunichWays-Junction-Review/1.0'}), timeout=45) as response:
            xml = ET.fromstring(response.read())
        positions = {int(n.attrib['id']): {'lat': float(n.attrib['lat']), 'lon': float(n.attrib['lon'])} for n in xml.findall('node')}
        result = []
        for way in xml.findall('way'):
            tags = {t.attrib['k']: t.attrib['v'] for t in way.findall('tag')}
            if 'highway' not in tags:
                continue
            nodes = [int(n.attrib['ref']) for n in way.findall('nd')]
            if any(n not in positions for n in nodes):
                raise ValueError('Map API returned an incomplete highway way')
            result.append({'type': 'way', 'id': int(way.attrib['id']), 'nodes': nodes,
                           'geometry': [positions[n] for n in nodes], 'tags': tags})
        print('Fetched', len(result), 'complete highway ways', flush=True)
        return result
    ways = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(fetch, urls):
            ways.update({w['id']: w for w in result})
    snapshot = {'source': 'Official OSM map API; normalized highway way geometry', 'urls': urls,
                'retrievedAt': datetime.now(timezone.utc).isoformat(), 'response': {'elements': list(ways.values())}}
    (ROOT / 'review-batch-03-ba09-remaining-osm.json.gz').write_bytes(gzip.compress(
        json.dumps(snapshot, ensure_ascii=False).encode(), mtime=0))


def coverage():
    source = load_snapshot('ba09-candidates-osm.json.gz')
    nodes = {n['id'] for n in source['response']['elements'] if n['type'] == 'node'}
    assignments = dict(EXISTING)
    assignments.update({s[1]: s[5] for s in SELECTION})
    flat = [node for ids in assignments.values() for node in ids]
    if len(flat) != len(set(flat)) or set(flat) != nodes:
        raise ValueError('Remaining inventory does not cover each BA09 candidate exactly once')
    return {'candidateNodes': len(nodes), 'existingSites': len(EXISTING), 'remainingSites': len(SELECTION),
            'assignments': assignments, 'candidateSnapshotDate': source['retrievedAt'],
            'scope': 'All nodes of the frozen BA09 primary/secondary/tertiary degree-four query; '
                     'not a claim that this filter detects every eligible junction in the district.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    if parser.parse_args().collect:
        collect()
    snapshot = load_snapshot('review-batch-03-ba09-remaining-osm.json.gz')
    ways = [w for w in snapshot['response']['elements'] if w['type'] == 'way']
    decision_path = ROOT / 'review-batch-03-ba09-remaining-decisions.json'
    decisions = json.loads(decision_path.read_text(encoding='utf-8'))['sites'] if decision_path.exists() else {}
    sites = []
    for number, identifier, name, lon, lat, nodes, question in SELECTION:
        feature = {'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                   'properties': {'id': identifier, 'name': name, 'reviewOrder': number, 'nextCheck': question}}
        site = prepare_site(feature, ways)
        site.update(district='BA09', candidateNodeIds=nodes)
        if identifier in decisions:
            apply_review(site, decisions[identifier])
        else:
            site['status'] = 'withheld-needs-technical-review'
        sites.append(site)
    OUT.mkdir(exist_ok=True)
    previous = OUT / 'review-data.json'
    if previous.exists():
        old = {s['id']: s for s in json.loads(previous.read_text(encoding='utf-8'))['sites']}
        for site in sites:
            prior = old.get(site['id'])
            if prior and site['version'] <= prior['version'] and any(site[k] != prior[k] for k in ('polygon', 'gates')):
                raise ValueError('Changed geometry needs an explicit revision: '+site['id'])
    for site in sites:
        name = f'K{site["number"]:02d}-{site["id"]}'
        commands = draw(site)
        if site.get('review', {}).get('activationReview', {}).get('status') == 'approved':
            for command in commands:
                if command.get('kind') == 'text':
                    command['text'] = command['text'].replace('NICHT AKTIV', 'IM BRANCH AKTIV · Live-Stand siehe Übersicht')
            report_path = ROOT / 'review-batch-03-ba09-routes.json'
            if report_path.exists():
                record = next((j for j in json.loads(report_path.read_text(encoding='utf-8'))['junctions'] if j['id'] == site['id']), {})
                blocked = [m for m in record.get('movements', []) if m['kind'] != 'right' and not m.get('enabled')]
                if blocked:
                    labels = ' / '.join(f'{m["entryLabel"]} → {m["exitLabel"]}' for m in blocked)
                    commands.append({'kind': 'text', 'text': f'GESPERRT: {labels} – Standardhinweise bleiben',
                                     'x': 28, 'y': 81, 'size': 17, 'color': '#b71c1c'})
        if site.get('review', {}).get('diagnosticOnly'):
            commands.append({'kind': 'text', 'text': 'DIAGNOSE: DREI STRASSENARME – AUSSCHLUSSVORSCHLAG',
                             'x': 28, 'y': 81, 'size': 17, 'color': '#b71c1c'})
        (OUT / f'{name}.svg').write_text(svg(commands), encoding='utf-8')
        (OUT / f'{name}.drawing.json').write_text(json.dumps(commands, ensure_ascii=False), encoding='utf-8')
        print(name, status_text(site), [(g['label'], g['osmWayId']) for g in site['gates']])
    record = {'version': 1, 'enabled': False, 'osmRetrievedAt': snapshot['retrievedAt'], 'sites': sites}
    previous.write_text(json.dumps(record, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    inventory = coverage()
    (ROOT / 'review-batch-03-ba09-remaining-inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    intro = ('Restliche BA09-Kandidaten aus der bisherigen Abfrage: fünf Standorte. '
             'Alle 32 Kandidatenpunkte sind entweder einem vorhandenen Prüffall oder einem dieser fünf Standorte zugeordnet. '
             'Aktuelle Freigaben und dauerhafte Ausschlüsse stehen an den Bildern. Keine Aktivierung.')
    cards = []
    for site in sites:
        group = '1-bestaetigt' if site['status'] == 'geometry-approved' else (
            '3-ausgeschlossen' if site['status'] == 'permanently-excluded' else '2-offen')
        image = f'../kreuzungspruefung/{group}/K{site["number"]:02d}-{site["id"]}'
        label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}')
        cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p>'
                     f'<a href="{image}.png"><img src="{image}.svg" alt="{label}"></a>'
                     f'<p><a href="{image}.png">PNG öffnen</a></p></article>')
    (OUT / 'index.html').write_text('<!doctype html><html lang="de"><meta charset="utf-8"><title>BA09 · Restliche Kandidaten</title>'
        '<style>body{font:17px Arial;margin:24px;background:#f3f4f5;color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}</style>'
        '<h1>BA09 · Restliche Kandidaten K18–K22</h1><p>'+html.escape(intro)+'</p><p>'
        '<a href="../kreuzungspruefung/2-offen/index.html">Prüfbilder im Ordner Offen</a> · '
        '<a href="../kreuzungspruefung/index.html">Gesamtübersicht</a></p>'
        +'<main>'+''.join(cards)+'</main></html>', encoding='utf-8')
    (OUT / 'README.md').write_text('# BA09 · Restliche Kandidaten K18–K22\n\n'+intro
        +'\n\n[Prüfungsübersicht](../kreuzungspruefung/index.html)\n\n'
        +'OSM-Daten: review-batch-03-ba09-remaining-osm.json.gz, © OpenStreetMap-Mitwirkende, ODbL.\n'
        +'Offline: `python docs/large-junction-analysis/prepare_ba09_remaining.py`.\n', encoding='utf-8')
    from organize_review_images import main as organize
    organize()
    from review_preflight import main as preflight
    preflight()


if __name__ == '__main__':
    main()
