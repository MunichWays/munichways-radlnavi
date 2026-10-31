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
Fehlende Felder und Platzhalter werden ausgeblendet. Eine Mapillary-Vorschau
steht bei ermittelbarer Bild-ID ganz oben. Der blau hinterlegte Titel lässt
sich ziehen oder mit den Pfeiltasten verschieben. „Verkleinern“ minimiert das
Fenster; an der unteren rechten Ecke kann es in der Größe geändert werden.
Escape oder „Schließen“ entfernt die Hervorhebung und
gibt den Fokus an den Auslöser zurück.

Ladefehler, fehlender Treffer und zu kleiner Zoom haben getrennte Meldungen.
Fehlgeschlagene Suche und Detailabfrage können erneut versucht werden.
Route, Start/Ziel und Zwischenziele bleiben von der Detailsuche unabhängig.

## Datenvertrag und Build

`frontend/street-details-source.json` legt URL, Erstellungsdatum und SHA-256 des geprüften
Snapshots fest. `build_street_details.mjs` lädt genau diesen Stand und stoppt
bei geänderter Prüfsumme, fehlenden/doppelten OSM-IDs oder ungültigen Geometrien.
Aktuell wird ausschließlich LineString unterstützt; MultiLineString wird
ausdrücklich abgelehnt. RadlNavi verwendet jetzt
`IST_RadlVorrangNetz_Oberbayern_V20.geojson` einschließlich zusätzlicher Strecken
außerhalb Münchens. Der Datenzugriff der MunichWays-App wird dadurch nicht geändert.

Ausgabe in `frontend/public/street-details/`:

- `manifest.json`: Schemaversion 1, SHA-256, Quell-URL, Quelldatum (`sourceCreatedAt`), Abrufdatum, Bounding Box
  und Featureanzahl. Veröffentlichung erst nach erfolgreicher Aufbereitung.
- `<sha256>/geometry.json`: originale Geometrien, Schlüssel `osm_<osm_id>` und
  kurze Namens-/Bewertungsfelder für die Kandidatenauswahl.
- `<sha256>/details/00.json` bis `99.json`: Felder pro Weg, gruppiert nach den
  letzten beiden Ziffern der OSM-ID. Die MunichWays-ID ist kein Primärschlüssel.

Der Oberbayern-Snapshot ergibt 27.314 Strecken, 10.108.851 Bytes Suchgeometrien und
100 Detailgruppen; die größte Gruppe umfasst 342.526 Bytes unkomprimiertes
JSON. Die Geometriedatei ist wegen der zusätzlich aufgenommenen Namen und
Bewertungen größer als die reine Geometrieschätzung der ursprünglichen Analyse.
Mit Python gzip komprimiert umfasst die Suchdatei 2.115.474 Bytes (rund 2,1 MB).

Die Umstellung erweitert den bisherigen Bestand um 8.190 Strecken. Alle 27.314
Geometrien sind LineStrings mit eindeutiger OSM-ID. Geprüfter Quellhash:
`2710ba91fb183f44498bf9079b842154f20ddb897aa14bc72da942d03c6015f3`.
Die ursprüngliche Analyse und ihr Snapshot-Report dokumentieren weiterhin die
damals geprüfte Münchner Quelle. Der aktuelle Bestand reicht ungefähr von
10,835 bis 12,716° Ost und von 47,624 bis 48,405° Nord; daraus folgt keine
vollständige Abdeckung jedes Weges in Oberbayern.

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
  aktiviert. Das schwebende Fenster bleibt auch beim Verschieben der Karte offen
  und wird auf die sichtbare Viewportgröße begrenzt.

## Feintuning

Die Ansicht heißt „Streckendetails“, besitzt einen blauen, verschiebbaren Header
wie „Hinweise prüfen“ und bleibt ohne modale Sperre über der Karte geöffnet.
„Verkleinern“ klappt den Inhalt ein; die untere rechte Ecke dient zum Skalieren.
Attribute erscheinen kompakt als „Bezeichnung: Wert“, mit Umbruch langer Texte.
Bekannte Ebenheitswerte sind übersetzt, beispielsweise `good` → „gut“.
Für Stellen ohne Treffer wird kein zusätzlicher Hinweis angezeigt.

