# Produktionsprüfung vom 7. September 2026

## Deployment

Standard-API und Direkt-API melden über `/version` Backend und Routing 2.3.0,
Commit `504391c696d79cc0b55c33063feccb8d870dd024`. Beide liefern bei der Analyse
`segments-v2`; die frühere Segmentoptimierung ist damit in Produktion vorhanden.
Standard liefert das OSRM-Gewicht `cyclability`, Direkt `distance`.

100 % Traffic liegen jeweils auf folgenden Revisionen:

| Dienst | Revision |
| --- | --- |
| API | `munichways-radlnavi-api-00027-f96` |
| Direkt-API | `munichways-radlnavi-direct-api-00001-f5j` |
| Routing | `munichways-radlnavi-routing-00010-q78` |
| Direkt-Routing | `munichways-radlnavi-direct-routing-00001-mjb` |

Alle vier Dienste haben keine Mindestinstanz. APIs: 1 CPU, 512 MiB;
Routing: 1 CPU, 2 GiB. Standard-Concurrency 20, Direkt-Concurrency 4.
Die Direkt-API verwendet dasselbe Backend-Image wie Standard. Der aktuelle
`cloudbuild-api.yaml` synchronisiert nach dem Backend-Deploy auch die aktivierte
Direkt-API (`sync_direct_api.py`). Ein erneuter Direkt-Graph-Build ist bei reinen
Backend-Änderungen nicht nötig; für die neuen Treppen-/Fährregeln schon.

## Messung und Befunde

Vier sequenzielle Anfragenpaare, kein Lasttest; zwei Zwischenziele:
`48.156304,11.540013 > 48.102548,11.568796 > 48.120477,11.655645 > 47.991860,11.828568`.
Route und `/tag_distribution` separat, vollständige OSRM-Legs inklusive
Entfernungen und gesnappter Endpunkte. Zeiten einschließlich Netzwerk:

| Variante | Route erster / zweiter Aufruf | Komfort erster / zweiter Aufruf |
| --- | --- | --- |
| Standard, 43,14 km | 0,514 / 0,396 s | 26,046 / 0,546 s |
| Direkt, 37,20 km | 0,397 / 0,343 s | 19,853 / 0,660 s |

Die Antworten beider Wiederholungen enthalten gleiche Distanzen und Komfortdaten.
Standard: Index 77, Abdeckung 84 %. Direkt: Abdeckung 50 %, daher gemäß bestehender
Abdeckungsschwelle kein belastbarer Index; das ist kein Timeout.

Cloud-Logs bestätigen die langen Analysezeiten serverseitig (25,720 / 19,546 s).
Die APIs waren bereits aktiv; es sind keine reinen Container-Kaltstarts.
Der starke Wiederholungseffekt spricht für Datenbank-/Dateicachezugriffe.
Die bisherige Protokollierung trennt SQL, JSON-Decodierung und Segmentberechnung
nicht. Ein konkreter SQL-Engpass oder Speichermangel ist damit noch nicht bewiesen.

Separat belegen Logs um 15:57 UTC einen echten doppelten Kaltstart:
Direkt-API startet um 15:57:00, Direkt-Routing erst um 15:57:10.
Der komplette Routing-Aufruf dauert 22,032 s, davon 11,953 s im Routing-Dienst.
Spätere warme Direkt-Routing-Anfragen liegen z. B. bei 0,012–0,025 s.

## Umsetzung und nächste Schritte

* Routing 2.3.1 schließt Fähren in beiden Profilen aus. Treppen bleiben in beiden
  Varianten zugänglich, soweit kein Zugangsverbot besteht. Gemeinsamer Faktor 20:
  Ein Meter Treppe kostet mindestens 20 normale Meter, bei Standard unter
  zusätzlicher Berücksichtigung der Komfortbewertung. ETA separat mit maximal
  2 km/h; `bicycle=dismount` wird nicht mehr pauschal gesperrt. `bicycle=no` bleibt
  verboten. Dafür beide Routing-Graphen neu bauen; ein API-Deploy genügt nicht.
