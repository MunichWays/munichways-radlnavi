# Architektur und Datenvertrag v1

## Grenzen

`junction_review` ist ein eigenständiger Python-Kern mit lokaler Browseroberfläche. Er importiert weder Backend-Module noch die bisherigen münchenspezifischen Generatoren. `adapters.py` übersetzt deren Ergebnisse in ein allgemeines Projektformat. Python-Standardbibliothek und Browser-APIs reichen zum Starten aus.

| Modul | Verantwortung |
| --- | --- |
| `model.py` | Formatversion, Validierung, stabile IDs, Geometriefingerprints und wirksamer Prüfstatus |
| `geometry.py` | Polygonprüfung und Schnittpunkte bestehender Anschlüsse mit ihren belegten Wegen |
| `gate_edit.py` | Atomare Flächen-/Anschlussbearbeitung, Weg-Snapping, Richtung und stabile Identitäten |
| `cycling.py` | Gemeinsame OSM-Zugangs-/Richtungsregeln für Vorschläge und manuelle Anschlussbearbeitung |
| `store.py` | Unveränderliche Imports, getrennte Änderungen, Revisionen, Verlauf und atomare Speicherung |
| `adapters.py` | Expliziter RadlNavi-Import und neutraler Export bestätigter Geometrien |
| `server.py` | Lokale HTTP-API und statische Oberfläche |
| `discovery.py` | OSM-Gebietssuche, eingefrorene Abfragen, Kandidatengruppierung, Spurpriorität und deterministische Geometrie-/Gatevorschläge |
| `osm_client.py` | Begrenzte Netzaufrufe, Wiederholung temporärer Fehler, serialisierte Abfragen und kurzlebiger Cache |
| `workspace.py` | Explizite Projektadressierung, gemeinsame Schreibsperren und abbrechbare Hintergrundaufträge |
| `render.py` | Eigenständige SVG-Prüfbilder mit Geometrie, Beschriftung und Fahrtrichtungspfeilen |
| `web/` | Übersicht, zuschaltbare OSM-Standardkarte, Offline-Vektorwege, Flächenbearbeitung und Prüfentscheidungen |
| `__main__.py` | Import, Demo, Serverstart und Export |

## Allgemeines Importformat

JSON mit `schemaVersion: 1`, `project`, `source` und `sites`. Ein kanonischer Import ist in jedem erzeugten Projekt unter `imports/<hash>.json` einsehbar und direkt wieder importierbar.

`project`: stabile `id`, freie `city`, `district` und optional `area` als GeoJSON-Polygon. Geokoordinaten sind immer `[Längengrad, Breitengrad]` in WGS84. Gebiete wählen Mittelpunkte aus; Kreuzungsflächen werden nicht an Stadtteilgrenzen abgeschnitten.

`source`: Adapterkennung, Quelldateiname, SHA-256, OSM-Zeitpunkt und Attribution. Der OSM-Zeitpunkt ist vom Prüfzeitpunkt getrennt. Für künftige direkte OSM-Imports müssen auch Knotenattribute und Restriktionsrelationen eingefroren werden. Die importierten alten Bildrunden sind keine vollständige Evidenz für eine technische Rechtsprüfung.

Jede Kreuzung enthält:

- `id`, `number`, `name`, `origin`, `geometryRevision`;
- geschlossenes `polygon`, `gates`, `logicalArms`;
- `ways`: unveränderte Tags und Koordinaten je OSM-Weg;
- `sourceFingerprint`, `provenance`, optionale Priorität `outgoingLanes`, `note`.

Ein Gate hat stabile `id`, separate `label`, `kind: entry|exit`, `location`, `osmWayId` und importierte Richtungsevidenz. Gemeinsame Entry-/Exit-Positionen bleiben zwei logische Gates. Änderungen einer Fläche dürfen diese Identitäten nicht neu nummerieren. `logicalArms` ordnet Straßenarme den Beschriftungen zu; fehlende Zuordnung wird angezeigt und nicht aus Winkelwerten erfunden.

