# Fahrminuten und Ladezeit der Direkt-Route

Nachtrag zur anschließenden Umsetzung: Die unten empfohlene Header-Ergänzung
ist inzwischen lokal in Backend 2.3.2 und im App-Branch
`233-b65_app-direkte-route-von-radlnavi-verwenden` implementiert. Der
Untersuchungsstand im folgenden Text bleibt als Grundlage erhalten.
`x-direct-api-url` wird bei erfolgreichen Standard-Routen mit der öffentlichen
Direkt-URL geliefert und über CORS exponiert. Ein leerer Header entfernt die
gemerkte URL; ein fehlender Header erhält die Kompatibilität mit älteren APIs.
Ungültige Werte beeinträchtigen Standard nicht und führen zur bisherigen
Discovery zurück. Neuere Header dürfen nicht von älteren, noch laufenden
Discovery-Antworten überschrieben werden. Komfortdaten bereits berechneter
Routen bleiben an ihren ursprünglichen Endpunkt gebunden.

Prüfung der Umsetzung: Flutter-Analyse ohne Befund; 55 fokussierte App-Tests
für API, Komfort, Routing-Fallback, Varianten und Navigationserholung bestanden;
29 Backend-Tests aus `test_app.py` und `test_direct_routing.py` bestanden.
Die App bleibt auf dem bereits vorbereiteten Build 3.1.23+65. Kein Commit,
Push oder Deployment. Für die Header-Ergänzung ist ein Backend-Deployment
erforderlich; sie benötigt keinen Routing-Graph-Neubau. Die davon getrennte
Profilkorrektur gegen übermäßiges Schieben benötigt diesen Neubau weiterhin.

Untersuchung vom 12.09.2026 in RadlNavi, App und Produktion. Ziel ist die
Ursachentrennung vor weiteren Laufzeitänderungen. Die vorhandene, noch nicht
veröffentlichte Profilkorrektur auf `fix/bicycle-oneway-pushing` wurde für einen
zusätzlichen lokalen Vergleich verwendet. In dieser Untersuchung wurden keine
App- oder Backend-Laufzeitänderungen und keine Deployments vorgenommen.

## Ergebnis

Die App zeigt die von RadlNavi gelieferten Sekunden korrekt als Minuten an.
Auf den untersuchten produktiven Direkt-Routen erklärt ein großer Schiebeanteil
die auffällig langen Fahrzeiten. Das bereits vorbereitete Routing-Profil 2.3.2
beseitigt das Problem auf beiden kurzen Münchner Beispielen, ohne die
Minutenberechnung zu verändern.

Daneben besteht eine vermeidbare Wartekette beim erstmaligen Laden von Direkt:
Die App beginnt die Standard-Komfortanalyse vor der Direkt-Verfügbarkeitsabfrage.
Die synchrone Analyse blockiert im Backend auch diese kleine Abfrage. Ihre
Antwortzeiten überschreiten in Produktionslogs teilweise die drei Sekunden,
die die App dafür erlaubt. Ein solcher Timeout löst BRouter als Ersatz aus.
Ob genau dieser Rückfall beim gemeldeten App-Test auftrat, ist ohne die
entsprechenden App-Logs nicht abschließend belegt.

## Produktionsstand und Messung

Abgefragt wurden die Standard-API `https://api.radlnavi.munichways.de` und die
dort unter `/routing_variants` veröffentlichte Direkt-API
`https://munichways-radlnavi-direct-api-melvpv5saa-ey.a.run.app`.
Beide `/version`-Antworten meldeten:

* Backend 2.3.1, Commit `d1d662958d90826ae0ec6cf17547cebc20c4fecd`.
* Routing 2.3.1, Commit `6c2fdbb2412fb677f628d48bdbcb824be3985d5c`.
* OSRM 26.6.5.

Die vorbereitete Routing-Version 2.3.2 ist damit noch nicht produktiv.
Die bestehenden Performanceänderungen von Backend 2.3.1 sind laut gemeldetem
Versionsstand auf beiden APIs vorhanden.

Verwendete Punkte in Reihenfolge Breite/Länge:

