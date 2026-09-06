# Ergänzung: Flutter-App und reale Route mit zwei Zwischenzielen

Stand: 5. September 2026. Ergänzt die
[Architekturempfehlung](routing-performance-analysis.md).

**Ergebnis**

Die Flutter-App fordert tatsächlich `comfort=true` an und wartet damit auf die
Komfortanalyse, bevor sie eine Route anzeigen kann. Die Beispielroute wurde
gegen genau die von der App verwendete öffentliche API gemessen. Sie ist
43,193 km lang und besteht aus drei Legs mit zwei Zwischenzielen.

Ohne Komfort betrug die vollständige HTTP-Antwortzeit in drei Vergleichsabrufen
0,221 / 0,244 / 0,237 Sekunden. Mit Komfort benötigte der erste Abruf 15,457
Sekunden; die beiden unmittelbar folgenden Wiederholungen benötigten 1,118 und
1,152 Sekunden. Alle Antworten enthielten dieselbe Routengeometrie, dieselbe
Distanz und dieselben 154 OSRM-Steps.

Damit ist für diese Route belegt: Die lange erste Wartezeit ist mit dem
zusätzlichen Analysepfad verbunden, während die navigierbare Route bereits
schnell geliefert werden kann. Warum der erste Analyseabruf erheblich langsamer
ist, ist damit noch nicht bewiesen. Eine alleinige Betrachtung warmer
Wiederholungen würde das Nutzerproblem unterschätzen.

**Messaufbau und Rohdaten**

Die Punkte wurden in der vorgegebenen Reihenfolge verwendet, ohne Optimierung
der Zwischenzielreihenfolge:

```text
Breitengrad, Längengrad
48.156304, 11.540013
48.102548, 11.568796
48.120477, 11.655645
47.991860, 11.828568
```

Alle vier Punkte liegen innerhalb des in der Flutter-App gebündelten
Oberbayern-Polygons; dies wurde mit derselben Punkt-in-Polygon-Logik überprüft.
Bei automatischer Anbieterwahl ist deshalb RadlNavi der vorgesehene erste
Anbieter. Eine explizite BRouter-Einstellung kann diesen Pfad übersteuern.

Gemessen am 5. September 2026, 14:50:52 bis 14:51:13 Uhr MESZ, von diesem
Windows-Arbeitsplatz über `https://api.radlnavi.munichways.de`. Alle Aufrufe
erfolgten sequenziell, mit einem wiederverwendeten HTTP-Client. Es gab keine
absichtlich parallelen Requests, keine Server-Neustarts, keine Cache-Löschung
und keine künstlichen Fehler. Ein erster Routingabruf von 0,400 Sekunden wurde
separat als Aufwärmabruf erfasst. Er wärmt nicht nachweislich die Analyse oder
alle Cloud-Run-Instanzen auf.

Die Parameter entsprechen `RadlNaviApi.route`: `alternatives=false`,
`steps=true`, `geometries=geojson`, `overview=full`,
`continue_straight=default`, `annotations=false`; für den Vergleich wird
`comfort=true` ergänzt beziehungsweise weggelassen. Ein weiterer Abruf fordert
`annotations=nodes` an. Dessen Knoten werden mit der heutigen Backend-Logik
über die Leg-Grenzen zusammengefügt und an `/tag_distribution` gesendet.

| Anfrage | Anzahl | Vollständige HTTP-Antwortzeit | Antwortinhalt |
| --- | ---: | --- | --- |
| Route ohne Komfort, erster separater Abruf | 1 | 0,400 s | Navigierbare Route |
| Route ohne Komfort, Vergleichsabrufe | 3 | 0,221 / 0,244 / 0,237 s | Je 195.157 Bytes |
| Route mit Komfort, erster Analyseabruf | 1 | 15,457 s | Route und Komfort |
| Route mit Komfort, direkte Wiederholungen | 2 | 1,118 / 1,152 s | Je 195.619 Bytes |
| Route mit Knotenannotationen, ohne Komfort | 1 | 0,237 s | 215.961 Bytes, 1.941 Knoten nach Zusammenführung |
| Separate vollständige `/tag_distribution`-Analyse | 1 | 1,210 s | 267.008 Bytes, Komfort plus drei Tag-Gruppen und Geometrien |

Alle elf HTTP-Aufrufe einschließlich zweier Versionsabfragen lieferten Status
200. Es wurde keine Antwortkompression gemeldet. Größen beziehen sich auf die
von Python gelesenen Antwortkörper. Der erste Komfortabruf benötigte bereits
15,414 Sekunden bis zum Empfang der Header; der anschließende Körperdownload
dauerte etwa 43 ms. Die zusätzliche Wartezeit steckt somit in diesem Abruf
überwiegend vor der Übertragung des Antwortkörpers.

