# Direkte Route (Issue #9)

## Entscheidung und API

Ab Routing 2.3.2 optimiert Direkt eine zügig fahrbare Fahrradroute ohne
Komfortgewichtung. Treppen und Schiebeabschnitte bleiben in beiden Profilen als
stark abgewertete Verbindung erhalten. Fähren sind ausgeschlossen. Schieben darf
keine gesperrte Fahrrad-Einbahnrichtung öffnen; explizite Gegenrichtungsfreigaben
bleiben erhalten. [Prüfung und Browser-Testmodus](oneway-pushing-qa.md).

Ab Routing 2.3.1 sind Fähren in beiden Profilen ausgeschlossen, auch bei
expliziter Fahrradfreigabe. In beiden Profilen bleiben Treppen (`highway=steps`) als
stark abgewertete Verbindung erhalten und werden mit höchstens 2 km/h berechnet.
Auch `bicycle=dismount` bleibt möglich; `bicycle=no` bleibt in beiden
Varianten gesperrt.

Die gemeinsamen Suchaufschläge entsprechen mindestens Faktor 10 für Schieben
und Faktor 20 für Treppen gegenüber normalem Fahren mit der Referenzgeschwindigkeit
20 km/h. Bei Standard wirkt zusätzlich die Komfortbewertung. Treppen und Schieben
werden nicht miteinander multipliziert. Die tatsächliche Fahrzeit wird weiter
aus den unveränderten Geschwindigkeiten berechnet.

`routing/direct.lua` verwendet die Fahrzeit mit diesen Suchaufschlägen. Es übernimmt die
Zugangsregeln, Geschwindigkeiten, Abbiegebeschränkungen und Navigationsausgabe aus
dem gemeinsamen `bike.lua`. `class:bicycle` und andere Komfortfaktoren haben auf
Direkt keinen Einfluss; echte Zugangsverbote, Einbahnrichtungen und der Schutz vor
dem Einfahren in `bicycle=use_sidepath` bleiben bestehen. Oberfläche,
Beschaffenheit und Höchstgeschwindigkeit wirken über dasselbe physische
Geschwindigkeitsmodell wie bei Standard auf Auswahl und angezeigte Fahrzeit.

Ampelwartezeit wird vollständig in der Fahrzeit ausgewiesen, fließt bei Direkt aber
nur zu 25 Prozent in das Suchgewicht ein. Dadurch darf Direkt eher eine zügige
Hauptverbindung mit Ampeln wählen. Das API-Gewicht heißt `fast_cycling`; es ist
wegen des reduzierten Ampelanteils und der Suchaufschläge nicht identisch mit
`duration`. Stop-Hindernisse, einschließlich Bahnübergängen, behalten ihr volles
Suchgewicht, auch wenn am selben Knoten eine Ampel eingetragen ist.

### Vorsichtige Bevorzugung gut befestigter Verbindungen

Der aktuelle Direkt-Teststand ergänzt reine Suchaufschläge:

| Merkmal | Faktor auf die Fahrzeit der Kante im Suchgewicht |
| --- | --- |
| Wohnstraße (`residential`) | 1,08 |
| Asphalt, Beton, Pflastersteine, unbekannte Oberfläche | 1,00 |
| Verdichteter Belag (`compacted`), feiner Kies (`fine_gravel`) | 1,05 |
| Kopfsteinpflaster (`cobblestone`, `sett`, `unhewn_cobblestone`) | 1,15 |
| Grober Kies, unbefestigt, Erde, Gras, Rasengitter, Holzschnitzel | 1,25 |
| Schlamm oder Sand | 1,50 |

Straßen- und Oberflächenfaktor werden für Radfahren miteinander multipliziert.
Die Aufschläge kommen zu den bereits vorhandenen oberflächenabhängigen
Geschwindigkeiten hinzu; sie verändern diese Geschwindigkeiten und die angezeigte
Fahrzeit nicht. Schieben und Treppen behalten ihre gesonderten gemeinsamen
Aufschläge. Hauptstraßen und asphaltierte Radwege erhalten keinen zusätzlichen
Klassenaufschlag. Die Standard-Gewichtung bleibt unverändert.

