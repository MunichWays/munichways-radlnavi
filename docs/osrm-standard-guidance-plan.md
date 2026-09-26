# OSRM-Standard als Basis für Routing und Ansagen

Stand: 26.09.2026, ergänzt um Lenbachplatz und eine Prüfansicht im Webfrontend.
Die beschriebenen Routing- und Flutter-Regeln wurden nicht geändert.

## Praktische Prüfmöglichkeit

Im Webfrontend gibt es jetzt **Hinweise prüfen**: vier Beispielrouten,
eigene Koordinaten, Übernahme der aktuellen Kartenroute, vollständige
Manöverliste, Browser-Vorlesen, Kartenmarkierung und Export der Rohantwort.
Die [Bedienungsanleitung](../frontend/README.md) beschreibt den lokalen Start.
Damit lassen sich Backend-Hinweise ohne Fahrt prüfen und konkrete Antworten
für spätere Replays sichern. Die Flutter-Ansagelogik bleibt gesondert zu prüfen.

## Entscheidungsempfehlung

Ja: aktuelle OSRM-Manöver sollen die maßgebliche Ausgangsbasis werden. Zuerst
die bestehenden App-Eingriffe einzeln gegen unveränderte Manöver vergleichen;
danach das Fahrradprofil kontrolliert an Upstream annähern. Ein vollständiger
Austausch des Profils oder das pauschale Entfernen aller App-Regeln ist durch
die bisherigen Befunde nicht gerechtfertigt.

Der Nutzen ist besonders am Birketweg konkret: Die produktive API liefert
bereits die gewünschten zwei Abbiegungen. Eine zusätzliche App-Regel entfernt
genau solche Folgen. Schrammerstraße zeigt dagegen eine bereits unvollständige
API-Manöverfolge. Waisenhausstraße benötigt eine zurückhaltende Präsentation
einer Wegverschwenkung. Lenbachplatz meldet eine Abweichung zwischen erwarteter
und beobachteter App-Ansage, die der gesicherte API-Datensatz allein noch
nicht reproduziert. Diese Fehlerklassen brauchen unterschiedliche Lösungen.

**Noch nicht nachgewiesen:** Ob OSRM 26.9.0 mit unverändertem Upstream-Profil
die beiden letzten Fälle besser löst. Es wurde kein entsprechender Graph gebaut.
Die Empfehlung für weniger Eigenlogik ist belastbar; ein quantifizierter
Qualitätsgewinn durch ein Engine-/Profilupdate steht noch aus.

## Untersuchungsstand und Belege

- RadlNavi-Checkout: `04d7f7a36b91a3b01a55678c5c37508ec0731ade`.
- Flutter-Checkout: `C:/Users/Thomas/dev/flutter/munich-ways-app`, HEAD
  `c3ea3302574e367330854f750be92cd7460e5503`. Bestehende lokale Änderung an
  `lib/ui/map/map_screen.dart` nicht verändert. Kein Telefonlauf ausgewertet.
- Produktive Versionsauskunft: OSRM **26.6.5**, Backend/Routing **2.3.2**,
  jeweils Commit `9f808aac713182cbbfef2eac205c2b641b54b045`.
  [Gesicherte Versionsantwort](osrm-standard-analysis/version.json).
  Produktionscode und untersuchter Checkout sind damit ausdrücklich nicht identisch.
- Vier GET-Abfragen gegen `https://api.radlnavi.munichways.de`, Variante
  `standard`, am 26.09.2026: drei um ca. 14:31 UTC, Lenbachplatz um 14:49 UTC. Vollständige Antworten inklusive
  URL, Zeit, Geometrie, Steps, Intersections und Annotationen liegen unter
  [osrm-standard-analysis](osrm-standard-analysis/).