* Arnulfstraße: `[48.142131, 11.554569]` → `[48.141745, 11.562248]`.
* Lenbachplatz: `[48.140805, 11.565394]` → `[48.141976, 11.571082]`.
* Lange Route mit zwei Zwischenzielen: `[48.156304, 11.540013]` →
  `[48.102548, 11.568796]` → `[48.120477, 11.655645]` →
  `[47.991860, 11.828568]`.

Requests entsprachen der App: `/route/v1/bike/...`, `variant`, `steps=true`,
`geometries=geojson`, `overview=full`, `alternatives=false`,
`continue_straight=default`. Zu `annotations=nodes,distance` kam für die
Diagnose `duration` hinzu. Einzelne Requests wurden nacheinander ausgeführt;
dies war kein Lasttest. Antwortzeit ist einschließlich HTTP-Übertragung vom
Entwicklungsrechner gemessen, nicht isolierte Server-Rechenzeit.

| Strecke | Variante | Länge | Fahrzeit | Schiebeabschnitte | Erste Antwort / Wiederholung |
| --- | --- | ---: | ---: | ---: | ---: |
| Arnulfstraße | Standard | 0,707 km | 2,70 min | 0 m | 0,245 / 0,213 s |
| Arnulfstraße | Direkt | 0,655 km | 8,48 min | 405 m | 15,367 / 0,232 s |
| Lenbachplatz | Standard | 0,532 km | 3,09 min | 0 m | 0,208 / 0,201 s |
| Lenbachplatz | Direkt | 0,509 km | 8,05 min | 448 m | 0,177 / 0,168 s |
| Lange Route | Standard | 43,144 km | 157,99 min | 117 m | 0,361 / 0,320 s |
| Lange Route | Direkt | 37,198 km | 227,36 min | 5.642 m | 0,352 / 0,287 s |

Auf der langen Direkt-Route entfallen 89,48 Minuten auf Steps mit Modus
`pushing bike`; diese Step-Dauern enthalten auch Manöververzögerungen.
Das ist kein Effekt einer Sekunden-/Minutenverwechslung.

Die erste Direkt-Antwort war deutlich langsamer als die unmittelbare
Wiederholung. Das passt zu Start-/Aufwärmkosten der getrennten Dienste;
die Messung allein zerlegt diese 15,367 Sekunden nicht in API-Start,
Routing-Start und weitere Wartezeiten. Die warmen Messungen belegen keine
generelle, längenabhängige Langsamkeit des Direkt-Routings gegenüber Standard.

## Datenfluss der Fahrzeit

App-Pfade beziehen sich auf `C:/Users/Thomas/dev/flutter/munich-ways-app`.

1. `lib/api/radlnavi_api.dart`, `route()`: Übernimmt `routes[0].duration`
   unverändert als `double` in `CycleRoute`; `weight` wird nicht als Fahrzeit
   verwendet.
2. `lib/ui/map/map_overlay/route_variant_comparison.dart`: Zeigt
   `(route.duration / 60).round()` an. Auch der Navigationskopf teilt durch 60.
3. `lib/ui/map/map_screen_model.dart`, `_loadRouteComfort()`: Ergänzt ausschließlich
   Komfortdaten am bestehenden Routenobjekt; es erfolgt keine Neuberechnung
   der Fahrzeit anhand von Komfort oder unbewertetem Streckenanteil.
4. `routing/bike.lua` und `routing/direct.lua`: Komfortbewertungen beeinflussen
   Routengewichte. Direkt behält Geschwindigkeiten und Abbiegeverzögerungen für
   die ETA. Schieben ist langsam und wurde im produktiven Direkt-Profil bisher
   bei der Streckenauswahl zu wenig vermieden. Die implizite Wiederöffnung von
   Einbahn-Gegenrichtungen als Schiebeverbindung verstärkt das Problem.

Unbewertete Strecken werden nicht direkt in zusätzliche Fahrminuten umgerechnet.
Bewertung und Wegart können mittelbar die gewählte Strecke und damit ihre
Geschwindigkeiten verändern. Auch eine korrekt berechnete kürzere Route kann
wegen langsameren Wegen oder mehr Abbiegeverzögerungen länger dauern.