Die OSRM-Fixtures prüfen die Bevorzugung einer fast gleich langen Hauptverbindung,
die weitere Nutzung einer deutlich kürzeren Wohnstraße, die Differenzierung
zwischen feinem und grobem Kies sowie gleiche Fahrzeiten beider Varianten auf
identischer Geometrie. Die Faktoren sind erste Kalibrierwerte, keine bereits
an den zwei vollständigen Münchner Vergleichsrouten optimierten Werte.
Stärkere Gewichtung echter Straßenwechsel und die Erkennung zusammenhängender
Straßen-/Radwegkorridore bleiben eine getrennte mögliche Erweiterung.

Bestehende Clients erhalten ohne Parameter weiterhin die Standardroute.

```text
GET /routing_variants
GET /route/v1/bike/{lon,lat;lon,lat;...}?variant=direct&steps=true&annotations=nodes,distance&geometries=geojson&overview=full
```

`variant=standard` ist ebenfalls explizit möglich. Alle OSRM-Optionen, Zwischenziele,
Legs, Manöver und Geometrien werden durchgereicht. `comfort=true` ergänzt wie
bisher den Komfort-Index an jeder Route. Für schnelle erste Anzeige sollte der
Client stattdessen die Route sofort anzeigen und danach analysieren:

```json
{
  "variant": "direct",
  "legs": [{"nodes": [1001, 1002], "distance": [73.8],
            "start": [11, 48.6], "end": [11.001, 48.6]}]
}
```

Dieser Body geht an `POST /tag_distribution`; pro OSRM-Leg werden dessen
`annotation.nodes`, `annotation.distance` und die gesnappten angrenzenden
`waypoints[].location` übernommen. Der ältere `node_ids`-Body bleibt unterstützt.
Die Antwort enthält dieselben Komfort-, Untergrund- und Beleuchtungsdaten wie bei
Standard. Eine unbekannte Variante wird zurückgewiesen; eine nicht verfügbare
Direktvariante ergibt 503, ein Proxy-Timeout 504. Es gibt keinen stillen Rückfall
auf eine Standardroute. `routing_variants.direct.available` bedeutet konfiguriert,
nicht einen aktuellen Erreichbarkeitstest.

## Isolation und Client-Verhalten

Für die App ist `routing_variants.direct.base_url` der bevorzugte Zugang zur
separaten öffentlichen Direkt-API. Dort funktionieren dieselben Pfade und Bodies;
ohne Variante ist dort Direkt voreingestellt. Damit laufen auch HTTP-Eingang,
JSON-Verarbeitung und Analyse außerhalb der Standard-API. Der darunterliegende
OSRM-Dienst bleibt privat. Die Weiterleitung über die Standard-API bleibt eine
zusätzliche Schnittstelle, ist aber nicht die Empfehlung für paralleles Vorladen.

