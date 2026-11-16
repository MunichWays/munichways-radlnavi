"""Keep all numbered review sheets in three status folders, without runtime changes."""

import html
import json
import re
import gzip
from pathlib import Path
from review_deployment_status import status_for

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kreuzungspruefung"
GROUPS = {"1-bestaetigt": "1. Bestätigt", "2-offen": "2. Offen", "3-ausgeschlossen": "3. Ausgeschlossen"}
BATCHES = [ROOT / "review-batch-01-images", ROOT / "review-batch-02-ba09-images",
           ROOT / "review-batch-03-ba09-remaining-images",
           ROOT / "review-batch-04-ba01-radlring-images",
           ROOT / "review-batch-05-ba01-remaining-images",
           ROOT / "review-batch-06-primary-images", ROOT / "review-batch-07-lanes-images"]


def add_lane_queue(groups):
    """Pending inventory rows have no geometry/links; prepared IDs replace them."""
    path = ROOT / 'review-lane-priority-queue.json'
    if not path.exists():
        return
    known = {s['id'] for sites in groups.values() for s in sites}
    for site in json.loads(path.read_text(encoding='utf-8'))['sites']:
        if site['id'] not in known:
            groups['2-offen'].append(dict(site, textOnly=True, kind='pending',
                status='inventory-open', version=0, polygon=[]))
            known.add(site['id'])


def add_supplemental_sites(groups, catalog, records):
    known = {site['id'] for sites in groups.values() for site in sites}
    for record in records:
        if record['id'] in known:
            raise ValueError('Duplicate review site: '+record['id'])
        known.add(record['id'])
        site = dict(record, textOnly=True, version=1)
        if record['kind'] == 'pilot':
            junction = next(j for j in catalog['junctions'] if j['id'] == record['id'])
            site.update(status='geometry-approved', polygon=junction['polygon']['coordinates'][0])
            group = '1-bestaetigt'
        else:
            site.update(status='excluded', polygon=[])
            group = '3-ausgeschlossen'
        groups[group].append(site)


def review_counts(groups):
    sites = [site for items in groups.values() for site in items]
    if len(sites) != len({site['id'] for site in sites}):
        raise ValueError('Review counts contain duplicate sites')
    return {**{group: len(items) for group, items in groups.items()}, 'total': len(sites)}


def city_scope():
    queue = json.loads((ROOT / 'munich-review-queue.geojson').read_text(encoding='utf-8'))
    snapshot = json.loads(gzip.decompress((ROOT / 'munich-candidates.json.gz').read_bytes()))
    return {'candidatePoints': len({f['properties']['osmNodeId'] for f in queue['features']}),
            'date': snapshot['retrievedAt'][:10]}