Zusätzlicher Vergleichseffekt: `lib/api/brouter_api.dart` schätzt bei BRouter
`shortest` die Dauer pauschal mit 16 km/h. RadlNavi verwendet abschnittsabhängige
Geschwindigkeiten, Schiebemodi und Abbiegeverzögerungen. Ein Providerwechsel
kann deshalb auch bei ähnlicher Länge die Minuten deutlich verändern. Der
Planer kennzeichnet diesen Ersatz als „BRouter · ohne Abbiegeansagen“.

## Gegenprobe mit vorbereitetem Profil 2.3.2

Die beiden Profile wurden mit dem eingefrorenen Münchner OSM-Ausschnitt unter
`routing/tests/fixtures/munich-oneway.osm` neu extrahiert, partitioniert und
angepasst. Zwei kurzlebige OSRM-Container wurden anschließend wieder entfernt.
Die Gegenrichtungs- und Schieberegeln sind in `oneway-pushing-qa.md` beschrieben.

| Strecke | Standard lokal | Direkt lokal | Schieben Direkt |
| --- | ---: | ---: | ---: |
| Arnulfstraße | 707,4 m / 2,70 min | 661,6 m / 2,24 min | 0 m |
| Lenbachplatz | 532,5 m / 3,09 min | 532,5 m / 3,09 min | 0 m |

Die Standardwerte entsprechen auf diesen Beispielen weiterhin den produktiven
Werten. Direkt benötigt keine künstliche ETA-Korrektur. Der OSM-Ausschnitt ist
vom 11.09.2026 und nicht derselbe PBF-Stand wie Produktion. Die lange Route
liegt außerhalb dieses kleinen Ausschnitts und wurde mit Profil 2.3.2 noch
nicht nachgemessen; dafür ist der vollständige Routing-Neubau erforderlich.

## Vermeidbare Wartekette beim ersten Direkt-Aufruf

Der App-Code startet die Alternative erst, wenn die angeforderte Route
verwendbar ist. Für den Standardfall ergibt sich:

1. `_calculateVariant()` setzt Standard auf `SHOWN` und startet sofort
   `_loadRouteComfort()` ohne darauf zu warten.
2. Nach Rückkehr startet `_requestRoute()` die Direkt-Alternative.
3. Beim ersten Direkt-Aufruf lädt `RadlNaviApi._discoverDirect()` die öffentliche
   Basis-URL über `/routing_variants` von der **Standard-API**. Timeout: 3 s.
4. `backend/src/app.py`, `tag_distribution()` ist zwar `async def`, ruft aber
   `analyze_route()` mit synchronen SQLite-Abfragen und JSON-Verarbeitung auf.
   Der einzelne Uvicorn-Prozess kann währenddessen die Verfügbarkeitsabfrage
   nicht bearbeiten. Eine höhere Cloud-Run-Concurrency beseitigt das nicht.
5. Bei Fehler/Timeout wechselt `lib/routing/routing_service.dart` zu BRouter.
   Das äußere Direkt-Limit von 45 s hebt das innere Discovery-Limit von 3 s
   nicht auf. Der Ersatz hat ein weiteres Limit von 75 s.

Erfolgreiche Discovery wird in der App zwischengespeichert. Daher betrifft
diese zusätzliche Abhängigkeit vor allem die erste Anfrage pro Providerinstanz;
spätere Direkt-Anfragen gehen unmittelbar an den getrennten Dienst. Die
genaue Reihenfolge der Ankunft am Server ist netzabhängig, weshalb der Fehler
nicht bei jeder ersten Anfrage auftreten muss.

Produktionslogs vom 11.09.2026, Zeitangaben UTC:

| Beginn `/routing_variants` | HTTP-Antwortzeit | Passender Analyseabschluss | Analysezeit |
| --- | ---: | --- | ---: |
| 10:26:31,280 | 6,990 s | 10:26:38,252 | 7,103 s |
| 15:58:55,275 | 3,012 s | 15:58:58,275 | 3,099 s |
| 16:46:45,498 | 1,055 s | 16:46:46,539 | 1,178 s |

