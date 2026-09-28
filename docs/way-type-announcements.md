# Ansage beim Wechsel zwischen Radweg und Straße

Stand: 28.09.2026. Lokal implementiert in Routingprofil und Flutter-App;
noch nicht committed, deployed oder mit einem neu extrahierten OSRM-Graph geprüft.

## Regel

An eine vorhandene Ansage wird beim eindeutigen Wechsel angehängt:

- Straße → Radweg: „In 60 Metern links abbiegen, auf Radweg.“
- Radweg → Straße: „Hier rechts abbiegen, auf Straße.“
- Geradeauswechsel: „In 60 Metern geradeaus weiterfahren, auf Radweg.“

„Hier“ ist der bestehende Sofortansage-Text der App. Voransage, Sofortansage
und die Zwischenansage auf langen Abschnitten verwenden denselben Zusatz.
Bei „danach sofort …“ gehört jeder Zusatz direkt zum jeweiligen Manöver.

| OSM-Tags | Einstufung |
| --- | --- |
| `highway=cycleway` oder `path` | Radweg |
| `living_street`, `residential`, `unclassified`, `road`, `tertiary`, `secondary`, `primary`, `trunk`, `motorway` und deren `_link`-Varianten | Straße |
| Straße mit `cycleway=lane` **und** `cycleway:lane=exclusive` | Radweg |
| Straße mit anderer oder fehlender Lane-Einstufung | Straße |
| `footway`, `track`, `service`, alle übrigen oder fehlenden Werte | kein Zusatz |

Seitenbezogene Angaben (`cycleway:right/left/both` mit `:lane`) werden
ebenfalls berücksichtigt. Spezifische Seiten-Tags haben Vorrang. Die
Zuordnung folgt der Fahrtrichtung; `:oneway=-1/no` und `driving_side=left`
werden berücksichtigt. Schieben und Fähren erhalten keine dieser Klassen.
Explizite Seiten-Einbahnrichtungen beziehen sich auf die OSM-Way-Richtung,
entsprechend der [OSM-Tagdefinition](https://wiki.openstreetmap.org/wiki/Key:cycleway:right:oneway).

Ein unbekannter/ignorierter Abschnitt unterbricht den Vergleich. Aus
Straße → service → Radweg wird deshalb kein unmittelbarer Wechsel
Straße → Radweg abgeleitet. Am Start und am Ziel erfolgt kein Wechselzusatz.

## Zuständigkeit und Datenvertrag

**RadlNavi / Routingprofil:** `routing/guidance_way_type.lua` leitet aus
OSM-Tags die Klassen `cycleway` bzw. `road` ab. `bike.lua` setzt sie zusätzlich
zu den vorhandenen Klassen, richtungsbezogen und nur im Cycling-Modus.
`direct.lua` erbt dies. Die neuen Regeln ändern selbst keine Geschwindigkeiten,
Gewichte, Zugangsregeln oder Abbiegestrafen.

**OSRM:** Die Route enthält die Klassen in `steps[].intersections[].classes`.
Die erste Kreuzung eines Steps liegt am Manöver; die Klasse beschreibt die
befahrene Ausfahrt. Das ist der dokumentierte
[OSRM-Datenvertrag](https://github.com/Project-OSRM/osrm-backend/blob/v26.6.5/docs/http.md#intersection-object).
Es gibt keine zusätzliche HTTP-Abfrage und keine Datenbankanreicherung.

**App:** `RadlNaviApi` vergleicht die letzte Kreuzung des vorherigen Steps
mit der ersten des aktuellen Steps, getrennt pro Leg. Nur zwei eindeutige,
verschiedene Klassen erzeugen `RouteManeuver.enteringWayType`.
Fehlende, widersprüchliche oder unbekannte Metadaten erzeugen keinen Zusatz.
Eine Änderung innerhalb eines Steps wird nicht an dessen früheres Manöver
angehängt. Zusätzliche Manöver innerhalb eines Steps werden nicht erfunden.

`VoiceGuidance` ergänzt die deutsche bzw. englische Sprachausgabe. Ein
OSRM-`notification`- oder gerader `new name`-Step bleibt bei einem erkannten
Wechsel relevant. Die Unterdrückung kurzer leichter Gegenkurven darf solche
Wechsel nicht entfernen. Geometrische Modifier-Korrekturen erhalten die Metadaten.

## Einführung und Prüfung

1. Routing-Regressionen mit beiden Profilen ausführen. Der CI-Test
   `routing/tests/test_guidance_classes.py` prüft die Ausgabe nach tatsächlicher
   Extraktion in beiden Richtungen.
2. Standard- und Direct-Graph mit dem neuen Profil **neu extrahieren**,
   partitionieren, anpassen und deployen. Nur ein App-Update reicht nicht.
3. Reale Antworten für Radweg ↔ Straße, exclusive/advisory lane und einen
   ignorierten Zwischenabschnitt sichern und auf dem Gerät nachfahren.
4. Voransage, Sofortansage, kombinierte Ansage und OSRM-Geradeauswechsel prüfen.

Die neue App arbeitet auch mit alten Serverantworten: Ohne neue Klassen
bleiben die bisherigen Ansagen bestehen. Das Web-Prüffenster zeigt die Zusätze
als Browsertext. Bei alten Serverdaten kann jeder Zusatz pro Hinweis manuell
simuliert werden. Die Rohantwort bleibt unverändert; Filter und
Ansagezeitpunkte der App werden nicht simuliert.

Lokal bestanden: 6 Lua-Klassifikationstests, OSRM-Extraktion und
Klassenausgabe für Standard und Direct in beiden Fahrtrichtungen sowie
68 gezielte App-Tests sowie TypeScript-Prüfung und 8 Tests für „Hinweise prüfen“.
Kein Gerätetest oder Produktions-Routing-Neubau.