def main():
    prepared = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
    target_version = (ROOT.parents[1] / 'backend/VERSION').read_text(encoding='utf-8').strip()
    state_path = ROOT / "review-deployment-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    field_tests = json.loads((ROOT / 'review-field-tests.json').read_text(encoding='utf-8'))['tests']
    technical = {}
    for filename in ("review-batch-02-ba09-routes.json", "review-batch-03-ba09-routes.json",
                     "review-batch-04-ba01-routes.json", "review-batch-05-k33-routes.json",
                     "review-batch-06-primary-routes.json", "review-batch-07-lanes-routes.json", "review-k18-v5-routes.json"):
        path = ROOT / filename
        if path.exists():
            technical.update({s["id"]: s for s in json.loads(path.read_text(encoding="utf-8"))["junctions"]})
    for path in ROOT.glob('review-k*-v*-draft-technical.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        technical[record['id']] = record
    updates = ROOT / 'review-updates-2026-11-14-routes.json'
    if updates.exists():
        technical.update({s['id']: s for s in json.loads(updates.read_text(encoding='utf-8'))['junctions']})
    sequences = ROOT / 'review-wilram-sequences-implementation.json'
    if sequences.exists():
        technical.update({s['id']: s for s in json.loads(sequences.read_text(encoding='utf-8'))['junctions']})
    groups = {key: [] for key in GROUPS}
    for batch in BATCHES:
        data_path = batch / "review-data.json"
        if not data_path.exists():
            continue
        for site in json.loads(data_path.read_text(encoding="utf-8"))["sites"]:
            status = site["status"]
            group = "1-bestaetigt" if status == "geometry-approved" else (
                "3-ausgeschlossen" if status == "permanently-excluded" else "2-offen")
            target = OUT / group
            target.mkdir(parents=True, exist_ok=True)
            name = f'K{site["number"]:02d}-{site["id"]}'
            for extension in ("png", "svg", "drawing.json"):
                destination = target / f"{name}.{extension}"
                sources = [batch / destination.name] + [OUT / other / destination.name for other in GROUPS if other != group]
                moved = False
                for source in sources:
                    if source.exists():
                        # Only explicit individual files within this analysis directory move.
                        assert source.resolve().is_relative_to(ROOT) and destination.resolve().is_relative_to(ROOT)
                        if not moved:
                            source.replace(destination)
                            moved = True
                        else:
                            # A freshly generated file takes priority over an older folder copy.
                            source.unlink()
                for doc in (batch / "index.html", batch / "README.md"):
                    if doc.exists():
                        text = doc.read_text(encoding="utf-8")
                        link = f"../kreuzungspruefung/{group}/{destination.name}"
                        text = re.sub(r'(href="|src="|\]\()(?:\.\./kreuzungspruefung/[^/]+/)?' + re.escape(destination.name),
                            lambda match: match[1] + link, text)
                        doc.write_text(text, encoding="utf-8")
            groups[group].append(site)
    add_supplemental_sites(groups, prepared, json.loads((ROOT / 'review-supplemental-sites.json').read_text(encoding='utf-8'))['sites'])
    add_lane_queue(groups)
    counts, scope = review_counts(groups), city_scope()
    style = '<style>body{font:17px Arial;margin:24px;color:#263238;background:#f3f4f5}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}.badge{font-weight:bold;padding:5px 8px;display:inline-block}.live{background:#d5efdf;color:#145a32}.pending,.older{background:#fff0c2;color:#764c00}.excluded{background:#eee;color:#444}small{display:block;margin-top:7px}.review-section{margin:16px 0;background:white;border:1px solid #ddd;border-radius:6px;padding:14px}.review-section>summary{cursor:pointer;font-size:1.2em;font-weight:bold}.review-section>summary:focus-visible{outline:2px solid #6a1b9a;outline-offset:4px}</style>'
    intro = 'Für Praxistests zählt die Spalte Live-Stand. Bestätigt bedeutet Geometriefreigabe. Im Branch aktivierte neue Beziehungen sind erst nach einem weiteren Deployment live. Diese Seite ist eine Momentaufnahme zum angegebenen Serverabgleich. K07 und K19 sind im Branch aktiviert; K09 bleibt dauerhaft ausgeschlossen.'
    index = ['<!doctype html><html lang="de"><meta charset="utf-8"><title>Kreuzungsprüfung</title>', style, '<h1>Kreuzungsprüfung</h1>']
    index.insert(3, '<p><b>'+html.escape(f'Erfasste Fälle gesamt: {counts["total"]} · davon bestätigt: {counts["1-bestaetigt"]} · offen: {counts["2-offen"]} · ausgeschlossen: {counts["3-ausgeschlossen"]}')+'</b></p>')
    index.insert(4, '<p>'+html.escape(f'Münchenweiter Suchumfang: {scope["candidatePoints"]} OSM-Kandidatenpunkte (Datenstand {scope["date"]}); Hauptstraßen bis einschließlich tertiary, ohne Kreisverkehre. Dies ist noch keine bereinigte Kreuzungszahl: getrennte Fahrbahnen erzeugen Mehrfachpunkte, komplexe/T-Kreuzungen können den Filter passieren und einzelne geeignete Fälle fehlen. Die Gesamtzahl tatsächlich geeigneter Münchner Kreuzungen ist noch nicht bestimmt.')+'</p>')
    index.append('<p>'+intro+'</p>')
    review_links = []
    remaining_gallery = ROOT / 'review-batch-03-ba09-remaining-images/index.html'
    if remaining_gallery.exists():
        review_links.append('<p><a href="../review-batch-03-ba09-remaining-images/index.html"><b>BA09-Prüfrunde K18–K22: aktueller Prüfstand</b></a></p>')
    if (ROOT / 'review-batch-06-primary-images/index.html').exists():
        review_links.append('<p><a href="../review-batch-06-primary-images/index.html"><b>Primary/Primary · K34–K37</b></a></p>')
    if (ROOT / 'outgoing-lanes-munich.html').exists():
        index.append('<p><a href="../outgoing-lanes-munich.html"><b>Priorität: Kreuzungen nach ausgehenden Fahrspuren</b></a></p>')
    if (ROOT / 'review-batch-07-lanes-images/index.html').exists():
        review_links.append('<p><a href="../review-batch-07-lanes-images/index.html"><b>K38–K41: nächste vier Kreuzungen zur Bildprüfung</b></a></p>')
    if (ROOT / 'review-batch-05-ba01-remaining-images/index.html').exists():
        review_links.append('<p><a href="../review-batch-05-ba01-remaining-images/index.html"><b>BA01 · Weitere Kreuzungen · K30–K33: Bildprüfung und Freigabestand</b></a></p>')
    if (ROOT / 'review-batch-04-ba01-radlring-images/index.html').exists():
        review_links.append('<p><a href="../review-batch-04-ba01-radlring-images/index.html"><b>BA01 · Altstadt-Radlring · K23–K29: Prüf- und Aktivierungsstand</b></a></p>')
    total = sum(m.get('enabled', False) for j in prepared['junctions'] if j.get('enabled') for m in j['movements'])
    if state and state['version']['backend'] == target_version and state['catalogVersion'] == prepared['version']:
        live_total = sum(m.get('enabled', False) for j in state['junctions'] if j.get('enabled') for m in j['movements'])
        live_count = sum(j.get('enabled', False) for j in state['junctions'])
        index.append('<p><b>'+html.escape(f'Backend {target_version} ist live: {live_count} Kreuzungen mit {live_total} aktiven Fahrbeziehungen.')+'</b></p>')
    else:
        index.append('<p><b>'+html.escape(f'Branch vorbereitet für Backend {target_version}: {total} aktive Fahrbeziehungen; Live-Stand siehe unten.')+'</b></p>')
    index.append('<details><summary>Live-Stand aktualisieren</summary><code>python docs/large-junction-analysis/update_review_deployment_state.py</code></details>')
    if state:
        summary = f'Letzter Serverabgleich: {state["checkedAt"]} · Live-Backend {state["version"]["backend"]} · Commit {state["version"]["backendCommit"][:7]}'
        build = state.get("deploymentRun", {})
        if build:
            summary += f' · Letzter Build: {build.get("conclusion") or build.get("status")} ({build.get("headSha", "")[:7]})'
        index.append('<p>'+html.escape(summary)+'</p>')
    else:
        index.append('<p>Live-Stand noch nicht abgeglichen. Bestätigt bedeutet noch nicht deployed.</p>')
    readme = ['# Kreuzungsprüfung', '', intro, '']
    index.append('<details class="review-section"><summary>Prüfgruppen ('+str(len(review_links))+')</summary>'+''.join(review_links)+'</details>')
    for group, title in GROUPS.items():
        key = (lambda s: (-(s.get('outgoingLaneTotal') or 0), s.get('number', 0), s['name'])) if group == '2-offen' else (lambda s: s.get('number', 0))
        sites = sorted(groups[group], key=key)
        index.append(f'<details class="review-section" id="{group}"><summary>{title} ({len(sites)})</summary><p><a href="{group}/index.html">Bildübersicht öffnen</a></p><table><tr><th>Kreuzung / Geometrie</th><th>Technische Prüfung</th><th>Live-Stand für Praxistests</th></tr>')
        cards = []
        readme.append(f'- [{title} ({len(sites)})]({group}/index.html)')
        for site in sites:
            name = f'K{site["number"]:02d}-{site["id"]}' if not site.get('textOnly') else None
            label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}' if name else ('Pilot · ' if site['kind'] == 'pilot' else '')+site['name'])
            phase = status_for(site, state, technical.get(site["id"]))
            badge = f'<span class="badge {phase["css"]}">{html.escape(phase["text"])}</span>'
            field_note = ''
            for test in field_tests:
                if test['result'] == 'passed' and test['geometryRevisions'].get(site['id']) == site['version']:
                    field_note = '<small style="color:#145a32">'+html.escape(f'Praxistest erfolgreich · {test["date"]} · viele Fahrbeziehungen (Thomas)')+'</small>'
            details = ''
            record = technical.get(site['id'], {})
            blocked_notice = ''
            if record.get('geometryRevision') == site['version']:
                blocked = [m for m in record.get('movements', []) if m['kind'] != 'right' and not m.get('enabled')]
                if blocked:
                    labels = ' / '.join(f'{m["entryLabel"]} → {m["exitLabel"]}' for m in blocked)
                    blocked_notice = '<p style="color:#616161;font-size:0.9em">'+html.escape(
                        f'Ohne Kreuzungsansage: {labels}. Standardhinweise bleiben.')+'</p>'
                items = []
                for movement in record.get('movements', []):
                    if movement['kind'] == 'right':
                        continue
                    direction = {'left': 'links', 'straight': 'geradeaus', 'special': 'Sonderfolge'}[movement['kind']]
                    live_site = next((j for j in state.get('junctions', []) if j['id'] == site['id'] and j.get('enabled')), {})
                    deployed = phase['geometryMatches'] and any(m.get('enabled') and m['id'] == movement['id'] for m in live_site.get('movements', []))
                    outcome = ('bestanden; live' if deployed else 'bestanden; noch nicht live') if movement.get('enabled') else 'gesperrt: '+movement.get('reason', 'Prüfung offen')
                    if movement.get('implementationPending'):
                        outcome = 'Routenführung geprüft; Sonderansage noch nicht implementiert, nicht aktiviert'
                    elif movement.get('requiresProtocolVersion') == 2:
                        outcome = 'implementiert/geprüft für neue App (Protokoll v2); noch nicht deployed'
                    items.append('<li>'+html.escape(f'{movement["entryLabel"]} → {movement["exitLabel"]}: {direction} — {outcome}')+'</li>')
                details = '<details><summary>Fahrbeziehungen anzeigen</summary><ul>'+''.join(items)+'</ul></details>'
            branch_site = next((j for j in prepared['junctions'] if j['id'] == site['id'] and j.get('enabled')), {})
            branch_count = sum(m.get('enabled', False) for m in branch_site.get('movements', []))
            branch_note = f'<small>Im Branch für Backend {html.escape(target_version)} aktiviert: {branch_count}</small>' if branch_count else ''
            sequences = sum(bool(m.get('sequence')) for m in branch_site.get('movements', []) if m.get('enabled'))
            if sequences:
                branch_note += f'<small>Davon {sequences} Sonderfolgen nur mit neuer App (Protokoll v2).</small>'
            if branch_count and branch_site['polygon']['coordinates'][0] != site['polygon']:
                branch_note = f'<small>Bisherige Branch-Fläche unverändert: {branch_count} aktive Beziehungen; v{site["version"]} nicht aktiviert.</small>'
            if site.get('textOnly'):
                index.append(f'<tr><td>{label}<small>{html.escape(site["note"])}</small></td><td>{html.escape(phase["technical"])}</td><td>{badge}</td></tr>')
                cards.append(f'<article><h2>{label}</h2><p>{badge}<small>{html.escape(phase["technical"])}</small></p><p>{html.escape(site["note"])}</p></article>')
            else:
                change_note = '<small>'+html.escape(site['note'])+'</small>' if site['status'] in {'geometry-draft', 'permanently-excluded'} or site.get('review', {}).get('pendingChange') else ''
                index.append(f'<tr><td><a href="{group}/{name}.png">{label}</a>{change_note}</td><td>{html.escape(phase["technical"])}{field_note}{branch_note}{blocked_notice}{details}</td><td>{badge}</td></tr>')
                gallery_notice = blocked_notice
                cards.append(f'<article><h2>{label}</h2><p>{badge}<small>{html.escape(phase["technical"])}</small>{field_note}{branch_note}</p>{gallery_notice}<p>{html.escape(site["note"])}</p><a href="{name}.png"><img src="{name}.svg" alt="{label}"></a><p><a href="{name}.png">PNG öffnen</a></p></article>')
        index.append('</table></details>')
        (OUT / group / "index.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'+style+f'<h1>{title}</h1><p><a href="../index.html">Alle Ordner</a></p><main>'+''.join(cards)+'</main></html>', encoding="utf-8")
    (OUT / "index.html").write_text(''.join(index)+'</html>', encoding="utf-8")
    (OUT / "README.md").write_text('\n'.join(readme)+'\n', encoding="utf-8")
    print('Review folders:', {k: len(v) for k, v in groups.items()})


if __name__ == "__main__":
    main()