Routendaten: Legs 8.708,0 / 9.099,7 / 25.385,3 Meter, 1.941 Geometriepunkte,
154 Steps. Sämtliche acht Routenantworten haben denselben SHA-256-Fingerabdruck
der normalisierten GeoJSON-Geometrie. Sowohl der Komfort-Proxy als auch die
separate Analyse liefern Index **77/100**, Abdeckung **83 %** und Verteilung
Schwarz 1 %, Rot 8 %, Gelb 43 %, Grün 31 %, unbewertet 17 %.

Das Backend meldete vor und nach der Messreihe unverändert Version `2.2.0`,
Commit `00a18f93f80cadbbe42c888549eef8b8214747d5`; Routing `2.1.0`, Commit
`2f8c2b4d7e749abb35b27072a77ed308789b69b6`; OSRM `26.6.5`. Die relevanten
Backend-Dateien dieses gemeldeten Commits unterscheiden sich nicht vom zuvor
untersuchten lokalen Stand. Eine OSM-`data_version` und `Server-Timing` wurden
in den Antworten nicht geliefert.

Reproduzierbarer [Messcode](../backend/benchmarks/live_route_latency.py) und
[vollständige Rohwerte](routing-performance-live.json):

```powershell
backend/.venv/Scripts/python.exe backend/benchmarks/live_route_latency.py --output docs/routing-performance-live.json
```

Ein erneuter Lauf überschreibt diese Ergebnisdatei. Für eine zweite Messreihe
einen anderen Ausgabepfad verwenden. Das Skript ruft den produktiven Dienst ab;
es ist eine kleine Vergleichsmessung und kein Lasttest.

Diese Werte messen Netzwerk und öffentliche API zusammen, nicht isoliert OSRM
und nicht die Darstellung auf einem Telefon. GPS, Flutter-Parsing, Kartenaufbau
und Sprachnavigation wurden nicht zeitlich vermessen. Drei Vergleichswerte sind
keine belastbare p95-Stichprobe. Die einzelne warme `/tag_distribution`-Messung
belegt keine allgemeine Obergrenze für diese Analyse.

**Was der App-Code zusätzlich erklärt**

Untersucht wurde `C:/Users/Thomas/dev/flutter/munich-ways-app`, HEAD
`3ea64dba3b9a796d926c22dd1b59f532f57f61e0`, einschließlich bereits vorhandener
lokaler Änderungen. Die folgenden Pfade beziehen sich auf dieses Repository.
Die App-Dateien wurden nur gelesen; Flutter-Tests und Geräteprofiling wurden
für diese Analyse nicht ausgeführt.

| Quellstelle | Befund und Auswirkung |
| --- | --- |
| `lib/api/radlnavi_api.dart`, `RadlNaviApi.route` | `comfort=true` ist fest gesetzt. Erst nach der gesamten Antwort entsteht `CycleRoute`. Alle Legs werden für Manöver verarbeitet, ihre Knotenannotationen werden bisher nicht als Analysekontext gespeichert. |
| `lib/routing/routing_service.dart`, `RoutingService.route` | Der kombinierte RadlNavi-Aufruf hat 20 Sekunden Timeout. Jede Ausnahme führt zum BRouter-Fallback. Damit kann allein die zusätzliche Analysewartezeit einen Anbieterwechsel auslösen. |
| `lib/ui/map/map_screen_model.dart`, `_requestRoute` | Die bisherige Route wird zu Beginn durch `MapRoute(null, LOADING)` ersetzt. Erst nach Abschluss des gesamten Providers wird `SHOWN` gesetzt und ein Routenereignis gesendet. Das gilt auch für Neuberechnungen. |
| Derselbe ViewModel, `resolveRouteStartPosition` | Bei Start ab aktuellem Standort wird vor der Routenanfrage ein GPS-Fix angefordert, mit 8 Sekunden Zeitlimit und anschließender Last-known-Position-Rückfalloption. Diese separate mögliche Wartezeit entfällt bei fest geplantem Start wie im API-Vergleich. |
| Derselbe ViewModel, `_routePlanRevision` und `_routeRequest` | Schutz gegen veraltete Routingantworten besteht bereits. Die Architektur sollte ihn auf die Analyse erweitern, statt eine konkurrierende zweite Generationsverwaltung einzuführen. |
| Derselbe ViewModel, `CancelableOperation.fromFuture` | Der Cancel-Callback protokolliert nur. Er beendet nicht den HTTP-Aufruf. Ein überholter Routingversuch kann weiterlaufen und später sogar noch den Fallback anstoßen. |
| `lib/ui/map/map_overlay/map_route_comfort_summary.dart` | Komfort wird nur bei vorhandenen Metadaten, `SHOWN` und vor Navigationsbeginn angezeigt. `null` unterscheidet nicht zwischen noch ladend, Fehler und nicht unterstütztem Anbieter. |
| `lib/ui/map/map_screen.dart`, `routeStream.listen` | Ein Routenereignis löst vor Navigation eine Kartenübersicht aus; während Navigation wird die Sprachführung aktualisiert. Ein reines Metadatenupdate sollte diesen Weg nicht erneut durchlaufen. |
| `lib/ui/map/voice_guidance.dart`, `VoiceGuidance.setRoute` | Neue Objektidentität von `CycleRoute` setzt Manöverfortschritt, bereits gesprochene Hinweise und Ankunftszustände zurück. Ein neues Objekt nur wegen nachgeladenem Komfort wäre deshalb ein Navigationsrisiko. |
| `lib/api/brouter_api.dart` | BRouter liefert in dieser Implementierung `supportsVoiceGuidance=false`, keine Manöver und keinen Komfort. Ein Anbieterwechsel kann damit die verfügbaren Funktionen ändern. |

