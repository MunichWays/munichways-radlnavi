# Issue #22: seitenspezifische OSM-Attribute in RadlNavi

Stand: 26.10.2026. Analyse und Umsetzungsvorschlag für
[RadlNavi #22](https://github.com/MunichWays/munichways-radlnavi/issues/22),
Codebasis `0aeead62ea82aa599a77eac7f274e3711f095536`.
Die Umsetzung für RadlNavi ist lokal abgeschlossen: Routing und Backend 2.3.8,
Breite ohne Routinggewichtung. Die Masterliste ist ein separater Folgeschritt.
Analyse und damaliger Ausgangszustand sind unten erhalten; aktuelle
Abnahmeergebnisse stehen im letzten Abschnitt. Noch nicht deployed.

## Ergebnis der Münchner Bestandsaufnahme

Die [Overpass-Abfrage](munich-side-tags.overpassql) sucht `highway`-Ways
innerhalb der Verwaltungsfläche München, Relation
[62428](https://www.openstreetmap.org/relation/62428), Area `3600062428`.
OSM-Datenstand: **26.10.2026, 17:30:00 UTC / 18:30:00 MEZ**;
Flächenstand: 15:22:36 UTC. Die Relation wurde mit abgefragt und als München,
`admin_level=6`, `wikidata=Q1726` geprüft.

| Gefundener Schlüssel | Ways | Werte |
| --- | ---: | --- |
| `cycleway:right:surface` | 3 | `asphalt` |
| `cycleway:left:width` | 4 | `2.0` |
| `cycleway:both:width` | 6 | `1.5` (1), `1.85` (4), `2` (1) |
| Alle seitenspezifischen `smoothness`-Varianten | 0 | — |
| `cycleway:<key>:left/right/both` | 0 | — |
| `<key>:left/right/both` ohne `cycleway:` | 0 | — |

**13 unterschiedliche Ways**, davon 3 mit Oberfläche und 10 mit Breite.
Links/rechts allein betreffen 7 Ways; `both` ergänzt weitere 6. Kein Treffer
enthält für dasselbe Attribut zwei unterschiedliche linke/rechte Werte.
Das zentrale reale Problem ist die Abweichung zwischen Radweg und Fahrbahn.

Die Zahlen sind Way-Zahlen, keine Straßen-, Kilometer- oder Fahrtenzahlen.
Geteilte Straßenabschnitte zählen einzeln. Enthalten sind alle `highway`-Werte,
ohne vorab Fahrradzugang zu filtern. Nicht erfasst sind Nachbargemeinden,
Nodes/Relationen als Attributträger oder andere Schlüssel wie
`width:lanes`, `surface:forward` und `*:conditional`. Null Treffer gelten nur
für diese Fläche, Schlüssel und diesen Datenstand. Der Anteil am gesamten
Münchner Wegenetz wurde nicht bestimmt.

Die [Rohantwort](munich-side-tags.json) und die offline erzeugte
[vollständige Auswertung](summary.json) enthalten alle Treffer, Kontexttags
und explizite Nullzählungen. Die QL-Abfrage lässt sich direkt in
[Overpass Turbo](https://overpass-turbo.eu/) ausführen.

## Schreibweise und Bedeutung

Das [OSM-Wiki zu cycleway:surface](https://wiki.openstreetmap.org/wiki/Key:cycleway:surface)
und die [Zusatzattribute zu cycleway](https://wiki.openstreetmap.org/wiki/Key:cycleway#Supplementary_details)
dokumentieren `cycleway:left/right/both:<key>` für `surface`, `smoothness`
und `width`. Diese Reihenfolge ist die erste Priorität. Die im Issue genannte
Reihenfolge `cycleway:<key>:left/right` kann als ausdrücklicher
Kompatibilitätsalias vorbereitet werden; sie ist im Münchner Snapshot nicht belegt.
Der Oberflächenwert heißt `asphalt`; `aspalt` sollte nicht automatisch
umgeschrieben werden. Unbekannte Werte bleiben als solche erhalten.

`left/right` beschreibt die Seite relativ zur **OSM-Knotenreihenfolge**,
nicht unmittelbar Hin-/Rückfahrt. In München gilt regulär rechts = forward,
links = backward. Einbahnstraßen und explizite
[`cycleway:<side>:oneway`](https://wiki.openstreetmap.org/wiki/Key:cycleway:right:oneway)
ändern diese Zuordnung: `yes/1` bedeutet entlang der Way-Richtung, `-1`
entgegen, `no` beide Richtungen. Auf Einbahnstraßen verlaufen ohne explizite
Gegenangabe auch linke Radstreifen in Straßenrichtung. `oneway:bicycle=no`
erlaubt Radgegenverkehr, legt aber allein keine Radwegseite fest.

Allgemeines `surface:left/right` kann dagegen die physische Hälfte eines
gemeinsamen Geh-/Radwegs beschreiben. Ein Richtungswechsel wechselt dort
nicht automatisch die Radverkehrsfläche. Solche Tags dürfen nicht pauschal
als Alias für `cycleway:left/right:surface` gelten.

Bei [width](https://wiki.openstreetmap.org/wiki/Key:width#Streets)
ist die Unterscheidung besonders wichtig: Fahrbahnbreite ist nicht
Radstreifenbreite. Ein allgemeines `width=5.5` darf keinen fehlenden
`cycleway:right:width`-Wert ersetzen.

## Ist-Zustand und betroffene Module

| Stelle | Verhalten heute | Vorbereitete Änderung |
| --- | --- | --- |
| `routing/bike.lua`, `get_cycling_tag`, Oberflächenblock in `process_way` | `cycleway:<key>` vor `<key>`; derselbe Wert für beide Richtungen | Gemeinsamer Resolver mit Fahrtrichtung, Seite, Herkunft und Konfliktstatus; Speed/Faktor je Richtung anwenden |
| `routing/direct.lua`, `process_direct_way` | Gemeinsame Speeds; nur ein `surface_cost` für beide Raten | Dieselbe Auflösung; Oberflächenkosten für forward/backward getrennt |
| `routing/guidance_way_type.lua` | Richtungslogik für Ansageklassen und exklusive Lanes existiert bereits | Regeln abgleichen, Attribute und Sprachausgabe nicht auseinanderlaufen lassen |
| `backend/src/geo_store.py` | Speichert sämtliche Way-Tags und Knotenreihenfolge | Kein neues DB-Feld und kein Schemawechsel nötig |
| `backend/src/route_analysis.py` | `EdgeCandidate.forward` vorhanden; `RouteSegment` bewahrt die Richtung noch nicht | Richtung pro befahrenem Vorkommen erhalten und zur Auflösung nutzen |
| `backend/src/app.py`, `analyze_route` | Verteilung und Detailgeometrien verwenden ausschließlich rohes `surface` | Beide Ausgaben aus derselben aufgelösten Oberfläche bilden |
| `frontend/src/App.tsx`, `analyzeRoute`, Untergrundanzeige | Zeigt `tag_distribution.surface` an | Vorhandene Antwortstruktur weiterverwenden; zunächst keine neue Oberfläche erforderlich |

`width` beeinflusst aktuell weder Routing noch Auswertung. `smoothness`
beeinflusst Fahrzeiten/Raten, hat aber keine eigene Frontend-Verteilung.
Die Untergrundanzeige ignoriert heute sogar die bereits unterstützten
unspezifischen `cycleway:surface`-Werte. Dieser bestehende Unterschied muss
beim Backend-Fix mit geschlossen werden.

Der damalige exportierte Lua-Resolver wurde mit `lupa==2.6` auf allen
13 Ways aufgerufen: [Baseline](baseline-resolver.json). Auf der Gerner Straße
liefert er `surface=sett`, `smoothness=bad`. Die ungenutzten OSRM-Library-Imports
wurden dafür gestubbt; `process_way`, Graph-Extraktion und Routing wurden
damit nicht getestet.

## Vorschlag für den ersten Umsetzungsschritt

1. **Seite bestimmen, dann Attribute auflösen.** Ein neues Lua-Modul, etwa
   `cycling_attributes.lua`, liefert dieselbe Seitenauswahl für Standard und
   Direct. Rechtsverkehr ist Standard; explizites `driving_side=left`,
   Straßenrichtung und Seiten-`oneway` müssen in Prüffällen enthalten sein.
   Ein vorhandenes Attribut allein erteilt keine Fahrradfreigabe.
   `cycleway:<side>=no` und `separate` schließen die Übernahme von dortigen
   Radwegattributen auf die Fahrbahn aus. Separat gemappte Radwege verwenden
   ihre eigenen Way-Tags.
2. **Präzedenz je Attribut:** für die ausgewählte Radwegseite
   `cycleway:<side>:<key>` → `cycleway:<key>:<side>` →
   `cycleway:both:<key>` → `cycleway:<key>:both` → `cycleway:<key>`.
   Kanonische Schlüssel gewinnen bei widersprüchlichen Aliaswerten; der
   Konflikt bleibt in Test-/Diagnoseinformationen sichtbar. Bei fehlendem
   `surface`/`smoothness` bleibt der bisherige allgemeine Fallback erhalten.
   Fehlende Radwegbreite bleibt unbekannt. Leere Werte gelten als fehlend;
   unbekannte nichtleere Werte behalten wie in #20 ihren Vorrang.
3. **Beide Richtungen unabhängig behandeln.** Unterschiedliche Oberflächen
   ergeben unterschiedliche Speeds und Direct-Kosten. `smoothness` bleibt
   ein unabhängig aufgelöster Faktor. Zugangsverbote, Schieben, Fähren,
   Maxspeed und Abbiegestrafen müssen ihre vorhandenen Grenzen behalten.
   Attribute dürfen gesperrte Richtungen nicht wieder öffnen.
4. **Mehrdeutige Seitenauswahl ausdrücklich begrenzen.** Bei zwei legalen
   Radwegseiten in derselben Richtung bevorzugt das Modell die reguläre
   Verkehrsseite, andernfalls die einzige passende Seite. Können Tags keine
   eindeutige Kandidatenmenge herstellen, keine freie Auswahl des günstigeren
   Belags: bisherigen unspezifischen Wert verwenden und Mehrdeutigkeit
   markieren. OSRM bildet bei an der Straße getaggten Radwegen keine eigene
   Geometrie je Seite ab. Eine solche Modellannahme belegt deshalb nicht die
   tatsächlich gefahrene physische Seite.
5. **Backend synchronisieren.** Eine Python-Implementierung derselben Regeln
   nutzt die OSM-Richtung jedes Segmentvorkommens. Lua und Python werden
   gegen gemeinsame JSON-Fälle geprüft. Hin-/Rückfahrt auf demselben Way
   dürfen unterschiedliche Oberflächen liefern. Detailgeometrien nur bei
   gleicher aufgelöster Eigenschaft zusammenführen; heute wird nur nach Way,
   Leg und Anschluss zusammengeführt. Mehrdeutige Way-Zuordnungen bleiben
   unbekannt. Die bestehende Antwortform bleibt kompatibel; ihre geänderte
   Bedeutung erhält eine neue `analysis.version` statt `segments-v2`.
6. **Breite zunächst auflösen und prüfen.** Kein neuer Bonus/Malus und keine
   Zugangssperre allein aus Breite. Eine Geschwindigkeits- oder Komfortregel
   braucht eigene fachliche Grenzwerte und Abnahme. Dafür ist keine neue
   Frontend-Anzeige im ersten Schritt erforderlich.

Für `<key>:left/right/both` ohne Präfix lautet die Empfehlung: Rohwerte
vollständig erfassen, aber bis zu einem eindeutig belegten Flächenmodell
nicht automatisch richtungsbezogen anwenden. Für München fehlt dafür derzeit
ein realer Treffer. Diese Einschränkung und eine spätere Breitengewichtung
sind fachliche Scope-Entscheidungen vor der Implementierung, keine technisch
gleichwertigen Schreibvarianten.

## Reale Abnahmebeispiele

Die [eingefrorene OSM-Datei](munich-examples.osm) enthält alle 13 Original-Ways
mit 58 referenzierten Nodes zum selben OSM-Zeitpunkt wie die Bestandsaufnahme.
Koordinaten, Tags, Way-Version und Zeitstempel sind erhalten; Benutzername
und Benutzer-ID wurden entfernt. Angrenzende Ways und Relationen fehlen:
geeignet für isolierte Profiltests, nicht für vollständige Netz-Routenwahl.

| Beispiel | Vorher | Erwartung nach Umsetzung |
| --- | --- | --- |
| [Gerner Straße, 4075460](https://www.openstreetmap.org/way/4075460) | Beide Richtungen `sett`, Faktor `bad` | Forward rechter Radweg `asphalt`; backward Fahrbahn `sett`; allgemeines `bad` bleibt unabhängig erhalten |
| [Sarasatestraße, 16548185](https://www.openstreetmap.org/way/16548185) | `asphalt`, Einbahnstraße | Oberfläche unverändert; Gegenrichtung bleibt gesperrt |
| [Frauendorferstraße, 16548329](https://www.openstreetmap.org/way/16548329) | `asphalt`, `intermediate`, `oneway:bicycle=no` | Keine Reisezeitänderung; Gegenverkehr bleibt erlaubt; rechter Radwegwert nicht automatisch auf linke Seite übertragen |
| [Oberanger, 30804563](https://www.openstreetmap.org/way/30804563) | Breite ignoriert | Breite `1.85` für beide Radstreifen auflösbar; gleiche Route und Dauer ohne neue Breitengewichtung |
| [Landwehrstraße, 146800310](https://www.openstreetmap.org/way/146800310) | `cycleway:left=no` und `cycleway:left:width=2.0` | Widerspruch erkennen; weder linker Radweg noch rechte Radstreifenbreite daraus ableiten |

Für die Gerner Straße ist ein signal- und manöverfreier Teilabschnitt zwischen
Node `12791580130` (11.5237591, 48.1615315) und Node `1676173828`
(11.5243873, 48.1607003) vorbereitet. Die Koordinaten stehen in lon/lat-Reihenfolge;
die genannte Reihenfolge ist forward.

Aus den aktuellen Tabellen rechnerisch: heute `min(20, 9) × 0.7 = 6.3 km/h`
in beiden Richtungen; nach dem vorgeschlagenen Fix forward
`min(20, 20) × 0.7 = 14 km/h`, backward weiterhin `6.3 km/h`.
Das entspricht pro 100 m etwa **57.1 → 25.7 s** forward. Direct erhält
forward Oberflächenkosten 1 statt 1.15; backward bleibt 1.15.
Diese Zahlen sind **abgeleitete Sollwerte, keine gemessenen OSRM-Ergebnisse**.
Die Backend-Untergrundverteilung muss auf Hin-/Rückfahrt jeweils den
korrespondierenden Wert und bei einer Rundfahrt beide Teilstrecken ausweisen.

Zusätzlich erforderlich sind synthetische Fälle für unterschiedliche
left/right-Oberflächen, seitenspezifisches `smoothness`, Alias-Konflikte,
`both` mit Seiten-Override, unabhängige Fallbacks, unbekannte/leere Werte,
`oneway=-1`, Gegenverkehr, einseitigen Zweirichtungsradweg,
`driving_side=left`, `separate/no`, gesperrte Richtungen sowie einen
gemeinsamen Geh-/Radweg mit `surface:left/right`. Dafür liefert der Münchner
Snapshot keine vollständige reale Testabdeckung. Die bestehenden Fälle aus
#20 für Ludwigsbrücke und Golo-Mann-Weg müssen unverändert bestehen bleiben.

## Umsetzungspakete, Version und Einführung

1. Gemeinsame JSON-Vertragsfälle und Resolver in Lua/Python; genaue Regeln
   für Alias, Seitenauswahl und unbekannte Werte festhalten.
2. Standard-Speeds und Direct-Raten umstellen. Neues Lua-Modul in
   `routing/Dockerfile` und `routing/tests/Dockerfile` mitkopieren.
3. Backend-Richtung erhalten, Untergrundverteilung und Geometrieaggregation
   anpassen; vorhandene Antwortstruktur mit Frontend-Regression prüfen.
4. Echte Standard-/Direct-Graphen aus der eingefrorenen Datei extrahieren,
   Zeiten/Gewichte in beiden Richtungen prüfen; zusätzlich eine synthetische
   Netzalternative für die veränderte Routenwahl testen. Die Originaldatei
   allein enthält dafür nicht genügend Netzumgebung.
5. Gesamte Routing-/Backend-CI aus `.github/workflows/routing-tests.yaml`
   einschließlich #20, Einbahn-, Schiebe- und Guidance-Regressionen ausführen.
   Vorher/nachher denselben Datensatz und dieselbe Routing-Variante verwenden.

Die Änderung wird als kleiner kompatibler Fix gemäß den
[Release-Regeln](../../RELEASES.md) mit **Routing 2.3.5 → 2.3.8** und
**Backend 2.3.7 → 2.3.8** veröffentlicht. Frontend aktuell 2.3.7 benötigt bei unveränderter
Antwortstruktur keinen eigenen Release. Versionsnummern vor Umsetzung erneut
gegen den dann aktuellen Stand prüfen. OSRM bleibt auf dem bereits gepinnten
26.6.5; ein Engine-Upgrade ist dafür nicht erforderlich.

Beide Routing-Datensätze benötigen `osrm-extract`, `osrm-partition` und
`osrm-customize` sowie anschließendes Deployment; ein Neustart alter Graphen
reicht nicht. Backend- und Graphwechsel koordiniert ausrollen, damit Anzeige
und Routenauswahl dieselben Regeln verwenden. Der Geo-Store muss die zum
Graphen passende OSM-Version enthalten; ein Schemawechsel ist nicht nötig.

## Reproduktion und tatsächlich erfolgte Prüfung

Vom Repository-Stamm aus, ohne Zusatzpakete für Abruf/Auswertung:

```shell
python docs/issue-22-analysis/collect.py
python docs/issue-22-analysis/summarize.py
```

`collect.py` ersetzt den Snapshot durch den dann aktuellen Overpass-Stand und
holt die Geometrie anschließend zu genau diesem Zeitpunkt. Für die hier
festgehaltene historische Geometrie kann die gespeicherte
[zweite QL-Abfrage](munich-examples.overpassql) verwendet werden. Attribution:
© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL.

Den ursprünglichen Resolver aus dem oben genannten Baseline-Commit erneut
untersuchen (`lupa==2.6` erforderlich):

```shell
backend/.venv/Scripts/python.exe docs/issue-22-analysis/check_baseline.py
```

Geprüft: Overpass-Antwort ohne Fehlervermerk, München-Relation, alle 27
Schlüsselzählungen, Übereinstimmung der 13 Way-IDs und aller Way-Tags zwischen
JSON und OSM-Datei, Vollständigkeit der 58 Nodes, offline reproduzierbare
Auswertung und tatsächlicher Aufruf des bisherigen Lua-Resolvers.
Diese erste Analyse enthielt noch keine Vorher-/Nachher-Routingmessung.

## Umgesetzt und mit OSRM geprüft

`routing/cycling_attributes.lua` und `backend/src/cycling_attributes.py`
verwenden dieselben 31 JSON-Vertragsfälle. Standard wendet Oberfläche und
Smoothness je Richtung an; Direct verwendet zusätzlich getrennte
Oberflächenkosten. Der Backend-Geo-Store bleibt unverändert. Die
Oberflächenverteilung verwendet die Richtung jedes Segmentvorkommens und
trennt Hin-/Rückfahrt bei unterschiedlichem Belag (`analysis.version=segments-v3`).
Explizites `bicycle=dismount` verwendet den allgemeinen Belag.

Breite wird für Inspektion aufgelöst, aber nicht in Routinggewichte,
Geschwindigkeiten oder Zugang übersetzt. Sie beeinflusst auch nicht die
Seitenauswahl von Oberfläche/Smoothness. Allgemeine physische
`surface:left/right`-Angaben werden weiterhin nicht als Fahrtrichtung ausgelegt.
Bei Wegen mit fester Dauer bleibt das bestehende gemeinsame OSRM-Gewicht
auf Basis unspezifischer Attribute erhalten; normale gerichtete Kanten
verwenden getrennte Geschwindigkeiten und Raten.

Der identische eingefrorene Testdatensatz wurde mit den ursprünglichen und
den neuen Profilen unter OSRM 26.6.5 vollständig extrahiert, partitioniert
und angepasst. [Gemessene Rohwerte](osrm-before-after.json):

| Gerner Straße, 103,6 m | Vorher Standard/Direct | Nachher Standard/Direct |
| --- | ---: | ---: |
| Forward: rechter Asphalt-Radweg | 59,2 s | 26,7 s |
| Backward: Pflaster-Fahrbahn | 59,2 s | 59,2 s |

Im synthetischen Netzbeispiel wählen beide alten Profile vorwärts den
195-m-Umweg. Beide neuen Profile wählen die 142,3-m-Asphaltverbindung;
rückwärts bleibt der Umweg bevorzugt. Das ist eine isolierte Netzabnahme,
keine Zusicherung für die gesamte produktive Münchner Route.

Lokal bestanden: Backend-Suite; Lua-Vertragsfälle und Fixture-Konsistenz;
OSRM-Tests für neue Attribute und Routenwahl; bestehende Standard-/Direct-,
#20-, Guidance-, Münchner Einbahn-, Schiebezugangs- und Bergmann-Regressionen;
14 Frontend-Tests aus `routingRequests.test.ts` und `App.routing.test.tsx`.
Die GitHub-Actions-Workflowdatei führt die neuen Prüfungen zusätzlich aus.
Produktiv sind noch die bisherigen Graphen aktiv; zur Einführung sind der
oben beschriebene Neubau beider Graphen und das Backend-Deployment nötig.
