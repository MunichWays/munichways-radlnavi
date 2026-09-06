# Routing-Performance: Analyse und Architekturvorschlag

Stand: 5. September 2026. Status: Umsetzungsempfehlung, noch nicht implementiert.
Untersuchter Commit: `5254859041d8eaa693368a503e1e58f89b78e9cd`.

Ergänzt um die Flutter-App und eine reale 43,193-km-Route mit zwei
Zwischenzielen: [App-Befunde und Live-Messung](routing-performance-flutter-live.md).
Die API lieferte diese Route ohne Komfort in 0,22–0,24 Sekunden; der erste
Komfortabruf benötigte 15,46 Sekunden, direkte Wiederholungen etwa 1,1 Sekunden.
Als erster Migrationsschritt kann die App bereits den vorhandenen Endpunkt
`/tag_distribution` nach der Routenanzeige verwenden. Der neue kompakte
Analyse-Endpunkt folgt anschließend.

**Entscheidungsempfehlung**

Die Routenberechnung wird von der nachgelagerten Analyse getrennt. Eine Route
ist mit Geometrie, Distanz, Fahrzeit, Zwischenhalten und Abbiegehinweisen sofort
vollständig navigierbar. Analysefehler und fehlende Bewertungen verändern diese
Verfügbarkeit nicht. Zusätzlich wird die gemeinsame Wegzuordnung beschleunigt.
Nur neue Endpunkte einzuführen würde den größten algorithmischen Aufwand und
die Blockierung anderer Anfragen bestehen lassen.

Die sinnvolle fachliche Trennung lautet:

1. **Route:** alle Daten zum Anzeigen und Navigieren.
2. **Kompakte Analyse:** Komfort-Index und kleine Verteilungen nach Bewertung,
   Untergrund und Beleuchtung, ohne wiederholte Weggeometrien.
3. **Details:** farbige Routenabschnitte und Geometrien für Hervorhebungen.

Komfort und andere Kennzahlen erhalten unabhängige Anzeigezustände. Ihre
Berechnung sollte aber die teure gemeinsame Vorarbeit teilen. Für die heutige
Datenquelle sind die Untergrund- und Beleuchtungsbalken selbst kein Grund für
drei unabhängige Analyseläufe.

Die spätere direkte Route bekommt ein eigenes vorbereitetes OSRM-Profil und
eigene Routing-Kapazität. Beide Varianten verwenden denselben API-Vertrag,
dieselbe Navigation und dieselbe Komfortberechnung. Die Standardroute wartet
weder auf die direkte Route noch auf deren Analyse.

**Untersuchungsumfang und Aussagegrenzen**

Geprüft wurden das Python-Backend, die React-Weboberfläche, das Lua-Routingprofil,
die Datenbankerzeugung und die Deployment-Konfiguration im Repository. Ergänzend
wurde die Flutter-App unter `C:/Users/Thomas/dev/flutter/munich-ways-app`
einschließlich ihrer vorhandenen lokalen Änderungen gelesen. Ihr API-Aufruf,
Routing-Fallback und die Kopplung von Routenobjekt und Sprachführung sind jetzt
in der verlinkten Ergänzung dokumentiert. Ein Geräteprofiling fand nicht statt.

Die genannten 8 beziehungsweise 20 Sekunden sind Beobachtungen des Nutzers.
Die Ergänzung enthält eine kleine Messreihe an der produktiven öffentlichen API;
Cloud-Logs und tatsächlich ausgerollte Cloud-Run-Einstellungen wurden nicht
erhoben. Lokal fehlt die produktive `geo.db`. Der Benchmark unten verwendet
bewusst synthetische Daten und ist kein Nachweis, welcher Anteil der beobachteten
20 Sekunden auf eine bestimmte interne Funktion entfällt.
Der Vergleich mit Google Maps oder bRouter begründet das Nutzerziel, aber keinen
Wechsel der Routing-Engine ohne vergleichbare Messungen.

**Was der Code heute macht**