- Aktuelles von GitHub als Latest ausgewiesenes Release bei der Recherche:
  [26.9.0 vom 01.09.2026](https://github.com/Project-OSRM/osrm-backend/releases/tag/v26.9.0).
  Unter anderem enthält es Änderungen an Fahrrad-Abbiegebeschränkungen und
  Flächenrouting. Die Release-Liste belegt keine Lösung unserer vier Fälle.
- Direkter Quellvergleich mit
  [Upstream bicycle.lua, v26.9.0](https://github.com/Project-OSRM/osrm-backend/blob/v26.9.0/profiles/bicycle.lua).
  Abgerufene Datei: SHA256
  `4e00933450e4d8299c38c3f069e068d038af924b7a84a5f2380402cbcf9950a5`.
  Vergleich zum lokalen `bike.lua`: 374 hinzugefügte, 162 entfernte Zeilen
  (einschließlich Kommentaren/Formatierung; kein Qualitätsmaß).

Die Aussage „uralte OSRM-Version“ beschreibt die Entstehung der Anpassungen,
nicht mehr den aktuellen Engine-Stand. Dockerfile und produktive Auskunft
nennen bereits 26.6.5. Ein neues Image aktualisiert das kopierte eigene
`bike.lua` nicht automatisch auf das aktuelle Upstream-Profil.

## Die vier Fälle

Alle Koordinaten in dieser Tabelle sind **[Breite, Länge]** wie in der Meldung.
OSRM-URLs und GeoJSON verwenden dagegen **[Länge, Breite]**.
Start/Ziel wurden bei diesen Abfragen um höchstens 1,16 m gesnappt. Das ist
kein Nachweis der richtigen Wegseite; bei späteren Vergleichsläufen mitprüfen.

| Fall | Eingabe | Nutzererwartung | Gesicherte produktive Antwort |
| --- | --- | --- | --- |
| Birketweg → Radweg parallel Reitknechtstraße | `[48.145395, 11.520751]` → `[48.145413, 11.522572]` | Links, danach sofort rechts; bisher keine Hinweise | 147,2 m; nach 47,2 m `continue/left`, 12,2 m später `turn/right` |
| Schrammerstraße → Hofgraben | `[48.139050, 11.576817]` → `[48.138800, 11.577644]` | Rechts, danach sofort links; bisherige Ansage unsicher | 75,6 m; nach 46,7 m einziges Zwischenmanöver `turn/slight left` |
| Waisenhausstraße, U-Bahn-Aufgänge | `[48.161527, 11.529508]` → `[48.162217, 11.529328]` | Bevorzugt keine Ansage für bloße Verschwenkung; geometrisch links/rechts | 81,9 m; nach 31,9 m einziges Zwischenmanöver `turn/slight left` |
| Lenbachplatz → Pacellistraße | `[48.140563, 11.568148]` → `[48.140709, 11.570143]` | Gemeldet: „leicht rechts halten“; erwartet: rechts abbiegen | 160 m; erstes API-Manöver `turn/right` bei 76,8 m, 10,2 m später `turn/left`; aktuelle Flutter-Regeln sagen für genau diese Geometrie einen anderen Effekt voraus |

### Birketweg: konkrete App-Ursache

[Rohantwort](osrm-standard-analysis/birketweg.json). Die Manöver liegen bei
`[11.521380,48.145394]` und `[11.521401,48.145503]` (Länge/Breite).
`continue/left` ist ein Richtungsmanöver und darf nicht als „geradeaus“
weggefiltert werden. `_isRelevant()` behält es im aktuellen App-Code auch bei.

Die Regel `_withoutStraightOffsetPairs()` entfernt zwei entgegengesetzte
Modifier bei Abstand höchstens 30 m und Gesamt-Richtungsänderung höchstens
25°. Sie prüft weder Kreuzungsalternativen noch Straßenwechsel und beschränkt
sich nicht auf leichte Abbiegungen. Hier ergeben sich etwa **12,23 m** und
**15,94°**: Das Paar erfüllt die Löschbedingung. Beide einzelnen Abbiegungen
sind deutlich (12-m-Fenster etwa 71,49° links und 87,43° rechts).

Damit erklärt der untersuchte Code zusammen mit der Live-Antwort das gemeldete
Verschwinden. Dies ist eine rechnerische Diagnose, noch kein Flutter-Replay
oder Nachweis der tatsächlich installierten App-Version. Die 12-m-Abschwächung
ist hier nicht der Auslöser. Die vorhandene Verkettung „danach sofort“ könnte
das Paar bereits sprechen: Ihre Standardschwelle beträgt 35 m.

**Spätere erste Änderung:** Dieses echte Doppelmanöver durchreichen. Die
Unterdrückung bloßer Verschwenkungen separat absichern, insbesondere durch
den vorhandenen Balanstraße-Test. Nicht nur den Grenzwert für alle Fälle senken.

### Lenbachplatz: Abweichung zwischen gemeldeter Ansage und gespeichertem Replay

[Rohantwort](osrm-standard-analysis/lenbachplatz.json). Gesnappt wird der
Start auf `[11.568150,48.140561]` (0,27 m) und das Ziel auf
`[11.570144,48.140712]` (0,34 m). Die API liefert nach 76,8 m `turn/right`
mit `bearing_before=60` und `bearing_after=123`; das nächste `turn/left` liegt
am Ende des 10,2 m langen Folgeschritts. Die erwartete Rechtsabbiegung wird
also im API-Modifier bereits als normales Rechtsmanöver klassifiziert.

Die Flutter-Regel `_adjustTurnModifierFromGeometry()` wandelt ein normales
`turn/right` nur dann in `slight right` um, wenn ihr 12-m-Fenster zwischen 15°
und 50° liegt. Die reproduzierbare Offline-Meterprojektion der gespeicherten
Antwort ergibt **54,36°**. Damit überschreitet dieser konkrete Snapshot die
Obergrenze um 4,36° und erfüllt die bekannte Regel nicht. Die lokalen
OSRM-Bearings unterscheiden sich um 63° (`60` nach `123`); Bearings sind ein
separater Wert und nicht identisch mit dem auf der Polyline gemessenen Winkel.

Die Richtungsänderung von `right` nach dem folgenden `left` über beide Manöver
beträgt nur etwa 17,30°. Deshalb erfüllt das Paar die bestehende
`_withoutStraightOffsetPairs()`-Bedingung (10,20 m Abstand, höchstens 25°) und
wird im inspizierten Flutter-Code komplett entfernt. Das sagt **keine** Ansage
„leicht rechts“ voraus: In dieser Checkout-Version wäre vielmehr das
Verschwinden der beiden Manöver zu erwarten. Die gemeldete leichte
Rechtsansage lässt sich also mit dem gesicherten Produktions-API-Snapshot und
dem inspizierten App-HEAD nicht gemeinsam reproduzieren.

Zu klären ist, ob die gemeldete Ansage von einer anderen installierten
App-Version, einer anderen Route/Geometrie, einem abweichenden OSRM-Snapshot
oder einem nicht reproduzierten Ansagepfad stammt. Im App-Replay müssen
Rohmanöver, projizierte Routendistanzen, Modifier nach beiden Geometriestufen,
Ergebnis der Paarfilterung und tatsächlicher TTS-Text für denselben
Request/Build protokolliert werden. Das API-Manöver `right` und die Nutzererwartung
„rechts abbiegen“ sind durch diesen Datensatz gestützt; die Ursache der
gehörten Ansage bleibt offen. Das enge Folgemanöver darf bei jeder
Winkelprüfung nicht ins erste Manöver eingerechnet werden.

### Schrammerstraße: bereits vor der App unvollständig

[Rohantwort](osrm-standard-analysis/schrammerstrasse.json). Der erste Step
enthält eine weitere Intersection bei `[11.577291,48.138941]`, ohne eigenen
Manöver-Step. Von dort sind es etwa 8,07 m bis zum `slight left` bei
`[11.577269,48.138870]`. Dessen `bearing_before=191`, `bearing_after=104`
zeigen eine deutliche linke Richtungsänderung; im 12-m-Geometriefenster ca. 71°.
Bearings allein beweisen aber nicht, wie OSRM die gesamte Kreuzung bewertet hat.

Die App kann das erste Rechtsmanöver mit `_geometryTurns()` nicht reparieren:
am markanten Geometrieknoten nur etwa 5,80 m eingehendes Segment, 51,52°
lokaler Winkel und nur 8,07 m Abstand zum vorhandenen Manöver. Das scheitert
an mehreren Schwellen (7 m, 60° und 25 m Abstand). Schon vorhandenes `slight`
wird durch `_adjustTurnModifierFromGeometry()` nie zu `left` hochgestuft.

**Noch offene Ursache:** Profil/Netzmodell oder OSRM-Guidance und deren
Zusammenfassung. Nicht als erwiesenen OSRM-Bug oder OSM-Kartenfehler behandeln.
Gleichen Korridor mit aktuellem Engine-Stand und Upstream-Profil vergleichen,
Intersection-Topologie/OSM-Tags prüfen. Kein weiterer pauschaler App-Winkelpatch.

### Waisenhausstraße: weniger Sprache, keine erfundenen Abbiegungen

[Rohantwort](osrm-standard-analysis/waisenhausstrasse.json). Die aktuelle
API liefert links statt der vermuteten Rechtsansage. Diese ursprüngliche
Beobachtung bleibt unbestätigt. Die Geometrie enthält mehrere leichte
Verschwenkungen, lokal etwa 38–43°; das gelieferte Linksmanöver misst im
12-m-Fenster ca. 26,50°. Die App ergänzt solche Winkel nicht (Minimum 60°).
Mit nur einem relevanten Manöver greift auch die Paar-Unterdrückung nicht.

**Ziel:** keine unnötige akustische Richtungsansage bei eindeutigem Verlauf des
Radwegs. Die Route soll sichtbar bleiben. Echte Wegwahl, Querung oder Gefahren
dürfen nicht allein wegen geringer Winkel/kurzer Abstände stumm werden.
Ob die Verschwenkung tatsächlich ohne relevante Wegwahl ist, muss anhand
des Kartenkontexts und später im Fahrtest bestätigt werden. Keine Sonderregel
„in der Nähe einer U-Bahn immer schweigen“ und kein künstliches zweites Manöver
nur damit eine Paarregel beide wieder löscht.

## Bestehende Eingriffe und ihre Zuständigkeit

| Ebene / Quellstelle | Heutiges Verhalten | Empfehlung |
| --- | --- | --- |
| `routing/Dockerfile` | Gepinnte Engine 26.6.5, eigenes Profil; Extract/Partition/Customize | Neue Engine separat messen; Vorverarbeitung und Server mit demselben Image/Digest |
| `routing/bike.lua`, `process_way`, `process_turn` | Zugänglichkeit, Schieben, Tempo, Komfortbewertung, Signal-/Querungskosten, Klassifikation | Fachlich erforderliche Profilregeln behalten, einzeln begründen und gegen Upstream testen |
| `routing/direct.lua` | Erbt `bike.lua`, ersetzt Auswahlkosten | Ist **kein** unverändertes OSRM-Standardprofil; als eigener Kontrollfall testen |
| `backend/src/app.py`, `osrm_route_proxy` | Proxy; optional Komfortmetadaten, keine Manöverkorrektur | Rohmanöver erhalten. Gemeinsame Normalisierung nur bei nachgewiesenem verbleibendem Fehler |
| `backend/src/app.py`, `/route` | Web-Wrapper übernimmt Steps aus erstem Leg | Nicht mit App-API verwechseln; Multi-Leg-Vertrag bei künftigen Änderungen beachten |
| App `lib/api/radlnavi_api.dart` | Liest alle Legs, übernimmt Typ/Modifier; schneidet finale Fuß-Zugangsmanöver ab | Routing-Vertrag und Zugangslogik erhalten; Diagnose benötigt vollständige Rohdaten |
| App `lib/model/route.dart`, `RouteManeuver` | Nur Ort, Typ, Modifier, Name, Exit | Bearings, Intersections, Step-/Leg-ID und Modus stehen hier nicht für fundierte Entscheidungen bereit |
| App `VoiceGuidance.setRoute()` | Projektion → Abschwächung → Relevanzfilter → Ergänzung → Paarlöschung | Jeden Eingriff separat abschaltbar/replaybar machen, Rohdaten unverändert behalten |
| App `_adjustTurnModifierFromGeometry()` | `turn/left,right` bei 15–50° im 12-m-Fenster zu `slight`; nicht umgekehrt | Nutzen gegen aktuelle Rohmanöver belegen; langfristig keine konkurrierende allgemeine Klassifikation |
| App `_geometryTurns()` | 60–135°, beide Nachbarsegmente ≥7 m; Sperrabstand 25 m zu Roh-/ergänzten Manövern | Besonders anfällig für dichte Geometrie und nahe Doppelabbiegungen; keine blinde Ausweitung |
| App `_withoutStraightOffsetPairs()` | Entfernt entgegengesetzte Manöver bei ≤30 m und ≤25° Gesamtrichtung | Höchste Priorität für kontrollierten Rückbau/Begrenzung; Birketweg belegt Fehlunterdrückung |
| App `_formatSpokenManeuver()`, Fortschritt/TTS | „danach sofort“ bis 35 m, Annäherung, Wiederholungen, Sprache | App-Aufgabe; erhalten und mit GPS-Replay überprüfen |
| Web `frontend/src/App.tsx` | Eigene Fortschrittswahl, `osrm-text-instructions("v5").compile("de", step)` | Separat prüfen; übernimmt nicht die Flutter-Heuristiken. `v5` ist kein Beleg für alte Serverversion |

Die App-Dateiangaben beziehen sich auf das oben benannte separate Repository.
Alle Regeln auf denselben Datenbestand beziehen: Anzeige und Sprache müssen
dieselbe Manöverbedeutung zeigen, dürfen aber unterschiedliche Detailmengen haben.

OSRM liefert strukturierte Manöver, keine fertige deutsche Sprachausgabe.
Sein [HTTP-Vertrag](https://github.com/Project-OSRM/osrm-backend/blob/v26.9.0/docs/http.md)
enthält auch Kreuzungen innerhalb eines Steps. Deshalb sind Steps und
Intersections gemeinsam zu untersuchen; eine Richtungsänderung ohne Step ist
nicht automatisch ein Datenverlust in der App.

Die [Profil-Schnittstelle](https://github.com/Project-OSRM/osrm-backend/blob/v26.9.0/docs/profiles.md#process_turn)
ordnet `process_turn` Gewicht und Dauer zu. Diese Funktion ist kein direkter
Schalter für „leicht links“ oder eine Textausgabe. Zugänglichkeit und
Klassifikation können Guidance indirekt beeinflussen, weshalb Profiländerungen
nicht mit reinen Ansagekorrekturen vermischt werden dürfen.

### Profil an Upstream annähern: was erhalten, was prüfen?

Der direkte Quellvergleich zeigt mehr als abweichende Geschwindigkeiten:

- Bewusste RadlNavi-Funktionen: `class:bicycle`-Kosten, saisonale Sperren,
  Treppen-/Schiebekosten, Ausschluss von Fähren, eigene Oberflächen-/Komfortwerte,
  Signal- und Hauptstraßenquerungskosten. Sie benötigen jeweils Produktentscheidung
  und Regression; sie sind nicht allein aufgrund ihres Alters überflüssig.
- `use_sidepath`: Upstream führt den Wert in der Zugangssperrliste; RadlNavi
  behält solche Fahrbahnen als eingeschränkte Kreuzungsmetadaten. Das ist ein
  absichtlicher Unterschied, relevant für die Hauptstraßenquerungstests.
- Upstream liest richtungsbezogene Zugangstags über `Tags`/`resolve_access`;
  der lokale allgemeine Access-Block nutzt `find_access_tag`. Diese Differenz
  gezielt mit Tags wie `vehicle:forward` untersuchen, nicht ungeprüft portieren.
- Unterschiedliche Barrierenbehandlung (Upstream Blacklist, lokal Whitelist),
  Signalverarbeitung, `highway=road`, Standardtempo (15 gegenüber 20 km/h),
  Oberflächen und Maximaltempo. Ein Austausch verändert Wegwahl und ETA.
- `use_turn_restrictions=true` ist lokal bereits vorhanden. Der entsprechende
  [Upstream-Fix in 26.9.0](https://github.com/Project-OSRM/osrm-backend/pull/7706)
  bedeutet nicht automatisch einen neuen Nutzen für dieses eigene Profil.

Zielbild: gepinnte Upstream-Basis plus kleine, nachvollziehbare Fachanpassungen
mit Begründung/Test je Abweichung. Nicht nur die gesamte alte Datei in eine
neue Basis kopieren. Vorher Funktionsunterschiede vollständig inventarisieren.

## Vergleichsplan vor Verhaltensänderungen

Ein öffentlicher OSRM-Autodemo-Server ist kein Fahrradvergleich. Der URL-Name
`bike` wählt keinen anderen vorverarbeiteten Graphen. Auch `variant=direct`
ist kein Upstream-Benchmark.

| Versuch | Engine | Profil | Zweck |
| --- | --- | --- | --- |
| P | Produktiv 26.6.5 | Produktivstand | Bereits gespeicherte Referenz; unbekannter PBF-Stand |
| A | 26.6.5 | Lokales RadlNavi-Profil | Reproduzierbare Ausgangslage |
| B | 26.9.0 | Dasselbe RadlNavi-Profil | Engine-Effekt isolieren, erforderliche API-Anpassungen protokollieren |
| C | 26.9.0 | Unverändertes `profiles/bicycle.lua` dieses Tags | Profil-Effekt gegenüber B isolieren |
| D | 26.9.0 | Upstream + begründete minimale RadlNavi-Anpassungen | Möglicher Zielzustand |

A–D benötigen **denselben PBF mit SHA256**, denselben Importstichtag
`RADLNAVI_ROUTING_DATE`, Algorithmus MLD, dokumentierte Build-Args sowie
Image-Digests, Profil- und Library-Hashes. P ist kein kausal sauberer A/B-Vergleich.
Das heutige Dockerfile akzeptiert nur `bike`/`direct`: Ein isolierter
Benchmark-Build für `/opt/bicycle.lua` muss erst vorbereitet werden.
Keine bestehenden Datensätze mit anderem OSRM-Image wiederverwenden.

Je Antwort identische Query-Parameter verwenden (die gespeicherten URLs dienen
als Vorlage). Erst Snapping und tatsächlich gewählten Korridor prüfen, dann
Manöver vergleichen. Bei abweichenden Routen Wegwahl und Guidance getrennt
bewerten. Zur Korridorprüfung zusätzliche Endpunkte vor/nach der Problemstelle
verwenden; keine erzwungenen Zwischenziele direkt auf den Abbiegungen, die
selbst `arrive/depart` erzeugen und das Resultat verfälschen.

Je A–D die Rohantwort mit folgenden App-Varianten abspielen: heutige Regeln;
ohne drei Geometrieheuristiken; danach jede Heuristik einzeln. Parser,
Zielzugang, Fortschritt, TTS und Sicherheits-/Recovery-Verhalten bleiben dabei
aktiv. Das ist eine Diagnoseoption, kein sofortiger Produktionsschalter.

Messgrößen: fehlende/zusätzliche entscheidungsrelevante Manöver, falsche Seite,
falscher Modifier, Anzahl unnötiger Ansagen, Doppelansagen und Vorlaufzeit.
Zusätzlich Route, Distanz, ETA, Komfort, Zugänglichkeit, Antwortzeit vergleichen.
Eine bloße Reduktion der Anzahl Ansagen ist kein Erfolgskriterium.

## Konkrete Aufträge für spätere LLM-Umsetzung

1. **Diagnose und Fixtures, ohne Produktänderung.** Gesicherte Antworten als
   Regressionseingaben übernehmen; App-Stand und Produktionsversion erneut
   feststellen. Roh-Step → Parser-Manöver → Projektion → Abschwächung →
   Ergänzung → Unterdrückung → Anzeige → TTS mit stabiler Leg-/Step-/Vorkommens-ID
   nachvollziehbar machen. Bei wiederholten Wegen keine Zuordnung nur anhand
   räumlicher Nähe. Kein pauschales Mitschreiben privater Nutzerrouten.
2. **Engine-/Profilvergleich A–C.** Reproduzierbaren Graphbuild und Bericht
   erstellen. Keine Ansagepatches während dieses Vergleichs. Bestehende Tests
   in `routing/tests/` und `routing/test_conditional_access.lua` verwenden.
   Insbesondere Zugang/Einbahn/Schieben, Seitenwegpflicht, Querungen,
   Komfortstrecken, Fähren/Treppen und Direktvariante schützen.
3. **App-Regeln gezielt reduzieren.** Zuerst Birketweg-Fixture im echten
   `VoiceGuidance` rot reproduzieren und Paarlöschung ursächlich begrenzen.
   Lenbachplatz als Diagnose-Fixture ergänzen und zunächst die berichtete
   „leicht rechts“-Ansage im App-HEAD reproduzieren. Im aktuellen Snapshot
   liegt der gemessene 12-m-Winkel außerhalb des Abschwächungsbereichs, während
   die bestehende Paarunterdrückung beide Manöver löschen würde. Roh-,
   Zwischen- und TTS-Ergebnis sichern. Nach Reproduktion verhindern, dass ein
   nahes Folge-`left` in das Winkelmaß des ersten Manövers eingeht. Erforderliche
   Topologieinformationen explizit modellieren, falls eine sichere
   Unterscheidung geometrisch nicht möglich ist. Balanstraße und
   Lautensackstraße nicht stillschweigend aus Tests entfernen. Nicht pauschal
   jedes `continue`, `slight` oder jede Folge <30 m stumm schalten.
4. **Verbleibende serverseitige Fehler beheben.** Wenn Schrammerstraße mit C/D
   korrekt ist, entsprechende minimale Profil-/Engineänderung übernehmen.
   Wenn sie weiterhin falsch ist, OSM-Netz/Tags prüfen und einen kleinen
   Upstream-Reproducer erstellen. Erst dann gemeinsame RadlNavi-Normalisierung
   erwägen. Roh-Steps erhalten, Zusatzdaten versioniert/optional anbieten;
   `distance`, `duration`, Geometrie, Leg-Grenzen und Annotationen konsistent
   halten. Keine widersprüchlichen server- und appseitigen Winkelkorrekturen.
5. **Präsentation und Fahrtest.** Waisenhausstraße als Fall für zurückhaltende
   Sprache prüfen. GPS-Replay mit Anfahrt deutlich vor dem ersten Manöver,
   mehreren Geschwindigkeiten, GPS-Schwankungen, Rerouting und Unterbrechungen;
   anschließend Telefon/Fahrt. Schrammerstraße/Birketweg müssen beide Aktionen
   rechtzeitig vermitteln. Profil D erst nach Routenregressionen freigeben.

Jeden Auftrag getrennt und reviewbar umsetzen. Vor jedem Schritt geltende
`AGENTS.md` lesen, lokale Änderungen erhalten und aktuelle HEADs dokumentieren.
Keine Änderungen allein anhand der hypothetischen Erwartungen dieser Analyse
als getestet melden. Bei der App laufende Flutter-/Telefon-Sitzungen beachten.

### Abnahmekriterien

- Birketweg: Links und danach rechts bleiben in Anzeige/Navigation vorhanden;
  zusammengesetzte Ansage rechtzeitig, keine zusätzlichen erfundenen Manöver.
- Lenbachplatz: mit demselben Request und App-Build die gemeldete Ansage
  reproduzieren; Ursache auf API, Geometriekorrektur oder Paarunterdrückung
  zurückführen. Danach rechts und das folgende Linksmanöver korrekt und
  eigenständig ankündigen.
- Schrammerstraße: echter Rechts-Links-Verlauf verständlich; zunächst mit
  aktuellem Graph/Topologie bestätigen. Nicht bloß `slight` zu `left` ersetzen
  und das fehlende Rechtsmanöver übersehen.
- Waisenhausstraße: bei bestätigtem eindeutigem Wegverlauf keine störende
  Richtungsansage; notwendige Wegwahl/Querung bleibt erkennbar.
- Gegenproben: echte nahe Doppelabbiegungen, harmlose Verschwenkung,
  ausgerundete Abzweigung mit vielen kleinen Segmenten, beide Fahrtrichtungen,
  `continue/left`, Kreisverkehr, Moduswechsel, Start/Zielnähe, Zwischenziele,
  Schleifen/doppelt befahrene Wege, Off-route/Recovery und TTS-Unterbrechung.
- App und Web behalten konsistente Richtungen; keine Regression bei Zugang,
  Komfortwahl, Direktvariante, ETA oder bestehendem Recovery-Verhalten.
- Rückfall: alte gepinnte Images **mit ihren passenden Graphen** vorhalten;
  App-Regeländerungen separat rücknehmbar. Keine kombinierte Großmigration.

## Grenzen und Reproduktion dieser Analyse

Die Live-Rohantworten sind gesichert. Der lokale Docker-Daemon war nicht
erreichbar; A–D wurden nicht gebaut. Der PBF der Produktion ist nicht aus der
Versionsantwort bestimmbar. Keine Flutter-Tests und kein Gerätetest ausgeführt,
keine OSM-Änderungen, kein Deployment. Die ursprüngliche Analyse erstellte
Dokumentation, Rohbelege und ein Offline-Diagnoseskript; anschließend wurde
die oben beschriebene Web-Prüfansicht ergänzt.

```powershell
python docs/osrm-standard-analysis/inspect_geometry.py
git diff --check
```

Das Skript wurde erfolgreich auf den vier gespeicherten Antworten ausgeführt.
Es verwendet eine lokale Meterprojektion und exakte Geometrieknoten für die
hier vorliegenden Manöver; es ist **kein allgemeiner App-Simulator**. Die
Schwellenprüfung am Birketweg liegt deutlich entfernt von Grenzwerten. Ein
echter Dart-Replay bleibt Teil von Auftrag 1/3.

Die frühere [Winkelanalyse](turn-instruction-analysis.md) bleibt als Hintergrund
nützlich. Ihre Empfehlung, zuerst die 12-m-Abschwächung zu bearbeiten, ist für
diese konkreten Fälle durch die vorliegenden Befunde zu präzisieren:
zuerst Paarlöschung und Rohmanöververgleich, kein vorschnelles größeres Winkelfenster.
