# Balan/Chiemgau und Arnulf/Steuben: vollständige Links-/Geradeausfreigabe

Stand: 07.11.2026. Der Nutzer hat das Balan-Polygon einschließlich aller
Ein-/Ausgänge anhand der Diagnosegrafik bestätigt und den Ausbau beider
Kreuzungen beauftragt. Das Arnulf-Polygon und West → Nord wurden zuvor
praktisch getestet. Die übrigen Beziehungen sind anhand der folgenden
Routen- und OSM-Prüfungen freigegeben; sie sind noch nicht alle vor Ort gefahren.

## Katalogumfang

Für **beide** Kreuzungen gelten dieselben acht gerichteten Beziehungen:

| Einfahrt aus | Links: Ausfahrt nach | Geradeaus: Ausfahrt nach |
| --- | --- | --- |
| Westen | Norden | Osten |
| Norden | Osten | Süden |
| Osten | Süden | Westen |
| Süden | Westen | Norden |

Damit enthält `munich-big-junctions-v2` zwei Kreuzungen und 16 Beziehungen.
Rechtsabbiegen und die vier ausgeschlossenen schwierigen Kreuzungen bleiben
ohne Zusatzmetadaten. Zusätzliche Gegenrichtungsfahrten auf einzelnen
Zweirichtungsradwegen werden nicht aus dieser Tabelle abgeleitet.

## Prüfnachweise

- [Gemeinsame GeoJSON-Prüfkarte](full-movements-review.geojson): beide
  unveränderten Polygone, Tore und alle freigegebenen Innenverläufe.
- [Prüfbericht](full-movements-review.json): konkrete API-URLs, Datenstände,
  zugeordnete OSM-Wege und die acht Rechtsabbiege-Gegenproben.
- 24 gespeicherte Live-Routenantworten unter
  `backend/tests/fixtures/big-junctions/`: 16 positive Beziehungen und acht
  regulär nutzbare Rechtsabbiegerouten ohne Zuordnung.
- [Reproduzierbare Erfassung](prepare_full_movements.py). Sie schreibt nur
  Prüfunterlagen und einen Katalogvorschlag, niemals den Laufzeitkatalog.

Alle 16 positiven Antworten erfüllen die produktiven Kriterien: vollständige
GeoJSON-Geometrien, durchgehende Cycling-Steps, genau eine vollständige
Durchfahrt, richtige gerichtete Tore, passende Anschlussrichtungen und
eindeutiger Innenkorridor. Die gesamte innere Strecke wurde zusätzlich in
höchstens 2-m-Abständen gegen ausdrücklich erlaubte OSM-Radverkehrswege und
deren Fahrtrichtungen geprüft, mit höchstens 1,25 m geometrischer Abweichung.
Die Laufzeitzuordnung behält ihre beidseitige Korridorprüfung mit 2,5 m bei.

Zwei vollständig gerade Arnulf-Routen haben nur Start- und Zielmanöver. Sie
erhalten trotzdem den Kreuzungshinweis und ein leeres `suppressedStepIndices`.
Es werden keine künstlichen Einzelmanöver erzeugt.

Bei den beiden Balan-Nord-Routen weicht der äußere Depart-Marker geringfügig
vom ersten Geometriepunkt ab. Nur für diesen ersten Startmarker sind bis zu
0,75 m erlaubt. Innere Manöver, Step-Verknüpfungen und die Rekonstruktion der
unveränderten Route bleiben exakt. Größere Startabweichungen oder auch kleine
Abweichungen innerer Manöver bleiben Regressionstests zufolge ausgeschlossen.

## App und Praxistest

Die allgemeine App-Anbindung ab Build **3.2.2+96** akzeptiert die neue
Katalogrevision ohne App-Änderung. Standard/RadlNavi verwenden; für beide
Voransagen 150–200 m vor der jeweiligen Einfahrt starten. Die Referenzabfragen
beginnen kürzer vor der Fläche und prüfen primär die Routen-/Torzuordnung.

Erwartet: Voransagen bei ungefähr 100 und 60 m bis zur Einfahrt, innerhalb
keine weiteren Navigations-/Abweichungsansagen, danach normale Führung beim
richtigen Ausgang und normale Abweichungsbehandlung beim falschen Ausgang.
Bei Geradeausfahrten lautet der Text „an der großen Kreuzung geradeaus fahren“.

Ein Katalogeintrag genehmigt den gespeicherten geplanten Innenverlauf. Eine
abweichende tatsächliche Fahrt innerhalb einer bereits zugeordneten Fläche
wird von der App toleriert; zusätzliche geplante Innenvarianten werden dadurch
nicht automatisch in den Katalog aufgenommen.
