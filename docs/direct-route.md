# Direkte Route (Issue #9)

## Entscheidung und API

`routing/direct.lua` minimiert die befahrbare Entfernung. Es übernimmt die
Zugangsregeln, Geschwindigkeiten, Abbiegebeschränkungen und Navigationsausgabe aus
dem unveränderten `bike.lua`. Komfortfaktoren und zeitbasierte Abbiegekosten
beeinflussen das Entfernungsgewicht nicht. Fahrzeit und Abbiegedauer bleiben für
die ETA erhalten. Ausgeschlossene Wege (`class:bicycle=-3`) und der Schutz vor
dem Einfahren in `bicycle=use_sidepath` bleiben bestehen. „Kürzeste“ gilt innerhalb
dieses zulässigen Netzes und der gesnappten Wegpunkte, nicht als Luftlinie.

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
wiederholt werden, einschließlich Cold Starts und Sättigung.

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

Der wöchentliche Workflow aktualisiert Direkt nach dem Standard-Kartenupdate,
sobald `DIRECT_API_URL` in der Standard-API gesetzt ist. Die erste Aktivierung
erfolgt explizit mit `cloudbuild-direct.yaml`. Bei manuellen Routing-Deployments
außerhalb dieses Workflows muss der zusätzliche Build ebenfalls folgen.
Die Analyse-Datenbank stammt wie bisher aus dem API-Image; deren bestehender
separater Aktualisierungszyklus bleibt bestehen. Beide Analysevarianten verwenden
dasselbe API-Image. Rollback: `DIRECT_API_URL` und `DIRECT_API_AUTH_AUDIENCE` aus
der Standard-API entfernen, außerdem `PUBLIC_DIRECT_API_URL`. Standardrouting benötigt diese Dienste nicht.

## Prüfungen

Backend: `backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests`.
46 Tests einschließlich Variantenwahl, URL-Erkennung, deaktivierter Direktfunktion, Fehlercodes,
Weitergabe aller Zwischenziele und Optionen, Parallelität, Kapazitätsgrenze und
Freigabe nach Abbruch.

Die OSRM-Testimages werden mit `routing/tests/Dockerfile` gebaut, einmal mit
`ROUTING_PROFILE=bike`, einmal mit `ROUTING_PROFILE=direct`. Auf Ports 18081/18082:
`routing/tests/test_profile_regressions.py` und `routing/tests/test_direct_profile.py`.
Der Vergleichsfall ist bewusst kürzer, aber langsamer: Standard 258,6 m / 50,7 s,
Direkt 147,6 m / 88,6 s. Zusätzlich: Sperren, Einbahn-Ausnahme für Radverkehr,
Abbiegeverbot, zwei Zwischenziele, Rückfahrt und Neuberechnung.

`backend/tests/Dockerfile.variants` baut aus einem vorhandenen Backend-Image die
aktuelle API mit passender Fixture-Datenbank. Zwei API-Container werden mit den
jeweiligen OSRM-Diensten verbunden; Standard bekommt zusätzlich `DIRECT_API_URL`.
`backend/tests/test_variants_live.py --base-url http://127.0.0.1:18090` prüft Route,
Manöver und nachgelagerte Analyse durch den tatsächlichen HTTP-Zugang. Der
Komfort-Index im Vergleichsfall ist 100 bzw. 35.

`backend/benchmarks/variants_load.py` erzeugt einen offenen, zeitgesteuerten
ABBA-Vergleich: Standard allein, zweimal mit Direktlast, Standard allein. Die
Standard-Ankunftsrate bleibt gleich, Direkt kommt zusätzlich dazu. Fehler und
Verspätungen bei der Anfrageerzeugung werden mitgezählt; Rohwerte werden gespeichert.
Nur gegen lokale oder ausdrücklich vorgesehene Staging-Dienste ausführen.

Fixture-Messung: fünf Standardanfragen/s, zusätzlich fünf Direktanfragen/s, jeweils
inklusive Komfort und zwei Zwischenzielen. 600 HTTP-Anfragen, keine Fehler.
Standard-p95: 48,221 ms allein, 55,992 ms mit Direktlast (+7,771 ms / +16,12 %).
Das belegt funktionierende Isolation, aber keine Null-Latenzgarantie. Rohdaten:
`direct-route-load-fixture.json`. Messrechner: Docker Desktop, acht CPUs,
etwa 4 GiB VM-RAM, je Testdienst ein CPU-Limit von einem Kern.

### Lange München-Route mit zwei Zwischenzielen

Getestet: `[48.156304,11.540013] > [48.102548,11.568796] >
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

Vor Performance-Freigabe: denselben Vergleich auf einer getrennt provisionierten
Staging-Umgebung wiederholen, mit mehreren längeren Routen, kalten Instanzen und
Sättigung. Standardlast und Ressourcen müssen konstant bleiben; Fehler und p95
sind zusammen zu bewerten. Cloud-Konfiguration und IAM wurden lokal statisch
geprüft, nicht deployt. Die Funktion ist implementiert, die Performance-Abnahme
und der App-Gerätetest sind noch offen.