Der einfache Einzelrundenimport überträgt bisherige Entscheidungen als Herkunftsevidenz, ohne eine neue lokale Bestätigung zu erteilen. Der explizite Gesamtadapter `radlnavi_overview.py` übernimmt dagegen die dokumentierten Entscheidungen nach Prüfung ihrer bestehenden Geometrie-Hashes als `importedDecision`. Diese bleibt an Geometrie- und Quellfingerprint gebunden. Technische Belege, Live-Momentaufnahme, Einzelbeziehungsausschlüsse und Wiedervorlagen werden separat übernommen. Dafür liest ausschließlich der Adapter die Quellen des bisherigen Übersichtsprogramms; der Kern kennt keine Münchner Daten oder Backend-Module.

`geometryMode` unterscheidet bearbeitbare Geometrien (`editable`), dokumentierte Pilotflächen ohne editierbare Weg-/Gatedaten (`reference`) und Inventarkandidaten ohne Fläche (`none`). Bei unnummerierten Fällen ist `number: null` zulässig; stabile IDs bleiben erhalten. Fälle ohne Geometrie können keine neue Sichtfreigabe erhalten. Pilotreferenzen bleiben bestätigt, werden aber ohne Anschlussdaten nicht als neue technisch prüfbare Geometrien exportiert. Ursprüngliche Ausschlussgründe einschließlich vorläufiger Zurückstellungen bleiben als Herkunftsevidenz erhalten; die Sammelgruppe „Ausgeschlossen“ behauptet keine dauerhafte Schließung.

## Speicherung und Gültigkeit

```text
projekt/
  imports/<datensatz-hash>.json   unveränderte, normalisierte Importstände
  project.json                  aktiver Import + getrennte Änderungen/Entscheidungen
```

Die JSON-Dateien sind portabel und ohne Datenbank lesbar. Schreibvorgänge verwenden eine temporäre Datei im gleichen Verzeichnis und atomaren Austausch. Ein Prozess verwaltet ein Projekt. Der lokale Server serialisiert Anfragen; `expectedVersion` verhindert das Überschreiben durch veraltete Browseransichten. Mehrere Serverprozesse auf demselben Projekt sind nicht unterstützt.

Eine Entscheidung bindet sich an Geometriefingerprint **und** Quellfingerprint. Ändert sich einer, ist die alte Entscheidung weiterhin dokumentiert, aber nicht mehr gültig. Flächenänderungen erhöhen die Geometrierevision und speichern den vorherigen Stand. Quellaktualisierungen archivieren vorhandene Korrekturen; ungeänderte Kreuzungen behalten ihre Entscheidung. Ein identischer Import erzeugt keine neue Arbeit.

Statusdimensionen bleiben getrennt:

- Sichtentscheidung: `open`, `confirmed`, `deferred`, `excluded`.
- Technik: ohne importierte Evidenz zunächst `not-run`.
- Deployment: ohne importierte Evidenz zunächst `unknown`.

Beim Gesamtimport ersetzen vorhandene, passende technische Belege und der zuletzt verifizierte Deploymentstand diese Anfangswerte. Sie sind keine erneute technische Prüfung oder erneute Live-Verifikation. Nach Geometrieänderungen erscheinen frühere Live-Daten nur noch als älterer Stand. Ein Reimport mit `--refresh` aktualisiert die Quelle; lokale Entscheidungen haben weiter Vorrang und können nicht durch einen älteren Import überschrieben werden.

## API

| Endpunkt | Inhalt |
| --- | --- |
| `GET /api/project` | Wirksame Daten, Verlauf und lokales Sitzungstoken |
| `POST /api/sites/<id>/preview` | `{expectedVersion, geometry?, gateEdit?}` prüfen; kein Speichern; älteres `{polygon}` bleibt unterstützt |
| `POST /api/sites/<id>/save` | `{expectedVersion, geometry?, gateEdit?, status?, note?, deferredUntil?}` gemeinsam speichern |
| `GET /api/export` | Nur aktuell bestätigte Geometrien als Download |
| `POST /api/areas/search` | `{name}` → Namen, Rahmen, ID und Ebene; ohne vollständige Geometrien |
| `POST /api/areas/at` | `{location: [lon, lat]}` → benannte Verwaltungsgebiete am Kartenpunkt; ohne vollständige Geometrien |
| `POST /api/areas/boundary` | `{id}` → nur die ausgewählte vollständige Verwaltungsgrenze |
| `POST /api/areas/validate` | `{area}` → lokale Geometrieprüfung ohne Netzaufruf |
| `POST /api/areas/prepare` | `{selection: {relationId, name}}` oder `{selection: {name, area}}` → HTTP 202 mit Auftrags-ID |
| `GET /api/jobs/<id>` | Auftragsstatus: `running`, `complete`, `failed`, `cancelled`; abgeschlossen mit `projectId` |
| `GET /api/jobs/current` | Diagnose des laufenden Auftrags; Wiederaufnahme im Browser erfolgt über dessen tabgebunden gespeicherte Auftrags-ID |
| `POST /api/jobs/<id>/cancel` | Import verhindern, solange er noch nicht abgeschlossen ist |
| `GET /api/projects` | Gespeicherte Projekte im gleichen Arbeitsverzeichnis auflisten |
| `POST /api/projects/select` | `{id}` → vorhandenes Projekt öffnen; keine Änderungen entfernen |
| `GET /api/sites/<id>/image.svg` | Aktuell gespeicherte Geometrie als eigenständiges Vektorbild |

