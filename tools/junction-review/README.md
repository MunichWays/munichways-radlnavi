# Lokale Kreuzungsprüfung

Neue Gebietsvorbereitungen überspringen Kreuzungen, deren OSM-Knoten bereits in
einem gespeicherten Projekt enthalten sind. Das gilt auch für ausgeschlossene
oder zurückgestellte Fälle und ältere `lane-candidate`-Importe. Der Abschluss
nennt die Anzahl; Verweise auf die ursprünglichen Projekte stehen im Datenstand
unter `source.existingJunctions`. Bloße räumliche Nähe gilt nicht als Duplikat,
damit benachbarte oder getrennte Kreuzungsflächen erhalten bleiben.

## Öffentliche mobile Karte

Die Nur-Lese-Karte wird mit dem RadlNavi-Frontend unter `/kreuzungspruefung/`
veröffentlicht. Lokale Bearbeitungen werden ausdrücklich als neuer Stand exportiert:

```powershell
$env:PYTHONPATH='tools/junction-review'
python -m junction_review publish-map --project .local/junction-review/munich --output docs/large-junction-analysis/public-junction-review.json
```

Den Export committen und das Frontend deployen. Der Export enthält ausgewählte
öffentliche Geometrie- und Prüfdaten, keine lokale Projektdatenbank oder Schreib-API.
Die Karte zeigt den Exportzeitpunkt; lokale Änderungen werden nicht automatisch synchronisiert.

Eigenständige Basis für die Sichtprüfung großer Radverkehrskreuzungen. Python ab 3.10, moderner Browser, keine Paketinstallation, kein Docker und kein Routingserver erforderlich.

## Starten

Im Repository-Hauptverzeichnis:

```powershell
python tools/junction-review/run.py start
```

Anschließend **http://127.0.0.1:8765** öffnen. `Strg+C` beendet den Server. Das Gesamtprojekt übernimmt den Stand der bisherigen Übersicht: 98 Fälle, davon 42 bestätigt, 41 offen und 15 ausgeschlossen/zurückgestellt (Übernahmestand 20.11.2026). Es erfolgt kein automatischer OSM-Abruf oder neuer Live-Abgleich.

Arbeitsdaten des Gesamtprojekts liegen in `.local/junction-review/munich/` und erscheinen nicht in Git. Diesen Ordner für eine Sicherung vollständig kopieren. Die bisherige Bildprüfung bleibt Referenz; neue Entscheidungen werden im Gesamtprojekt gespeichert. RadlNavi-Laufzeitdaten werden nicht verändert.

Nach einem frischen Checkout einmalig den bisherigen Stand übernehmen:

```powershell
python tools/junction-review/run.py migrate-overview
```

Falls bereits lokale Prüfentscheidungen im früheren K47–K50-Projekt liegen: `--carry-project .local/junction-review/munich-nine-lanes` hinzufügen. Entscheidungen werden nur bei übereinstimmenden Quellen übernommen; Konflikte werden nicht überschrieben. Die kleine ursprüngliche Demo bleibt mit `python tools/junction-review/run.py demo` verfügbar.

## Bedienung

### Entry-/Exit-Punkte bearbeiten

Ein **Straßenarm** bezeichnet eine Straße in einer Richtung ab der Kreuzung samt ihren Radwegen,
zum Beispiel „Marsstraße nach Nordost“. Entry und Exit auf gegenüberliegenden Straßenseiten können
zum selben Arm gehören. Umgekehrt kann ein durchgehender OSM-Radweg um eine Ecke führen und damit
Punkte verschiedener Arme enthalten. Bei OSM-Projekten zeigt die Auswahl Straßenname, Himmelsrichtung
und zugeordnete Punkte; die Beschreibung bleibt beim Verschieben von Punkten an die ursprüngliche
Straßenrichtung gebunden. Ein ausdrücklich ausgewählter Zielweg wird orange markiert. Endet ein
OSM-Weg direkt an der Grenze, für einen weiter außen liegenden Punkt seine belegte Fortsetzung wählen.

In einer Kreuzung **„Entry/Exit bearbeiten“** einschalten. Einen Anschluss in der Liste auswählen oder auf seinen Punkt klicken. Zum Verschieben den Punkt ziehen oder **„Ziel auf Karte wählen“** und dann auf den gewünschten Radweg klicken. Die Flächengrenze folgt dem verschobenen Punkt; andere Anschlüsse werden auf ihren belegten Wegen an die neue Grenze angepasst.

