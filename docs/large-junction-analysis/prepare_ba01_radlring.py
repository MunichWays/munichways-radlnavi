"""Reproduce BA01 Altstadt-Radlring geometry drafts offline; never writes runtime data."""

from copy import deepcopy
import gzip
import html
import json
from math import cos, radians
from pathlib import Path

from build_review_images import draw, extract_gates, number_gates, prepare_site, svg

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'review-batch-04-ba01-radlring-images'
SNAPSHOT = ROOT / 'review-batch-04-ba01-radlring-osm.json.gz'
DRAFTS = ROOT / 'review-batch-04-ba01-radlring-drafts.json'


def prepare(record, ways):
    feature = {'geometry': {'coordinates': record['origin']}, 'properties': {
        'id': record['id'], 'name': record['name'], 'reviewOrder': record['number'],
        'nextCheck': record['note']}}
    site = prepare_site(feature, ways)
    site.update(district='BA01', version=record['version'], polygon=record['polygon'],
                onRoadWayIds=record['onRoadWayIds'], status='geometry-draft',
                candidateNodeIds=record['candidateNodeIds'],
                proposedLogicalArms=record['proposedLogicalArms'],
                basis='Frozen OSM cycling crossings and explicitly scoped road/ lane approaches; '
                      'manually bounded draft, no geometry or movement approval.')
    if record.get('reviewDecision'):
        site['review'] = record['reviewDecision']
        site['status'] = record['reviewDecision']['status']
    lon, lat = site['origin']
    mx = 111320 * cos(radians(lat))
    project = lambda p: ((p[0] - lon) * mx, (p[1] - lat) * 111320)
    # A lane on the right and a separate path on the left do not make two
    # carriageway gates. Keep the frozen source unchanged; constrain extraction.
    extraction = deepcopy(site['ways'])
    overrides = record.get('roadDirectionOverrides', {})
    for way in extraction:
        if str(way['id']) in overrides:
            way['tags']['oneway:bicycle'] = overrides[str(way['id'])]
    site['roadDirectionOverrides'] = overrides
    site['gates'] = extract_gates(extraction, site['polygon'], project, site['onRoadWayIds'])
    number_gates(site['gates'], (0, 0), project)
    for gate in site['gates']:
        label = record.get('preservedLabels', {}).get(f'{gate["osmWayId"]}:{gate["kind"]}')
        if label:
            gate['label'] = label
    by_id = {w['id']: w for w in site['ways']}
    for gate in site['gates']:
        if gate['osmWayId'] not in site['onRoadWayIds']:
            continue
        tags = by_id[gate['osmWayId']]['tags']
        lane = {k: v for k, v in tags.items() if k.startswith('cycleway') and v == 'lane'}
        if lane:
            gate['laneEvidence'] = lane
        gate['positionBasis'] = 'OSM carriageway centerline; lateral lane position unverified'
    excluded = record.get('excludedGateDirections', {})
    site['gates'] = [g for g in site['gates'] if g['kind'] not in excluded.get(str(g['osmWayId']), [])]
    for gate in site['gates']:
        if str(gate['osmWayId']) in excluded:
            gate['shared'] = False
            gate['scopeNote'] = 'Opposite exit excluded by Thomas; legal OSM cycling directions unchanged.'
    if site['status'] == 'geometry-approved':
        from review_preflight import fingerprint
        if fingerprint(site) != site['review'].get('geometrySha256'):
            raise ValueError('Approved BA01 geometry fingerprint changed: '+site['id'])
        site['polygonApproved'] = True
    return site


