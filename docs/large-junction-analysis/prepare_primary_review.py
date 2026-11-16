"""Reproduce K34-K37 from frozen OSM map extracts; no runtime writes."""
import gzip
import html
import json
from pathlib import Path

from build_review_images import draw, svg
from prepare_ba01_radlring import prepare as prepare_geometry

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'primary-primary-context-osm.json.gz'
DRAFTS = ROOT / 'review-batch-06-primary-drafts.json'
OUT = ROOT / 'review-batch-06-primary-images'


def prepare(record, ways):
    site = prepare_geometry(record, ways)
    site['district'] = 'München · Primary/Primary'
    site['basis'] = ('Frozen surface cycling connections, bounded crossing nodes with 8m waiting-area padding; '
                     'Human geometry and activation decisions are recorded separately; technical evidence in review-batch-06-primary-routes.json.')
    return site


def main():
    snapshot = json.loads(gzip.decompress(SOURCE.read_bytes()))
    sources = {s['id']: s for s in snapshot['sites']}
    records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
    sites = [prepare(record, sources[record.get('sourceId', record['id'])]['elements']) for record in records]
    OUT.mkdir(exist_ok=True)
    data_path = OUT / 'review-data.json'
    if data_path.exists():
        previous = {s['id']: s for s in json.loads(data_path.read_text(encoding='utf-8'))['sites']}
        for site in sites:
            old = previous.get(site['id'])
            if old and site['version'] <= old['version'] and any(site[k] != old[k] for k in ('polygon', 'gates')):
                raise ValueError('Explicit revision required: '+site['id'])
            if old and old.get('polygonApproved') and not site['polygonApproved']:
                raise ValueError('Existing approval cannot be dropped')
    intro = ('K34 bis K37 sind geometrisch freigegeben und technisch geprüft. '
             'Im lokalen Branch für Backend 2.4.16 aktiviert; Live-Stand siehe Gesamtübersicht. '
             'K35 West und K37 Ost bilden zwei getrennte Flächen. '
             'Brückenfahrbahnen, Kfz-Rampen und Tunnel bleiben ausgeschlossen. '
             'Bei K36 liegt der nördliche Exit auf einem Radfahrstreifen; '
             'dessen Punkt zeigt die OSM-Fahrbahnmittellinie. '
             'Entry/Exit gleicher Nummer bilden kein Fahrbeziehungspaar.')
    cards, rows = [], []
    for site in sites:
        name = f'K{site["number"]:02d}-{site["id"]}'
        commands = draw(site)
        for command in commands:
            if command['kind'] == 'text':
                command['text'] = command['text'].replace('Korrigierter Entwurf', 'Entwurf')
                if site.get('review', {}).get('activationReview', {}).get('status') == 'approved':
                    command['text'] = command['text'].replace('NICHT AKTIV', 'IM BRANCH; NICHT DEPLOYED')
        (OUT / f'{name}.drawing.json').write_text(json.dumps(commands, ensure_ascii=False), encoding='utf-8')
        (OUT / f'{name}.svg').write_text(svg(commands), encoding='utf-8')
        label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}')
        cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p>'
                     f'<a href="{name}.png"><img src="{name}.svg" alt="{label}"></a></article>')
        rows.append(f'| K{site["number"]:02d} v{site["version"]} | [{site["name"]}]({name}.png) | {len(site["gates"])} |')
    (OUT / 'index.html').write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<title>Primary/Primary · K34–K37</title><style>body{font:17px Arial;margin:24px;'
        'background:#f3f4f5;color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));'
        'gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}</style>'
        '<h1>Primary/Primary · K34–K37</h1><p>'+intro+'</p>'
        '<p><a href="../kreuzungspruefung/index.html">Gesamtübersicht</a> · '
        '<a href="overview.png">Kontaktübersicht</a></p><main>'+''.join(cards)+'</main>'
        '<p>OSM-Kartenausschnitte vom 16.11.2026 · © OpenStreetMap-Mitwirkende, ODbL.</p></html>', encoding='utf-8')
    (OUT / 'README.md').write_text('\n'.join(['# Primary/Primary · K34–K37', '',
        '[Galerie](index.html) · [Kontaktübersicht](overview.png)', '', intro, '',
        '| Fall | Kreuzung | Punkte |', '| --- | --- | --- |', *rows, '',
        'Quelle: ../primary-primary-context-osm.json.gz; offizielle OSM map API, vollständige Highway-Ways.',
        'Auswahl: ../primary-primary-munich-inventory.json. K12 ist bereits bearbeitet.',
        'Offline: `python docs/large-junction-analysis/prepare_primary_review.py`.',
        'Geometriestatus je Fall siehe Gesamtübersicht. Technische Prüfung und Branch-Aktivierung abgeschlossen; Live-Stand siehe Gesamtübersicht.', '']), encoding='utf-8')
    data_path.write_text(json.dumps(dict(version=1, district='München', enabled=False,
        osmRetrievedAt=snapshot['retrievedAt'], sites=sites), ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    from organize_review_images import main as organize
    organize()
    from review_preflight import main as preflight
    preflight()


if __name__ == '__main__':
    main()
