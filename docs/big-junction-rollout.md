# Große Kreuzungen: Zielbild und Ausbau

## Aufteilung zwischen Backend und App

RadlNavi behält Route, Geometrie und bisherige Einzelhinweise bei. Es ordnet
einer passenden Route zusätzlich geprüfte Kreuzungsdurchfahrten zu: Polygon,
Fahrbeziehung sowie Einfahrts- und Ausfahrtsanker auf der konkreten Route.
Die App bildet daraus den zusammengefassten Hinweis, berechnet die Entfernung
bis zur Einfahrt und steuert Ansagen sowie Abweichungsprüfung während der Fahrt.

Die Ansagen bei ungefähr 100 und 60 Metern, das Weglassen von „Hier“ und die
Ruhe innerhalb der Fläche sind damit App-Verhalten. Nach bestätigter falscher
Ausfahrt greift wieder die Abweichungs- und Neuberechnungslogik der App.
RadlNavis eigene Oberfläche zeigt zunächst weiterhin die Einzelhinweise.

## Geplanter Katalog für München

Die geeigneten großen Kreuzungen werden zentral als versionierte Daten im
Backend hinterlegt. Overpass und OSM dienen zur Kandidatensuche; ein Treffer
allein aktiviert keine Kreuzung. Die Ersterfassung erfolgt halbautomatisch
mit manueller Prüfung. Der Katalog wird schrittweise erweitert und bei
Änderungen am Straßennetz überprüft.

Pro Kreuzung sollen gespeichert werden:

- Stabile Kennung und geprüftes Polygon einschließlich der Radwegquerungen.
- Ein- und Ausgänge der tatsächlich vorhandenen Radverkehrsverbindungen.
- Einzeln freigegebene Fahrbeziehungen für links und geradeaus, mit zulässigen
  Routenverläufen und Anschlussrichtungen. Bei vier geeigneten Armen sind
  höchstens acht solche Beziehungen zu prüfen; keine wird automatisch geerbt.
- Prüfdatum, OSM-Bezüge, Referenzrouten und dokumentierte Ausschlüsse.

Unklare Kreuzungen oder Fahrbeziehungen bleiben ohne Zusatzmetadaten. Dazu
gehören zunächst die vier bereits ausgeschlossenen schwierigen Fälle.
Rechtsabbiegen bleibt außerhalb des vereinbarten Umfangs.

Der allgemeine Katalog und die App-Anbindung sind umgesetzt. Die App
akzeptiert neue Katalogrevisionen und Kennungen mit dem gleichen API-Vertrag;
Links- und Geradeausbeziehungen haben eigene Texte und Richtungssymbole.
Weitere geprüfte Kreuzungen erfordern Katalogdaten und Backend-Deployment.

Die stadtweite Suche hat 495 Kandidatenpunkte erfasst. Die getrennte
[Prüfliste](large-junction-analysis/munich-review-queue.geojson) aktiviert
nichts. Vor einer Freigabe werden zusammengehörige Punkte gruppiert,
vier tatsächliche Radverkehrsrichtungen nachgewiesen, das Polygon geprüft und
jede erlaubte Fahrbeziehung mit Referenzroute dokumentiert. Nicht bestätigte
Beziehungen bleiben deaktiviert, auch wenn eine andere Beziehung am gleichen
Ort bereits erfolgreich getestet wurde.

## Freigabe und weitere Erfassung

Live freigegeben ist ausschließlich Arnulfstraße West → Steubenplatz Nord,
links, für den geprüften geplanten Routenverlauf. Eine abweichende Fahrt
innerhalb dieser zugeordneten Fläche wird von der Pilot-App toleriert.

Der Nutzer hat den Praxistest am 06.11.2026 erfolgreich abgeschlossen. Die
Arnulf-Linksbeziehung wird deshalb in der App standardmäßig aktiviert.
Die passende Testplanung führt weiterhin von 48.150550, 11.517800 nach
48.150871, 11.520477 (rund 168 Meter bis zur Einfahrt).

Die weitere stadtweite Polygonprüfung ist noch offen. Aus den 495 Punkten
wurden bewusst keine pauschalen aktiven Flächen oder Fahrbeziehungen erzeugt.

API-Vertrag und aktuelle Grenzen: [Katalog und API](big-junction-pilot-api.md).
