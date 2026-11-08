"""Frozen BA09 selection and offline review sheets; never writes runtime data."""

from datetime import datetime, timezone
import argparse
import gzip
import html
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from math import cos, radians
from build_review_images import prepare_site, draw, svg, status_text, extract_gates, number_gates, apply_review

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "review-batch-02-ba09-images"
SELECTION = [
    (11, 2467495003, "wintrich-allacher", "Wintrichring / Allacher Straße / Nederlinger Straße"),
    (12, 564080, "menzinger-wintrich", "Menzinger Straße / Wintrichring / Maria-Ward-Straße"),
    (13, 245339, "arnulf-landshuter", "Arnulfstraße / Landshuter Allee"),
    (14, 29004859, "nymphenburger-landshuter", "Nymphenburger Straße / Landshuter Allee"),
    (15, 401307391, "leonrod-landshuter", "Leonrodstraße / Landshuter Allee"),
    (16, 363211, "dachauer-leonrod", "Dachauer Straße / Leonrodstraße / Schwere-Reiter-Straße"),
    (17, 20980542, "dachauer-loth", "Dachauer Straße / Lothstraße"),
]
NOTES = {
    11: "Vier Hauptarme; zusätzliche Zweirichtungsanschlüsse im Westen. Bitte prüfen, welche westlichen Nebenanschlüsse zur Kreuzung gehören; keine OSM-Richtung stillschweigend entfernen.",
    12: "Menzinger Straße wird zweimal geschnitten: Bitte Flächengrenze und westlichen Anschluss Maria-Ward-Straße prüfen. Acht Punkte allein bestätigen noch keine vier Arme.",
    13: "Mehrere Zweirichtungsäste: Bitte Abgrenzung zur Schlörstraße und Donnersbergerstraße sowie lokale Abzweige prüfen. Breiter Komplex, vor Aktivierung separat technisch klären.",
    14: "Vier Entries und fünf Exits sind zulässig. Für die südöstlichen Ausgänge ist keine gemeinsame äußere Zusammenführung im gerichteten Graph belegt. Bitte ihre Lage prüfen; Tunnel-Fahrbahnen bleiben ohne Radverkehrsarm.",
    15: "Versetzte Anschlüsse Leonrod-/Frundsbergstraße: Bitte prüfen, ob ein gemeinsamer Komplex sinnvoll ist. Explizite Leonrod-Radfahrstreifen sind als Fahrbahn-Mittellinien dargestellt.",
    16: "Wie K11: vier Entries und fünf Exits sind durch Zweirichtungsführung zulässig. Entry-4 / Exit-1 bleiben am gemeinsamen nordöstlichen Punkt. Bitte Lage dieses Punkts und Polygonumfang bestätigen oder korrigieren.",
    17: "Lothstraße: Nordost-Radfahrstreifen als gemeinsame Fahrbahn-Mittellinienpunkte; keine exakten Streifenpositionen. Südwestlicher Loth-Arm noch ohne gesicherte Punkte: Straßenführung klären. Radfreigegebener Fußweg im Norden sichtbar.",
}


def prepare(feature, ways):
    site = prepare_site(feature, ways)
    site["note"] = NOTES[site["number"]]
    # Only explicitly mapped lanes on the named junction arms; never infer lanes
    # from an ordinary road or change runtime direction/access handling.
    lane_name = {15: "Leonrodstraße", 17: "Lothstraße"}.get(site["number"])
    road_ids = [w["id"] for w in site["ways"] if lane_name
        and w.get("tags", {}).get("name") == lane_name
        and w["tags"].get("bicycle") not in {"no", "private", "use_sidepath"}
        and any(w["tags"].get(key) == "lane" for key in
            ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both"))]
    if road_ids:
        lon, lat = site["origin"]
        mx = 111320 * cos(radians(lat))
        project = lambda p: ((p[0] - lon) * mx, (p[1] - lat) * 111320)
        site["onRoadWayIds"] = road_ids
        site["gates"] = extract_gates(site["ways"], site["polygon"], project, road_ids)
        number_gates(site["gates"], (0, 0), project)
        for gate in site["gates"]:
            if gate["osmWayId"] in road_ids:
                gate["positionBasis"] = "OSM carriageway centerline with explicit cycleway=lane; lateral lane position unverified"
    return site


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def features():
    snapshot = load(ROOT / "ba09-candidates-osm.json.gz")
    nodes = {n["id"]: n for n in snapshot["response"]["elements"] if n["type"] == "node"}
    return [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [nodes[node]["lon"], nodes[node]["lat"]]},
        "properties": {"id": identifier, "name": name, "reviewOrder": number,
            "osmNodeId": node, "district": "BA09", "enabled": False,
            "nextCheck": "Radwegseiten, Pfeilrichtungen und Vollständigkeit prüfen; alle Querungen und Warteflächen innerhalb, keine Nachbarkreuzung. Unklare Arme bleiben zurückgestellt."}}
        for number, node, identifier, name in SELECTION]


