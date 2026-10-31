# US #35: Umsetzung und Betrieb der V20-Streckendetails

Frontendversion: **2.3.8**. User Story: [#35](https://github.com/MunichWays/munichways-radlnavi/issues/35).
Die [ursprüngliche Analyse](README.md) bleibt als Entscheidungsgrundlage erhalten.

## Bedienung

Rechtsklick oder langes Drücken auf der Karte öffnet das vorhandene Menü. Ab
Zoom 14 sucht ein Web Worker im V20-Datenbestand. Bei einem Treffer erscheint
„Details anzeigen“, bei mehreren Treffern zunächst eine Auswahl im Dialog.
Der ausgewählte Abschnitt wird mit seiner vollständigen V20-Geometrie violett
hervorgehoben. Der OSM-Bewertungslayer muss dafür nicht eingeschaltet sein.

Die Ansicht zeigt Namen, Bewertung/Happy Bike Level und OSM-Klasse sowie
Ist-Zustand, Forderungen und Netzplanung, Links und technische Angaben.
Fehlende Felder und Platzhalter werden ausgeblendet. Mapillary ist als Link
verfügbar. Unter „Mehr → Streckendetails an Kartenmitte“ ist die Funktion auch
ohne Maus erreichbar. Escape oder „Schließen“ entfernt die Hervorhebung und
gibt den Fokus an den Auslöser zurück.

Ladefehler, fehlender Treffer und zu kleiner Zoom haben getrennte Meldungen.
Fehlgeschlagene Suche und Detailabfrage können erneut versucht werden.
Route, Start/Ziel und Zwischenziele bleiben von der Detailsuche unabhängig.

## Datenvertrag und Build

`frontend/street-details-source.json` legt URL und SHA-256 des geprüften
Snapshots fest. `build_street_details.mjs` lädt genau diesen Stand und stoppt
bei geänderter Prüfsumme, fehlenden/doppelten OSM-IDs oder ungültigen Geometrien.
Aktuell wird ausschließlich LineString unterstützt; MultiLineString wird
ausdrücklich abgelehnt. Der Snapshot umfasst einen Münchner Ausschnitt.

Ausgabe in `frontend/public/street-details/`:

- `manifest.json`: Schemaversion 1, SHA-256, Quell-URL, Abrufdatum, Bounding Box
  und Featureanzahl. Veröffentlichung erst nach erfolgreicher Aufbereitung.
- `<sha256>/geometry.json`: originale Geometrien, Schlüssel `osm_<osm_id>` und
  kurze Namens-/Bewertungsfelder für die Kandidatenauswahl.
- `<sha256>/details/00.json` bis `99.json`: Felder pro Weg, gruppiert nach den
  letzten beiden Ziffern der OSM-ID. Die MunichWays-ID ist kein Primärschlüssel.

Der reale Snapshot ergibt 19.124 Strecken, 7.008.083 Bytes Suchgeometrien und
100 Detailgruppen; die größte Gruppe umfasst 262.131 Bytes unkomprimiertes
JSON. Die Geometriedatei ist wegen der zusätzlich aufgenommenen Namen und
Bewertungen größer als die reine Geometrieschätzung der ursprünglichen Analyse.
Mit Python gzip komprimiert umfasst die Suchdatei 1.422.031 Bytes (rund 1,4 MB).

Der Docker-Build erstellt den Datenbestand in einer eigenen Stage und kopiert
ihn separat in das nginx-Image. Die Hash-Konfiguration invalidiert beim
Datenupdate den betreffenden Buildcache. nginx liefert fehlende Daten als 404,
revalidiert das Manifest und kann Snapshotdateien dauerhaft cachen. Der Client
bleibt für alle Abfragen beim einmal gewählten Snapshot. Ist dieser nach einem
Deployment nicht mehr vorhanden, nennt die Fehlermeldung das Neuladen der Seite.

Lokal: `npm run prepare:street-details` vor `npm start`; alternativ `--source`
für eine bereits heruntergeladene Datei. Ohne lokale Daten verwendet der
Entwicklungsproxy `/street-details` vom veröffentlichten Frontend.
Generierte Daten, Quelldownload und Testbrowser bleiben außerhalb von Git.

## Laufzeit und Abweichungen von der Planung

- Ein gleichmäßiges geografisches Raster ersetzt eine zusätzliche R-Tree-
  Abhängigkeit. Große Feature-Bounding-Boxes kommen in eine begrenzte Überlaufliste.
  Nach der Vorauswahl entscheidet der Abstand zu allen Liniensegmenten.
- Suchradius: acht CSS-Pixel in Web-Mercator-Auflösung am Suchpunkt, höchstens
  20 Meter. Die Berechnung ist von der Kartenrotation unabhängig.
- Der Worker lädt und parst Geometrien einmal pro Sitzung und hält den Index.
  Nur nahe Kandidaten werden an React übertragen. Die kurzen Namens- und
  Bewertungsfelder erlauben eine verständliche Auswahl ohne Detaildownloads.
- Der Hauptthread lädt jeweils nur die gewählte Detailgruppe. Bis zu acht
  Gruppen werden im Speicher gehalten. Ein neuer Klick oder Schließen bricht
  entbehrliche Anfragen ab; verspätete Antworten werden ignoriert.
- Manifest und Geometriedownload haben je 45 Sekunden Timeout; Detaildownloads
  30 Sekunden. Workerfehler lassen einen neuen Worker beim Wiederholen zu.
- Leere/ungültige Antworten und HTML statt JSON werden zurückgewiesen.
  Rohes HTML wird nicht in React eingesetzt: nur Linktext und geprüfte absolute
  HTTP-/HTTPS-URLs werden übernommen. Zugangsdaten in URLs sind nicht erlaubt.
- Der bereits vorhandene Leaflet-Fork enthält `tapHold`; dieser ist explizit
  aktiviert. Die zusätzliche Kartenmitte-Aktion bietet einen sichtbaren
  Tastaturzugang. Auf schmalen Ansichten füllt der Detaildialog den Bildschirm.

OSRM, Backend und Routingprofile wurden nicht verändert. Ein Frontend-
Deployment reicht aus. Die GitHub-Actions-Regressionen prüfen jetzt auch
Frontendänderungen, Datenaufbereitung und TypeScript.

## Prüfprotokoll

Geprüft am 31. Oktober 2026 mit Node 20.11.0:

- Datenaufbereitung gegen den per SHA-256 festgelegten Originalsnapshot:
  19.124 gültige Strecken, 100 Detailgruppen; keine doppelten OSM-IDs.
- `npm run test:street-details-build`: drei Tests erfolgreich, einschließlich
  Hashwechsel, fehlender/doppelter IDs und ungültiger Geometrien.
- Vollständige Frontend-Suite: 13 Testsuites, 90 Tests erfolgreich.
  Nach der letzten Menükorrektur wurden die betroffenen Routing-/Clienttests
  erneut ausgeführt: neun Tests erfolgreich.
- `npm run lint:street-details`: keine Fehler oder Warnungen in den neuen
  Produktmodulen. `tsc --noEmit` erfolgreich.
- Produktionsbuild einschließlich separatem Worker erfolgreich. Bereits
  vorhandene Warnungen aus `App.tsx`/`routeTransfer.ts` sowie der veralteten
  Browserslist-Datenbank bleiben sichtbar. Die neue CI prüft die Detailmodule
  strikt und baut das Bundle mit den bestehenden Warnungen.
- `node tests/street_details.browser.mjs`: Desktop-Rechtsklick und mobiles
  Touch-Halten mit echten V20-Daten im Produktionsbundle erfolgreich, jeweils
  mit echtem Worker, Kandidatenauswahl, Detailabruf, sichtbarer Hervorhebung,
  erreichbarem Schließen, Fokus-Rückgabe und Wiederverwendung des Index.
  Realer Abschnitt: OSM `372013735` am Thomas-Wimmer-Ring. Der mobile Test
  verwendet Touch-Emulation in Headless Edge bei 390 × 844 CSS-Pixeln;
  der Desktoptest 1280 × 900. Screenshots wurden visuell geprüft.
- Dokumentationsverweise und `git diff --check` geprüft.

Docker-/nginx-Laufzeitprüfung und ein vollständiger Containerbuild konnten
lokal nicht ausgeführt werden, weil der Docker-Daemon nicht läuft. Ein Test
auf einem physischen iPhone/Android-Gerät und ein Produktionsdeployment sind
noch nicht erfolgt. Die Browserprüfung ersetzt diese gerätespezifische Abnahme
nicht; externe Basiskartentiles sind im lokalen Test ausgespart.