Für einen gemeinsamen Entry in P3: **Entry-2** wählen, unter **„Zusammenlegen“ → „Mit Entry-3 zusammenlegen“** einstellen und das Ziel auf dem gemeinsamen südlichen Radweg setzen. Bei überlappenden Wegen lässt sich der Zielweg ausdrücklich auswählen (`OSM 421302932`, gemeinsamer Radweg vor der Verzweigung). Entry-2 behält seine Nummer, Entry-3 entfällt; die übrigen Anschlüsse werden nicht umnummeriert. Zwei Entry-Punkte bzw. zwei Exit-Punkte desselben Straßenarms können zusammengelegt werden.

**„Gewählten Punkt löschen“** entfernt den Punkt auch aus seiner Straßenarmzuordnung. Alle Bearbeitungen sind zunächst ein Entwurf. Mit **„Änderungen verwerfen“** zurück zum gespeicherten Stand oder mit **„Geometrie speichern“** Fläche, Anschlüsse und Zuordnungen gemeinsam speichern. Eine bestehende Bestätigung und technische Evidenz werden bei geänderter Geometrie ungültig. Neue Anschlüsse und Änderungen der Straßenarmdefinition sind noch kein Bestandteil dieses Editors.

### Münchner Stadtbezirke

Alle 25 Stadtbezirke sind unter **„Münchner Stadtbezirk“** fest auswählbar,
zum Beispiel **BA04 Schwabing-West**. Die Auswahl und Grenzen werden lokal geladen;
ein OSM-Abruf ist erst für **„Sichtprüfung vorbereiten“** nötig. Die vollständigen
Teilflächen von BA18 und BA19 bleiben erhalten.

Die Checkbox **„Stadtbezirke München“** über dem OSM-Hinweis blendet violette,
gestrichelte Grenzen und Bezirksnamen in Übersicht, Detail und Gebietsauswahl ein.
Die Einstellung gilt gemeinsam für alle Karten und bleibt im Browser gespeichert.
Die gebündelte Datei `junction_review/web/stadtbezirke.geojson` ist eine unveränderte
Kopie von `frontend/public/data/stadtbezirke.geojson`, dem RadlNavi-Datenstand.
Bestehende Projekte und Freigaben werden durch Auswahl oder Einblenden nicht verändert.

### Neue Stadt, Stadtteil oder gezeichnete Fläche

In der Übersicht **„Gebiet auswählen und Sichtprüfung vorbereiten“** aufklappen.

1. **„Stadtteil auf Karte wählen“** anklicken und in den gewünschten Bezirk klicken. Aus den gefundenen Verwaltungsgebieten den Bezirk wählen. Alternativ Stadt oder Stadtteil mit genauem OSM-Namen suchen (zum Beispiel `Neuhausen-Nymphenburg`). Einen Treffer auswählen; die Verwaltungsgrenze erscheint lila. Die OSM-Relationsnummer und Verwaltungsebene helfen bei gleichnamigen Orten.
2. Alternativ die Karte verschieben/zoomen und **„Fläche einzeichnen“** wählen. Mindestens drei verschiedene Eckpunkte setzen; vier oder mehr sind ebenfalls möglich. Abschließen per Startpunkt-Klick, Doppelklick, Eingabetaste oder **„Fläche schließen“**. **„Letzten Punkt entfernen“** korrigiert den letzten Klick; Escape beendet das Zeichnen. Selbstüberschneidungen werden vor dem OSM-Abruf angezeigt. Eine gesuchte Stadt kann auch als Kartenausschnitt für eine kleinere gezeichnete Fläche dienen.
3. **„Sichtprüfung vorbereiten“** startet einen Hintergrundauftrag und lädt einmalig OSM-Daten. Spinner und Laufzeit zeigen den laufenden Vorgang. **„Abbrechen“** verhindert den Import eines noch nicht abgeschlossenen Auftrags; der laufende Netzabruf kann noch auslaufen. Nach Neuladen lässt sich ein laufender Auftrag wieder aufnehmen. Je nach Gebiet/Overpass-Auslastung dauert das einige Minuten. Es erfolgt kein neuer OSM-Abruf beim bloßen Öffnen der App oder beim Kartenverschieben.
4. Die neue Prüfliste und Karte öffnen sich automatisch. `P1`, `P2`, … bezeichnet die Priorität im neuen Projekt, keine Münchner K-Nummer. Bekannte ausgehende Fahrspuren absteigend, danach einfache Geometrien; unbekannte Spurzahlen folgen zuletzt.
5. Kreuzung öffnen, Fläche, Radverkehrsanschlüsse und Richtungen prüfen. **„Prüfbild als SVG herunterladen“** liefert ein eigenständiges Vektorbild mit Pfeilen und Beschriftungen ohne Hintergrundkarten-Abhängigkeit.