Andere Verfügbarkeitsabfragen benötigten serverseitig nur etwa 2–3 ms.
Die zeitlichen Zusammenhänge und der Code stützen die Blockierungsursache.
HTTP 200 im Serverlog beweist dabei nicht, dass die App vor ihrem Timeout eine
Antwort erhalten hat. Ohne zugehöriges App-Log lässt sich der konkrete
BRouter-Rückfall des Nutzers nicht zuordnen.

Die Analyse vom ersten Tabellenfall benötigte 2.083 ms für Nodes und 5.009 ms
für Ways, aber nur 10,9 ms für die Segmentzuordnung. Auch auf Direkt gibt es
analoge Warnungen: am 11.09. um 16:47:14 UTC insgesamt 6.713 ms, davon 1.937 ms
Nodes, 4.771 ms Ways und 4,7 ms Segmentzuordnung. Der verbleibende Engpass
dieser Fälle liegt im Datenladen und Decodieren, nicht in der bereits
optimierten Segmentzuordnung. Die Logs trennen SQL, Datei-I/O und JSON-Decodierung
innerhalb der jeweiligen Ladephase noch nicht weiter auf.

## Empfohlene Reihenfolge

1. **Fahrzeitproblem an der Routenauswahl beheben:** die vorhandene, getestete
   Profilkorrektur 2.3.2 fertig ausliefern und beide Routing-Graphen neu bauen.
   Danach die lange Route einschließlich Schiebeanteil erneut messen. Keine
   pauschale Fahrradgeschwindigkeit oder Begrenzung der Direkt-Minuten in der
   App einführen; das würde vorhandene Schiebewege lediglich verdecken.
2. **Discovery von der Komfortanalyse unabhängig machen:** als kleine additive
   Schnittstellenergänzung die bereits konfigurierte öffentliche Direkt-URL in
   der erfolgreichen Standard-Routenantwort mitliefern, beispielsweise als
   Response-Header. Die App validiert und merkt sich diese Information beim
   Einlesen der Route, bevor sie die Komfortanalyse startet. Dann kann die
   Alternative ohne weiteren Standard-API-Aufruf beginnen. Die bisherige
   Discovery bleibt als kompatibler Ersatz für ältere Backends erhalten.
   Keine interne OSRM-URL veröffentlichen; deaktivierte Direkt-Konfiguration,
   ungültige URLs und Cache-Erneuerung explizit behandeln. Bei Browser-Clients
   gegebenenfalls den Header über CORS zugänglich machen.
3. **Verbleibende Start- und Datenladezeiten getrennt optimieren:** Dienste
   weiterhin isoliert halten. Eine größere Thread-/Worker-Umstellung im
   Backend ist kein gleichwertig kleiner Fix: die gemeinsame SQLite-Verbindung,
   Parallelitätsgrenzen und Standard-Navigation müssten dafür gezielt abgesichert
   werden. Auch eine bloße Erhöhung des Discovery-Timeouts beseitigt die
   unnötige Abhängigkeit nicht.

Die Header-Ergänzung ist eine Umsetzungsempfehlung, noch kein implementierter
Vertrag. Sie verursacht weder einen zusätzlichen Routing-Request noch eine
zusätzliche Datenbankabfrage für Standard und erfordert keine Neuordnung des
Navigationszustands in der App. Sie beseitigt keine echten Direkt-Kaltstarts
und beschleunigt nicht automatisch die Komfortanalyse selbst.

Vor Auslieferung dieses zweiten Schritts sollten Tests prüfen: langsame
Standard-Komfortanalyse ohne Discovery-bedingten BRouter-Rückfall; unverändert
früh nutzbare Standardroute; Kompatibilität ohne neuen Header; deaktiviertes
Direkt und echte Direkt-Ausfälle mit weiterhin funktionierendem Ersatz;
Routenwechsel/Abbruch und verspätete Komfortantworten ohne falsche Zuordnung.

In dieser Untersuchung liefen keine Flutter-Prüfungen und keine Änderungen
an Produktionsdiensten. Die lokalen Kurztests ersetzen weder den vollständigen
Graph-Neubau noch den anschließenden App-Praxistest.