* Backend 2.3.1 protokolliert bei langsamer Segmentaufbereitung ab einer Sekunde
  die Zeiten für Knotenladen, Wegeladen und Segmentzuordnung, zusammen mit
  Anzahlen und Variante. Keine Koordinaten oder Knoten-IDs in diesen Logs.
* Gegen die belegten doppelten Kaltstarts empfiehlt sich eine Mindestinstanz
  für Direkt-API **und** Direkt-Routing. Das verursacht zusätzliche laufende
  Kosten und wurde weder in Produktion noch als Deployment-Default geändert.
  Mindestinstanzen allein lösen die nachgewiesenen langsamen Analysen nicht.
* Der abdeckende SQLite-Index `(node_id, way_id)` wurde inzwischen lokal auf
  der echten Oberbayern-Datenbank verglichen und in den Datenbankaufbau übernommen.
  Beide Indizes werden nach dem Datenimport aufgebaut. Es werden keine Wege,
  Tags oder Schleifen aus den Quelldaten entfernt.
* Der API-Container startet Python direkt aus der vorhandenen virtuellen Umgebung;
  Poetry läuft nur beim Build. Das vermeidet dessen Aufwand bei jedem Kaltstart.
* Nach Deployment beider APIs mit der Zeitmessung zuerst neue lange Routen,
  dann Wiederholungen prüfen. Die lokale Verbesserung ist noch kein Nachweis
  derselben Einsparung unter Cloud-Run-Dateisystembedingungen.

Bei dieser Prüfung wurden keine Produktionskonfigurationen verändert und keine
Deployments ausgelöst. Die Produktionsabnahme der Änderungen steht noch aus.

## Lokale Prüfung

58 Backend-Tests im Linux-Backend-Image erfolgreich, einschließlich echtem
Osmium-Import einer geschlossenen Teststrecke und Prüfung des SQLite-Abfrageplans.
Das lokale Windows-Testenvironment enthält Osmium nicht; der vollständige Lauf
erfolgte deshalb mit den vorhandenen Linux-Abhängigkeiten.
Standard- und Direkt-Regressionsprüfungen mit
echtem OSRM 26.6.5 und kleiner Testkarte erfolgreich, einschließlich Fähre und
Treppen mit Fahrradfreigabe in beiden Richtungen, Zwischenzielen, Rückweg,
Abbiegebeschränkungen und kürzerer, aber langsamerer Direktstrecke.
Wegen eines EOF-Fehlers im lokalen BuildKit wurden vorhandene Testimages mit
eingebundenen aktuellen Profilen verwendet und die Testgraphen darin neu erzeugt.
Ein vollständiger Oberbayern-Graph wurde nicht gebaut.

## Vertiefter Offline-Vergleich

Docker Desktop, 8 virtuelle CPUs / ca. 3,75 GiB RAM insgesamt. Je Backend-Worker
1 CPU und 512 MiB; reale Oberbayern-Datenbank aus `radlnavi-backend:latest`,
ca. 3 GiB. Eine separate Kopie erhielt den neuen Index. Die eingefrorene lange
München-Route umfasst 1.923 unterschiedliche Knoten, 1.443 geladene Wege und
1.944 durchlaufene Segmente.

| Messwert | Bisheriger Index | Abdeckender Index |
| --- | --- | --- |
| SQLite-Leseaufruf-Bytes, Knoten | 5.136.540 | 5.136.542 |
| SQLite-Leseaufruf-Bytes, Wege | 17.154.238 | 10.608.831 |
| Wegeladen, warme Wiederholungen | 27,24–28,12 ms | 24,12–26,71 ms |
| Query-Plan | `USING INDEX` | `USING COVERING INDEX` |

Das sind ca. 38 % weniger angeforderte Bytes beim Wegeladen, bzw. 29 % weniger
für Knoten- und Wegeladen zusammen. `rchar` aus `/proc/self/io` misst Leseaufrufe,
**keine physischen Datenträgerzugriffe**. Die lokalen Dateicaches wurden nicht
global geleert; deshalb werden die ersten Laufzeiten nicht als kontrollierter
Cloud-Kaltstartvergleich gewertet. Eine neue SQLite-Verbindung wurde je Lauf
geöffnet. Die vollständigen Antworten inklusive Highlight-Geometrien sind
identisch (SHA-256 `fb02e18caf87620f4dbb5eac3decacc7c3bbf3a0e6b1a316ecc666d26885801e`).