Das Timeout beendet laut Dart nur das Warten auf das Ergebnis; die zugrunde
liegende Arbeit kann weiterlaufen. `CancelableOperation.fromFuture` verwirft
spätere Ergebnisse und ruft den bereitgestellten Cancel-Callback auf. Für
Transportabbruch muss dieser tatsächlich mit dem HTTP-Request verbunden sein.
[Dart: Future.timeout](https://api.dart.dev/dart-async/Future/timeout.html),
[async: CancelableOperation.fromFuture](https://pub.dev/documentation/async/latest/async/CancelableOperation/CancelableOperation.fromFuture.html).

Im gemessenen Erstabruf wurde das 20-Sekunden-Limit nicht überschritten. Der
Fallback ist daher ein aus dem Code abgeleitetes Risiko, kein beobachtetes
Ereignis dieser Messreihe. Im Fallback kommen potenziell weitere Wartezeiten
hinzu: Der Service gewährt BRouter bis zu 75 Sekunden. Ein später erfolgreiches
RadlNavi-Ergebnis ersetzt nach Ablauf des Timeouts den gestarteten Fallback
nicht automatisch.

**Präzisierte Empfehlung für die erste Umsetzung**

Der erste spürbare Schritt benötigt noch keinen neuen Backend-Endpunkt:

1. `RadlNaviApi` fordert die Route ohne `comfort=true`, aber mit
   `annotations=nodes` an. Die Rohannotationen aller Legs werden zusätzlich
   zum bisherigen Navigationsmodell als Analysekontext erhalten.
2. Der normale Routingpfad setzt die Route auf `SHOWN`, ermöglicht Navigation
   und beendet seine Ladeanzeige. Routingfehler dürfen weiterhin den bestehenden
   Anbieter-Fallback auslösen.
3. Nur für ein erfolgreiches RadlNavi-Ergebnis startet eine nachgelagerte
   Komfortanfrage. Als Übergang liefert der bestehende Endpunkt
   `/tag_distribution` bereits exakt das benötigte zentrale `comfort`-Objekt.
   Die Messung bestätigt für diese Route denselben Wert wie `comfort=true`.
4. Analyse bekommt eigene Zustände, eigenes Zeitlimit und Wiederholen. Ein
   Analysefehler darf weder `MapRouteState.ERROR` noch BRouter-Fallback auslösen.
   Für BRouter-Ergebnisse wird nicht mit den Knoten einer anderen Route
   weiteranalysiert.
5. Komfort wird als Metadatum zur stabilen Route aktualisiert. Für den kleinen
   ersten Schritt kann das existierende `CycleRoute`-Objekt erhalten bleiben;
   ViewModel-Benachrichtigung aktualisiert die Anzeige, ohne einen neuen Eintrag
   in `routeStream` zu senden. Langfristig Metadaten nach `routeId` getrennt
   halten und Navigation an eine stabile Geometrie-/Navigationsrevision binden.
6. Die vorhandene Planrevision und die Identität der zugehörigen Route werden
   vor Übernahme jeder Analyseantwort geprüft. Ende der Route, Variantenwechsel,
   neue Zwischenhalte und Neuberechnung entwerten überholte Metadatenanfragen.

Der Zwischenstand überträgt noch die größere Detailantwort und macht die
Analyse selbst nicht schneller. Er ermöglicht aber eine frühe navigierbare
Route mit dem vorhandenen Backend. Die folgenden Backend-Schritte bleiben
notwendig: kompakte Antwort ohne Detailgeometrien, beschleunigte gemeinsame
Wegzuordnung, vorberechnete Längen und Trennung der Ausführungskapazität. Eine
laufende Analyse kann im heutigen Backend weiterhin andere Anfragen blockieren.

Bei Neuberechnung die noch nutzbare aktive Route separat vom Status der neuen
Anfrage halten. Ein `LOADING`-Status soll nicht pauschal das gerade navigierte
Routenobjekt löschen. Ein tatsächlicher Wechsel übernimmt das neue Ergebnis
atomar; ein Komfortupdate tut das ausdrücklich nicht.

**Erstzugriff gezielt untersuchen**

Die Werte 15,46 Sekunden versus etwa 1,1 Sekunden erfordern zusätzlich eine
Messung des ersten Analysezugriffs je Instanz und Kartendatenstand. Plausible
Erklärungen sind kalte Datenbank-/Dateisystemseiten, Instanzinitialisierung oder
Wartezeit durch andere Anfragen. Aus diesen HTTP-Antworten lässt sich keine
dieser Ursachen eindeutig auswählen. Im untersuchten Backend ist kein expliziter
Cache für vollständige Komfortergebnisse implementiert.

Empfohlen sind interne Zeitmessungen für SQLite-Lesen, JSON-Dekodierung,
Wegzuordnung, Distanzen und Antwortserialisierung, dazu Instanz-/Revisionskennung
und erste Anfrage seit Prozessstart. Die gleiche Route auf einer neuen
Staging-Instanz und anschließend neue Routen durch andere Gebiete vergleichen.
Ein bloßes Warmhalten des Routingdienstes beziehungsweise `/health` garantiert
keine vorgewärmten Analysedaten. Erst danach über gezieltes Vorladen, Indexlayout
und warme Analyseinstanzen entscheiden.

**Konsequenz für die direkte Route**

Die App hat bereits eine temporäre direkte/kürzeste Auswahl. Sie schaltet in
`setTemporaryShortestRouteEnabled` auf `BRouterProfile.shortest`, berechnet neu
und ersetzt die bisherige Route. Es gibt noch keinen Cache mit zwei parallel
verfügbaren vollständigen Varianten. Der Schalter ist damit ein vorhandener
UI-Anknüpfungspunkt, aber noch keine Umsetzung der gewünschten Funktionsgleichheit.

Die zukünftige direkte RadlNavi-Variante sollte diesen Schalter auf einen zweiten
RadlNavi-Graphen führen und genau denselben Parser für Manöver, Zwischenhalte
und Zielzugang verwenden. Beide Varianten erhalten unabhängig nachgeladene
Komfortdaten. Der bereits vorhandene Umgang mit noch offenen Zwischenhalten
in `refreshRoute` und die bestehende Ansagenlogik werden gemeinsam genutzt.
Die BRouter-Rückfalloption bleibt eine davon getrennte Anbieterentscheidung.

Für sofortiges Umschalten in der Planung müssen beide fertigen Routen gehalten
werden. Die Standardroute erscheint zuerst; die direkte Route und deren Analyse
folgen nachrangig. Eigene Rechenkapazität für die direkte Route und begrenzte
Analyseparallelität bleiben die Empfehlung für unveränderte Standardlatenz
auch bei mehreren Nutzern.

**Abnahmefälle für die App-Änderung**

- Die konkrete 43,193-km-Route wird nutzbar, während eine künstlich verzögerte
  Analyse noch läuft; beide Zwischenziele bleiben in den Manövern erhalten.
- Analysefehler, Timeout und Wiederholen verändern weder Routinganbieter noch
  Routengeometrie, Navigation oder bereits gesprochene Hinweise.
- Eine verspätete Analyseantwort nach Zieländerung, Abbruch, Neuberechnung oder
  Variantenwechsel bleibt ohne Wirkung auf die aktive Route.
- Reines Nachladen von Komfort erzeugt kein neues Routenereignis, keinen
  Kamerawechsel und keinen Reset der Sprachführung.
- Ein echter Routingfehler aktiviert weiterhin den bisherigen Fallback; fehlende
  Komfortunterstützung eines Anbieters wird getrennt von „Analyse lädt“ dargestellt.
- Bei Neuberechnung bleibt eine noch verwendbare aktive Route bis zur
  erfolgreichen Übernahme oder expliziten Behandlung eines Fehlers verfügbar.

Die bestehenden API-Tests erwarten derzeit explizit `comfort=true`; sie müssen
bei der Umsetzung auf den neuen Vertrag angepasst und um verzögerte Analyse,
Fehlererholung und Ereignis-/Objektidentität ergänzt werden. Das ist keine
reine Änderung einer Query-Option, sondern eine kleine kontrollierte Änderung
des asynchronen Zustandsablaufs.
