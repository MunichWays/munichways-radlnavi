"""Prepare K30-K33 offline from the frozen BA01 snapshot; no runtime changes."""

import gzip
import html
import json

from build_review_images import draw, svg
from prepare_ba01_radlring import ROOT, SNAPSHOT, prepare as prepare_geometry

DRAFTS = ROOT / 'review-batch-05-ba01-remaining-drafts.json'
OUT = ROOT / 'review-batch-05-ba01-remaining-images'


def prepare(record, ways):
    site = prepare_geometry(record, ways)
    for key in ('excludedMovements', 'gateMigration', 'excludedGateDirections'):
        if key in record:
            site[key] = record[key]
    return site


def main():
    snapshot = json.loads(gzip.decompress(SNAPSHOT.read_bytes()))
    ways = [w for w in snapshot['response']['elements'] if w['type'] == 'way']
    records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
    sites = [prepare(record, ways) for record in records]
    OUT.mkdir(exist_ok=True)
    data_path = OUT / 'review-data.json'
    if data_path.exists():
        previous = {s['id']: s for s in json.loads(data_path.read_text(encoding='utf-8'))['sites']}
        for site in sites:
            old = previous.get(site['id'])
            if old and site['version'] <= old['version'] and any(site[k] != old[k] for k in ('polygon', 'gates')):
                raise ValueError('Explicit revision required: '+site['id'])
            if old and old.get('polygonApproved') and not site['polygonApproved']:
                raise ValueError('Existing geometry approval cannot be dropped')
    intro = ('K30 v3 ist freigegeben und mit drei Fahrbeziehungen im Branch aktiviert; K31 und K32 sind dauerhaft ausgeschlossen. '
             'K33 v2 ist mit acht geprüften Fahrbeziehungen aktiviert. Bei künftigen Entwürfen Kreuzungsumfang, Radwegseite, '
             'Pfeile und fehlende Anschlüsse prüfen. Warteflächen und zusammengehörende Querungen '
             'gehören hinein; benachbarte Einmündungen bleiben draußen. Gemeinsame Entry-/Exit-Punkte '
             'sind zulässig. Fahrbahnpunkte zeigen die OSM-Mittellinie. Aktivierungs-/Live-Stand siehe Gesamtübersicht; keine pauschale '
             'technische Fahrbeziehungsfreigabe. K30 hat nach Entfernung der Ottostraße drei Straßenarme; '
             'drei eindeutige Fahrbeziehungen bestehen die vorhandene Winkelprüfung ohne Vierarm-Topologie.')
    cards = []
    rows = []
    for site in sites:
        name = f'K{site["number"]:02d}-{site["id"]}'
        commands = draw(site)
        if site.get('review', {}).get('activationReview', {}).get('status') == 'approved':
            for command in commands:
                if command['kind'] == 'text':
                    command['text'] = command['text'].replace('NICHT AKTIV', 'IM BRANCH · NOCH NICHT DEPLOYED')
        (OUT / f'{name}.drawing.json').write_text(json.dumps(commands, ensure_ascii=False), encoding='utf-8')
        (OUT / f'{name}.svg').write_text(svg(commands), encoding='utf-8')
        label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}')
        cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p>'
                     f'<a href="{name}.png"><img src="{name}.svg" alt="{label}"></a></article>')
        rows.append(f'| K{site["number"]:02d} v{site["version"]} | [{site["name"]}]({name}.png) | {len(site["gates"])} |')
    (OUT / 'index.html').write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<title>BA01 · Weitere Kreuzungen · K30–K33</title><style>body{font:17px Arial;margin:24px;'
        'background:#f3f4f5;color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));'
        'gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}</style>'
        '<h1>BA01 · Weitere Kreuzungen · K30–K33</h1><p>'+intro+'</p>'
        '<p><a href="../kreuzungspruefung/index.html">Gesamtübersicht</a> · '
        '<a href="overview.png">Kontaktübersicht</a></p><main>'+''.join(cards)+'</main>'
        '<p>© OpenStreetMap-Mitwirkende, ODbL. Keine Vollständigkeitsbehauptung für BA01.</p></html>', encoding='utf-8')
    (OUT / 'README.md').write_text('\n'.join(['# BA01 · Weitere Kreuzungen · K30–K33', '',
        '[Galerie](index.html) · [Kontaktübersicht](overview.png)', '', intro, '',
        '| Fall | Kreuzung | Punkte |', '| --- | --- | --- |', *rows, '',
        'Quelle: ../review-batch-04-ba01-radlring-osm.json.gz; Abfrage und Abrufzeit gespeichert.',
        'Offline: `python docs/large-junction-analysis/prepare_ba01_remaining.py`.', '',
        'Stachus, Odeonsplatz, Prinzregentenstraße und Isartor bleiben separat zu untersuchen. Am Sendlinger Tor umfasst K33 nur den zentralen Knoten.',
        'Frühere dauerhafte Ausschlüsse bleiben unverändert.', '']), encoding='utf-8')
    data_path.write_text(json.dumps(dict(version=1, district='BA01', enabled=False,
        osmRetrievedAt=snapshot['retrievedAt'], sites=sites), ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    from organize_review_images import main as organize
    organize()
    from review_preflight import main as preflight
    preflight()


if __name__ == '__main__':
    main()