Bei vorübergehenden HTTP-Fehlern (zum Beispiel 502), Zeitüberschreitungen oder
abgebrochenen Antworten wechselt der Abruf zwischen `overpass-api.de` und
`overpass.private.coffee`. Insgesamt bleiben es höchstens drei Versuche; der
zuletzt erfolgreiche Dienst wird für folgende Abrufe weiterverwendet. Beide
öffentlichen Dienste können gleichzeitig überlastet oder nicht erreichbar sein.
Die Fehlermeldung nennt dann die betroffenen Dienste und Fehlerarten. Unvollständige
Antworten werden weder importiert noch zwischengespeichert; vorhandene Projekte
und Freigaben bleiben erhalten. Der Serverstart selbst löst keinen Abruf aus.

Jede Auswahl erhält ein separates Projekt unter `.local/junction-review/area-<hash>/`. Das vorhandene München-Projekt wird nicht überschrieben. Unter **„Gespeichertes Projekt“ → „Öffnen“** wechseln. Dieselbe Auswahl öffnet ihren gespeicherten Stand ohne erneuten OSM-Abruf; Entscheidungen bleiben erhalten. `osm-snapshot.json` enthält die vollständige Abfrageantwort einschließlich Knotentags und Restriktionsrelationen, die Importdatei zusätzlich Abfrage und Algorithmusversion. Den ganzen Projektordner sichern.

Neue Gebiete lassen bereits vorhandene Kreuzungen projektübergreifend aus, unabhängig vom Prüfstatus. Vorrang haben identische IDs und gemeinsame OSM-Kandidatenknoten. Bei älteren RadlNavi-Importen ohne diese Knoten wird zusätzlich die vollständige Menge der Straßennamen (unabhängig von ihrer Reihenfolge) mit höchstens 15 m Abstand der Mittelpunkte verglichen. Nähe allein genügt nicht; widersprüchliche OSM-IDs und mehrdeutige Zuordnungen werden nicht zusammengeführt. Bestehende Projekte werden beim Öffnen nicht automatisch bereinigt. Dokumentierte Duplikatentfernungen erhalten den eingefrorenen Import und frühere Entscheidungen.

Die Programmlogik in `discovery.py` braucht kein LLM. Sie sucht Straßen ab `tertiary`, gruppiert nahe gemeinsame Straßenknoten ohne unbegrenzte Kettenbildung, ermittelt Straßenarme an einer vorgeschlagenen Fläche und sortiert T-Kreuzungen und Kreisverkehre aus. Straßen auf getrennten Ebenen werden nicht allein wegen einer geometrischen Überschneidung verbunden. Das Auswahlgebiet begrenzt die Kandidaten, nicht deren Kreuzungsflächen.

Fahrspuren werden nach Möglichkeit auf der ausgehenden Fortsetzung mindestens 80 m vom Mittelpunkt abgelesen. Explizite Richtungswerte haben Vorrang; ungerade/fehlende Spurzahlen und mehrdeutige Fortsetzungen bleiben unbekannt. Separate Radwege, erlaubte Zweirichtungswege, Radfahrstreifen und erlaubte Straßenabschnitte erzeugen Grenzanschlüsse. `oneway:bicycle` hat Vorrang vor `oneway`. Radfahrstreifen bleiben auf OSM-Straßenmittellinien schematisch; ihre reale Seitenlage wird nicht erfunden.

**Entwürfe bleiben offen.** Die Fläche ist ein konservativer geometrischer Startvorschlag, keine automatisch bestätigte Wartefläche. Versetzte Knoten, viele Anschlüsse, benachbarte Kreuzungen, Zweirichtungswege, Straßenführung und fehlende Evidenz erscheinen als Prüfpunkte. Restriktionsrelationen werden archiviert, hier jedoch noch nicht als vollständige technische Fahrbeziehungsprüfung ausgewertet. Bestätigen, technische RadlNavi-Prüfung und Aktivieren bleiben getrennte Schritte. Es gibt keine automatische Änderung am Backend.