Die Fußzeile lautet für den festgelegten Snapshot:
„Datenstand 26.10.2026, Quelle IST_RadlVorrangNetz_Oberbayern_V20.geojson.“
Das Datum stammt aus der zusammen mit dem Quellhash gepflegten `createdAt`-
Angabe, nicht aus dem Build-/Downloadzeitpunkt. Die GeoJSON enthält selbst kein
Datumsfeld. Der vom Datenverantwortlichen genannte 26. Oktober stimmt mit dem
am 31. Oktober geprüften HTTP-Header `Last-Modified: Mon, 26 Oct 2026 18:55:33 GMT`
überein. Bei einem neuen Quelldatenstand müssen Hash und Quelldatum aktualisiert werden.

Eine ermittelbare Mapillary-Bild-ID aus einem Mapillary-Link führt ganz oben
zur offiziellen Bild-Einbettung im Foto-Modus. Die URL wird aus validierten
Mapillary-Links erzeugt; beliebige Fremdhosts werden nicht als Vorschau akzeptiert.
Es werden keine API-Zugangsdaten aus der App kopiert. Der Anbieter lädt die
Vorschau in einem eigenen iframe; ein zusätzlicher Bildlink bleibt verfügbar.
Die Einbettung wurde ohne Anmeldung mit einem realen Bild im Testbrowser geprüft.
Grundlage: [offizielle Mapillary-Einbettung](https://help.mapillary.com/hc/en-us/articles/115001778705-How-to-embedding-a-Mapillary-capture-into-your-own-app).

Der Kartenmitte-Button ist entfernt. „Hinweise prüfen“ steht als dezente Aktion
ohne Rahmen direkt über „Über RadlNavi“; dessen Beschreibung verwendet den
vereinfachten Text zum gemeinsam bewerteten Radnetz.

OSRM, Backend und Routingprofile wurden nicht verändert. Ein Frontend-
Deployment reicht aus. Die GitHub-Actions-Regressionen prüfen jetzt auch
Frontendänderungen, Datenaufbereitung und TypeScript.

Feintuning-Prüfung: vollständige Frontend-Suite mit 93 Tests erfolgreich,
Datenbuild-Tests, Lint und TypeScript ebenfalls erfolgreich. Die Browserprüfung
deckt zusätzlich Verschieben, Minimieren/Wiederherstellen, Kartenbedienung bei
offenem Fenster und die tatsächliche Mapillary-Einbettung ab.

## Prüfprotokoll

Quellenwechsel auf Oberbayern: neue Prüfsumme und alle Geometrien erfolgreich
im Datenbuild validiert; 26 betroffene Frontendtests erfolgreich. Zusätzlich
wurde der vollständige Suchindex mit dem realen neuen Datenbestand aufgebaut
und OSM-Weg `171431838` („Wuhrweg“, 12,228° Ost / 48,053° Nord) gefunden und
aus der zugehörigen Detailgruppe geladen. Eine kleine Originalgeometrie dieses
neu hinzugekommenen Weges ist als Regressionstest eingecheckt.

Die folgenden Angaben beziehen sich auf die ursprüngliche Umsetzung:

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


## Netzauswahl

Die Radiobuttons "Alle Details" (Standard) und "RadVorrang-Netz" ersetzen den
bisherigen Bewertungsschalter. Alle Details behält den bisherigen Kachellayer
und die vollständige Detailsuche. RadVorrang-Netz zeigt ausschließlich die
6.507 passenden V20-Abschnitte als nicht interaktiven Leaflet-Canvas-Layer und
beschränkt die Detailsuche auf dieselben OSM-IDs. Beim Wechsel schließen sich
offene Streckendetails und die Markierung wird entfernt.

Das Kriterium wurde in der App geprüft:
[`StreetDetails.fromV20Json`](https://github.com/MunichWays/munich-ways-app/blob/master/lib/model/street_details.dart)
verwendet `!['-', null, ''].contains(properties['munichways_mw_rv_route'])`.
Die Regel wird exakt übernommen: zusammengesetzte Werte wie `Standard,-` und
`-,-` sind enthalten; es wird weder getrimmt noch an Kommas aufgeteilt.

Der Datenbuild erzeugt `priority-network-v1.json` (gefilterte Geometrien und kurze
Bewertungsfelder) und `priority-ids-v1.json` (Mitgliedschaft für den Suchworker).
Beide liegen beim bestehenden Snapshot-Hash. Bestehende `geometry.json` bleibt
bytegleich, damit bereits immutable gecachte Daten kompatibel bleiben.
Die Zusatzdateien werden erst bei Auswahl des RadVorrang-Netzes geladen.
Abbruch, Ladefehler und erneutes Laden sind abgedeckt; ein fehlgeschlagener
Netzdownload zeigt eine Fehlermeldung mit Wiederholung an.

Validierung der Netzauswahl: 98 Frontendtests in 14 Suites und vier Datenbuildtests
erfolgreich, ebenso TypeScript, striktes Lint und Produktionsbuild. Der echte
Produktionsbuild wurde auf Desktop und mit mobiler Touch-Emulation geprüft:
Standardauswahl, Wechsel beider Layer, Bereinigung des Canvas und gefilterte
Detailsuche mit echtem Worker und anschließendem Detailabruf.

## Start- und Infofenster

`AboutDialog.tsx` ersetzt den bisherigen kurzen Über-Dialog. Er erscheint bei
jedem Start und lässt sich über „Mehr → Über RadlNavi“ erneut öffnen.
Schließen-Symbol, „Karte entdecken“, Escape und Klick auf den Hintergrund
schließen den modalen Dialog. Die drei nativen, per Tastatur bedienbaren
Aufklappabschnitte starten geschlossen. Die Farblegende steht im ersten
Abschnitt; die neuen Links zum Änderungsprotokoll und Downloadordner stehen
unter „Daten & Aktualisierungen“. Der Text entspricht der gelieferten Vorlage.

Der Dialog ist auf 560 px Breite und 800 px Höhe begrenzt, auf kleinen
Bildschirmen mit 12 px Rand. Die Größenberechnung berücksichtigt den sichtbaren
Viewport, da die Kartenfläche auf Mobilgeräten über den Layoutbereich hinausragen
kann. Nur der Inhalt scrollt; Titel, Schließen-Symbol und Abschlussaktion bleiben
erreichbar. Ein kleines MunichWays-Logo steht über dem Titel. Es gibt weder alte
uMap-Bearbeitungslinks noch eine pauschale V20-Dateiangabe im Starttext; der
konkrete Quellenname bleibt im datenabhängigen Streckendetail-Fenster.

## Deutsche OSM-Anzeigen und Feedback

`streetOsmText()` übersetzt Straßenart, Oberfläche, Ebenheit, Fahrradregelung,
Zugang und Beleuchtung. Mehrfachwerte und Angaben wie „links: …; rechts: …“
werden einzeln übersetzt. `streetWidth()` zeigt metrische Breiten mit
Dezimalkomma. Die Oberflächenübersetzung wird auch in der bisherigen
Routenanalyse verwendet; Betonplatten und Betonspurbahnen sind entsprechend
der [OSM-Dokumentation](https://wiki.openstreetmap.org/wiki/DE:Key:surface)
benannt. Eigennamen und technische IDs werden nicht übersetzt. Neue unbekannte
Werte bleiben erhalten, damit keine Informationen verloren gehen.

Gegen den vollständigen aktuellen Snapshot geprüft: alle 91 unterschiedlichen
Sachwerte in den sechs Feldern haben eine deutsche Anzeige. Der bestehende
Dialogtest prüft die deutschsprachigen Felder einschließlich Mehrfach-Zugang
und Dezimalkomma.

„Feedback geben“ im Hauptmenü und „Feedback an mail@munichways.de“ im Infofenster
öffnen per `mailto:` eine Nachricht mit Betreff „Feedback zu RadlNavi“.