Fehlerhafte Geometrie: HTTP 400. Veralteter Bearbeitungsstand: 409. POST benötigt JSON und `X-Review-Token`. Der Server bindet ausschließlich `127.0.0.1` und akzeptiert nur die eigene Origin/Host-Adresse. Statische Dateien sind explizit freigegeben; es gibt keinen Zugriff auf beliebige lokale Dateipfade.

Es gibt kein serverweit veränderliches aktives Projekt. Daten-/Schreibanfragen adressieren das Projekt mit `X-Review-Project`, Downloadlinks mit `?project=<id>`. Ohne Angabe gilt das Startprojekt. Jeder Projektpfad wird auf das gemeinsame Arbeitsverzeichnis begrenzt. `Workspace` hält je Projekt genau eine `ProjectStore`-Instanz, damit parallele Requests dieselbe Schreibsperre und Versionsprüfung verwenden. Ein Projektwechsel in einem Tab kann Schreibzugriffe eines anderen Tabs nicht umleiten.

Ein laufender Auftrag wird im `sessionStorage` seines Browser-Tabs vermerkt. Neuladen nimmt nur diesen Auftrag wieder auf; ein anderer Tab übernimmt nicht automatisch das Ergebnis eines fremden Vorbereitungsauftrags. Nach Serverneustart wird eine nicht mehr bekannte Auftrags-ID verworfen, ohne gespeicherte Projekte anzutasten.

`web/api.js` kapselt Projektadressierung, Abbruch, Zeitüberschreitungen und Fehlermeldungen; `web/drawing.js` enthält reine, getestete Zeichenregeln. `web/area-ui.js` besitzt die Zustände der Gebietsauswahl und Aufträge. Spinner, Laufzeit, hervorgehobene Treffer und lokale Fehlerzustände bleiben an die Anfrage gebunden. Wiederholte Punkte, Startpunkt-Klick und Doppelklick werden vor der Übergabe an die OSM-Pipeline behandelt. Selbstüberschneidungen bleiben im Editor korrigierbar.

Der Overpass-Client serialisiert Netzaufrufe, wiederholt temporäre HTTP- und Netzwerkfehler höchstens zweimal und speichert maximal 20 kleine erfolgreiche Antworten für 15 Minuten. Suchabfragen laden keine Vollgeometrien. Temporäre Ausfälle ergeben HTTP 503 mit `retryable: true`, keine lokale Polygonfehlermeldung. Speicher-/Größenfehler verlangen ein kleineres Gebiet. Nach Abbruch kann ein bereits laufender Netzabruf noch auslaufen; weitere Wiederholungen und der Projektimport werden verhindert. Höchstens ein Vorbereitungsworker ist gleichzeitig aktiv. Ein Abbruch und der abschließende Import sind gegeneinander gesperrt; ein bereits fertiges Projekt wird nicht als abgebrochen ausgegeben.

Der Export hat `kind: junction-geometry-review`, Version 1 und `requiresTechnicalValidation: true`. Er enthält keine Aktivierung. Ein künftiger Routingadapter konsumiert diesen Stand und liefert technische Ergebnisse gebunden an beide Fingerprints zurück. Kopieren in einen Produktionskatalog und Deployment bleiben explizite Schritte.

## Weiterentwicklung mit geringem Tokenverbrauch