- Übersicht: neueste Nummern oben, Gruppen einklappbar, Namenssuche und anklickbare Kartenpunkte.
- Die Kreuzungsliste links lässt sich über ☰ im kompakten Kopfbereich einklappen. Die Einstellung bleibt im Browser gespeichert. Die Karte nutzt die verfügbare Fensterhöhe und passt sich beim Ein-/Ausklappen ohne Verlust des Ausschnittmittelpunkts an.
- Karte: Mausrad oder Plus/Minus zum Zoomen, Hintergrund ziehen zum Verschieben. Standardmäßig wird die OSM-Standardkarte aus dem Internet geladen. Mit „OSM“ ausschalten, um nur die importierten Offline-Wege anzuzeigen; die Auswahl bleibt im Browser gespeichert.
- Detail: Fläche, Entry-/Exit-Punkte, Straßenarme und bisherige Prüfentscheidungen.
- Die Karte startet mit den offenen Fällen. Über die Auswahl oben rechts sind auch alle, bestätigte oder ausgeschlossene Fälle sichtbar. Hohle Punkte sind noch ohne vorbereitete Geometrie; sie können kommentiert, zurückgestellt oder ausgeschlossen, aber nicht geometrisch freigegeben werden. K47–K50 sind bereits zur Sichtprüfung vorbereitet.
- Gelbe Merker führen zu einzelnen Wiedervorlagen. Technischer Stand, bewusst ausgenommene Fahrbeziehungen und zuletzt dokumentierter Live-Abgleich stehen je Kreuzung unter der Karte. Eine geänderte Fläche macht diese Belege historisch und hebt die eigene Geometriefreigabe auf.
- „Fläche bearbeiten“: Eckpunkte ziehen. Die bestehenden Anschlüsse werden an den Schnittpunkten ihrer OSM-Wege neu berechnet. Nicht eindeutige Schnittpunkte werden abgelehnt. Neue Anschlüsse und Straßenarme ergänzen ist ein späterer Schritt.
- „Nur Fläche speichern“: neue Geometrierevision. Eine bisherige Bestätigung gilt anschließend nicht mehr.
- „Entscheidung speichern“: offen, bestätigt, zurückgestellt oder ausgeschlossen; Zurückstellung/Ausschluss brauchen einen Grund. Eine Wiedervorlage kann datiert werden.
- Export: ausschließlich aktuell bestätigte Geometrien; keine automatische technische Prüfung oder Aktivierung.

Die Kreuzungsnotiz stammt aus dem importierten Entwurf. Eigene Entscheidungen stehen separat darunter. Der Gesamtimport übernimmt vorhandene Freigaben mit ihrer ursprünglichen Evidenz und kontrolliert deren Geometrie-Hash. Der einfache Einzelrundenimport hingegen startet als neue Prüfung. Neue Entscheidungen werden noch nicht in die bisherige RadlNavi-Prüfungsübersicht zurückgeschrieben und aktivieren keine Ansagen.

## Andere Bildrunden und Städte

```powershell
python tools/junction-review/run.py import-radlnavi --source docs/large-junction-analysis/review-batch-09-nine-lanes-images/review-data.json --project .local/junction-review/mein-projekt --id mein-projekt --city München --district "Auswahl neun Fahrspuren"
python tools/junction-review/run.py serve --project .local/junction-review/mein-projekt --port 8766
```

Optional: `--numbers 47 49` oder `--area gebiet.geojson`. Die Gebietsauswahl akzeptiert eine GeoJSON-Polygongeometrie ohne Löcher und filtert nach Kreuzungsmittelpunkten. Stadt und Stadtteil sind frei wählbar; die Basis ermittelt noch keine Kandidaten allein aus einem Ortsnamen.

Für einen anderen Datenlieferanten steht `import --source projekt.json --project ...` bereit. Es erwartet das allgemeine Datenformat aus [ARCHITECTURE.md](ARCHITECTURE.md), ohne RadlNavi-Abhängigkeit.

