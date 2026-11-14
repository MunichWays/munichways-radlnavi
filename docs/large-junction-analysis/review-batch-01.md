# Nächste Prüfrunde: zehn Standorte

Stand: 07.11.2026. Arnulfstraße/Steubenplatz ist der [Praxisbenchmark](arnulf-benchmark.md).
Balanstraße/Chiemgaustraße ist bereits aktiv und zählt nicht zu diesen zehn neuen Standorten.

Dies ist eine Vorauswahl zur Sichtung, keine Liste freigegebener Kreuzungen. Acht Standorte
liegen im weiteren Umfeld von Arnulfstraße; zwei stammen aus den ursprünglichen Problemmeldungen.
Die geometrische Sichtprüfung ist inzwischen erfolgt; Referenzrouten und
Fahrbeziehungen sind noch zu prüfen. Der aktuelle Stand folgt direkt darunter.

Die [Bildergalerie](review-batch-01-images/index.html) und die
[Bild-Prüfliste](review-batch-01-images/README.md) sind nach Thomas' Sichtprüfung
aktualisiert: K01–K04 geometrisch bestätigt. Nach der ergänzenden Korrektur
liegen K05 und K06 als v2 zur Sichtprüfung vor: K05 mit einem gemeinsamen
Entry-4 am östlichen Verzweigungspunkt; K06 mit Straßen-Entry/Exit in der
Lachnerstraße vor der Ampel. Rufinistraße in K06 bleibt ohne Entry.
K07 wartet auf Einbeziehung der Radfahrstreifen und einen neuen OSM-Stand.
K08 und K10 enthalten korrigierte v2-Bilder zur erneuten Geometrieprüfung.
K09 ist als große T-Kreuzung dauerhaft ausgeschlossen und geschlossen.
Das bestätigt noch keine Fahrbeziehungen; alle neuen Standorte sind inaktiv.

| Nr. | Standort / Kartenansicht | Nächste Sichtprüfung |
| --- | --- | --- |
| 1 | [Ständlerstraße / Balanstraße](https://www.openstreetmap.org/?mlat=48.1046008&mlon=11.6051623#map=19/48.1046008/11.6051623) | Bereits gemeldete Geradeausroute als Referenz; Radwegquerungen und sämtliche vier Arme prüfen. |
| 2 | [Fürstenrieder Straße / Agnes-Bernauer-Straße](https://www.openstreetmap.org/?mlat=48.1397689&mlon=11.5031886#map=19/48.1397689/11.5031886) | Getrennte Fahrbahnen zu einem Komplex zusammenfassen; vier Radverkehrsarme prüfen. |
| 3 | [Fürstenrieder Straße / Gotthardstraße](https://www.openstreetmap.org/?mlat=48.1354156&mlon=11.5028688#map=19/48.1354156/11.5028688) | Vier Radverkehrsarme und Führung an den Straßenbahngleisen prüfen. |
| 4 | [Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke](https://www.openstreetmap.org/?mlat=48.1414144&mlon=11.51868#map=19/48.1414144/11.51868) | Alle vier Fahrbahnknoten zusammenfassen; Radweganschlüsse auf beiden Seiten der Brücke prüfen. |
| 5 | [Westendstraße / Zschokkestraße / Tübinger Straße](https://www.openstreetmap.org/?mlat=48.1344755&mlon=11.522715#map=19/48.1344755/11.522715) | Versetzte Anschlüsse prüfen: nur weiterverfolgen, wenn ein eindeutiger Kreuzungskomplex mit vier Radverkehrsarmen entsteht. |
| 6 | [Nymphenburger Straße / Waisenhausstraße / Lachnerstraße](https://www.openstreetmap.org/?mlat=48.1565188&mlon=11.5309626#map=19/48.1565188/11.5309626) | Vierten Arm über die Lachnerstraße und alle zulässigen Radweganschlüsse nachweisen. |
| 7 | [Marsstraße / Pappenheimstraße](https://www.openstreetmap.org/?mlat=48.1459514&mlon=11.5496026#map=19/48.1459514/11.5496026) | Unbenannte Verbindungen prüfen; ein vierfacher Straßenknoten allein bestätigt keine vier Radverkehrsarme. |
| 8 | [Arnulfstraße / Hackerbrücke / Wredestraße](https://www.openstreetmap.org/?mlat=48.1434822&mlon=11.5487832#map=19/48.1434822/11.5487832) | Brückenanschlüsse, Straßenbahn und Radverkehr in beiden Richtungen prüfen; bei unklarer Führung zurückstellen. |
| 9 | [Landsberger Straße / Barthstraße](https://www.openstreetmap.org/?mlat=48.1403416&mlon=11.5281809#map=19/48.1403416/11.5281809) | Zuerst klären, ob der vierte Straßenast ein eigenständiger Radverkehrsarm ist; bei T-Form verwerfen. |
| 10 | [Thomasiusplatz / Balanstraße / Werinherstraße](https://www.openstreetmap.org/?mlat=48.1157081&mlon=11.6021533#map=19/48.1157081/11.6021533) | Frühe Gabelung und Wohnstraßenarm Wilramstraße: komplexer Reservekandidat; keine Vierarmigkeit unterstellen. |

## Sichtung und Freigabe

1. Vier echte Radverkehrsarme nachweisen; T-Kreuzungen, Kreisverkehre und unklare Anschlüsse aussortieren. Ein Kandidat darf ersatzlos entfallen.
2. Für geeignete Standorte Polygonentwürfe mit allen Radwegquerungen und markierten Ein-/Ausgängen erstellen und sichten.
3. Bis zu vier Links- und vier Geradeausbeziehungen einzeln technisch prüfen; Rechtsabbiegen als Gegenprobe prüfen.
4. Nur bestätigte Beziehungen im Backend aktivieren und danach vor Ort mit dem Benchmark vergleichen. Die vorhandene App unterstützt weitere Katalogeinträge.

Die [GeoJSON-Datei](review-batch-01.geojson) enthält nur inaktive Standortpunkte.
Die [Overpass-Abfrage](review-batch-01.overpassql) lädt die Highway-Geometrie im Umkreis
von 180 Metern für die Detailprüfung in Overpass Turbo. Die Kreise sind Abfrageradien,
keine vorgeschlagenen Kreuzungsflächen. Bei abgeschnittenen Anschlüssen den Radius vergrößern.
Straßennamen der acht westlichen Standorte sind durch den gespeicherten
[OSM-Abruf](next-batch-road-names.json.gz) belegt; die beiden weiteren stammen aus
`osm-examples.json`. Keine Laufzeitdatei wird von diesem Vorbereitungsschritt geändert.
