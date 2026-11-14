"""Prepare ten inactive review locations; never writes the runtime catalog."""

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    snapshot = json.loads(gzip.decompress((ROOT / "next-batch-road-names.json.gz").read_bytes()))
    nodes = {n["id"]: n for n in snapshot["response"]["elements"] if n["type"] == "node"}
    # Names and coordinates from incident OSM ways; these are locations, not verified polygons.
    entries = [
        (440793, "fuerstenrieder-agnes-bernauer", "Fürstenrieder Straße / Agnes-Bernauer-Straße", "Getrennte Fahrbahnen zu einem Komplex zusammenfassen; vier Radverkehrsarme prüfen."),
        (21135729, "fuerstenrieder-gotthard", "Fürstenrieder Straße / Gotthardstraße", "Vier Radverkehrsarme und Führung an den Straßenbahngleisen prüfen."),
        (21411423, "landsberger-elsenheimer", "Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke", "Alle vier Fahrbahnknoten zusammenfassen; Radweganschlüsse auf beiden Seiten der Brücke prüfen."),
        (21134870, "westend-zschokke", "Westendstraße / Zschokkestraße / Tübinger Straße", "Versetzte Anschlüsse prüfen: nur weiterverfolgen, wenn ein eindeutiger Kreuzungskomplex mit vier Radverkehrsarmen entsteht."),
        (27590215, "nymphenburger-waisenhaus", "Nymphenburger Straße / Waisenhausstraße / Lachnerstraße", "Vierten Arm über die Lachnerstraße und alle zulässigen Radweganschlüsse nachweisen."),
        (363189, "mars-pappenheim", "Marsstraße / Pappenheimstraße", "Unbenannte Verbindungen prüfen; ein vierfacher Straßenknoten allein bestätigt keine vier Radverkehrsarme."),
        (1956100, "arnulf-hackerbruecke", "Arnulfstraße / Hackerbrücke / Wredestraße", "Brückenanschlüsse, Straßenbahn und Radverkehr in beiden Richtungen prüfen; bei unklarer Führung zurückstellen."),
        (21164573, "landsberger-barth", "Landsberger Straße / Barthstraße", "Zuerst klären, ob der vierte Straßenast ein eigenständiger Radverkehrsarm ist; bei T-Form verwerfen."),
    ]
    features = []
    for node_id, identifier, name, check in entries:
        n = nodes[node_id]
        features.append(feature(identifier, name, [n["lon"], n["lat"]], check, node_id))

    examples = json.loads((ROOT / "osm-examples.json").read_text(encoding="utf-8"))["elements"]
    for identifier, name, road, check in [
        ("staendler-balan", "Ständlerstraße / Balanstraße", "Ständlerstraße", "Bereits gemeldete Geradeausroute als Referenz; Radwegquerungen und sämtliche vier Arme prüfen."),
        ("thomasiusplatz", "Thomasiusplatz / Balanstraße / Werinherstraße", "Werinherstraße", "Frühe Gabelung und Wohnstraßenarm Wilramstraße: komplexer Reservekandidat; keine Vierarmigkeit unterstellen."),
    ]:
        a = [w for w in examples if w["type"] == "way" and w.get("tags", {}).get("name") == road]
        b = [w for w in examples if w["type"] == "way" and w.get("tags", {}).get("name") == "Balanstraße"]
        shared = {}
        for u in a:
            for v in b:
                for node_id in set(u.get("nodes", [])) & set(v.get("nodes", [])):
                    g = u["geometry"][u["nodes"].index(node_id)]
                    shared[node_id] = [g["lon"], g["lat"]]
        if not shared:
            raise ValueError(f"No common OSM node: {name}")
        node_id = min(shared)
        features.append(feature(identifier, name, shared[node_id], check, node_id))

    # Put the already reported, relatively nearby-to-Balan case first; reserve case last.
    features.insert(0, features.pop(8))
    for i, f in enumerate(features, 1):
        f["properties"]["reviewOrder"] = i
    decisions_path=ROOT / "review-batch-01-decisions.json"
    if decisions_path.exists():
        decisions=json.loads(decisions_path.read_text(encoding="utf-8"))["sites"]
        for f in features:
            review=decisions.get(f["properties"]["id"])
            if review:
                f["properties"].update(status=review["status"],geometryReviewRevision=review["revision"],
                    polygonApproved=review["status"]=="geometry-approved",nextCheck=review["note"])
    result = {"type": "FeatureCollection", "scope": "Ten inactive review locations; no polygons or movement approvals", "attribution": "OpenStreetMap contributors, ODbL", "features": features}
    assert len(features) == 10 and len({f["properties"]["id"] for f in features}) == 10
    (ROOT / "review-batch-01.geojson").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    query = '[out:json][timeout:120];\n(\n' + ''.join(f'  way[highway](around:180,{f["geometry"]["coordinates"][1]},{f["geometry"]["coordinates"][0]});\n' for f in features) + ');\nout body geom;\n'
    (ROOT / "review-batch-01.overpassql").write_text(query, encoding="utf-8")
    lines = ["# Nächste Prüfrunde: zehn Standorte", "", "Stand: 07.11.2026. Arnulfstraße/Steubenplatz ist der [Praxisbenchmark](arnulf-benchmark.md).", "Balanstraße/Chiemgaustraße ist bereits aktiv und zählt nicht zu diesen zehn neuen Standorten.", "", "Dies ist eine Vorauswahl zur Sichtung, keine Liste freigegebener Kreuzungen. Acht Standorte", "liegen im weiteren Umfeld von Arnulfstraße; zwei stammen aus den ursprünglichen Problemmeldungen.", "Noch fehlen geprüfte Polygone, Ein-/Ausgänge und Referenzrouten. Insbesondere die letzten", "beiden Prüfungen zu Barthstraße und Thomasiusplatz können zum Ausschluss führen.", "", "| Nr. | Standort / Kartenansicht | Nächste Sichtprüfung |", "| --- | --- | --- |"]
    for f in features:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        lines.append(f'| {p["reviewOrder"]} | [{p["name"]}](https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}) | {p["nextCheck"]} |')
    lines += ["", "## Sichtung und Freigabe", "", "1. Vier echte Radverkehrsarme nachweisen; T-Kreuzungen, Kreisverkehre und unklare Anschlüsse aussortieren. Ein Kandidat darf ersatzlos entfallen.", "2. Für geeignete Standorte Polygonentwürfe mit allen Radwegquerungen und markierten Ein-/Ausgängen erstellen und sichten.", "3. Bis zu vier Links- und vier Geradeausbeziehungen einzeln technisch prüfen; Rechtsabbiegen als Gegenprobe prüfen.", "4. Nur bestätigte Beziehungen im Backend aktivieren und danach vor Ort mit dem Benchmark vergleichen. Die vorhandene App unterstützt weitere Katalogeinträge.", "", "Die [GeoJSON-Datei](review-batch-01.geojson) enthält nur inaktive Standortpunkte.", "Die [Overpass-Abfrage](review-batch-01.overpassql) lädt die Highway-Geometrie im Umkreis", "von 180 Metern für die Detailprüfung in Overpass Turbo. Die Kreise sind Abfrageradien,", "keine vorgeschlagenen Kreuzungsflächen. Bei abgeschnittenen Anschlüssen den Radius vergrößern.", "Straßennamen der acht westlichen Standorte sind durch den gespeicherten", "[OSM-Abruf](next-batch-road-names.json.gz) belegt; die beiden weiteren stammen aus", "`osm-examples.json`. Keine Laufzeitdatei wird von diesem Vorbereitungsschritt geändert.", ""]
    (ROOT / "review-batch-01.md").write_text("\n".join(lines), encoding="utf-8")
    print("Prepared 10 inactive review locations and a detail query; no runtime changes.")


def feature(identifier, name, coordinates, check, node_id):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates}, "properties": {"id": identifier, "name": name, "osmNodeId": node_id, "status": "needs-arm-and-cycleway-review", "enabled": False, "polygonApproved": False, "nextCheck": check}}


if __name__ == "__main__":
    main()
