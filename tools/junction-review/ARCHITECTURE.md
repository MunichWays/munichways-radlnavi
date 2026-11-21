# Architektur und Datenvertrag v1

## Grenzen

`junction_review` ist ein eigenständiger Python-Kern mit lokaler Browseroberfläche. Er importiert weder Backend-Module noch die bisherigen münchenspezifischen Generatoren. `adapters.py` übersetzt deren Ergebnisse in ein allgemeines Projektformat. Python-Standardbibliothek und Browser-APIs reichen zum Starten aus.

| Modul | Verantwortung |
| --- | --- |
| `model.py` | Formatversion, Validierung, stabile IDs, Geometriefingerprints und wirksamer Prüfstatus |
| `geometry.py` | Polygonprüfung und Schnittpunkte bestehender Anschlüsse mit ihren belegten Wegen |
| `store.py` | Unveränderliche Imports, getrennte Änderungen, Revisionen, Verlauf und atomare Speicherung |
| `adapters.py` | Expliziter RadlNavi-Import und neutraler Export bestätigter Geometrien |
| `server.py` | Lokale HTTP-API und statische Oberfläche |
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
| `POST /api/sites/<id>/preview` | `{expectedVersion, polygon}` prüfen; kein Speichern |
| `POST /api/sites/<id>/save` | `{expectedVersion, polygon?, status?, note?, deferredUntil?}` speichern |
| `GET /api/export` | Nur aktuell bestätigte Geometrien als Download |

Fehlerhafte Geometrie: HTTP 400. Veralteter Bearbeitungsstand: 409. POST benötigt JSON und `X-Review-Token`. Der Server bindet ausschließlich `127.0.0.1` und akzeptiert nur die eigene Origin/Host-Adresse. Statische Dateien sind explizit freigegeben; es gibt keinen Zugriff auf beliebige lokale Dateipfade.

Der Export hat `kind: junction-geometry-review`, Version 1 und `requiresTechnicalValidation: true`. Er enthält keine Aktivierung. Ein künftiger Routingadapter konsumiert diesen Stand und liefert technische Ergebnisse gebunden an beide Fingerprints zurück. Kopieren in einen Produktionskatalog und Deployment bleiben explizite Schritte.

## Weiterentwicklung mit geringem Tokenverbrauch

Kandidatensuche, OSM-Datenzugriff, Vorschlagsgenerator und Routingadapter werden als getrennte Module ergänzt. Ihr Ergebnis durchläuft denselben Datenvertrag. Keine neue Python-Datei pro Bildrunde; Auswahl und Sonderentscheidungen gehören in Projektdaten. Vorhandene bestätigte Fälle und Ausschlüsse werden als Regressionsevidenz übernommen, ohne historische Entscheidungen umzuschreiben.

Der Editor verändert zunächst nur die Fläche und berechnet bestehende Gates neu. Zusätzliche Anschlüsse, Richtungsänderungen und Straßenarmzuordnungen brauchen einen späteren expliziten Bearbeitungsschritt. Ein einzelner Schnittpunkt belegt noch keine rechtlich oder sprachlich korrekte Fahrbeziehung.

Die optionale Hintergrundkarte lädt Standard-Tiles direkt aus `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Nur der sichtbare Ausschnitt wird angefordert, nach kurzer Verzögerung beim Verschieben/Zoomen. Der Browser übernimmt Cache und Referer nach der [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/). Die CSP erlaubt ausschließlich diesen zusätzlichen Bildhost, keine zusätzlichen Skripte oder API-Verbindungen. Ohne Tiles bleiben die importierten Vektorwege sichtbar. Die Oberfläche verwendet für Tiles und Geometrien eine gemeinsame lokale Web-Mercator-Projektion; das gespeicherte Datenformat ändert sich nicht.