Der Index spart die zusätzlichen Tabellenzugriffe, wie im
[SQLite Query Planner](https://www.sqlite.org/queryplanner.html#covidx) beschrieben.

Separater Startvergleich ohne parallelen Indexaufbau, gleiche Ressourcen:
Poetry-Launcher 2,058 / 1,404 / 1,430 s bis `/health`, direkter Python-Launcher
0,870 / 0,871 / 0,894 s. Diese Messung umfasst Python/ASGI-Start, aber weder
Cloud-Run-Instanzbereitstellung noch den OSRM-Start.

Reproduzierbare Werkzeuge: `backend/benchmarks/database_lookup.py` für den
Indexvergleich, `analysis_worker.py` und `analysis_load.py` für lokale isolierte
API-Vergleiche. Der Lasttest verwendet bewusst dieselben eingefrorenen OSRM-Legs
für beide Varianten: Damit vergleicht er die identische Analysearbeit, nicht die
Qualität oder Laufzeit unterschiedlicher Routing-Graphen.

ABBA-Vergleich mit je 25 Anfragen pro Phase und 2 Anfragen/s pro aktiver Variante:
Ohne CPU-Zuordnung lag Standard allein bei p50 226/276 ms, unter Parallelbetrieb
bei 318/337 ms; p95 hatte einen Ausreißer auf 1.157 ms. Der gemeinsame lokale
Docker-Host ist somit keine vollständig unabhängige Cloud-Umgebung.

Kontrollierte Wiederholung mit Standard auf virtueller CPU 0, Direkt auf CPU 2
und Lastgenerator auf CPU 4 (weiterhin je 1 CPU / 512 MiB):

| Phase | Standard p50 / p95 | Direkt p50 / p95 |
| --- | --- | --- |
| A: Standard allein | 263 / 394 ms | — |
| B: Beide parallel | 273 / 331 ms | 280 / 333 ms |
| B: Beide parallel | 296 / 344 ms | 286 / 344 ms |
| A: Standard allein | 243 / 422 ms | — |

Alle Antworten erfolgreich und inhaltsgleich. Standard und Direkt sind im
warmen Betrieb ähnlich schnell. Im kontrollierten Test gab es keine Erhöhung
des Standard-p95, die Mediane schwankten bzw. stiegen leicht. Dies beweist weder
eine Produktionslatenz noch garantiert es fehlende Ressourcenkonkurrenz bei
beliebiger Last. Die getrennten Cloud-Run-Dienste bleiben unverändert bestehen.

## Lokaler Praxistest

Im Repository; wegen des gemeinsamen Fährverbots auch Standard neu bauen.
Direkt erst anschließend bauen, damit es den neuen Standard-Kartenstand übernimmt:

```powershell
docker compose build backend routing
docker compose -f compose.yaml -f compose.direct.yaml build direct-routing
docker compose -f compose.yaml -f compose.direct.yaml up --no-build
```

Das Backend baut die Datenbank mit neuem Index. Beide API-Varianten nutzen dieses
Image. Direkt-Routing baut den Graphen mit neuen Treppen-/Fährregeln aus demselben
Kartenausschnitt wie das neu gebaute Standard-Image. Das vorhandene Frontend
wird mitgestartet; dessen Neubau ist für diese Änderungen nicht erforderlich.

Prüfen: bekannte lange Route, anschließend eine andere lange Route, Wiederholung
und Wechsel zwischen den Varianten. Zusätzlich eine bisherige Treppen-/Fährroute
gezielt als Direkt testen. Die App muss für diesen lokalen Vergleich auf das
lokale Backend zeigen; RadlNavi im Browser zeigt weiterhin nur Standard.

Konkreter Praxistest für beide Varianten am Starnberger See (Breite/Länge):
`[47.996029, 11.344079] > [47.959608, 11.346577]`.
Die berechnete Strecke muss ohne Schiff/Fähre am Ufer verlaufen. Dieser reale
Korridor ist erst nach dem vollständigen Graph-Neubau prüfbar; die automatisierten
Testkarten decken Fähren mit und ohne Dauer sowie beide Richtungen ab.
