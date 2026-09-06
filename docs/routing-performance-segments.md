# Segmentzuordnung und Performance im RadlNavi

Stand: 6. September 2026. Lokale Implementierung auf Basis von `f05172e`.
Die direkte Route und ihre Infrastruktur sind nicht Teil dieser Änderung.

## Umsetzung

- SQL sucht zuerst eindeutige Weg-IDs. Jeder Weg wird je Anfrage nur einmal
  gelesen und sein JSON nur einmal dekodiert. Parameterlisten werden auf
  höchstens 900 Einträge bzw. das tatsächliche SQLite-Limit begrenzt.
- Ein Index über gerichtete benachbarte Knotenpaare hält Weg-ID, Kantenposition
  und Richtung fest. Geschlossene Wege und wiederholte Knoten gehen vollständig
  ein; die erste Fundstelle eines Knotens bestimmt nicht mehr die Zuordnung.
- Das Ergebnis ist eine geordnete Liste von Segmentvorkommen mit Leg- und
  Segmentindex. Lookup-IDs werden dedupliziert, Befahrungen niemals.
- Mehrere Vorkommen derselben Kante innerhalb desselben OSM-Weges haben dieselben
  verwendeten Tags. Konkurrieren unterschiedliche Wege, bleibt die Zuordnung
  unbewertet. Es gibt keine Bevorzugung anhand der SQL-Reihenfolge, des besseren
  Komfortwertes oder einer lediglich vermuteten Fortsetzung.
- Komfort, Untergrund und Beleuchtung verwenden dieselbe Zuordnung und dieselbe
  Länge. Geometrien für Hervorhebungen werden nur für die Detailantwort erzeugt.
- Zusammenhängende Abschnitte werden zusammengefasst. Getrennte Besuche desselben
  Weges erhalten getrennte LineStrings; es entsteht keine Verbindung über einen
  tatsächlich anderswo gefahrenen Umweg hinweg.
- Bei Knotenlisten wird die bisherige geodätische WGS84-Methode beibehalten.
  Ihre Koeffizienten und bereits berechnete Kantenlängen werden innerhalb einer
  Anfrage wiederverwendet. Es gibt keinen anfragenübergreifenden Cache und damit
  keine neue Invalidierungsabhängigkeit beim Austausch der Datenbank.

## Teilkanten und Zwischenhalte