| Bereich | Befund | Konsequenz |
| --- | --- | --- |
| Web-Routing | `calculateRoute` setzt Route und Metadaten und startet anschließend `/tag_distribution`. | Die Route kann bereits vor dem Komfort-Index angezeigt und die Navigation gestartet werden. |
| App-kompatibler Proxy | `/route/v1/...?...&comfort=true` ruft nach OSRM synchron die Komfortanalyse auf und sendet erst anschließend die Antwort. | Die Flutter-App verwendet diese Option nachweislich und wartet auf Routing **plus** Analyse. Nach 20 Sekunden kann ihr Anbieter-Fallback zu BRouter greifen. |
| Fehlerbehandlung im Proxy | Ausnahmen der Komfortanalyse werden abgefangen und die gültige OSRM-Antwort zurückgegeben. | Ein gewisser Fehlerschutz besteht bereits. Die bis zur Ausnahme verstrichene Zeit bleibt; ein Client-Timeout kann trotzdem vorher eintreten. |
| Analyse | Komfort und `/tag_distribution` verwenden `retrieve_route_ways` und `route_way_distance`. | Ein Komfort-Endpunkt allein beseitigt diese gemeinsame Kostenstelle nicht. |
| Wegsuche | Für jedes aufeinanderfolgende Knotenpaar werden alle Kandidatenwege durchsucht; `in` und `index` durchsuchen zusätzlich deren Knotenlisten. | Mit mehr Routenknoten und Kandidatenwegen steigt die Arbeit überlinear. |
| SQL | Der Join liefert denselben Weg für mehrere getroffene Knoten erneut. Dessen JSON wird vor der Dictionary-Deduplizierung mehrfach geparst. | Vermeidbare Datenübertragung innerhalb des Prozesses, Allokation und JSON-Arbeit. |
| Distanzen | Geodätische Distanzen werden für die Wegabschnitte bei jeder Analyse neu berechnet. | Auch nach schnellerer Zuordnung bleibt relevanter Aufwand je Segment. |
| Details | `/tag_distribution` liefert Geometrien unter allen drei Tag-Gruppen. | Koordinaten werden mehrfach serialisiert, übertragen und im Frontend verarbeitet. |
| Nebenläufigkeit | `async def`-Handler enthalten blockierende `requests.get`, SQLite-Aufrufe und Python-Schleifen. Das Docker-Kommando startet Uvicorn ohne zusätzliche Worker. | Eine laufende Analyse oder ein wartender Upstream-Aufruf kann den Event-Loop dieses Prozesses und damit andere Anfragen blockieren. |
| Web-Zustände | Gemeinsamer Fortschrittsbalken; minimierte Analyseansicht verlangt alle drei Anzeigen. Fetches haben keine Request-Generation, Abbruchsteuerung oder Fehlerbehandlung. | Teilergebnisse werden teilweise verborgen; verspätete Antworten können Daten einer neueren Route überschreiben. |
| Zusatzrouting | `/route` fordert `alternatives=true` an, verwendet aber nur `routes[0]`. | Potenziell unnötige OSRM-Arbeit. Der tatsächliche Zeitgewinn durch Abschalten muss gemessen werden. |

Quellstellen: [Backend](../backend/src/app.py), insbesondere `osrm_route_proxy`,
`retrieve_ways_by_node_ids`, `retrieve_route_ways`, `route_way_distance`,
`tag_distribution` und `route`; [Weboberfläche](../frontend/src/App.tsx),
`analyzeRoute`, `calculateRoute` und die Analyseanzeige;
[Backend-Start](../backend/Dockerfile).

Für die Wegsuche ist ein grobes Kostenmodell `O(N × W × L)` hilfreich:
`N` Routensegmente, `W` Kandidatenwege und `L` Knoten je Kandidatenweg. Das ist
keine Aussage über die Komplexität des OSRM-Routings. Ein einmal aufgebauter
Index über benachbarte Knotenpaare reduziert die Zuordnung auf ungefähr
`O(S + N + Treffer)`, mit `S` als Summe der Knoten/Kanten aller Kandidatenwege.

