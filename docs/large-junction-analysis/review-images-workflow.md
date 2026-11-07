# Wiederholbare Bildprüfung

Die [erste Bilderrunde](review-batch-01-images/index.html) enthält zehn
Standorte aus der Vorauswahl. K01–K04 sind nach Thomas' Sichtprüfung geometrisch
bestätigt; K05, K06, K08 und K10 liegen als korrigierte v2 vor. K07 bleibt zurückgestellt,
K09 ist dauerhaft ausgeschlossen und geschlossen. Alle neuen Standorte bleiben
inaktiv. Die Bildfreigabe ist eine
Geometriefreigabe; zulässige Routen und einzelne Fahrbeziehungen werden danach
getrennt geprüft.

## Prüfung durch Thomas

Pro vorbereitetem Bild nur drei Fragen:

1. Liegen Entry und Exit auf der richtigen Radwegseite und stimmen die Pfeile?
2. Liegen alle Querungen, Verkehrsinseln und üblichen Wartepositionen innerhalb der Fläche?
3. Fehlt ein Anschluss oder umfasst die Fläche bereits eine benachbarte Kreuzung?

Antwort beispielsweise `K01 v1 passt; K02 Entry-3 weiter nach außen`.
Nur bei ungeklärten Streckenführungen folgt ein zusätzliches Streckenbild mit
einer konkreten Frage. Acht überlagerte Referenzrouten sind für diese
Geometrieprüfung nicht erforderlich.

Norden steht oben. Vom ersten Exit im Uhrzeigersinn ab Norden ausgehend
werden Entry und Exit jeweils fortlaufend nummeriert. Beim üblichen Aufbau
ergibt das Exit-1, Entry-1, Exit-2, Entry-2 usw. Gleiche Nummern gehören nicht
zwangsläufig zum gleichen Straßenarm und sind kein Fahrbeziehungspaar.
Zweirichtungspunkte sind mit einem Stern gekennzeichnet und werden zunächst
technisch geklärt. Die Punktnamen werden bei erneutem Rendern anhand von
OSM-Weg und Richtung erhalten. Ändert sich diese Struktur, bricht der Generator
ab; die neue Zuordnung muss ausdrücklich in einer neuen Revision erfolgen.
Für K05, K06, K08 und K10 ist diese Änderung samt Zuordnung der v1- zu den v2-Punkten in
`review-batch-01-decisions.json` dokumentiert. Die ursprüngliche v1-Geometrie
liegt separat in `review-batch-01-v1-geometry.json`.

## Vorbereitung und technische Verantwortung

Die Overpass-Daten werden einmal pro Runde gesammelt und eingefroren.
`build_review_images.py` erzeugt offline alle SVGs, Zeichnungsdaten, die Galerie
und eine gemeinsame Prüfdatendatei. `render_review_images.ps1` erzeugt daraus
PNG-Einzelbilder und ein Übersichtsbild mit Windows System.Drawing.
Es werden keine zusätzlichen Python-Pakete oder Kartenkacheln benötigt.

Der automatische Polygonentwurf ist eine konvexe Hülle um nahe Radweg-
Verzweigungs- und Straßenquerungsknoten, erweitert um acht Meter. Er ist
eine Arbeitshilfe und keine vermessene Grenze. Entwürfe mit weniger oder
mehr als acht getrennten Punkten, gemeinsamen Zweirichtungspunkten oder
abweichender Entry-/Exit-Reihenfolge werden zurückgestellt. Acht Punkte allein
weisen weder vier logische Arme noch die Verbindung zwischen den Punkten nach.
Eine ausdrückliche Sichtfreigabe darf eine abweichende Punktstruktur bestätigen.
Die erste Sichtfreigabe von K05/K06 wurde durch die ergänzende Nutzerkorrektur
ersetzt; die revidierten v2 sind noch nicht freigegeben.
Freigaben sind an einen Fingerabdruck der geprüften Geometrie
gebunden; ein neuer OSM-Stand kann sie nicht stillschweigend übernehmen.

Die Straßenführung wird vorerst für die ausdrücklich benannten Arme der
Hackerbrücke und Lachnerstraße ergänzt. An der Hackerbrücke liegen Entry-2 und Exit-3 am gleichen Fahrbahnpunkt
an Ampelnode 4696310002. Für K07 sind vor einer erneuten Prüfung zusätzlich
`cycleway=lane` sowie `cycleway:left/right/both=lane` zu berücksichtigen. Die vom
Nutzer gemeldete OSM-Korrektur ist im eingefrorenen Datensatz noch nicht belegt.
Wilramstraße in K10 und Rufinistraße in K06 bleiben ausdrücklich ohne eigene
Guidance-Beziehungen. Das ändert keine OSM-Zugangs- oder Einbahnregel.

K05 v2 umfasst den gemeinsamen Verzweigungsknoten 364847915. Die beiden alten
Entries werden durch Entry-4 auf dem gemeinsamen ankommenden Weg 160643860
ersetzt; die Verzweigung und beide folgenden Radwegäste liegen innerhalb.
Dabei wird die östliche Fläche erweitert und Exit-1 geringfügig verschoben.
K06 v2 nutzt Fahrbahnweg 152093782 für Entry-2 und Exit-3; ihr gemeinsamer
Grenzpunkt liegt rund fünf Meter vor Ampelnode 11209620540. Die Ampel ist über
die offizielle OSM-API in `lachner-signal-evidence.json` belegt. Das Polygon
bleibt unverändert; die nachfolgenden Nummern werden im Uhrzeigersinn angepasst.

Vor Aktivierung weiterhin durch uns zu prüfen: vier logische Radverkehrsarme,
Einbahnregeln und Radverkehrszulässigkeit, durchgängige Referenzrouten,
Links-/Geradeausklassifikation und Rechtsabbiege-Gegenproben, exakte Zuordnung
der API-Geometrie und bestehende Katalogprüfungen. Unklarheiten bleiben inaktiv.

Die eingefrorenen OSM-Daten und alle Entwürfe liegen ausschließlich unter
`docs/large-junction-analysis`; der produktive Katalog wird nicht geschrieben.

```powershell
# Nur für einen ausdrücklich gewünschten neuen OSM-Abruf:
python docs/large-junction-analysis/collect_review_batch.py

# Offline erneut rendern:
python docs/large-junction-analysis/build_review_images.py
powershell -NoProfile -ExecutionPolicy Bypass -File docs/large-junction-analysis/render_review_images.ps1
```