Geprüft wurden der Quellcode der eingesetzten
[OSRM-Version 26.6.5](https://github.com/Project-OSRM/osrm-backend/blob/v26.6.5/include/engine/guidance/assemble_geometry.hpp)
und echte Antworten der öffentlichen RadlNavi-API. In dieser Version stehen
in `annotation.nodes` an den Rändern die begrenzenden OSM-Knoten. Die erste und
letzte Distanzannotation beschreiben jedoch bereits die tatsächlich gefahrenen
Teile dieser Kanten. Die Längenliste muss deshalb je Leg genau einen Eintrag
weniger als die Knotenliste haben. Der Adapter prüft zusätzlich die Summe gegen
die auf Dezimeter gerundete Leg-Distanz (Toleranz 0,2 m).

Die gespeicherte lange Beispielroute hat am 6. September **43.144 m**, drei Legs
und 524/458/965 Knoten. Sie unterscheidet sich damit etwas von der Messung am
5. September (43.193 m); daraus wird kein Geschwindigkeitsvergleich abgeleitet.
Zwei weitere gespeicherte Antworten prüfen einen Zwischenhalt auf derselben
Kante: vorwärts 35,5 m und mit Rückfahrt 53,4 m. Ein Zusammenfügen der Knotenlisten
kann dabei eine nicht gefahrene Rückkante erzeugen oder Teillängen verlieren.

Der vorhandene Endpunkt akzeptiert zusätzlich zur unveränderten Knotenliste
einen Kontext je Leg. Beispiel mit schematischen IDs und Längen:

```json
{
  "legs": [
    {
      "nodes": [1, 2],
      "distance": [20],
      "start": [11.50002, 48.1],
      "end": [11.50004, 48.1]
    },
    {
      "nodes": [1, 2],
      "distance": [30],
      "start": [11.50004, 48.1],
      "end": [11.50007, 48.1]
    }
  ]
}
```

`distance` wird unverändert aus OSRM übernommen, `start` und `end` aus den
gesnappten `waypoints[].location`, nicht aus den ursprünglich angeklickten
Koordinaten. Die Koordinatenreihenfolge ist Länge/Breite. Ungültige, negative oder
nicht endliche Distanzen und inkonsistente Arraylängen werden zurückgewiesen.
Ohne gesnappte Endpunkte werden bei vorhandenen Distanzannotationen die beiden
Randkanten nicht als vollständige Kanten hervorgehoben; die Kennzahlen verwenden
trotzdem die gelieferten korrekten Teillängen.

`/route` ergänzt `analysis_legs`, die Weboberfläche reicht diesen Kontext an
`/tag_distribution` weiter. Sie fällt bei älteren Backends auf `node_ids` zurück.
Der Proxy mit `comfort=true` verwendet denselben Kern und analysiert alle Legs
getrennt. Er entfernt intern ergänzte Annotationen auch bei Analysefehlern.
Anfragen ohne `comfort=true` bleiben ohne Analysearbeit.

## Bewusste Ergebniskorrekturen und Grenzen

Die Komfortformel und die Schwelle von 70 % bleiben gleich. Auf eindeutigen
Routen mit derselben Längenbasis prüft der Benchmark gleiche Komfortwerte,
Tag-Distanzen und Hervorhebungsgeometrien gegen die alte Implementierung.

Bei Schleifen, getrennten Wegbesuchen, Mehrdeutigkeiten und unbekannten Kanten
können sich Werte absichtlich ändern: künstliche Verbindungen und doppelt
gezählte Kandidaten entfallen; bekannte Längen unbekannter Abschnitte gehen
einmal in den unbewerteten Anteil ein. Die Version `segments-v2` kennzeichnet
diese Semantik. `distanceBasis` unterscheidet `node_geometry`, `osrm` und `mixed`.
OSRM verwendet eine andere Distanzmethode als die bisherige WGS84-Nachberechnung;
auch dadurch sind kleine Änderungen der gerundeten Kennzahlen möglich.

Fehlen Knoten und zugleich Distanzannotationen, ist ihre Länge nicht ermittelbar.
Solche Lücken werden nicht überbrückt. `analysis.distanceComplete=false` zeigt
die unvollständige Längenbasis; `totalDistance` umfasst dann nur bekannte Längen.
Der Komfort-Index bleibt verborgen. Das bisher numerische `coverage`-Feld wird
in diesem Fall konservativ auf 0 gesetzt, nicht aus den restlichen Fragmenten
als scheinbar vollständige Abdeckung berechnet.

Bei `node_ids` bedeutet `distanceComplete=true` nur, dass alle übergebenen
Knotenpaare messbar sind. Start, Ziel und Zwischenhalte innerhalb von Kanten
lassen sich aus diesem alten Format nicht rekonstruieren. Die bestehende App
profitiert von SQL-, Zuordnungs- und WGS84-Optimierung; exakte Teilkanten benötigen
auch dort später den Leg-Kontext. Die App wird in dieser Änderung nicht angepasst.

Die SQLite-Datenbank und der OSRM-Graph werden weiterhin unabhängig gebaut.
Mehrdeutigkeiten werden daher konservativ behandelt, nicht über vermeintlich
eindeutige Routing-Metadaten aufgelöst. Gemeinsame Datensnapshots, ein beim Import
erstellter Segmentindex, kompakte neue Endpunkte und die Lastisolation zwischen
Analyse und Routing bleiben weitere Schritte. Insbesondere enthält der Backend-
Event-Loop weiterhin synchrone HTTP-/SQLite-Arbeit. Die Optimierung verkürzt
diese Arbeit, garantiert aber keine unveränderte Routinglatenz unter Parallelzugriffen.

## Prüfung und Messung

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
backend/.venv/Scripts/python.exe backend/benchmarks/route_analysis.py --repeat 3
```

35 Backend-Tests decken die Komfortformel, SQL-Batches und Dekodierung, Schleifen
in beiden Richtungen, Wiederholungen innerhalb eines Weges, getrennte Besuche,
Teilstrecken eines Weges, Teilkanten, Zwischenhalte und Rückfahrt, Mehrdeutigkeiten,
fehlende Knoten mit/ohne Längen, leere Strecken, Validierungsfehler und den
optionalen Proxy mit unveränderten Navigationsdaten ab. Ein unabhängiger Zähler
prüft zusätzlich 30 deterministische Zufallsfahrten mit je 60 Kanten.

Der Frontend-Produktionsbuild besteht mit den bereits vorhandenen ESLint-
Warnungen. Der Container-Einstieg wurde auf `src.app:app` umgestellt und kopiert
den neuen Analysekern mit. Kein vollständiger Container-/PBF-Build oder
Produktionsdeployment wurde ausgeführt. Eine produktive `geo.db` liegt lokal
nicht vor; die gespeicherten Live-Antworten prüfen den Annotationsvertrag,
nicht die reale Segmentbewertung oder deren Produktionslaufzeit.

Die Offline-Messung verwendet dieselbe synthetische SQLite-Datenbank für den
Referenzcode aus `f05172e` und die neue Implementierung. Angegeben werden Mediane
aus drei Aufrufen je Fall, ohne OSRM, Netzwerk oder Produktionslast. Die
Distanzannotationen werden außerhalb der Messung vorbereitet, wie bei einer
bereits gelieferten OSRM-Route. Rohwerte:
[routing-performance-segments-benchmark.jsonl](routing-performance-segments-benchmark.jsonl).

| Routenknoten | Komfort vorher | Komfort neu, Knotenliste | Komfort neu, OSRM-Längen |
| ---: | ---: | ---: | ---: |
| 1.000 | 134 ms | 68 ms | 14 ms |
| 2.000 | 308 ms | 160 ms | 20 ms |
| 4.000 | 960 ms | 325 ms | 68 ms |
| 8.000 | 2.631 ms | 661 ms | 120 ms |

Bei 8.000 Knoten entspricht das etwa Faktor **4** für bestehende Knotenlisten
und Faktor **22** mit bereits gelieferten OSRM-Längen. Die vollständige
Detailberechnung sinkt in diesem Fall von 2.807 ms auf 747 ms bzw. 129 ms.
Das anschließende JSON-Encoding benötigt separat etwa 233 ms; die kompatible
Detailantwort umfasst weiterhin rund 688 kB unkomprimiert. Diese verbleibenden
Kosten sind ein Argument für einen späteren kompakten Analyse-Endpunkt.
Die Messungen sind keine End-to-End- oder p95-Aussage für die produktive App.

## Manueller Test durch Thomas

Nach Schließen des Browsers und zehn Minuten Pause wurden die getesteten Routen
in 1–2 Sekunden angezeigt, der Radl-Komfort nach etwa drei Sekunden. Auch beim
schnellen Verschieben von Start und Ziel wurden keine Fehler beobachtet; die
Routenverläufe erschienen unverändert. Dies ist ein positiver Alltagstest,
kein nachgewiesener Server-Kaltstart oder Test erzwungen verspäteter Antworten.

Beim allerersten Versuch wurde nach etwa einer Minute Sanduhr abgebrochen.
Möglicherweise lief zu diesem Zeitpunkt noch der Build; die Ursache ist nicht
nachgewiesen und der Hänger trat in den anschließenden Tests nicht erneut auf.
Zwischenhalte und Rückfahrten innerhalb einer Kante wurden automatisiert geprüft;
ein manueller App-Test mit lokalem Backend steht dafür noch aus. Das bestehende
Webfrontend benötigt für die Freigabe dieser Optimierung keine neue
Zwischenziel-Funktion.
