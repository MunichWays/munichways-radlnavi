# BA09 · Bildprüfung Runde 2

[Galerie](index.html) · [Übersicht](overview.png)

BA09 Neuhausen-Nymphenburg · sieben geometrisch bestätigte Kreuzungen · 70 Beziehungen für Backend 2.4.6 freigegeben. Tatsächlicher Live-Stand siehe zentrale Prüfungsübersicht. Norden oben; Entry/Exit im Uhrzeigersinn. Gleiche Nummern bilden kein Fahrbeziehungspaar. Stern: gemeinsamer Zweirichtungspunkt.

Bitte Radwegseite, Pfeilrichtung und fehlende Arme prüfen. Alle Querungen, Inseln und Warteflächen müssen innerhalb liegen; benachbarte Kreuzungen außerhalb. Technisch unklare Bilder sind ausdrücklich zurückgestellt, keine vollständigen Vorschläge.

Rückmeldung beispielsweise: `K11 v1 passt` oder `K12 Entry-2 fehlt`.

| ID | Kreuzung | Punkte | Status |
| --- | --- | --- | --- |
| K11 v3 | [Wintrichring / Allacher Straße / Nederlinger Straße](../kreuzungspruefung/1-bestaetigt/K11-wintrich-allacher.png) | 9 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |
| K12 v2 | [Menzinger Straße / Wintrichring / Maria-Ward-Straße](../kreuzungspruefung/1-bestaetigt/K12-menzinger-wintrich.png) | 8 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |
| K13 v2 | [Arnulfstraße / Landshuter Allee](../kreuzungspruefung/1-bestaetigt/K13-arnulf-landshuter.png) | 12 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |
| K14 v2 | [Nymphenburger Straße / Landshuter Allee](../kreuzungspruefung/1-bestaetigt/K14-nymphenburger-landshuter.png) | 9 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |
| K15 v3 | [Leonrodstraße / Landshuter Allee](../kreuzungspruefung/1-bestaetigt/K15-leonrod-landshuter.png) | 8 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |
| K16 v1 | [Dachauer Straße / Leonrodstraße / Schwere-Reiter-Straße](../kreuzungspruefung/1-bestaetigt/K16-dachauer-leonrod.png) | 9 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |
| K17 v6 | [Dachauer Straße / Lothstraße](../kreuzungspruefung/1-bestaetigt/K17-dachauer-loth.png) | 8 | Geometrie bestätigt – Prüf-/Live-Stand siehe Übersicht |

Aktivierungs- und Live-Stand aller Kreuzungen siehe zentrale Prüfungsübersicht.
Nicht neu aufgenommen: Romanplatz (zwei nahe, komplexe Teilknoten), Menzinger/Schragenhofstraße und Schwere-Reiter/Ackermannstraße (Verdacht auf T-Struktur), Dachauer/Landshuter Allee (komplexer Tunnel-/Dreiecksanschluss). Dies sind Zurückstellungen, keine neuen dauerhaften Ausschlüsse.
K07 bleibt unabhängig davon bis zur gesonderten OSM-Prüfung zurückgestellt.

Bezirkszuordnung: OSM-Relation 54387 (admin_level=9, ref=9); Kandidatenknoten innerhalb dieser Grenze, einschließlich grenznaher Kreuzungen. Zusammengehörige Fahrbahnknoten werden als ein Standort behandelt.

Die Geometrien und 70 technisch bestandene Beziehungen sind für Backend 2.4.6 freigegeben; zwei K13-Beziehungen bleiben gesperrt. Fahrbeziehungen, Einbahnregeln und API-Referenzrouten werden vor jeder Aktivierung separat geprüft. Fahrbahn-Radfahrstreifen sind bei fehlenden Punkten technisch nachzuarbeiten; es wird kein Radverkehrsarm aus acht Punkten allein abgeleitet.

OSM-Nachweise: ../ba09-candidates-osm.json.gz und ../review-batch-02-ba09-osm.json.gz. © OpenStreetMap-Mitwirkende, ODbL.

Offline neu erzeugen: `python docs/large-junction-analysis/prepare_ba09_review.py`.