Direkt-OSRM und Direkt-Analyse laufen in eigenen Diensten. Die Standard-API leitet
nur explizite Direkt-Anfragen asynchron weiter: höchstens vier gleichzeitig pro
API-Prozess, 100 ms Wartezeit auf Zulassung, vier gepoolte Verbindungen, 5 s
Connect- und 45 s Read-Timeout. Dies ist kein globales Limit über alle Instanzen
und kein garantierter Gesamtzeit-Deadline. Pooling folgt der
[HTTPX-Dokumentation](https://www.python-httpx.org/async/).

Bei Verwendung der Weiterleitung verursachen der gemeinsame API-Zugang und die Infrastruktur weiterhin etwas
Zusatzaufwand. Vollständig unveränderte Latenz unter beliebiger Last ist damit
nicht garantiert. Der Lastvergleich muss vor Aktivierung auf der Zielumgebung
wiederholt werden. Vereinbart ist ein begrenzter Test nach dem Produktionsdeploy,
einschließlich einzelner Cold Starts, ohne Sättigungstest.

Die App soll zuerst Standard anfordern und anzeigen, danach Direkt über dessen
eigene `base_url` laden. Beide
Varianten erhalten getrennte Route-/Analyse-Zustände; Antworten werden nur bei
passender Planungsrevision und Variante übernommen. Ein Direkt-Fehler darf weder
Standard löschen noch die Navigation stoppen. Beim Wechsel übernimmt die App
Geometrie, Legs, Manöver und Komfort derselben Variante gemeinsam. Neuberechnung
verwendet die aktive Variante und die verbleibenden Zwischenziele. Die tatsächliche
Flutter-Umschaltung und Ansage auf dem Gerät sind eine folgende App-Änderung;
dieser Branch liefert und prüft dafür den Backend-Vertrag.

## Lokal starten

Zuerst `docker compose --parallel 1 build routing backend frontend`, anschließend
`docker compose -f compose.yaml -f compose.direct.yaml build direct-routing` und
`docker compose -f compose.yaml -f compose.direct.yaml up -d`.
Der Direkt-Build verwendet die PBF aus dem bereits gebauten Standard-Image.
`--parallel 1` begrenzt die gleichzeitig laufenden Service-Builds, damit
Kartenaufbereitung und Backend-Datenbankaufbau den lokalen Rechner nicht
gleichzeitig belasten. Bei einem Docker-Desktop-Verbindungsabbruch zuerst die
Engine wieder starten und denselben Build mit vorhandenem Cache wiederholen;
keinen Cache-Reset oder `--no-cache` verwenden.
Beide Routing-Images behalten den Kartenstand; neue Builds schreiben zusätzlich
`/data/map.sha256`. Keine Startabhängigkeit der Standard-API auf Direkt.

Die Zusatzdienste sind optional und verwenden je höchstens einen CPU-Kern.
Auf einem einzelnen Rechner ist dies keine reservierte Rechenkapazität; RAM,
Host-CPU und Docker-VM bleiben gemeinsam. In Cloud Run erhalten beide Varianten
eigene Routing- und Analyse-Instanzen.

## Rollout vorbereiten

`cloudbuild-direct.yaml` ist ein expliziter, zusätzlicher Rollout. Zuerst den neuen
Standard-API-Code regulär deployen und den Standard-Routing-Rollout abwarten.
Danach diesen Build mit `--no-source` und `COMMIT_SHA` ausführen. Er lädt den
angegebenen Repository-Commit und baut das
Direktprofil aus dem Image-Digest der letzten bereiten Standard-Routing-Revision,
deployt einen privaten Direkt-Router und eine öffentliche Direkt-API und gibt
erst zuletzt deren URL über die Standard-API bekannt.
Die Digest-Felder entsprechen der
[Cloud-Run-Revisionsbeschreibung](https://docs.cloud.google.com/run/docs/reference/rest/v1/namespaces.revisions).
Die Direkt-API übernimmt den Image-Digest der bereiten Standard-API. Der Build-Account
benötigt wie bei den bestehenden Deployments Deployment-Rechte und zusätzlich
die Berechtigung, die Invoker-Bindungen der neuen Dienste zu setzen.
Vor Veröffentlichung der URL prüft `backend/check_direct_deployment.py` den
Direkt-Modus, `fast_cycling`-Gewichtung, Navigationsschritte, einen Zwischenhalt und die
separate Komfortanalyse. `index=null` bei niedriger Abdeckung ist zulässig.
Frisch gesetzte Cloud-Run-Aufrufrechte können verzögert wirksam werden. Der Check
wiederholt deshalb HTTP 403/429/502/503/504 und Transportfehler mit 5 bis 30 Sekunden
Abstand innerhalb eines gemeinsamen Acht-Minuten-Fensters. Dauerhafte Fehler oder
ungültige Antworten brechen weiterhin ab; die URL wird dann nicht veröffentlicht.
Hintergrund: [Google IAM Access change propagation](https://docs.cloud.google.com/iam/docs/access-change-propagation).

Der wöchentliche Workflow aktualisiert Direkt nach dem Standard-Kartenupdate,
sobald `DIRECT_API_URL` in der Standard-API gesetzt ist. Die erste Aktivierung
erfolgt explizit mit `cloudbuild-direct.yaml`. Bei manuellen Routing-Deployments
außerhalb dieses Workflows muss der zusätzliche Build ebenfalls folgen.
Die Analyse-Datenbank stammt wie bisher aus dem API-Image; deren bestehender
separater Aktualisierungszyklus bleibt bestehen. Beide Analysevarianten verwenden
dasselbe API-Image. Rollback: `DIRECT_API_URL` und `DIRECT_API_AUTH_AUDIENCE` aus
der Standard-API entfernen, außerdem `PUBLIC_DIRECT_API_URL`. Standardrouting benötigt diese Dienste nicht.
Die API-Builds (`cloudbuild-api.yaml` und `cloudbuild.yaml`) aktualisieren eine
bereits aktivierte Direkt-API auf dasselbe neue Backend-Image. Deren Direktprofil,
OSRM-Zugang und Routing-Version bleiben erhalten; CORS wird mitgeführt.
Die Aktualisierung beider APIs erfolgt nacheinander, nicht atomar.

## Prüfungen

Backend: `backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests`.
Die Tests umfassen IAM-Wartezeit, Deployment-Vertrag, Image-Synchronisierung, Variantenwahl,
URL-Erkennung, deaktivierter Direktfunktion, Fehlercodes,
Weitergabe aller Zwischenziele und Optionen, Parallelität, Kapazitätsgrenze und
Freigabe nach Abbruch.

Die OSRM-Testimages werden mit `routing/tests/Dockerfile` gebaut, einmal mit
`ROUTING_PROFILE=bike`, einmal mit `ROUTING_PROFILE=direct`. Auf Ports 18081/18082:
`routing/tests/test_profile_regressions.py` und `routing/tests/test_direct_profile.py`.
Der Vergleichsfall enthält eine kurze, langsame Verbindung und einen längeren,
aber schneller befahrbaren Weg. Direkt muss den schnelleren Weg wählen.
Zusätzlich werden gleiche ETA unabhängig von `class:bicycle`, reduzierte
Ampelgewichtung, stark abgewertete Treppen und Schiebewege, Sperren,
Einbahn-Ausnahme für Radverkehr, Abbiegeverbot, zwei Zwischenziele, Rückfahrt und
Neuberechnung geprüft.

`backend/tests/Dockerfile.variants` baut aus einem vorhandenen Backend-Image die
aktuelle API mit passender Fixture-Datenbank. Zwei API-Container werden mit den
jeweiligen OSRM-Diensten verbunden; Standard bekommt zusätzlich `DIRECT_API_URL`.
`backend/tests/test_variants_live.py --base-url http://127.0.0.1:18090` prüft Route,
Manöver und nachgelagerte Analyse durch den tatsächlichen HTTP-Zugang. Der
Komfort-Index im Vergleichsfall ist bei beiden Profilen 100, da beide denselben
schnelleren Weg wählen. Die erzwungenen Zwischenziele prüfen weiterhin andere
Teilstrecken und die eindeutige Zuordnung ihrer Analyse.

`backend/benchmarks/variants_load.py` erzeugt einen offenen, zeitgesteuerten
ABBA-Vergleich: Standard allein, zweimal mit Direktlast, Standard allein. Die
Standard-Ankunftsrate bleibt gleich, Direkt kommt zusätzlich dazu. Fehler und
Verspätungen bei der Anfrageerzeugung werden mitgezählt; Rohwerte werden gespeichert.
Nur gegen lokale oder ausdrücklich für den jeweiligen Test freigegebene Dienste
ausführen. Die hier gespeicherten Messungen entstanden ausschließlich lokal.

Fixture-Messung: fünf Standardanfragen/s, zusätzlich fünf Direktanfragen/s, jeweils
inklusive Komfort und zwei Zwischenzielen. 600 HTTP-Anfragen, keine Fehler.
Standard-p95: 48,221 ms allein, 55,992 ms mit Direktlast (+7,771 ms / +16,12 %).
Das belegt funktionierende Isolation, aber keine Null-Latenzgarantie. Rohdaten:
`direct-route-load-fixture.json`. Messrechner: Docker Desktop, acht CPUs,
etwa 4 GiB VM-RAM, je Testdienst ein CPU-Limit von einem Kern.

### Historische Messung des früheren Distanzprofils

Die folgenden Ergebnisse stammen vom ersetzten Distanzprofil und sind keine
Sollwerte für `fast_cycling`. Getestet wurde: `[48.156304,11.540013] > [48.102548,11.568796] >
[48.120477,11.655645] > [47.991860,11.828568]`, bestehende lokale Oberbayern-PBF.
Standard: 43,193 km, 154 Navigationsschritte, Komfort 77 bei 84 % Abdeckung.
Direkt: 37,201 km, 136 Schritte, 52 % Abdeckung. Deshalb liefert Direkt hier
regelkonform **keine belastbare Indexzahl** (`index=null`,
`sufficientCoverage=false`). Dies ist kein Timeout: Analyse und Verteilung werden
geliefert; die bestehende Mindestabdeckung gilt unverändert für beide Varianten.
Die App muss diesen bestehenden Zustand auch für Direkt darstellen.

Alle drei Legs sowie die Übereinstimmung zwischen integriertem Komfort und
separatem `/tag_distribution` wurden geprüft. Beide Analysen kennen die vollständige
OSRM-Distanz; Direkt meldet vier ungeklärte Segmente, davon drei mehrdeutig.
Ergebnis: `direct-route-munich-route.json`. Einzelmessungen inklusive Navigation
und Komfort: 397 ms Standard, 299 ms Direkt; keine Latenzgarantie daraus ableiten.

ABBA-Lastvergleich mit zwei Standardanfragen/s und zusätzlich zwei Direktanfragen/s,
je 50 Anfragen pro Phase (300 insgesamt), jeweils null Fehler:

| Zugang für Direkt | Standard p50 allein / mit Direkt | Standard p95 allein / mit Direkt |
| --- | --- | --- |
| Weiterleitung | 186 / 197 ms | 1042 / 472 ms |
| Eigene API | 198 / 211 ms | 311 / 656 ms |

Rohdaten: `direct-route-load-munich.json` und
`direct-route-load-munich-separated.json`. Die Phasen streuen erheblich, auch
innerhalb der Baseline. Insbesondere ist die zweite Messung **kein bestandener
Nachweis unveränderter Standardlatenz**. Die Ursache der Ausreißer ist nicht
isoliert; gemeinsamer VM-/Host-Einfluss ist eine mögliche Erklärung, kein Beweis.
Die separate API entfernt den gemeinsamen Standardprozess aus dem Direktpfad,
garantiert auf diesem gemeinsam genutzten Host aber keine gleichbleibende Latenz.

Vereinbarte Abnahme ohne Staging: Nach dem Produktionsdeploy zuerst einzelne
Routen und Cold Starts prüfen, danach zu einer ruhigen Zeit einen kurzen Vergleich
mit begrenzter Zusatzlast über die separate Direkt-API durchführen. Bei steigender
Standardlatenz oder Fehlern die Testanfragen stoppen. Keine Sättigungstests;
die Aussage gilt nur für die geprüfte Last. Cloud-Konfiguration und IAM wurden
lokal geprüft, nicht deployt. Die Performance-Abnahme und der App-Gerätetest sind
noch offen. Siehe `direct-route-qa.md` für den Abgleich mit der App-Ziellösung.
