# Zentrale Kreuzungen · Technische Prüfung K42-K46; K46 Entry-1 nur rechts; K44 Wiedervorlage ab 23.11.2026

Echte Standardrouten, unveränderte freigegebene Flächen, gerichtete OSM-Korridore und Laufzeitprüfung. Aktivierungs-/Live-Stand siehe zentrale Übersicht.

| Fall | Links/geradeaus bestanden | Rechtskontrollen |
| --- | --- | --- |
| K42 v1 | 8/8 | 4/4 |
| K43 v1 | 8/8 | 4/4 |
| K44 v2 | 7/8 | 4/4 |
| K45 v2 | 8/8 | 4/4 |
| K46 v2 | 7/10 | 5/5 |

Gesamtkatalog: 38 positive Routen, 21 Rechts- und 38 Fußkontrollen.

## Gesperrte Beziehungen

- K44 Entry-3 → Exit-1: ValueError: Route does not cross polygon exactly once
- K46 Entry-1 → Exit-3: Thomas: Entry-1 ist eine reine Rechtszufahrt; keine Geradeaus-/Linksbeziehung. Normale Hinweise bleiben.
- K46 Entry-1 → Exit-4: Thomas: Entry-1 ist eine reine Rechtszufahrt; keine Geradeaus-/Linksbeziehung. Normale Hinweise bleiben.
- K46 Entry-3 → Exit-4: ValueError: Inner route lacks legal directed OSM support within 1.25m

K44 Entry-3 → Exit-1: Standardroute fährt zunächst auf der Marsstraße nach Südosten und über Lämmerstraße/Hirtenstraße zurück in die Seidlstraße; mehrfache Flächenquerung statt der vorgesehenen Linksbeziehung. Keine Links-Makroansage; die zwei tatsächlich gefahrenen Geradeausquerungen bleiben gültig. Wiedervorlage ab 23.11.2026: OSM except=bicycle.

K46 Entry-3 → Exit-4: Standardroute verwendet den inneren Gehwegabschnitt 1017221653 ohne belegte Fahrradfreigabe (kein bicycle=yes/designated im eingefrorenen OSM). Keine Erweiterung des Radkorridors auf unbelegte Gehwege; normale Hinweise bleiben.
Thomas meldet eine ergänzte Fahrrad-Ausnahme an der OSM-Linksabbiegebeschränkung. Wiedervorlage ab 23.11.2026; OSM-Relation und Routing-Datenimport prüfen, dann dieselbe Standardroute erneut testen. Bis dahin deaktiviert.
