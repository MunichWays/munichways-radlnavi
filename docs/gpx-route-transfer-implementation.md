# GPX und Routenübergabe – Umsetzung und Testablauf

Issue: [MunichWays-App #168](https://github.com/MunichWays/munich-ways-app/issues/168).
Feature-Branch in beiden Repositories: `feature/gpx-route-transfer`.

Erweiterung auf 50 Zwischenziele: [User Story MunichWays/munich-ways-app#288](https://github.com/MunichWays/munich-ways-app/issues/288),
Branch `fix/288-b86-gpx-50-stops` in beiden Repositories.

## Testbare Teilschritte

1. **Webplanung:** Start, bis zu 50 Zwischenziele und Ziel suchen oder als
   `Breitengrad, Längengrad` eingeben. Zwischenziele mit Pfeilen sortieren,
   entfernen und auf der Karte verschieben. Umkehren dreht die gesamte Reihenfolge.
   Die Webplanung verwendet den vorhandenen OSRM-Endpunkt und berücksichtigt alle
   Legs für Schritte und Komfortanalyse.
2. **Dateiübergabe:** GPX herunterladen. In der App den Routenplaner öffnen,
   „Route importieren“ wählen, Vorschau prüfen und „Speichern & übernehmen“.
   App beenden, neu starten und gespeicherte Route öffnen. Geometrie und Hinweise
   bleiben erhalten; keine Routinganfrage beim Laden der Originalstrecke.
   [Kleine Testdatei mit zwei Zwischenzielen](gpx-examples/munichways-two-stops.gpx)
   enthält eine synthetische Testroute und dient dem Importtest, nicht einer
   Empfehlung zum Abfahren.
3. **Rückweg:** In der App über „GPX exportieren“ die Datei teilen/speichern,
   anschließend in RadlNavi importieren. Originalstrecke und Ziele vergleichen.
   Unberechnete Pläne zuerst berechnen. Einzelne fremde GPX-1.1-Tracks werden
   ohne Abbiegeansagen und ohne erfundene Fahrzeit übernommen. Mehrere Tracks
   oder getrennte Segmente werden derzeit verständlich abgelehnt.
4. **Link/QR:** Nach Einrichtung des Servers „In App öffnen / teilen“ auswählen
   und Speicherung ausdrücklich bestätigen. Link oder Handykamera verwenden.
   Link lädt denselben Snapshot; Übernahme/Speichern erfolgen über denselben
   App-Importdialog. Der Link gilt genau 90 Tage. Gespeicherte Kopien bleiben
   unabhängig davon auf dem Handy. Ohne App zeigt der Weblink eine Vorschau,
   GPX-Download und Installationslinks.

## Verhalten importierter Originalstrecken

Die App speichert Snapshotdateien unter `route-snapshots/<id>.json` im privaten
Anwendungsverzeichnis. `savedRoutes.json` enthält nur die Referenzen und die
vorhandenen Planungs-/Favoritenfelder. Alte gespeicherte Pläne bleiben lesbar.
Snapshotdateien werden vor dem Index geschrieben; Aufräumen folgt erst nach
erfolgreichem Indexspeichern. Schreiben innerhalb eines Store-Objekts ist serialisiert.
Die Routenliste lädt nur den Index; erst bei Auswahl wird genau der benötigte
Snapshot gelesen. Verspätete Ladeantworten können eine neue Auswahl nicht ersetzen.

Importe ersetzen keine Route allein wegen desselben Namens. Bei 25 gespeicherten
Routen muss zunächst ein Eintrag entfernt werden. Beschädigte oder fehlende
Snapshots werden nicht stillschweigend neu berechnet. Importabbruch oder Fehler
ändern die aktuelle Route nicht.

Originalstrecken deaktivieren automatische Neuberechnung und Variantenwechsel
für diesen Routenmodus, ohne die allgemeinen Einstellungen umzuschreiben. Beim
Abweichen bleibt das Original erhalten. Im Routenplaner kann man bewusst Orte
ändern und eine neue Route berechnen. Normale Planung und Neuberechnung bleiben
außerhalb des Originalmodus erhalten. Ein Import beendet eine laufende Navigation
erst nach ausdrücklicher Übernahme.

## Austauschvertrag

GPX 1.1 enthält den vollständigen Track in den Standardfeldern. Unter
`extensions/mw:route`, Namensraum `https://www.munichways.de/gpx/1`, liegt ein
XML-escaped JSON-Snapshot. `version: 1` umfasst Name, Zeit, Anbieter `radlnavi`,
Variante, geordneten Plan (`name`, `coordinates` in **Längengrad/Breitengrad**) und
eine OSRM-Antwort mit genau der gewählten Route und allen Legs/Steps.

Grenzen: 4 MiB Datei/JSON, 100.000 Trackpunkte, 50 Zwischenziele. Importprüfungen
vergleichen Standardtrack und Snapshot sowie Track und aufeinanderfolgende
Stepgeometrien. Unbekannte native Formatversionen werden abgelehnt. Externe
XML-Entitäten/DOCTYPE sind nicht zugelassen. Keine beliebigen URLs aus Dateien
oder Links abrufen. Komfort ist optional und kein Importhindernis.

Keine Google- oder komoot-Integration und keine zusätzliche Exportauswahl
„Standard-GPX ohne Zusatzdaten“. Ein fremder Track wird beim Export natürlich
weiterhin als Standardtrack ausgegeben, da er keine MunichWays-Navigationsdaten hat.

## Lokaler Linkdienst

Docker Compose nutzt einen eigenen persistenten Datenträger `shared-routes`.
Für eine schnelle lokale Prüfung ohne Routingdatenbank kann der isolierte Router
gestartet werden; er benötigt keine OSRM-Instanz:

```powershell
$env:SHARED_ROUTES_DIR = "$PWD/backend/.shared-routes"
$env:SHARE_PUBLIC_BASE_URL = 'http://localhost:3000'
backend/.venv/Scripts/python.exe -m uvicorn dev_shared_routes:app --app-dir backend --port 8001
```

Für das Webfrontend in einem zweiten Terminal:

```powershell
cd frontend
$env:REACT_APP_BACKEND_URL = 'http://localhost:8001'
npm start
```

Dieser isolierte Dienst stellt nur Teilen/Lesen bereit. Bereits vorhandene GPX-
Dateien können übernommen und geteilt werden; neue Routenberechnung benötigt den
normalen Backenddienst. Die FastAPI-Hülle `backend/dev_shared_routes.py` erlaubt
für diesen Test bereits den Zugriff von `http://localhost:3000`.

## Produktion vorbereiten

Cloudprojekt read-only verifiziert: `munichways-radlnavi-prod`, Region
`europe-west3`, Standard-API `munichways-radlnavi-api`. Der aktuell allgemeine
gcloud-Projektstandard zeigt auf ein anderes Projekt; Befehle daher immer mit
explizitem `--project` ausführen.

Einmalige Einrichtung nach Veröffentlichung der neuen Backendversion (am
15. Oktober 2026 für `munichways-radlnavi-prod` ausgeführt und live geprüft):

```powershell
backend/configure_route_sharing.ps1 -Project munichways-radlnavi-prod
```

Das Skript richtet einen privaten GCS-Bucket mit 90-Tage-Löschregel ein, gibt dem
API-Dienstkonto Objektzugriff und setzt `SHARED_ROUTES_BUCKET` sowie
`SHARE_PUBLIC_BASE_URL`. Fehlende Konfiguration ergibt HTTP 503 statt eines
flüchtigen Containerspeichers. Lesen nach Ablauf ergibt HTTP 410; bereits
gelöschte Objekte ergeben HTTP 404. Die API begrenzt Uploadgröße sowie Erstellung
pro IP/Instanz; diese Grenze ist keine globale, instanzübergreifende Quote.

`cloudbuild-api.yaml` setzt die beiden Sharing-Variablen künftig bei jedem
API-Deployment und prüft anschließend den Speicherzugriff. Die einmalige
Bucket-Einrichtung bleibt eine Aufgabe für einen entsprechend berechtigten
Projektadministrator; das Build-Dienstkonto erhält dafür keine zusätzlichen
Storage-Admin-Rechte. Der reine Lesecheck erstellt keine Testobjekte. Der
separate Live-Rundlauf zur Einrichtung prüfte Erstellen, CORS, identisches
Zurücklesen und 90 Tage Laufzeit; die synthetischen Testobjekte wurden entfernt.

Firebase Hosting muss `firebase-public/.well-known/` veröffentlichen. Der Web-
Container leitet `/r/<id>` an React weiter. Android-Manifest und iOS-Entitlements
sind auf `radlnavi.munichways.de/r/` begrenzt. Die AASA-Datei nutzt das vorhandene
iOS-Team `J9FYFLM2K5` und Bundle `com.munichways.app`.

`assetlinks.json` enthält den aus dem vorhandenen lokalen APK ausgelesenen
**Debug-Zertifikatfingerabdruck**. Für Play-/Store-Builds muss zusätzlich der
SHA-256-Fingerabdruck des tatsächlichen App-Signing-Zertifikats ergänzt werden;
ein Uploadzertifikat allein genügt dafür nicht. iOS benötigt ein aktualisiertes
Provisioningprofil mit Associated Domains und eine Prüfung auf macOS/iPhone.
Die Zertifikat-/iOS-Zuordnung ist noch auf Geräten zu verifizieren. Der private
Routenspeicher und die API-Konfiguration sind eingerichtet; der erfolgreiche
Live-Dateirundlauf bestätigt noch keine native App-/Universal-Link-Zuordnung.

## Handyprüfung

- Native GPX aus RadlNavi importieren, speichern, neu starten und laden:
  gleiche Strecke, gleiche Zwischenziele und verfügbare Abbiegehinweise.
- Gleichen Namen zweimal importieren: keine bisherige Route ersetzen.
- Abbrechen, beschädigte Datei, Datei über 4 MiB, unbekannte Erweiterung und
  mehrere Segmente prüfen; danach muss ein gültiger Import funktionieren.
- Fremden einzelnen Track laden: Strecke sichtbar, keine Abbiegeansagen oder
  falsche Dauer; Export und Webimport erhalten den Track.
- Laufende Navigation: Importvorschau darf sie nicht ersetzen. Übernehmen
  beendet sie; anschließend Originalnavigation neu starten.
- Route verlassen: Original bleibt erhalten, keine automatische Umplanung.
  Routeneinstellung ändern und neu laden: weiterhin Original. Normale Route
  anschließend planen: reguläre Neuberechnung wieder verfügbar.
- Dateien aus Android-Dateimanager/Messenger und iOS-Dateien öffnen; Content-URI-
  bzw. Security-Scoped-Zugriff prüfen. Android-Dateizuordnung hängt auch vom
  bereitgestellten GPX-MIME-Typ ab; der Dateiauswahldialog bleibt der sichere Weg.
- Nach Hostingveröffentlichung: QR-/HTTPS-Link bei kalter/warmer App, ohne App,
  ohne Netz, erneutem Öffnen nach Fehler und nach 90 Tagen prüfen. Offline-Laden
  gespeicherter Strecken verspricht keine Offline-Karten.
