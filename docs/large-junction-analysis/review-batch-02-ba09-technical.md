# BA09: technische Fahrbeziehungsprüfung

Geprüft gegen echte Standardrouten und die freigegebenen Geometrien. Der Aktivierungsstand steht im Backendkatalog und in der Prüfungsübersicht. Die Prüfung selbst startet weder Build noch Deployment.

| Kreuzung | Revision | Links/geradeaus bestanden | Rechtskontrollen ohne Makro |
| --- | --- | --- | --- |
| K11 | v3 | 10/10 | 5 |
| K12 | v2 | 8/8 | 4 |
| K13 | v2 | 16/18 | 9 |
| K14 | v2 | 10/10 | 5 |
| K15 | v3 | 8/8 | 4 |
| K16 | v1 | 10/10 | 5 |
| K17 | v6 | 8/8 | 4 |

## Weiterhin gesperrt

Diese Beziehungen behalten Standardhinweise. Gerichtete Legalitätsprüfung, Korridortoleranzen und lokale Richtungsprüfung bleiben unverändert.

- K13 Entry-2 → Exit-5 (left): ValueError: Route does not cross polygon exactly once
- K13 Entry-3 → Exit-5 (left): ValueError: Route does not cross polygon exactly once

## Prüfumfang

- Die Ansagerichtung folgt der explizit geprüften Reihenfolge der vier Straßenarme und deren zugeordneten Entry-/Exitpunkten. Die lokale Fahrtrichtung bleibt über reale Referenzpfade geprüft. Ohne dokumentierte Armzuordnung gelten weiterhin die bisherigen Winkelgrenzen.
- Ein minimal versetzter Zielmarker ist nur beim letzten, geometrisch punktförmigen Arrive-Schritt mit Distanz/Dauer null bis 0,75 m zulässig. Innere Manöver und Geometrieanschlüsse bleiben exakt.
- Eindeutige Flächenquerung, richtige Entry-/Exitpunkte und gerichteter OSM-Korridor.
- Reale Testpunkte außerhalb der Fläche: regulär 45 m; bei kurzen Anschlüssen bis mindestens 12 m, mit Reserve zur 10-m-Laufzeitprüfung. Entfernungen stehen im JSON-Prüfbericht.
- K17: OSM-Weg 38349617 als innere Fortsetzung der freigegebenen Lothstraßen-Fahrbahn. Nur vollständig innerhalb liegende Segmente; keine neuen Gates. Zugangsbeschränkungen bleiben wirksam.
- Gesamter vorgeschlagener Katalog: positive Routen, gesperrte Beziehungen, Rechtskontrollen und Schiebeabschnitte als Regression geprüft; ursprüngliche Routendaten bleiben unverändert.

[Detaillierte Belege](review-batch-02-ba09-routes.json) · [Prüfungsübersicht mit Live-Stand](kreuzungspruefung/index.html)