Die Gebietspipeline ist als Programmlogik implementiert, kein Prompt pro Kreuzung. `prepare(raw, selection)` ist rein und offline wiederholbar; `discover` ergänzt OSM-Zugriff und Datenvertrag. Der Server archiviert die vollständige Antwort vor dem Import. Auswahlidentität, unveränderlicher Import und lokale Korrekturen bleiben getrennt. Ein paralleler zweiter Vorbereitungsauftrag wird abgewiesen. Ein erneuter Auftrag für dasselbe bestehende Gebiet lädt dessen Projekt und verändert keine Entscheidungen. Eine vollständige technische Rechts-/Routingprüfung wird hier nicht behauptet.

Overpass wird ausschließlich durch einen expliziten Such-/Vorbereitungsauftrag angesprochen. Namen sind als QL-Strings maskiert, Relationsnummern validiert, gezeichnete Flächen geometrisch geprüft. Abfragen haben Zeit- und Antwortgrößenlimits; bei Fehlern bleibt das aktive Projekt bestehen. Serverseitige Netzaufrufe gehen an einen festen Overpass-Endpunkt, nicht an URLs aus Browseranfragen. Gebietssuche folgt der [Overpass-Dokumentation](https://dev.overpass-api.de/overpass-doc/en/full_data/polygon.html).

Kandidatensuche, OSM-Datenzugriff und Vorschlagsgenerator verwenden denselben Datenvertrag; ein Routingadapter kann später technische Ergebnisse ergänzen. Keine neue Python-Datei pro Bildrunde; Auswahl und Sonderentscheidungen gehören in Projektdaten. Vorhandene bestätigte Fälle und Ausschlüsse werden als Regressionsevidenz übernommen, ohne historische Entscheidungen umzuschreiben.

Der Editor verändert Fläche und bestehende Gates gemeinsam. `geometry` enthält `polygon`, `gates`, `logicalArms`. `gateEdit` ist `{action: add|move|delete|merge, gateId, location?, wayId?, mergeIds?}`. Beim Verschieben wird auf einen erlaubten OSM-Weg innerhalb von 12 m eingerastet und die angrenzende Flächengrenze angepasst. Uneindeutige Ziele verlangen einen expliziten Weg. Belegte Richtung und Ein-/Ausfahrt werden geprüft; falsche Richtung, Selbstüberschneidung und unauflösbare Grenzquerungen werden abgelehnt. Zusammenlegen ist auf gleichartige Anschlüsse desselben Straßenarms beschränkt; Ziel-ID und Labels bleiben stabil. `mergedFrom`, vorherige Geometrie und `gateChanges` dokumentieren entfernte bzw. verschobene Anschlüsse.

`web/gate-ui.js` hält Auswahl und Zielauswahl. Jede Vorschau enthält den vollständigen bereits geänderten Entwurf, damit eine spätere Flächenänderung gelöschte Punkte nicht wiederherstellt. Der Speicher übernimmt `logicalArms` zusammen mit Polygon und Gates, erhöht die Revision und bindet Freigaben/Evidenz weiterhin an den gesamten Geometriefingerprint. Zusätzliche Anschlüsse und neue Straßenarmdefinitionen brauchen einen späteren Bearbeitungsschritt. Ein einzelner Schnittpunkt belegt noch keine rechtlich oder sprachlich korrekte Fahrbeziehung.

Die optionale Hintergrundkarte lädt Standard-Tiles direkt aus `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Nur der sichtbare Ausschnitt wird angefordert, nach kurzer Verzögerung beim Verschieben/Zoomen. Der Browser übernimmt Cache und Referer nach der [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/). Die CSP erlaubt ausschließlich diesen zusätzlichen Bildhost, keine zusätzlichen Skripte oder API-Verbindungen. Ohne Tiles bleiben die importierten Vektorwege sichtbar. Die Oberfläche verwendet für Tiles und Geometrien eine gemeinsame lokale Web-Mercator-Projektion; das gespeicherte Datenformat ändert sich nicht.

`add` verwendet `kind: entry|exit`, `arm`, `location` und optional `wayId`. Die bisherige Grenze liegt hoechstens 12 m vom Ziel entfernt. Nummern werden aus bestehenden Punkten und Geometriehistorie fortgeschrieben; neue IDs folgen `manual-<kind>-<number>`. Vollstaendige Entwuerfe validieren neue Identitaeten, Strassenarm, Quellweg und Richtung erneut. `gateChanges.added` haelt Ergaenzungen getrennt von Verschiebungen fest.
