# K05: Zschokkestraße wieder mit Standardhinweisen

Stand 08.11.2026: K05 v3 von Thomas freigegeben; Backend 2.4.5 mit Katalog `munich-big-junctions-v4` für das angeforderte Deployment vorbereitet.

Der Praxistest widerlegt die Linksansage für Entry-1 → bisherigen Exit-4. Die spätere Kurve der Zschokkestraße darf die Abbiegerichtung an der großen Kreuzung nicht bestimmen. Thomas bevorzugt ausdrücklich Standardhinweise für diesen Ausgang (Option 4).

## Backendkorrektur

- `east-west-left` und `south-west-left` sind zurückgezogen: beide enden am bisherigen Exit-4.
- Diese Routen erhalten keine K05-Kreuzungsmetadaten; die Standardhinweise und Route bleiben unverändert.
- Die sechs übrigen K05-Fahrbeziehungen bleiben erhalten. Der vorbereitete Katalog enthält insgesamt 74 aktive Fahrbeziehungen.
- Die freigegebene v3-Fläche ersetzt die bisherige v2-Fläche; die sechs verbleibenden Beziehungen sind mit unveränderten echten Routen gegen die neue Fläche validiert. K11–K17 werden durch diese Korrektur nicht aktiviert.
- `review-movement-exclusions.json` hat Vorrang vor der geometrischen Winkelklassifikation; die Offline-Neuerzeugung darf die beiden Beziehungen nicht wieder aktivieren.

## Freigegebene neue Fläche

[K05 v3](kreuzungspruefung/1-bestaetigt/K05-westend-zschokke.png) entfernt Exit-4 aus der Kreuzungsführung und verschiebt Entry-4 nach Südwesten auf Radweg 172218550. Die äußere Verzweigung und der weitere Zschokkestraßenbogen liegen außerhalb. Alle anderen Punktpositionen und Namen bleiben erhalten.

Thomas hat diese Ersatzfläche ausdrücklich bestätigt und Commit, Push und Backend-Build/Deployment beauftragt. Die ursprüngliche v2-Geometrie bleibt als archivierter Referenzfall erhalten. Vor dem erfolgreichen Deployment bleibt die bisherige Produktionsversion aktiv.

## Prüfung

Die gespeicherten realen Routen `westend-zschokke-east-west-straight.json` und `westend-zschokke-south-west-left.json` prüfen den Rückfall auf Standardhinweise. Alle weiteren positiven Katalogfälle und Rechtsabbiege-Gegenproben bleiben Teil der Backendtests.
