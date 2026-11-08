"""Keep all numbered review sheets in three status folders, without runtime changes."""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "kreuzungspruefung"
GROUPS = {"1-bestaetigt": "1. Bestätigt", "2-offen": "2. Offen", "3-ausgeschlossen": "3. Ausgeschlossen"}
BATCHES = [ROOT / "review-batch-01-images", ROOT / "review-batch-02-ba09-images"]


def main():
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
                for source in sources:
                    if source.exists():
                        # Only explicit individual files within this analysis directory move.
                        assert source.resolve().is_relative_to(ROOT) and destination.resolve().is_relative_to(ROOT)
                        source.replace(destination)
                for doc in (batch / "index.html", batch / "README.md"):
                    if doc.exists():
                        text = doc.read_text(encoding="utf-8")
                        link = f"../kreuzungspruefung/{group}/{destination.name}"
                        text = re.sub(r'(href="|src="|\]\()(?:\.\./kreuzungspruefung/[^/]+/)?' + re.escape(destination.name),
                            lambda match: match[1] + link, text)
                        doc.write_text(text, encoding="utf-8")
            groups[group].append(site)
    style = '<style>body{font:17px Arial;margin:24px;color:#263238;background:#f3f4f5}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}</style>'
    intro = 'Bestätigt bedeutet Geometriefreigabe; die Aktivierung der Fahrbeziehungen wird separat geprüft. Zurückgestellte Fälle bleiben unter Offen. K07 bleibt zurückgestellt; K09 dauerhaft ausgeschlossen.'
    index = ['<!doctype html><html lang="de"><meta charset="utf-8"><title>Kreuzungsprüfung</title>', style, '<h1>Kreuzungsprüfung</h1><p>'+intro+'</p>']
    readme = ['# Kreuzungsprüfung', '', intro, '']
    for group, title in GROUPS.items():
        sites = sorted(groups[group], key=lambda s: s["number"])
        index.append(f'<h2><a href="{group}/index.html">{title} ({len(sites)})</a></h2><ul>')
        cards = []
        readme.append(f'- [{title} ({len(sites)})]({group}/index.html)')
        for site in sites:
            name = f'K{site["number"]:02d}-{site["id"]}'
            label = html.escape(f'K{site["number"]:02d} v{site["version"]} · {site["name"]}')
            index.append(f'<li><a href="{group}/{name}.png">{label}</a></li>')
            cards.append(f'<article><h2>{label}</h2><p>{html.escape(site["note"])}</p><a href="{name}.png"><img src="{name}.svg" alt="{label}"></a><p><a href="{name}.png">PNG öffnen</a></p></article>')
        index.append('</ul>')
        (OUT / group / "index.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8">'+style+f'<h1>{title}</h1><p><a href="../index.html">Alle Ordner</a></p><main>'+''.join(cards)+'</main></html>', encoding="utf-8")
    (OUT / "index.html").write_text(''.join(index)+'</html>', encoding="utf-8")
    (OUT / "README.md").write_text('\n'.join(readme)+'\n', encoding="utf-8")
    print('Review folders:', {k: len(v) for k, v in groups.items()})


if __name__ == "__main__":
    main()