Ein identischer Import bleibt unverändert. Geänderte Importdaten brauchen ausdrücklich `--refresh`. Frühere Imports und Entscheidungen bleiben archiviert; Entscheidungen betroffener Kreuzungen werden ungültig. Entfernen vorhandener Kreuzungen beim Refresh wird verweigert; für Teilmengen ein eigenes Projekt anlegen. Geometriekorrekturen werden bei geändertem Quelldatensatz archiviert und müssen am neuen Vorschlag geprüft werden.

Nur einen Server pro Projekt starten und den Import/Refresh bei beendetem Server ausführen. Verschiedene Projekte können auf verschiedenen Ports laufen. Gleichzeitige Browseransichten desselben Servers sind durch Versionsprüfungen geschützt.

```powershell
python tools/junction-review/run.py export --project .local/junction-review/munich --output .local/junction-review/geometrien.json
```

## Prüfen

Technische RadlNavi-Ergebnisse in die Karte zurückübernehmen:

Die zehn Fälle der Bezirksrunde BA01–BA03 einschließlich K89 und der Wiedervorlagen
K44/K46 sind als Batch 12 eingefroren. Offline reproduzieren mit
`python docs/large-junction-analysis/verify_ba01_ba03_project.py`; `--import-results`
übernimmt die Ergebnisse fingerprintgebunden in ihre jeweiligen Projekte. Bestehende
Live-Beziehungen bleiben als live dokumentiert; bestandene Wiedervorlagen bleiben bis
zur gesonderten Aktivierung deaktiviert. Die internen Prüfnummern ab 101 vergeben keine
neuen K-Nummern. Stachus nutzt für die ausdrücklich freigegebene Geradeausbeziehung
die vorhandene Winkelprüfung, ohne einen fehlenden vierten Arm zu erfinden.

Die nachfolgenden Ansageentscheidungen zu P2/P7 und die Lachnerstraßen-Prüfung K06
stehen in Batch 13: `python docs/large-junction-analysis/verify_guidance_followups.py`
(offline), optional `--import-results`. Die erste Regelversion bleibt archiviert;
`approved-v2.json` enthält zusätzlich die bestätigte südliche Gleichwertigkeit bei P7.
Gleichwertige Straße-/Radweg-Ausgänge brauchen eine ausdrückliche Zuordnung zum selben
Straßenarm; die Straßenklasse allein erteilt keine Ausnahme. Wechselt das Routing auf
einen ausdrücklich gleichwertigen Entry, wird die tatsächlich nachgewiesene Beziehung
verwendet und als abgedeckt dokumentiert, ohne doppelte überlappende Makros anzulegen.

```powershell
python tools/junction-review/run.py import-technical --report docs/large-junction-analysis/review-batch-09-nine-lanes-routes.json
```

Der Bericht braucht eine Bindung an die exakt bestätigten Geometrie- und Quellfingerprints. Abweichende oder inzwischen geänderte Fälle werden abgelehnt. Ein erneuter identischer Import bleibt unverändert. Prüfentscheidung und Aktivierungsstand werden nicht geändert. Nach Änderungen am Python-Werkzeug einen laufenden Server mit `Strg+C` beenden und wieder mit `start` starten.

Kurzer Arbeitsstand für weitere Aufgaben, ohne große Geometriedateien zu lesen:

```powershell
python tools/junction-review/run.py status --project .local/junction-review/munich
```

Mit `--json` entsteht ein kompakter Maschinenbericht mit Status, Revision, veralteten Entscheidungen, fehlenden Straßenarmzuordnungen und Wiedervorlagen.

```powershell
python -m unittest discover -s tools/junction-review/tests -p 'test_*.py'
node --test tools/junction-review/tests/test_map.mjs tools/junction-review/tests/test_area_ui.mjs tools/junction-review/tests/test_gate_ui.mjs
```

Die Python-Tests verwenden K47–K50 als echte Importreferenz und temporäre Projekte. Dazu kommen eingefrorene OSM-Topologien, simulierte 502-/HTML-Fehler, Cache, Auftragsabbruch und getrennte Projektzugriffe. JavaScript-Tests prüfen echte UI-Ereignisbehandlungen für Fehlerversuch/Wiederholung, sichtbare Suchtreffer, Spinner/Abbruch, Doppelklick, Vierpunktflächen und korrigierbare Selbstüberschneidungen. Diese Tests ersetzen keine visuelle Browserprüfung. Sie verändern keine Freigaben. Ein eigener GitHub-Workflow führt beide Prüfungen aus.

