"""Keep all numbered review sheets in three status folders, without runtime changes."""

import html
import json
import re
from pathlib import Path
from review_deployment_status import status_for

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kreuzungspruefung"
GROUPS = {"1-bestaetigt": "1. Bestätigt", "2-offen": "2. Offen", "3-ausgeschlossen": "3. Ausgeschlossen"}
BATCHES = [ROOT / "review-batch-01-images", ROOT / "review-batch-02-ba09-images"]


def main():
    prepared = json.loads((ROOT.parents[1] / 'backend/src/big_junctions.json').read_text(encoding='utf-8'))
    target_version = (ROOT.parents[1] / 'backend/VERSION').read_text(encoding='utf-8').strip()
    state_path = ROOT / "review-deployment-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    technical = {}
    for filename in ("review-batch-02-ba09-routes.json",):
        path = ROOT / filename
        if path.exists():
            technical.update({s["id"]: s for s in json.loads(path.read_text(encoding="utf-8"))["junctions"]})
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
    style = '<style>body{font:17px Arial;margin:24px;color:#263238;background:#f3f4f5}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}.badge{font-weight:bold;padding:5px 8px;display:inline-block}.live{background:#d5efdf;color:#145a32}.pending,.older{background:#fff0c2;color:#764c00}.excluded{background:#eee;color:#444}small{display:block;margin-top:7px}</style>'
    intro = 'Für Praxistests zählt die Spalte Live-Stand. Bestätigt bedeutet Geometriefreigabe. Im Branch aktivierte neue Beziehungen sind erst nach einem weiteren Deployment live. Diese Seite ist eine Momentaufnahme zum angegebenen Serverabgleich. K07 bleibt zurückgestellt; K09 dauerhaft ausgeschlossen.'
    index = ['<!doctype html><html lang="de"><meta charset="utf-8"><title>Kreuzungsprüfung</title>', style, '<h1>Kreuzungsprüfung</h1><p>'+intro+'</p>']
    total = sum(m.get('enabled', False) for j in prepared['junctions'] if j.get('enabled') for m in j['movements'])
    index.append('<p><b>'+html.escape(f'Branch vorbereitet für Backend {target_version}: {total} aktive Fahrbeziehungen. Build/Deployment startet Thomas selbst.')+'</b></p>')
    index.append('<p>Nach dem Deployment den Live-Stand aktualisieren: <code>python docs/large-junction-analysis/update_review_deployment_state.py</code></p>')
    if state:
        summary = f'Letzter Serverabgleich: {state["checkedAt"]} · Live-Backend {state["version"]["backend"]} · Commit {state["version"]["backendCommit"][:7]}'
        build = state.get("deploymentRun", {})
        if build:
            summary += f' · Letzter Build: {build.get("conclusion") or build.get("status")} ({build.get("headSha", "")[:7]})'
        index.append('<p>'+html.escape(summary)+'</p>')
    else:
        index.append('<p>Live-Stand noch nicht abgeglichen. Bestätigt bedeutet noch nicht deployed.</p>')
    readme = ['# Kreuzungsprüfung', '', intro, '']
    for group, title in GROUPS.items():
        sites = sorted(groups[group], key=lambda s: s["number"])
        index.append(f'<h2><a href="{group}/index.html">{title} ({len(sites)})</a></h2><table><tr><th>Kreuzung / Geometrie</th><th>Technische Prüfung</th><th>Live-Stand für Praxistests</th></tr>')
        cards = []
        readme.append(f'- [{title} ({len(sites)})]({group}/index.html)')
        for site in sites:
            name = f'K{site["number"]:02d}-{site["id"]}'
            label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}')
            phase = status_for(site, state, technical.get(site["id"]))
            badge = f'<span class="badge {phase["css"]}">{html.escape(phase["text"])}</span>'
            details = ''
            record = technical.get(site['id'], {})
            blocked_notice = ''
            if record.get('geometryRevision') == site['version']:
                blocked = [m for m in record.get('movements', []) if m['kind'] != 'right' and not m.get('enabled')]
                if blocked:
                    labels = ' / '.join(f'{m["entryLabel"]} → {m["exitLabel"]}' for m in blocked)
                    blocked_notice = '<p style="color:#b71c1c;background:#ffebee;padding:8px"><b>'+html.escape(
                        f'GESPERRT: {labels}. Keine große-Kreuzung-Ansage; Standardhinweise bleiben.')+'</b></p>'
                items = []
                for movement in record.get('movements', []):
                    if movement['kind'] == 'right':
                        continue
                    direction = {'left': 'links', 'straight': 'geradeaus'}[movement['kind']]
                    live_site = next((j for j in state.get('junctions', []) if j['id'] == site['id'] and j.get('enabled')), {})
                    deployed = phase['geometryMatches'] and any(m.get('enabled') and m['id'] == movement['id'] for m in live_site.get('movements', []))
                    outcome = ('bestanden; live' if deployed else 'bestanden; noch nicht live') if movement.get('enabled') else 'gesperrt: '+movement.get('reason', 'Prüfung offen')
                    items.append('<li>'+html.escape(f'{movement["entryLabel"]} → {movement["exitLabel"]}: {direction} — {outcome}')+'</li>')
                details = '<details><summary>Fahrbeziehungen anzeigen</summary><ul>'+''.join(items)+'</ul></details>'
            branch_site = next((j for j in prepared['junctions'] if j['id'] == site['id'] and j.get('enabled')), {})
            branch_count = sum(m.get('enabled', False) for m in branch_site.get('movements', []))
            branch_note = f'<small>Im Branch für Backend {html.escape(target_version)} aktiviert: {branch_count}</small>' if branch_count else ''
            index.append(f'<tr><td><a href="{group}/{name}.png">{label}</a></td><td>{html.escape(phase["technical"])}{branch_note}{blocked_notice}{details}</td><td>{badge}</td></tr>')
            cards.append(f'<article><h2>{label}</h2><p>{badge}<small>{html.escape(phase["technical"])}</small>{branch_note}</p>{blocked_notice}<p>{html.escape(site["note"])}</p><a href="{name}.png"><img src="{name}.svg" alt="{label}"></a><p><a href="{name}.png">PNG öffnen</a></p></article>')
        index.append('</table>')
        (OUT / group / "index.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'+style+f'<h1>{title}</h1><p><a href="../index.html">Alle Ordner</a></p><main>'+''.join(cards)+'</main></html>', encoding="utf-8")
    (OUT / "index.html").write_text(''.join(index)+'</html>', encoding="utf-8")
    (OUT / "README.md").write_text('\n'.join(readme)+'\n', encoding="utf-8")
    print('Review folders:', {k: len(v) for k, v in groups.items()})


if __name__ == "__main__":
    main()
