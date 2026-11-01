# RadlNavi Frontend

This is the frontend for [radlnavi.de](https://www.radlnavi.de).

Beim Start erscheint ein kompaktes Infofenster (560 px, auf Mobilgeräten nahezu
bildschirmbreit). Drei zunächst eingeklappte Abschnitte erklären Farben,
RadlVorrang-Netz und Datenaktualisierungen. Schließen-Symbol, Escape oder
„Karte entdecken“ schließen es; unter „Mehr → Über RadlNavi“ lässt es sich
wieder öffnen. Der Inhalt scrollt innerhalb des Fensters, die Abschlussaktion
bleibt sichtbar. Die Farblegende steht nur im aufgeklappten Bewertungsabschnitt.
Im Hauptmenü und im Infofenster führt „Feedback“ per E-Mail zu `mail@munichways.de`.

## Streckendetails (US #35, Version 2.3.8)

Die RadlNavi-Datenquelle ist `IST_RadlVorrangNetz_Oberbayern_V20.geojson` und
enthält auch Streckendetails außerhalb Münchens.

Rechtsklick oder langes Drücken auf die Karte öffnet das Kontextmenü. Ab Zoom 14
erscheint bei einem V20-Treffer **Details anzeigen**. Bei mehreren Treffern wird
der Abschnitt im Dialog ausgewählt und auf der Karte violett hervorgehoben.
Das Fenster lässt sich am blauen Titel verschieben, mit „Verkleinern“ minimieren
und an der unteren rechten Ecke in der Größe ändern. Die Karte bleibt bedienbar.
Unter „Mehr“ stehen „Alle Details“ (Standard) und „RadVorrang-Netz“ zur Auswahl.
Die Auswahl filtert Kartenlinien und Detailsuche gemeinsam. Das RadlVorrang-Netz
verwendet dieselbe V20-Regel wie die App: `munichways_mw_rv_route` fehlt nicht
und ist weder leer noch genau `-`.

OSM-Sachwerte werden auf Deutsch angezeigt (Straßenart, Oberfläche, Ebenheit,
Fahrradregelung, Zugang und Beleuchtung), auch bei Mehrfachwerten. Breiten nutzen
das deutsche Dezimalkomma. Eigennamen und IDs bleiben erhalten; unbekannte neue
OSM-Werte bleiben lesbar, statt Informationen zu verwerfen.

„Stadtbezirke“ unter „Mehr“ ist standardmäßig ausgeschaltet. Der feste lokale
GeoJSON-Bestand zeigt Grenzen sowie ab Zoom 12 die anklickbaren BA-Nummern.
Namen erscheinen beim Überfahren der Labels; Strecken-Rechtsklicks bleiben
erreichbar. [Import und Darstellung](../docs/stadtbezirke.md).

Für den ersten lokalen Test die Daten erzeugen, dann den Entwicklungsserver starten:

```powershell
npm run prepare:street-details
npm start
```

Der Build prüft die in `street-details-source.json` festgelegte SHA-256. Das dort
hinterlegte `createdAt` bezeichnet den Datenstand der Quelldatei und wird
unabhängig vom Downloadzeitpunkt angezeigt. Eine
geänderte Quelldatei muss vor dem Aktualisieren dieses Hashs geprüft werden.
Mit `npm run prepare:street-details -- --source PFAD.geojson` kann derselbe
Snapshot lokal eingelesen werden. Erzeugte Dateien liegen unter
`public/street-details/` und werden nicht eingecheckt. Der Docker-Build erstellt
sie in einer eigenen Stage. Ohne lokale Daten verwendet `npm start` den
Produktionsproxy; dafür muss diese Version bereits veröffentlicht sein.

Automatisierte Prüfungen:

```powershell
npm run test:street-details-build
npm run lint:street-details
$env:CI='true'
npm test -- --watchAll=false --runInBand
npx tsc --noEmit
npm run build
```

Der optionale Browsertest prüft das Produktionsbundle mit echten V20-Daten,
Web Worker und Desktop-/Touch-Ereignissen in einer separaten Headless-Edge-Instanz:

```powershell
npm install --prefix .cache/browser --no-save --package-lock=false playwright@1.56.1
node tests/street_details.browser.mjs
```

Mit `$env:STREET_TEST_MAPILLARY='1'` vor dem Browsertest wird zusätzlich die
echte Mapillary-Einbettung mit Internetzugriff geladen und geprüft.

Dafür müssen Microsoft Edge installiert und die Daten vor `npm run build`
erzeugt worden sein. Mit `STREET_TEST_BROWSER_CHANNEL=chrome` lässt sich ein
installierter Chrome verwenden. Screenshots liegen im ignorierten `.cache`.
Externe Kartentiles sind im Test ausgespart; Routing und Produktionsdaten
werden dabei nicht verändert. Test auf echter Hardware bleibt zusätzlich sinnvoll.

Technische Einzelheiten: [Umsetzung zu US #35](../docs/issue-35-v20-details/implementation.md).

## Hinweise und Ansagen am Rechner prüfen

Frontend mit `npm start` starten und `http://localhost:3000` öffnen.
Im Seitenmenü **Hinweise prüfen** wählen. GPS und eine laufende Navigation
sind dafür nicht erforderlich.

1. Beim Öffnen werden die aktuellen Start-/Zielkoordinaten der Kartenansicht
   übernommen und ihre Hinweise automatisch geladen. Alternativ eines der vier
   Beispiele auswählen oder Start/Ziel als `Breite, Länge`
   eingeben, dann **Route prüfen**. Auch eine auf der Karte geplante
   Route mit **Aktuelle Kartenroute übernehmen** verwenden.
2. Alle Manöver der Reihe nach lesen oder einzeln/gesamt vorlesen lassen.
   Die Meterangabe ist die Position des Manövers ab Routenstart, die Distanz
   danach gehört zum anschließenden Wegstück. Auch nahe Doppelabbiegungen,
   Start/Ziel und sämtliche gelieferten Legs bleiben sichtbar.
   Wenn der Routingserver die Wegklassen `road` und `cycleway` liefert,
   ergänzt die Vorschau bei einem eindeutigen Wechsel „auf Straße“ oder
   „auf Radweg“. Über **Wegwechsel-Zusatz für Hinweis …** lässt sich jeder
   Zusatz auch mit alten Serverantworten simulieren und wieder auf
   **Automatisch aus Routendaten** zurückstellen. Die Simulation ändert weder
   die Karte noch die herunterladbare Rohantwort.
3. **Hinweis … auf Karte** markiert den Manöverort und das folgende Wegstück
   orange. Das Prüffenster bleibt dabei geöffnet, die Karte bleibt bedienbar.
   Am Titel lässt sich das Fenster verschieben (auch per Pfeiltasten nach
   Fokussieren des Titels), an der unteren rechten Ecke in der Größe ändern.
   **Verkleinern** reduziert es auf die Titelleiste; **Öffnen** zeigt den Inhalt wieder.
4. **Rohantwort herunterladen** sichert die API-Antwort samt Abfrage-URL und
   Abrufzeit. Bei übernommener Kartenroute wird das bereits gelieferte
   Route-Objekt des Web-Wrappers mit Übernahmezeit exportiert.

Die Prüfansicht verwendet die konfigurierte Backend-Adresse; lokal leitet
der Entwicklungsproxy an das produktive Backend weiter. `?variant=direct`
aktiviert wie in der Kartenansicht die Direktvariante. Die Auswahl eines
Beispiels befüllt nur die Eingabe; eine neue Abfrage erfolgt über **Route prüfen**.

Die API liefert strukturierte Manöver. Deutsche Texte erzeugt wie im
Webfrontend `osrm-text-instructions`; vorgelesen wird mit der Browserstimme.
Das ist keine Simulation der Flutter-Filter, Verkettung, GPS-Fortschrittslogik
oder tatsächlichen Ansagezeitpunkte. Auch die Wegwechsel-Zusätze sind eine
Textvorschau und kein Replay der App. Roh-Typ und Modifier stehen deshalb neben
jedem übersetzten Hinweis; die vollständigen Step-Daten lassen sich aufklappen.

## Kartenansicht (Issue #281 der MunichWays-App)

Rechts oben steht zwischen Zoom und Legende ein Kartenlayer-Symbol. Es bietet
**Standard** (bisherige OSM-Karte, unverändert) und **Dezent** (dieselbe Grundkarte
entsättigt und aufgehellt). Bewertungen, Route, Haltepunkte und andere
Überlagerungen behalten ihre Farben. Die Auswahl bleibt beim nächsten Besuch
erhalten; bei gesperrtem Browserspeicher funktioniert sie für den aktuellen Besuch.

Dezent ist keine neue detailärmere Datenquelle: Beschriftungen werden nicht
entfernt. Es gibt keine zusätzlichen Kachelabfragen, Anbieter, Kontingente oder
Abhängigkeiten. Leaflet und seine Drehfunktion bleiben bestehen.

Lokal prüfen: zwischen beiden Ansichten wechseln, Karte verschieben/zoomen/drehen,
Bewertungen und RadVorrang-Netz vergleichen, eine Route mit Zwischenzielen planen
und laden, Seite neu laden und die gespeicherte Wahl kontrollieren. Menü auch mit
Tastatur öffnen, mit Escape schließen; kleine Fenster und Browserzoom prüfen.
Die Auswahl darf Ausschnitt, Route, Netzmodus oder Navigation nicht verändern.