## Weitere Ausbaustufen

Die technische Kartenrunde vom 21.11.2026 (26 neue bestätigte Münchner Fälle) lässt sich
ohne Netzabruf reproduzieren:

```powershell
python docs/large-junction-analysis/verify_munich_project.py
```

`--collect` ergänzt fehlende echte Standardrouten, `--import-results` übernimmt passende Ergebnisse
in das lokale München-Projekt. Der eingefrorene Freigabestand bleibt unverändert; Import nur bei
übereinstimmenden Geometrie- und Quellfingerprints. Mehrdeutige Ausfahrten und nicht nachgewiesene
Beziehungen bleiben deaktiviert. Das Kommando ändert weder Laufzeitkatalog noch Deployment.

Gespeicherte Projekte lassen sich im Bereich „Kreuzungen“ auswählen und mit „Umbenennen“ benennen.
Der Anzeigename wird separat im lokalen Projekt gespeichert; ID, Gebiet, Geometrien und Prüfentscheidungen
bleiben unverändert. Der Name bleibt auch nach Neustart und Quelldatenaktualisierung erhalten.

Fehlende Geometrien im bestehenden Projekt ohne LLM vorbereiten:

```powershell
python tools/junction-review/run.py prepare-open --project .local/junction-review/munich
```

Nur offene Fälle ohne Geometrie werden ergänzt. Kleine OSM-Kartenabfragen landen im lokalen
`preparation-cache`; erfolgreiche Entwürfe werden bei Wiederholung übersprungen.
Freigegebene Geometrien, Ausschlüsse, IDs und Nummern bleiben erhalten. Entscheidungen in anderen
lokalen Projekten werden als Hinweis markiert, damit sie nicht nochmals geprüft werden müssen.
Eine räumliche Zuordnung ist kein automatischer Freigabetransfer. Unklare Fälle bleiben offen.
`preparation-report.json` enthält vorbereitete, verknüpfte, unklare und fehlgeschlagene Fälle.
Die Vorschläge benötigen weiterhin eine Sichtprüfung; technische Prüfung und Aktivierung folgen separat.

1. Vorschlagsqualität mit weiteren echten Geometrien prüfen; die automatischen Flächen bleiben unbestätigte Heuristiken.
2. Strassenarmdefinitionen bearbeiten; Hinzufuegen, Verschieben, Loeschen und Zusammenlegen von Anschluessen sind implementiert.
3. RadlNavi-Adapter für technische Fahrbeziehungsprüfung und Rückmeldung in die bestehende Übersicht.

Standardfälle sollen durch wiederholbare Regeln bearbeitet werden. LLM-Unterstützung ist für benannte Sonderfälle vorgesehen und wird von dieser Basis nicht aufgerufen.

## Hintergrundkarte

Die [OSM-Standardkacheln](https://operations.osmfoundation.org/policies/tiles/) werden direkt vom Browser geladen, mit sichtbarer Attribution, Browser-Cache und Referer. Nur Kacheln im sichtbaren Ausschnitt werden angefordert; kein Vorabdownload. Die Datenprüfung funktioniert auch ohne Hintergrundkarte. Flächen, Wege und Tiles verwenden dieselbe Web-Mercator-Projektion; gespeicherte Geokoordinaten bleiben WGS84.

### Entry/Exit hinzufügen

Im Anschlusseditor Typ (Entry/Exit), vorhandenen Straßenarm und bei parallelen Wegen den OSM-Zielweg auswählen. "Punkt hinzufügen: auf Karte setzen" wählen und auf den Weg nahe der Flächengrenze klicken. Die Grenze folgt dem Punkt; bei mehr als 12 m Abstand zuerst die Fläche erweitern. Fahrtrichtung und OSM-Zulässigkeit werden geprüft. Neue Punkte erhalten fortlaufende Nummern, bestehende bleiben unverändert. Erst "Geometrie speichern" übernimmt den Entwurf.

P5-Test: Der südliche parallele Straßenabschnitt ist OSM-Weg **3302001**, `highway=residential`. Als **Exit** dem Straßenarm **Arm-3 (Entry-1)** zuordnen und nahe der südöstlichen Flächengrenze setzen. P5 wird durch die Implementierung nicht verändert.