Die Blockierung folgt aus der konkreten Verwendung synchroner Funktionen in
den Handlern. FastAPI führt normale `def`-Handler im Threadpool aus; direkt
aufgerufene Hilfsfunktionen werden dagegen nicht automatisch ausgelagert.
[FastAPI-Dokumentation](https://fastapi.tiangolo.com/async/#very-technical-details).

**Lokaler Nachweis des Optimierungspotenzials**

Reproduzierbar mit [route_analysis.py](../backend/benchmarks/route_analysis.py):

```powershell
backend/.venv/Scripts/python.exe backend/benchmarks/route_analysis.py
```

Python 3.12.1 unter Windows 11, SQLite im Speicher, zusammenhängende Route,
acht Kanten je Weg, Median aus drei Durchläufen je Messgröße. Beide Varianten
verwenden die tatsächlichen SQL-Lesefunktionen des Backends. Der Prototyp
ersetzt nur die Wegsuche durch einen pro Anfrage aufgebauten Knotenpaar-Index.
Für diese Fixtures werden identische Wegzuordnung und identischer Komfortwert
mit Assertions geprüft. Rohwerte: [Benchmark-Ergebnis](routing-performance-benchmark.json).

| Routenknoten | Kandidatenwege | Heutige Zuordnung inkl. SQL | Prototyp inkl. SQL und Indexaufbau |
| ---: | ---: | ---: | ---: |
| 1.000 | 125 | 47 ms | 21 ms |
| 2.000 | 250 | 130 ms | 23 ms |
| 4.000 | 500 | 548 ms | 67 ms |
| 8.000 | 1.000 | 1.805 ms | 132 ms |

Bei 8.000 Knoten sinkt die Zuordnungszeit hier etwa um Faktor 14. Die komplette
Komfortberechnung sinkt nur von etwa 2,71 auf 1,34 Sekunden: Distanzberechnung
und weitere Arbeit bleiben bestehen. Die abschließende Indexformel benötigt in
diesen Messungen nur 0,006 bis 0,012 Millisekunden. Die vollständige bisherige
Detailantwort umfasst bei 8.000 Knoten etwa 688 kB unkomprimiertes JSON.

Die Messblöcke laufen nacheinander; Systemlast und Allokationen beeinflussen
die Einzelwerte. Insbesondere ist die Differenz zwischen `all_tags_current_ms`
und `comfort_current_ms` kein sauber isolierter Preis der zusätzlichen Balken.
Gemessen wurden weder Netzwerk noch OSRM, Cold Starts, Browser-Rendering oder
Produktionsdaten. Routenknoten lassen sich nicht pauschal in Kilometer umrechnen.
Der Prototyp übernimmt die bestehende Weggruppierung und ist ausdrücklich noch
keine korrekte allgemeine Lösung für Schleifen und mehrdeutige OSM-Wege.

Die vorhandenen 13 Backend-Tests wurden erfolgreich ausgeführt. Sie prüfen
unter anderem Indexformel und API-Verhalten, sind aber kein Lasttest und decken
die folgenden Zuordnungsfälle noch nicht ausreichend ab.

**Beschleunigung und fachliche Korrektheit gemeinsam angehen**

Als erste Optimierung eindeutige Kandidatenwege bereits in SQL ermitteln,
beispielsweise über eine Unterabfrage auf eindeutige `way_id`, und ihre Tags
nur einmal dekodieren. SQL-Parameterlisten begrenzen beziehungsweise in Blöcken
abfragen. Lookup-IDs dürfen dedupliziert werden; die geordnete Route mit
Mehrfachbefahrungen darf es nicht.

Danach einen Index `(node_a, node_b) -> Kandidatenabschnitte` aufbauen. Seine
Einträge enthalten Weg-ID, Position im Weg und relevante Tags. Richtung und
Mehrdeutigkeiten müssen erhalten bleiben. Zwei OSM-Knoten identifizieren nicht
in jedem Fall eindeutig einen tatsächlich befahrenen OSM-Weg. Bei mehreren
Kandidaten muss eine belastbare Zuordnung über Routing-Metadaten oder zusätzliche
Kontextprüfung erfolgen; ungelöste Fälle bleiben unbewertet und werden nicht
mehrfach gezählt.

Das interne Ergebnis wird eine **geordnete Liste befahrener Segmentvorkommen**,
mit Leg- und Segmentindex, Länge, Bewertung, Untergrund und Beleuchtung. Darauf
werden alle Kennzahlen in einem Durchlauf aggregiert. Geometrien werden erst
für die Detailantwort aufgebaut. Damit lassen sich auch mehrere Besuche desselben
Weges korrekt und ohne künstliche Verbindung zwischen getrennten Abschnitten
abbilden.

Für dauerhaft kurze Analysezeiten empfiehlt sich anschließend ein beim
Kartenimport aufgebauter Segmentindex in SQLite mit kompakten Tag-Spalten und
vorberechneten Längen. SQLite muss dafür nicht durch einen anderen Datenbanktyp
ersetzt werden. Der Index verlagert Arbeit vom einzelnen Request zum Build;
zusätzliche Datenbankgröße, Importzeit und Speicherbedarf sind zu messen.
Routen sollen per Batch-Lookup analysiert werden, nicht mit einer SQL-Abfrage je
Segment.

OSRM-Distanzannotationen können die tatsächlich befahrenen Teillängen liefern,
wenn ihre Zuordnung zur Route im Adapter verifiziert ist. `annotation.nodes`
enthält laut Dokumentation nicht die ersten/letzten vom Nutzer angegebenen
Koordinaten. Ein blindes `zip(nodes, nodes[1:], distances)` darf daher nicht
ungeprüft eingeführt werden. Anfang, Ende und jeder Zwischenhalt innerhalb
einer Kante brauchen gezielte Tests mit der eingesetzten OSRM-Version.
[OSRM 26.6.5: Annotationen](https://github.com/Project-OSRM/osrm-backend/blob/v26.6.5/docs/http.md#annotation-object).

Heute entstehen darüber hinaus mögliche Bewertungsfehler:

- Fehlende Knoten werden vor der Paarbildung entfernt. Die verbleibenden Knoten
  dürfen dadurch nicht künstlich zu benachbarten Routenpunkten werden.
- Nicht zugeordnete Strecken verschwinden aus der bisherigen Gesamtdistanz der
  Analyse. Künftig müssen sie die unbewertete Strecke erhöhen. Die bewertete
  Abdeckung bezieht sich auf die gesamte tatsächlich befahrene Route.
- Getrennte Besuche desselben Wegs werden heute in einer einzigen Knotenliste
  gesammelt; die Distanzfunktion kann dadurch eine nicht befahrene Verbindung
  zwischen diesen Besuchen mitzählen.
- Leg-Grenzen müssen erhalten bleiben. Zwischenhalte, Schleifen und Rückwege
  dürfen weder künstliche Segmente noch verlorene Mehrfachbefahrungen erzeugen.

Die Formel bleibt fachlich einheitlich: Schwarz 0, Rot 35, Gelb 70, Grün 100;
Index über bewertete Länge, Anzeige ab 70 % bewerteter Gesamtlänge. Unbekannte
Abschnitte sind nicht automatisch schlecht bewertet. Korrekturen an der
Längenbasis können bisherige Ergebnisse trotzdem verändern und müssen separat
versioniert und anhand realer Routen erklärt werden.

**Schnittstelle: pragmatische, kompatible Einführung**

Für neue Clients bleibt die Routenanfrage OSRM-kompatibel, ohne `comfort=true`.
Sie fordert `steps=true`, alle benötigten Legs sowie zunächst
`annotations=nodes,distance` an. Nicht benötigte Alternativrouten werden nicht
angefordert. Der heutige Web-Wrapper `/route` unterstützt nur Start/Ziel und
übernimmt Hinweise und Annotationen aus dem ersten Leg; für Zwischenhalte ist
der allgemeine Proxy oder ein vollständiger Adapter erforderlich.

Für den ersten App-Schritt genügen `annotations=nodes` und der vorhandene
Endpunkt `/tag_distribution`, dessen `comfort`-Feld nachgelagert übernommen wird.
Das wurde mit der Beispielroute erfolgreich gegen die produktive API geprüft.
Dabei bleibt die größere Detailantwort vorerst bestehen. Ein Analyseupdate darf
in Flutter weder ein neues Routenereignis senden noch die von der Sprachführung
verwendete Routenidentität ersetzen; siehe die App-Ergänzung.

Ein neuer zustandsloser Endpunkt `POST /route_analysis` analysiert anschließend
**die bereits gelieferte Route**, nicht erneut Start und Ziel. Der vorgeschlagene
Vertrag enthält:

| Feld | Zweck |
| --- | --- |
| `requestId`, `routeId`, `variant` | Zuordnung im Client; `variant` ist `standard` oder später `direct`. |
| `routingDataVersion` | Identifiziert den zum Routing verwendeten Kartendatenstand. |
| `legs[]` | Unveränderte Reihenfolge mit Knotenannotationen, Distanzannotationen und Leg-Distanzen. |
| `geometry` und gesnappte Wegpunkte | Kontext für vollständige Anfangs-/Endsegmente und Prüfung der Segmentzuordnung. |
| `include` | Standard `comfort,summary`; optional `details` für Hervorhebungen. |

Der Server validiert Größen, Zahlen und die Konsistenz des Kontextes und bildet
aus dem tatsächlichen Inhalt einen Fingerabdruck. Eine frei gewählte Client-ID
ist kein vertrauenswürdiger Cache-Key. Im ersten Schritt wird der Kontext erneut
übertragen; das kostet Bandbreite, benötigt aber weder eine zusätzliche
Routenberechnung noch einen obligatorischen zentralen Routenspeicher.

Die kompakte Antwort enthält dieselben Zuordnungs-IDs, `analysisVersion`,
`analysisDataVersion`, den heutigen `comfort`-Wert sowie kleine Meter-/Prozent-
Verteilungen für Untergrund und Beleuchtung. Sie enthält keine `ways`-Geometrien.
`index=null` bei unzureichender Abdeckung bleibt ein erfolgreiches fachliches
Ergebnis; Analysefehler und Datenversionskonflikte bekommen eigene Zustände.

Die Detailantwort verwendet eine gemeinsame Segmentliste mit Tag-Attributen
oder Bereiche in der Routenlinie, statt dieselben Koordinaten dreimal unter
verschiedenen Tag-Gruppen zu liefern. Wenn die farbige Bewertungslinie wie heute
standardmäßig sichtbar sein soll, werden ihre Details nach der kompakten Analyse
mit niedriger Priorität geladen; zusätzliche Hervorhebungen können bei Bedarf
folgen. Die Grundroute bleibt währenddessen sichtbar.

Bestehende Clients mit `comfort=true` und `/tag_distribution` bleiben kompatibel.
Diese Endpunkte verwenden intern denselben optimierten Analysekern. Der alte
Komfort-Proxy wartet weiterhin für seinen Aufrufer auf die Analyse; erst die
Client-Migration beseitigt dessen Warteabhängigkeit. Im bestehenden Proxy müssen
zugleich Timeouts, Fehlerfallback und das Entfernen nur intern benötigter
Annotationen auch im Fehlerfall konsistent bleiben.

Für den ersten Ausbau genügen normale unabhängige HTTP-Anfragen. SSE,
WebSockets oder eine Job-Queue bringen für das Nachladen einzelner kleiner
Ergebnisse zunächst mehr Zustands- und Betriebsaufwand. Bei späterem Bedarf
an besonders kleinen mobilen Requests kann `routeId` auf einen kurzlebigen
gemeinsamen Routenspeicher verweisen; das ist eine spätere Optimierung.

**Backend-Ausführung und Lastisolation**

Routing-HTTP und Tokenbeschaffung dürfen den Event-Loop nicht blockieren.
Empfohlen sind ein langlebiger asynchroner HTTP-Client mit Connection-Pooling,
getrennten Verbindungs-/Antwortzeitlimits und eine wiederverwendete, bis kurz vor
Ablauf gültige Authentifizierung. Blockierende Authentifizierungsarbeit wird
ausgelagert. CPU-lastige Analyse erhält begrenzte Ausführungskapazität außerhalb
des Routing-Event-Loops.

Ein Wechsel zu `def` oder Thread-Auslagerung erfordert neue SQLite-Verbindungen
im ausführenden Thread; die bisher im Lifespan angelegte globale Verbindung
darf nicht einfach weitergereicht werden. Python aktiviert standardmäßig
`check_same_thread=True`.
[SQLite-Dokumentation](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.connect).

Threads allein garantieren keine CPU-Isolation. Für die Anforderung, dass
Analysen die Standardroute auch bei Parallelzugriffen nicht verzögern, empfehle
ich eine separat skalierbare Analyse-Instanz beziehungsweise einen separaten
Cloud-Run-Service mit demselben Analysekern. Der öffentliche API-Zugang kann
gleich bleiben. Auch alte `comfort=true`-Anfragen warten dann asynchron auf
diesen Dienst und blockieren nicht den Routing-Event-Loop.

Konfiguriert sind im Repository für die API 1 vCPU, 512 MiB, maximal zwei
Instanzen und Concurrency 20; für OSRM 1 vCPU, 2 GiB, maximal eine Instanz und
Concurrency 20. Beide haben `min-instances=0`. Diese Grenzen sind kein Nachweis
der aktuellen Live-Konfiguration. Concurrency 20 erzeugt keine 20 unabhängig
verfügbaren CPU-Kerne; bei erschöpfter Kapazität entstehen Warteschlangen.
[Deployment API](../cloudbuild-api.yaml),
[Deployment OSRM](../routing/cloudbuild.yaml),
[Cloud Run: Concurrency](https://docs.cloud.google.com/run/docs/about-concurrency).

Cold Starts müssen getrennt von warmen Routen gemessen werden. Für ein
verlässliches Ziel von wenigen Sekunden ist nach dieser Messung mindestens
eine warme Standard-Routing- und API-Instanz zu erwägen; das verursacht laufende
Kosten. Ein reines Hochsetzen der Concurrency ist keine Latenzlösung.
[Cloud Run: Minimum instances](https://docs.cloud.google.com/run/docs/configuring/min-instances).

Die Live-Messung zeigt einen langsamen ersten Analyseabruf trotz vorheriger
schneller Routenabrufe. Zusätzlich zur allgemeinen Instanzbereitschaft deshalb
den Zustand der Analysedatenbank und ihrer Dateisystemseiten instrumentieren.
Die Messung allein beweist weder einen Cold Start noch eine bestimmte
Cache-Ursache. Eine warme Routing-Instanz garantiert keine warmen Analysedaten.

**Datenstände und Caches**

API-Datenbank und Routinggraph laden heute unabhängig `oberbayern-latest.osm.pbf`.
Routing wird zusätzlich wöchentlich gebaut. Damit können Graph und Analyse
verschiedene OSM-Stände verwenden. Ein Git-Commit beziehungsweise die gemeldete
Routing-Version identifiziert die verwendete PBF-Datei nicht zuverlässig.

Künftig einen unveränderlichen PBF-Snapshot samt Prüfsumme als gemeinsame Quelle
für beide Profile und den Analyseindex verwenden. `routingDataVersion`,
Profilversion und Analyseversion in Antworten und interner Verarbeitung
mitführen. Während des Rollouts kompatible alte Analysedaten vorhalten oder
explizit „Analyse für diese Datenversion nicht verfügbar“ zurückgeben; die Route
bleibt nutzbar.

Begrenzte Caches können die gemeinsame Segmentzuordnung für Summary und Details
sowie identische Streckenabschnitte beider Varianten wiederverwenden. Schlüssel
berücksichtigen geordnete Legs, Richtung, Teilkanten, Geometrie-/Routenfingerabdruck,
Datenstand und Analyseversion. Ein Routencache benötigt zusätzlich Profil,
Wegpunkte und alle routenrelevanten Optionen. OSRM-Snapping-Hints dürfen nicht
ungeprüft zwischen Profilen oder Graphversionen übernommen werden.

Ein Prozesscache ist nur eine Optimierung: Bei mehreren Cloud-Run-Instanzen ist
ein Treffer nicht garantiert. Ein Miss wird korrekt neu aus dem übergebenen
Routenkontext analysiert. Erst wenn die Messung wiederholte Analysen als relevante
Kostenstelle zeigt, einen gemeinsamen Cache ergänzen. Gleichzeitige identische
Arbeit begrenzen; TTL und Speicherobergrenzen festlegen. Ein Cache ersetzt die
algorithmische Verbesserung nicht.

**App und Web: unabhängige Ergebnisse, gemeinsame Navigation**

Je Routenvariante gibt es einen vollständigen Routendatensatz und getrennte
Zustände für Routing, kompakte Analyse und Details. Mögliche Analysezustände:
`idle`, `loading`, `ready`, `error`. Niedrige Bewertungsabdeckung ist ein
`ready`-Ergebnis und kein Netzwerkfehler.

In Flutter sind Schutz gegen veraltete Routingantworten und eine Planrevision
bereits vorhanden. Diese auf Metadatenanfragen erweitern. `VoiceGuidance.setRoute`
erkennt einen Wechsel derzeit anhand der Objektidentität; Metadaten deshalb zur
stabilen Route ergänzen und vom Ereignis einer neuen Navigationsroute trennen.

Bei jeder Änderung von Start, Ziel, Zwischenhalten oder einer Neuberechnung wird
eine Request-Generation erhöht. Ergebnisse werden nur übernommen, wenn
Generation, Variante und Route noch passen. Alte Requests werden nach Möglichkeit
abgebrochen; der Generationstest bleibt nötig, weil ein Abbruch bereits laufende
Serverarbeit nicht zuverlässig beendet. Gleiches gilt für verzögerte Debounce-
Aufrufe.

Die Oberfläche zeigt zuerst Route, Fahrzeit, Distanz und Navigation. Beim
Komfort-Index steht anfangs „Wird berechnet …“, bei Fehler „Derzeit nicht
verfügbar“ mit Wiederholen nur für die Analyse. Es gibt keinen endlosen globalen
Routing-Ladebalken wegen fehlender Beleuchtungsdaten. Die minimierte Ansicht
wartet ebenfalls nicht mehr auf sämtliche Analysekomponenten.

**Die direkte Route vorbereiten**

Arbeitsannahme für „direkt“: eine möglichst kurze, praktikabel befahrbare
Verbindung ohne zusätzlichen Komfortbonus. Vor Umsetzung ist festzulegen, ob
primär **Distanz** oder **Fahrzeit** minimiert werden soll. Das ist eine
fachliche Profilentscheidung und keine Frontend-Einstellung mit identischem
Graph. „Direkt“ bedeutet nicht Luftlinie.

Das vorhandene Profil enthält Komfortfaktoren, Nebenwegpräferenzen und
Abbiegegewichtungen. Insbesondere werden am Ende von `process_way` eigene
`forward_rate`/`backward_rate` gesetzt. Nur `weight_name` umzubenennen reicht
daher nicht aus. Bei einer Distanzgewichtung müssen außerdem Einheiten und
Skalierung der Abbiegegewichte zusammenpassen.
[Routingprofil](../routing/bike.lua).

Gemeinsame Regeln für Befahrbarkeit, Einbahnstraßen, Abbiegeverbote,
Baustellen/zeitliche Einschränkungen und explizite Sicherheitsentscheidungen
werden in gemeinsam genutzte Profilbausteine ausgelagert. Die beiden Varianten
unterscheiden sich kontrolliert im Optimierungsziel. Eine Komfortpräferenz darf
entfallen, ohne dass dabei versehentlich eine Ausschlussregel entfällt.

OSRM legt das Profil bei der Datenvorbereitung fest. Eine andere Zeichenfolge
im URL-Pfad oder `alternatives=true` erzeugt kein zweites Optimierungsziel.
Für die geplante Lösung werden zwei Graphen aus demselben PBF-Snapshot aufgebaut
und über getrennte OSRM-Dienste hinter einer expliziten Variantenzuordnung der
API angeboten.
[OSRM 26.6.5: Profile und Routenoptionen](https://github.com/Project-OSRM/osrm-backend/blob/v26.6.5/docs/http.md).

Empfohlener Ablauf:

```mermaid
sequenceDiagram
    participant C as App / Web
    participant R as Routing-API
    participant S as OSRM Standard
    participant D as OSRM Direkt
    participant A as Analyse
    C->>R: Standardroute, alle Wegpunkte
    R->>S: Routing mit Hinweisen und Annotationen
    S-->>R: Vollständige Route
    R-->>C: Standardroute
    Note over C: Anzeigen und Navigation ermöglichen
    par Kennzahlen zur Standardroute
        C->>A: Exakten Routenkontext analysieren
        A-->>C: Komfort und kompakte Verteilungen
    and Zweite Variante nachladen
        C->>R: Direkte Route, dieselben Wegpunkte
        R->>D: Routing mit demselben Antwortvertrag
        D-->>R: Vollständige direkte Route
        R-->>C: Direkte Route
        C->>A: Exakten direkten Routenkontext analysieren
        A-->>C: Komfort und kompakte Verteilungen
    end
    Note over C,A: Details nachrangig laden; Analyse ist logisch separat, öffentliche URL kann gleich bleiben
```

Die zweite Routenanfrage startet standardmäßig nach Anzeige der Standardroute.
Damit entstehen beim ersten Routing keine zusätzlichen Antwortdaten oder
Upstream-Abhängigkeiten. Eigene OSRM-Kapazität für „direkt“ schützt auch spätere
Standardanfragen anderer Nutzer. Die Analyse begrenzt parallele Arbeit und
bevorzugt Kennzahlen der aktuell gewählten Route gegenüber Details und
Analysen der inaktiven Variante. Eine starre Bevorzugung von „standard“ bei der
Navigation wäre falsch: Neuberechnungen der aktiv navigierten Variante haben
Vorrang vor Hintergrundarbeit.

Beide Varianten enthalten sämtliche Legs, Manöver und Navigationseigenschaften;
kein verkürztes GPX-/Linienformat für die direkte Route. Die Navigation liest
aus `activeRouteId`. In der Planung wechselt die Auswahl auf bereits geladene
Daten ohne neue Routenanfrage. Bei identischen Verläufen darf „beide gleich“
angezeigt und die Analyse wiederverwendet werden.

Während der Navigation muss ein Wechsel die aktuelle Position und die noch
offenen Zwischenhalte berücksichtigen. Eine alte Alternativroute ab dem
ursprünglichen Start ist nicht automatisch eine gültige aktuelle Route.
Gegebenenfalls wird die gewählte Variante ab der aktuellen Position neu
berechnet; die bisherige Navigation bleibt bis dahin aktiv. Fortschritt,
nächste Hinweise und ausstehende Ansagen werden beim atomaren Wechsel passend
zur neuen Route aktualisiert. Neuberechnung behält die aktive Variante bei.
Funktionsgleichheit einschließlich Ansage muss in der separaten App geprüft
werden. Der ergänzend geprüfte App-Code bietet dafür gemeinsame RadlNavi-
Manöververarbeitung und Sprachführung. Die heutige direkte/kürzeste Auswahl
berechnet dagegen über BRouter neu und liefert in dieser Implementierung weder
Manöver-Sprachausgabe noch Komfort. Sie ist noch keine gleichwertige zweite
RadlNavi-Variante.

Eigene Dienste bedeuten zusätzliche Graphspeicherung, Buildzeit, Deployment und
gegebenenfalls laufende Warmhaltekosten. Ohne zusätzliche Kapazität kann
Nachladen zwar die Warteabhängigkeit entfernen, aber keine unveränderte
Standardlatenz unter gleichzeitiger Last garantieren.

**Umsetzungsreihenfolge und Abnahme**

| Schritt | Konkreter Lieferumfang | Abnahme |
| --- | --- | --- |
| 1. Messbasis | Serverzeiten für Auth, OSRM, SQL, Zuordnung, Länge, Aggregation und Serialisierung; Clientzeiten für Route sichtbar, Navigation bereit, Komfort sichtbar und Details sichtbar. | Reproduzierbare kurze, mittlere und 30–40-km-Routen mit 0, 2 und 5 Zwischenhalten; warm/kalt getrennt. |
| 2. Schnelle Entkopplung | Zuerst App-Migration weg von `comfort=true` mit nachgelagertem bestehendem `/tag_distribution`; anschließend kompakte Analyse-API. Unabhängige Zustände, Generation/Abbruch/Fehlerbehandlung; ungenutzte Alternativen im Web-Wrapper abschalten. Blockierende Backend-Ausführung beheben und Analysekapazität abgrenzen. | Route und Navigation funktionieren bei verzögerter/fehlgeschlagener Analyse; alte Antworten überschreiben keine neue Route; Metadaten lösen keinen Navigationsreset oder Anbieterwechsel aus. |
| 3. Analysekern | SQL-Deduplizierung, Knotenpaar-Index, geordnete Segmentvorkommen, gemeinsame Aggregation und getrennte Details. | Vergleich mit bisherigen Werten auf unproblematischen Routen; korrekte Ergebnisse für fehlende/mehrdeutige Knoten, Schleifen, Rückwege, Teilkanten und Zwischenhalte. |
| 4. Daten und Dauerleistung | Gemeinsamer versionierter Snapshot; vorberechnete Segmente/Längen; begrenzte Caches nach Messung; Warmhaltung/Skalierung abstimmen. | Versionswechsel und Cache-Miss funktionieren; Speicher und p95 unter Last innerhalb vereinbarter Grenzen. |
| 5. Direkte Variante | Gemeinsame Profilbasis, eigener Graph/Dienst, identischer Routenvertrag, variantensichere Navigation und Vergleichsanzeige. | Funktionsgleichheit bei Hinweisen, Ansage, Neuberechnung und Komfort; Standardlatenz im A/B-Lasttest unverändert innerhalb der Messtoleranz. |

Zielwerte als **vorgeschlagene Abnahmekriterien**, nicht als bereits erreichte
oder zugesicherte Produktionswerte:

- Warme Route einschließlich Navigationsdaten: p95 höchstens 3 Sekunden für
  das vereinbarte München-Testset, inklusive 30–40 km mit Zwischenhalten.
- Kompakte Analyse: p95 höchstens 1 Sekunde zusätzliche Zeit ab ihrer Anfrage.
- Auswahl einer bereits geladenen, noch gültigen Variante in der Planung:
  sichtbar innerhalb von 100 ms auf den vereinbarten Referenzgeräten.
- Hintergrundanalyse und direkte Variante: kein systematischer Anstieg der
  Standard-p95; zunächst 5 % als Mess-/Regressionstoleranz im kontrollierten
  A/B-Test ansetzen. Das ist keine Erlaubnis, die Standardroute absichtlich
  später zu liefern.

Für eine belastbare p95-Auswertung mindestens 100 Beobachtungen pro relevanter
Testgruppe in einer Staging-Umgebung erheben; Cache-Hits und -Misses ausweisen.
Mit derselben Standardanfragelast jeweils ohne und mit Analysen/direkter Route
messen. Parallelität stufenweise erhöhen, beispielsweise 1, 5 und 20 laufende
Requests, und Warteschlangen, Fehler, Event-Loop-Verzögerung und CPU/RAM erfassen.
Cold-Start-Ziele separat festlegen. Browser-/App-Netzwerkprofile und Endgeräte
festhalten; keine unkontrollierten Lasttests auf Produktion.

Zusätzliche Fehlertests: Analyse-Timeout/500, niedrige Abdeckung, Datenversions-
wechsel, geänderte Zwischenhalte während einer Anfrage, Variantenwechsel bei
laufender Analyse, nicht verfügbare direkte Route und Neuberechnung während
der Navigation. API-Abwärtskompatibilität und bestehende Routingregressionen
für die Standardroute bleiben Teil der Abnahme.

**Abgewogene Alternativen**

| Alternative | Bewertung |
| --- | --- |
| Nur Komfort in eigenen Endpunkt verschieben | Verbessert die erste Antwort für migrierte Clients; gemeinsame teure Suche und gegenseitige Blockierung bleiben. Als alleinige Lösung unzureichend. |
| Komfort, Untergrund und Beleuchtung jeweils separat berechnen | Für die heutige gemeinsame Datenquelle unnötige Wiederholung. Besser ein kompakter gemeinsamer Durchlauf mit unabhängig nutzbaren Feldern. |
| Nur mehr Instanzen oder höhere Concurrency | Kann Warteschlangen beeinflussen; löst das überlineare Verfahren und die Payload-Größe nicht. Kapazität anhand Messungen ergänzen. |
| Nur Cache | Hilft bei wiederholten Routen; lange neue Routen und Neuberechnungen bleiben teuer. |
| Direkte Route als heutige OSRM-Alternative | Optimiert weiterhin dasselbe Profil und erfüllt damit die fachliche Anforderung nicht. |
| Beide Varianten auf demselben einzelnen OSRM-Dienst parallel berechnen | Zusätzliche Konkurrenz um die vorhandene CPU; keine belastbare Zusage für unveränderte Standardlatenz. |
| Routing-Engine austauschen | Gegenwärtig keine Evidenz, dass OSRM selbst die beobachtete Hauptwartezeit verursacht. Erst den gemessenen Routenkern beurteilen, nachdem Analyse und Infrastruktur getrennt sichtbar sind. |