def collect(batch):
    query = '[out:json][timeout:120];\n(\n' + ''.join(
        f'way[highway](around:190,{f["geometry"]["coordinates"][1]},{f["geometry"]["coordinates"][0]});\n'
        for f in batch) + ');\nout body geom;\n'
    (ROOT / "review-batch-02-ba09.overpassql").write_text(query, encoding="utf-8")
    request = Request("https://overpass-api.de/api/interpreter", data=urlencode({"data": query}).encode(),
        headers={"User-Agent": "MunichWays-Junction-Catalog/1.0"})
    with urlopen(request, timeout=150) as response:
        data = json.load(response)
    if data.get("remark") or not data.get("elements"):
        raise ValueError("Incomplete Overpass response")
    snapshot = {"query": query, "retrievedAt": datetime.now(timezone.utc).isoformat(), "response": data}
    (ROOT / "review-batch-02-ba09-osm.json.gz").write_bytes(gzip.compress(
        json.dumps(snapshot, ensure_ascii=False).encode(), mtime=0))
    print("Saved", len(data["elements"]), "highway ways")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    batch = features()
    if args.collect:
        collect(batch)
    snapshot = load(ROOT / "review-batch-02-ba09-osm.json.gz")
    ways = [w for w in snapshot["response"]["elements"] if w["type"] == "way"]
    sites = [prepare(f, ways) for f in batch]
    decisions_path = ROOT / "review-batch-02-ba09-decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))["sites"] if decisions_path.exists() else {}
    for site in sites:
        if site["id"] in decisions:
            apply_review(site, decisions[site["id"]])
    OUT.mkdir(exist_ok=True)
    previous = OUT / "review-data.json"
    if previous.exists():
        old = {s["id"]: s for s in json.loads(previous.read_text(encoding="utf-8"))["sites"]}
        for site in sites:
            if (site["id"] in old and site["version"] <= old[site["id"]]["version"]
                and any(site[key] != old[site["id"]][key] for key in ("polygon", "gates"))):
                raise ValueError(f'Geometry changed for {site["id"]}; create an explicit review revision first.')
    cards, rows = [], []
    technical_path = ROOT / 'review-batch-02-ba09-routes.json'
    technical = {s['id']: s for s in json.loads(technical_path.read_text(encoding='utf-8'))['junctions']} if technical_path.exists() else {}
    for site in sites:
        name = f'K{site["number"]:02d}-{site["id"]}'
        commands = draw(site)
        if site["status"] == "geometry-approved":
            for command in commands:
                if command.get("kind") == "text":
                    command["text"] = command["text"].replace("Freigabestand siehe Prüfbericht", "Prüf-/Live-Stand siehe Übersicht")
                    if site.get('review', {}).get('activationReview', {}).get('status') == 'approved':
                        command['text'] = command['text'].replace('NICHT AKTIV', 'Für Backend 2.4.6 freigegeben')
        record = technical.get(site['id'], {})
        blocked = [m for m in record.get('movements', []) if m['kind'] != 'right' and not m.get('enabled')]
        if blocked and record.get('geometryRevision') == site['version']:
            labels = ' / '.join(f'{m["entryLabel"]} → {m["exitLabel"]}' for m in blocked)
            commands.append({'kind': 'text', 'text': f'GESPERRT: {labels} (links) – Standardhinweise bleiben',
                             'x': 28, 'y': 81, 'size': 17, 'color': '#b71c1c'})
        (OUT / f"{name}.svg").write_text(svg(commands), encoding="utf-8")
        (OUT / f"{name}.drawing.json").write_text(json.dumps(commands, ensure_ascii=False), encoding="utf-8")
        status = status_text(site).replace("Freigabestand siehe Prüfbericht", "Prüf-/Live-Stand siehe Übersicht")
        cards.append(f'<article><h2>K{site["number"]:02d} · {html.escape(site["name"])}</h2><p>{status}</p><a href="{name}.png"><img src="{name}.svg" alt="{html.escape(site["name"])}"></a><p><a href="{name}.png">PNG öffnen</a> · <a href="{name}.svg">SVG öffnen</a></p></article>')
        rows.append(f'| K{site["number"]:02d} v{site["version"]} | [{site["name"]}]({name}.png) | {len(site["gates"])} | {status} |')
        print(name, status, len(site["gates"]), "gates")
    intro = "BA09 Neuhausen-Nymphenburg · sieben geometrisch bestätigte Kreuzungen · 70 Beziehungen für Backend 2.4.6 freigegeben. Tatsächlicher Live-Stand siehe zentrale Prüfungsübersicht. Norden oben; Entry/Exit im Uhrzeigersinn. Gleiche Nummern bilden kein Fahrbeziehungspaar. Stern: gemeinsamer Zweirichtungspunkt."
    checks = "Bitte Radwegseite, Pfeilrichtung und fehlende Arme prüfen. Alle Querungen, Inseln und Warteflächen müssen innerhalb liegen; benachbarte Kreuzungen außerhalb. Technisch unklare Bilder sind ausdrücklich zurückgestellt, keine vollständigen Vorschläge."
    (OUT / "index.html").write_text('<!doctype html><html lang="de"><meta charset="utf-8"><title>BA09 · Bildprüfung Runde 2</title><style>body{font:17px Arial;margin:24px;background:#f3f4f5;color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px}img{width:100%}p{line-height:1.5}</style><h1>BA09 · Bildprüfung Runde 2</h1><p>'+intro+'</p><p>'+checks+'</p><main>'+''.join(cards)+'</main></html>', encoding="utf-8")
    (OUT / "README.md").write_text("\n".join(["# BA09 · Bildprüfung Runde 2", "", "[Galerie](index.html) · [Übersicht](overview.png)", "", intro, "", checks, "", "Rückmeldung beispielsweise: `K11 v1 passt` oder `K12 Entry-2 fehlt`.", "", "| ID | Kreuzung | Punkte | Status |", "| --- | --- | --- | --- |", *rows, "", "Aktivierungs- und Live-Stand aller Kreuzungen siehe zentrale Prüfungsübersicht.", "Nicht neu aufgenommen: Romanplatz (zwei nahe, komplexe Teilknoten), Menzinger/Schragenhofstraße und Schwere-Reiter/Ackermannstraße (Verdacht auf T-Struktur), Dachauer/Landshuter Allee (komplexer Tunnel-/Dreiecksanschluss). Dies sind Zurückstellungen, keine neuen dauerhaften Ausschlüsse.", "K07 bleibt unabhängig davon bis zur gesonderten OSM-Prüfung zurückgestellt.", "", "Bezirkszuordnung: OSM-Relation 54387 (admin_level=9, ref=9); Kandidatenknoten innerhalb dieser Grenze, einschließlich grenznaher Kreuzungen. Zusammengehörige Fahrbahnknoten werden als ein Standort behandelt.", "", "Die Geometrien und 70 technisch bestandene Beziehungen sind für Backend 2.4.6 freigegeben; zwei K13-Beziehungen bleiben gesperrt. Fahrbeziehungen, Einbahnregeln und API-Referenzrouten werden vor jeder Aktivierung separat geprüft. Fahrbahn-Radfahrstreifen sind bei fehlenden Punkten technisch nachzuarbeiten; es wird kein Radverkehrsarm aus acht Punkten allein abgeleitet.", "", "OSM-Nachweise: ../ba09-candidates-osm.json.gz und ../review-batch-02-ba09-osm.json.gz. © OpenStreetMap-Mitwirkende, ODbL.", "", "Offline neu erzeugen: `python docs/large-junction-analysis/prepare_ba09_review.py`.", ""]), encoding="utf-8")
    evidence = {"version": 1, "district": "BA09", "enabled": False, "osmRetrievedAt": snapshot["retrievedAt"], "sites": sites}
    (OUT / "review-data.json").write_text(json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))+'\n', encoding="utf-8")
    (ROOT / "review-batch-02-ba09.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": batch}, ensure_ascii=False, indent=2)+'\n', encoding="utf-8")
    from organize_review_images import main as organize_images
    organize_images()
    if (ROOT / "review-reference-cases.json").exists():
        from review_preflight import main as preflight
        preflight()


if __name__ == "__main__":
    main()
