# Gezeichnete 6 Faelle · Technische Prüfung P3 / K51, P5 / K52, P6 / K53

Echte Standardrouten, unveränderte freigegebene Flächen, gerichtete OSM-Korridore und Laufzeitprüfung. Aktivierungs-/Live-Stand siehe zentrale Übersicht.

| Fall | Links/geradeaus bestanden | Rechtskontrollen |
| --- | --- | --- |
| K51 v3 | 8/10 | 4/5 |
| K52 v2 | 8/8 | 4/4 |
| K53 v1 | 8/8 | 4/4 |

Gesamtkatalog: 24 positive Routen, 13 Rechts- und 24 Fußkontrollen.

## Gesperrte Beziehungen

- K51 Entry-5 → Exit-1: ValueError: Wrong entry gate
- K51 Entry-5 → Exit-2: ValueError: Wrong entry gate
- K51 Entry-5 → Exit-3: ValueError: Wrong entry gate

## Zuordnung und Diagnose

- P3 = K51, P5 = K52, P6 = K53. Die P-Nummern im lokalen Projekt bleiben erhalten.
- P3 Entry-5: Die echten Referenzrouten werden auf den benachbarten Entry-4 verlegt. Entry-5 nach Exit-1/Exit-2 bleibt deshalb deaktiviert; keine Aenderung der freigegebenen Geometrie. Die Rechtsroute ist ebenfalls kein Nachweis fuer Entry-5, bleibt aber ohne Makro.
- P5: Der gerichtete innere Abschnitt von Blankbauerstrasse, OSM 3302000, verbindet die Radwege mit dem freigegebenen Strassen-Exit auf OSM 3302001. Nur vollstaendig innere Segmente werden zur Korridorpruefung zugelassen.
- Armzuordnung: P5 automatische Arm-1/2 = Nord, Arm-3 = Ost, Arm-4/5 = Sued, Arm-6 = West; P6 Arm-1 = Nord, Arm-2 = Ost, Arm-3/4 = Sued, Arm-5 = West. Die technische Zuordnung liegt separat zur unveraenderten Geometriefreigabe.
- Aktivierungsstand steht in der lokalen Kartenuebersicht; kein Deployment durch dieses Pruefkommando.
