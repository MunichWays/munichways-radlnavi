# Lokale Kreuzungsprüfung

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
node --test tools/junction-review/tests/test_map.mjs
```

Die Python-Tests verwenden K47–K50 als echte Importreferenz und temporäre Projekte. Sie verändern keine Freigaben. Ein eigener GitHub-Workflow führt beide Prüfungen aus.

## Weitere Ausbaustufen

1. Stadt-/Stadtteilsuche, Gebietsgrenzen und ein zwischengespeicherter OSM-Datenabruf.
2. Allgemeine Kandidatensuche, Gruppierung und Priorisierung; bestehende Generatorregeln schrittweise übernehmen.
3. Neue/entfernte Anschlüsse, Zuordnung der Straßenarme und geführtes Verschieben von Gates bearbeiten.
4. RadlNavi-Adapter für technische Fahrbeziehungsprüfung und Rückmeldung in die bestehende Übersicht.

Standardfälle sollen durch wiederholbare Regeln bearbeitet werden. LLM-Unterstützung ist für benannte Sonderfälle vorgesehen und wird von dieser Basis nicht aufgerufen.

## Hintergrundkarte

Die [OSM-Standardkacheln](https://operations.osmfoundation.org/policies/tiles/) werden direkt vom Browser geladen, mit sichtbarer Attribution, Browser-Cache und Referer. Nur Kacheln im sichtbaren Ausschnitt werden angefordert; kein Vorabdownload. Die Datenprüfung funktioniert auch ohne Hintergrundkarte. Flächen, Wege und Tiles verwenden dieselbe Web-Mercator-Projektion; gespeicherte Geokoordinaten bleiben WGS84.