def main():
    snapshot = json.loads(gzip.decompress(SNAPSHOT.read_bytes()))
    records = json.loads(DRAFTS.read_text(encoding='utf-8'))['sites']
    ways = [w for w in snapshot['response']['elements'] if w['type'] == 'way']
    sites = [prepare(record, ways) for record in records]
    OUT.mkdir(exist_ok=True)
    data_path = OUT / 'review-data.json'
    if data_path.exists():
        previous = {s['id']: s for s in json.loads(data_path.read_text(encoding='utf-8'))['sites']}
        for site in sites:
            old = previous.get(site['id'])
            if old and site['version'] <= old['version'] and any(
                    site[k] != old[k] for k in ('polygon', 'gates')):
                raise ValueError(f'Explicit revision required: {site["id"]}')
            if old and old.get('polygonApproved') and not site['polygonApproved']:
                raise ValueError('Existing BA01 geometry approval cannot be dropped')
    cards, rows = [], []
    for site in sites:
        name = f'K{site["number"]:02d}-{site["id"]}'
        commands = draw(site)
        for command in commands:
            if command['kind'] == 'text':
                command['text'] = command['text'].replace('Korrigierter Entwurf', 'Entwurf').replace(
                    'Radwege / geprüfte Straßenführung', 'Radwege / Straßenführung im Entwurf')
                if site.get('review', {}).get('disposition') == 'permanently-deferred':
                    command['text'] = command['text'].replace('Dauerhaft ausgeschlossen – Fall geschlossen',
                        'Dauerhaft zurückgestellt – nur bei Praxisproblem neu prüfen')
                if site.get('review', {}).get('activationReview', {}).get('status') == 'approved':
                    command['text'] = command['text'].replace('NICHT AKTIV', 'IM BRANCH · NOCH NICHT DEPLOYED')
        (OUT / f'{name}.drawing.json').write_text(json.dumps(commands, ensure_ascii=False), encoding='utf-8')
        (OUT / f'{name}.svg').write_text(svg(commands), encoding='utf-8')
        label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}')
        cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p>'
                     f'<a href="{name}.png"><img src="{name}.svg" alt="{label}"></a></article>')
        rows.append(f'| K{site["number"]:02d} v{site["version"]} | [{site["name"]}]({name}.png) | {len(site["gates"])} |')
    open_count = sum(s['status'] == 'geometry-draft' for s in sites)
    excluded_count = sum(s['status'] == 'permanently-excluded' for s in sites)
    approved_count = sum(s['polygonApproved'] for s in sites)
    intro = (f'Altstadt-Radlring: {approved_count} geometrisch bestätigt, {open_count} Entwürfe offen, {excluded_count} dauerhaft ausgeschlossen/zurückgestellt. Aktivierungs-/Live-Stand siehe Gesamtübersicht. '
             'Bitte Umfang, Radwegseite, Pfeile und fehlende Anschlüsse prüfen. Querungen und Warteflächen '
             'gehören hinein, benachbarte Einmündungen bleiben draußen. Strecken müssen noch nicht abgefahren werden. '
             'Gemeinsame Zweirichtungspunkte sind zulässig; Entry/Exit gleicher Nummer bilden kein Paar. '
             'Fahrbahnpunkte liegen auf der OSM-Mittellinie, nicht auf einer vermessenen Radfahrstreifenkante.')
    inventory = json.loads((ROOT / 'review-batch-04-ba01-radlring-inventory.json').read_text(encoding='utf-8'))
    deferred = ''.join(f'<li>{html.escape(s["name"])}: {html.escape(s["reason"])}</li>'
                       for s in inventory['deferred'])
    (OUT / 'index.html').write_text('<!doctype html><html lang="de"><meta charset="utf-8">'
        '<title>BA01 · Altstadt-Radlring</title><style>body{font:17px Arial;margin:24px;background:#f3f4f5;'
        'color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}'
        'article{background:white;padding:16px}img{width:100%}p,li{line-height:1.5}</style>'
        '<h1>BA01 · Altstadt-Radlring · K23–K29</h1><p>'+intro+'</p>'
        '<p><a href="../kreuzungspruefung/index.html">Gesamtübersicht</a> · '
        '<a href="overview.png">Kontaktübersicht</a></p><main>'+''.join(cards)+'</main>'
        '<h2>Separat vorgemerkt</h2><ul>'+deferred+'</ul>'
        '<p>Keine Vollständigkeitsbehauptung für BA01. © OpenStreetMap-Mitwirkende, ODbL.</p></html>', encoding='utf-8')
    (OUT / 'README.md').write_text('\n'.join(['# BA01 · Altstadt-Radlring', '',
        '[Galerie](index.html) · [Kontaktübersicht](overview.png)', '', intro, '',
        '| Fall | Kreuzung | Punkte |', '| --- | --- | --- |', *rows, '',
        'Quelle: ../review-batch-04-ba01-radlring-osm.json.gz (Abfrage und Abrufzeit gespeichert).',
        'Bezirksgrenze: OSM-Relation 56391; Grenzkreuzungen einschließlich äußerer Zufahrten.',
        'Auswahl und Zurückstellungen: ../review-batch-04-ba01-radlring-inventory.json.',
        'Offline: `python docs/large-junction-analysis/prepare_ba01_radlring.py`.',
        'PNG: `powershell -NoProfile -ExecutionPolicy Bypass -File docs/large-junction-analysis/render_review_images.ps1 -BatchDirectory review-batch-04-ba01-radlring-images`.', '',
        'Keine technische Fahrbeziehungsfreigabe, Aktivierung oder Änderung am Laufzeitkatalog.', '']), encoding='utf-8')
    data_path.write_text(json.dumps({'version': 1, 'district': 'BA01', 'enabled': False,
        'osmRetrievedAt': snapshot['retrievedAt'], 'sites': sites}, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    from organize_review_images import main as organize
    organize()
    from review_preflight import main as preflight
    preflight()
    print(f'BA01: {open_count} open, {excluded_count} excluded/deferred; runtime unchanged.')


if __name__ == '__main__':
    main()
