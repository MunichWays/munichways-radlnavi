# RadlNavi ↔ App: am PC planen, später fahren

Analyse zu [App-Issue #168](https://github.com/MunichWays/munich-ways-app/issues/168),
Stand: 14. Oktober 2026. Vorschlag, noch keine implementierte Funktion.

Die anschließend beauftragte Umsetzung und ihre Testschritte stehen in
[GPX-Routenübergabe: Umsetzung](gpx-route-transfer-implementation.md).
Festgelegt wurden 90 Tage Linkgültigkeit; Google, komoot-Anpassungen und eine
zusätzliche Standard-GPX-Exportauswahl bleiben außerhalb des Umfangs.

## Empfehlung

Den Ablauf gemeinsam für Web und App entwickeln: **am PC mit Zwischenzielen
planen → auf dem Handy übernehmen → lokal speichern → später fahren**.
GPX dient als austauschbare Datei. Ein anschließender Teilen-Link mit QR-Code
beseitigt den umständlichen Dateitransfer. Dafür ist kein Benutzerkonto nötig.

Arbeitsannahme: Die am PC ausgewählte Strecke soll erhalten bleiben. Eine neue
Route durch dieselben Zwischenziele kann sinnvoll sein, muss aber eine bewusste
Nutzerentscheidung sein. Für eine Übergabe mit Abbiegeansagen braucht die App
zusätzlich zur Linie die Navigationsdaten. Ein gewöhnlicher GPX-Track allein
erfüllt diesen Anspruch nicht.

## Geprüfter Bestand

Codebasis: RadlNavi `05400da`, lokaler App-Checkout `53c3420`. Beide Arbeitsbäume
waren zu Beginn sauber. Das gespeicherte Routenmodell wurde zusätzlich gegen
den GitHub-Standardbranch der App geprüft. Die übrigen Codebefunde beziehen
sich auf diese lokalen Checkouts, nicht auf nachgewiesenes Produktionsverhalten.

| Bereich | Heute | Konsequenz |
| --- | --- | --- |
| Webplanung | `frontend/src/App.tsx` hält Start und Ziel; `calculateRoute()` nutzt `/route` | Zwischenziele fehlen in Oberfläche und regulärem Anfragepfad. |
| GPX-Export | `exportGpx()` übergibt nur `route.geometry` an `togpx` | Die LineString wird als `trk/trkseg/trkpt` ausgegeben. Planungsziele, Variante und Abbiegeinformationen werden nicht übertragen. |
| Web-API | `backend/src/app.py:/route` nimmt nur Start/Ziel; liefert `steps` und `annotation` aus `legs[0]` | Nur weitere Punkte anfügen reicht nicht: Der Antwortvertrag muss alle Legs berücksichtigen. |
| Gemeinsame Routingbasis | `/route/v1/bike/{coordinates}` unterstützt Koordinatenlisten; `RouteInspector` und die App nutzen diesen OSRM-Vertrag | Diesen vorhandenen Pfad für Mehrpunktplanung bevorzugen; Analyse und Darstellung vollständig anpassen. |
| Appplanung | `setRoutePlan()` und `route_planner_sheet.dart` unterstützen Start, geordnete Zwischenziele und Ziel | Vorhandenen Planer und Speicherdialog wiederverwenden. |
| Appspeicherung | `SavedRoute` speichert Orte, Name und Favoriten, keine berechnete Strecke | Für exakt erhaltene importierte Strecken ist eine rückwärtskompatible Erweiterung erforderlich. |
| Laden | `setSavedRoutePlan()` ruft `setRoutePlan()` auf und löst `_requestRoute()` aus | Ein importierter Streckenverlauf würde auf diesem Weg neu berechnet. |
| Navigation | `CycleRoute` enthält Punkte, Manöver, Schiebeabschnitte und Zielzugang; `RadlNaviApi.route()` liest Steps aller Legs | Den bestehenden Parser auch für übertragene Routingantworten nutzbar machen, statt eine zweite Navigationsinterpretation einzuführen. |
| Neuberechnung | `refreshRoute()` berechnet ab aktuellem Standort über verbleibende Zwischenziele; automatische Neuberechnung ist vorhanden | Importierte Originalstrecke und neu berechnete Route müssen unterschiedliche, ausdrücklich gewählte Modi sein. |
| Datei-/Linkeingang | Kein GPX-Import oder entsprechender Plugin-Eintrag gefunden; Android nur Launcher-Filter, keine entsprechende iOS-Link-/Dokumentregistrierung | Dateiauswahl, „Öffnen mit/Teilen an“ und App-Links sind eigene Integrationsschritte. |
| Speicherung | `SavedRoutesStore` nutzt eine lokale JSON-Datei, höchstens 25 Einträge; gleicher Name ersetzt bisherigen Eintrag | Große Streckendaten getrennt ablegen; Namenskonflikte beim Import sichtbar behandeln. |

Quellstellen der App: [SavedRoute](https://github.com/MunichWays/munich-ways-app/blob/53c3420/lib/model/saved_route.dart),
[SavedRoutesStore](https://github.com/MunichWays/munich-ways-app/blob/53c3420/lib/api/saved_routes_store.dart),
[Routenmodell](https://github.com/MunichWays/munich-ways-app/blob/53c3420/lib/model/route.dart),
[Planung und Neuberechnung](https://github.com/MunichWays/munich-ways-app/blob/53c3420/lib/ui/map/map_screen_model.dart),
[RadlNavi-Parser](https://github.com/MunichWays/munich-ways-app/blob/53c3420/lib/api/radlnavi_api.dart).

## Was GPX leisten soll

[GPX 1.1](https://www.topografix.com/GPX/1/1/) unterscheidet einzelne Wegpunkte,
geordnete Routenpunkte und Tracksegmente und erlaubt eigene Erweiterungen.
Die folgenden Nutzungsregeln sind eine MunichWays-Entscheidung, keine allgemeine
GPX-Konvention:

- **Track:** vollständiger geplanter Verlauf als `trk`; Segmente getrennt erhalten.
- **Plan:** Start, bewusst gesetzte Zwischenziele und Ziel mit Reihenfolge und
  Namen in einer versionierten MunichWays-Erweiterung. Optional zusätzlich
  `rte/rtept` für andere Programme. Nicht jeden Trackpunkt zum Zwischenziel machen.
- **Navigation:** ausgewählte Routingantwort mit Geometrie, allen Legs/Steps,
  Distanz, Dauer und Variante in derselben Erweiterung. Schiebeabschnitte und
  Zielzugang müssen durch den bestehenden Parser erhalten bleiben.
- **Herkunft:** Formatversion, Erstellungszeit und Routinganbieter/-variante;
  Backendversion, soweit verfügbar. Komfortdaten bleiben optionale Metadaten.

Intern einen gemeinsamen, versionierten `RouteTransfer`-Vertrag definieren.
Die eigene GPX-Erweiterung und ein späterer Linkdienst transportieren denselben
Inhalt. Die genaue XML-/JSON-Abbildung wird im ersten Arbeitspaket festgelegt;
die komplette Rohantwort samt überflüssigen Annotationen muss nicht gespeichert
werden. Geometrie und Steps müssen aber denselben Routensnapshot beschreiben.

Standard-GPX bleibt in anderen Programmen als Track nutzbar. Entfernt ein
anderes Programm die Erweiterung, wird die Datei in MunichWays als gewöhnlicher
Track behandelt. Verlorene Ansagen dürfen nicht stillschweigend erfunden werden.

**Fremde GPX-Dateien:** `trk` zunächst als Strecke mit Vorschau übernehmen,
ohne Abbiegeansagen zu versprechen. `rtept` können je nach Quelle Zwischenziele,
Abbiegepunkte oder eine dichte Linie sein. Deshalb nicht ungeprüft als Plan
interpretieren. Einzelne `wpt` ergeben keine verlässlich geordnete Fahrtroute.
Eine ausdrücklich gewählte Neuberechnung ist möglich, liefert aber eine neue
Route. Ein geometrischer Winkel allein ist kein zuverlässiges Straßenmanöver.

## Umsetzung in sinnvoller Reihenfolge

### 1. Zwischenziele und vollständige Routingdaten im Web

Start, geordnete Zwischenziele und Ziel als gemeinsamen Planungszustand führen.
Zwischenziele per Suche/Karte hinzufügen, verschieben, entfernen und sortieren;
beim Umkehren die gesamte Reihenfolge umkehren. Eine feste erste Obergrenze
festlegen und in Web, App und API konsistent prüfen.

Bevorzugt den vorhandenen OSRM-Endpunkt für die reguläre Webplanung verwenden.
Ergebnis durch einen Adapter an die vorhandene Webdarstellung anbinden. Schritte,
Endpunktzugänge und Analysedaten aller Legs erhalten; Analysegrenzen nicht
wegflatten. `routingRequests.ts`, Komfortanalyse und GPX-Export mit anpassen.
Alternativ müsste `/route` rückwärtskompatibel um Mehrpunktplanung und alle Legs
erweitert werden; beide Wege gleichzeitig wären unnötig.

**Abnahme:** Start + zwei Zwischenziele + Ziel ergeben drei vollständige Legs;
Ändern und Umkehren funktionieren. GPX enthält die angezeigte ausgewählte Route.
Standard/Direkt, Schiebeabschnitte und Komfortzuordnung bleiben korrekt.

### 2. Eine vollständige Dateiübergabe Web → App

Zunächst an einer gemeinsamen Testdatei den `RouteTransfer`-Vertrag beweisen:
Webexport → Appparser → identische Geometrie und Manöver. Den Parser aus
`RadlNaviApi.route()` von der HTTP-Abfrage trennen und für diesen Import nutzen.

Dann Dateiauswahl im Routenplaner ergänzen: sichtbare Aktion „Route importieren“
mit Beschriftung/Tooltip, bei Bedarf neben Speichern. Datei zunächst in einen
temporären Zustand lesen, validieren und auf der Karte mit Name, Länge,
Zwischenzielen und verfügbarer Navigation zeigen. Erst „Übernehmen“ ersetzt den
Plan; Speichern bleibt eine bewusste Aktion.

`SavedRoute` um Art und optionale Snapshotreferenz erweitern. Alte Einträge
bleiben als neu berechenbare Pläne lesbar. Snapshots separat lokal speichern,
IDs unabhängig vom Namen verwenden, Referenzen und Dateien konsistent halten.
Importiertes Laden darf nicht automatisch `setSavedRoutePlan()` mit dessen
Neuberechnungspfad verwenden. Einen kontrollierten Übernahmepfad im bestehenden
ViewModel schaffen; alte Routingantworten durch Planrevision entwerten.

Für Originalstrecken automatische Neuberechnung und Variantenwechsel zunächst
sperren. Bei Abweichung informieren und Original erhalten. „Neue Route ab hier
planen“ ist eine eigene Aktion; Verbindung zum geplanten Start ebenfalls separat
behandeln. Einstieg mitten in eine Rundtour nicht anhand des räumlich nächsten
Punktes allein entscheiden. Aktive Navigation beim Import erst nach bewusster
Übernahme beenden oder ersetzen.

**Abnahme:** Am PC planen, GPX auf dem Handy auswählen, prüfen, speichern, App
beenden, neu öffnen und dieselbe Strecke mit denselben Navigationsdaten laden.
Ohne Netz ist der Snapshot lesbar; daraus folgt noch keine Offline-Karte oder
Offline-Neuberechnung. Fehler und Abbruch erhalten die bisherige Route.

### 3. Komfortable Übergabe über Teilen-Link und QR-Code

Webaktion „In App öffnen“ erstellt einen kurzen HTTPS-Link und zeigt ihn als
QR-Code; denselben Link kann man kopieren oder selbst per Messenger versenden.
Die Handykamera genügt zum Scannen, ein Scanner innerhalb der App ist zunächst
unnötig. QR-Code und Link enthalten eine Referenz auf denselben Snapshot, nicht
tausende Trackpunkte. Nur Start/Ziele im Link würden wieder eine neue Berechnung
auslösen und keine Streckentreue garantieren.

Für diese Empfehlung ist ein kleiner serverseitiger Austauschdienst nötig:
versionierte validierte Snapshots, zufällige nicht erratbare IDs, festgelegte
Ablaufzeit, Größen-/Anfragelimits und Aufräumen. Speichern erfolgt ausdrücklich
beim Teilen. Zugriff hat, wer den Link besitzt; über die enthaltenen Orte
informieren. Nach Übernahme lokal speichern, damit Linkablauf die gespeicherte
Route nicht löscht. Keine frei übergebbaren Backend-/Download-URLs ausführen.

[Android App Links](https://developer.android.com/training/app-links) und
[iOS Universal Links](https://developer.apple.com/documentation/xcode/supporting-universal-links-in-your-app)
erfordern Domainzuordnung und Appkonfiguration. Domain unter eigener Kontrolle
wählen, Verifikationsdateien in `/.well-known/` ausliefern; der vorhandene Firebase-
Hostingpfad ist zu prüfen. Ohne installierte App zeigt der Link eine Webvorschau
mit GPX-Download und Installationshinweis. Automatische Übernahme nach einer
Neuinstallation nicht voraussetzen: Link anschließend erneut öffnen.

**Abnahme:** Android und iOS, App kalt/warm gestartet, App nicht installiert,
Link abgelaufen, Netzfehler mit erneutem Versuch. Kein doppelter Import durch
mehrfach zugestellte Links; derselbe Vorschau-/Übernahmepfad wie beim Dateiimport.

### 4. Rückweg und allgemeiner GPX-Austausch

Dateien aus Downloads/Messenger über „Öffnen mit/Teilen an MunichWays“ an denselben
Importdienst leiten. Android Content-URIs und iOS-Dokumentübergabe ausdrücklich
testen; Dateiauswahl allein registriert die App nicht als GPX-Empfänger.

Danach App-GPX-Export und Web-GPX-Import hinzufügen. Gespeicherter Snapshot:
Original exportieren. Gespeicherter Plan ohne Snapshot: erst ausdrücklich
berechnen, dann aktuellen Verlauf exportieren. Fremde Tracks im Web anzeigen;
Neuberechnung/Bearbeitung klar vom Original trennen. Native Dateien können ihren
Plan samt Snapshot wieder öffnen. Routennamen, Reihenfolge, Schleifen und
Segmente müssen beim Rundlauf erhalten bleiben.

## Übergabewege im Vergleich

| Weg | Vorteil | Aufwand/Grenze | Priorität |
| --- | --- | --- | --- |
| GPX-Dateiauswahl | Ohne Austauschserver; kompatibler Dateiaustausch | Datei muss aufs Handy; Standard-GPX liefert keine vollständigen App-Ansagen | Erste technische Übergabe |
| Kurzer HTTPS-Link + QR | Einfach vom PC zur App; derselbe Link zum Weitergeben | Austauschdienst, Ablaufregel, Domainverifikation, Webfallback | Danach bevorzugter Nutzerweg |
| Plan direkt im Link | Ohne Snapshotserver möglich bei begrenzter Punktzahl | Neuberechnung; keine Garantie derselben Strecke, begrenzte Link-/QR-Größe | Nur bewusst als Plan teilen |
| Google-Konto/Cloud-Synchronisation | Könnte mehrere Geräte automatisch synchronisieren | Neues Login-, Berechtigungs- und Synchronisationssystem; iOS ebenfalls lösen | Für #168 zurückstellen |

## Fehlerbehandlung und notwendige Tests

- Ungültiges XML, fehlende/ungültige Koordinaten, leere Strecken und unbekannte
  Erweiterungsversion mit verständlicher Meldung behandeln. GPX 1.0/1.1 und
  Namespaces bewusst unterstützen oder verständlich ablehnen. Externe Entitäten
  nicht auflösen; Dateigröße, Punktzahl und Verarbeitung begrenzen.
- Mehrere Tracks/Segmente auswählbar machen oder zunächst klar ablehnen;
  Lücken nicht als befahrbare Verbindung zeichnen. Unbekannte optionale
  Erweiterungen ignorieren, beschädigte native Navigationsdaten nicht verwenden.
- Geometrie, Manöver, Legs und Endpunkte gemeinsam prüfen. Bei fehlenden
  Ansagen höchstens bewusst als Track übernehmen. Keine geschätzte Dauer oder
  Komfortwerte als ursprüngliche Metadaten ausgeben.
- Speichern fehlgeschlagen, gleicher Name und Speicherlimit sichtbar behandeln;
  bestehende Einträge nicht unbemerkt ersetzen. Nach einem Fehler muss ein
  gültiger Import sofort wieder möglich sein.
- Gemeinsame Fixtures: einfache Strecke, zwei Zwischenziele, Direktvariante,
  Schiebeabschnitt/Zielzugang, Rundtour mit identischem Start/Ziel, wiederholte
  Punkte, Hin-/Rückweg auf derselben Straße, mehrere getrennte Segmente,
  Umlaute/Sonderzeichen und manipulierte/zu große Datei.
- App-Lebenszyklus, laufende Navigation, verspätete Routing-/Analyseantworten,
  Standort fern vom Start, Offline-Laden und Abweichung prüfen. Die bestehende
  Normalnavigation und Neuberechnung müssen außerhalb des Importmodus erhalten
  bleiben.

## Konkreter nächster Schritt

Mit Arbeitspaket 1 beginnen und parallel im selben fachlichen Entwurf eine
gemeinsame kleine Testdatei für Arbeitspaket 2 spezifizieren. Vor breiter UI-
Implementierung die Dateiübergabe mit bestehenden App-Manövern beweisen. Anschließend
Appimport/Persistenz fertigstellen, dann den QR-/Linkweg. App-Export und Webimport
sind Folgepakete, keine Voraussetzung für die erste Richtung PC → Handy.

Die größten Risiken sind Routentreue und Navigationszustand, nicht der
Downloadbutton. Aufwandsgrößen: Web-Zwischenziele mittel; snapshotfähiger Import,
Persistenz und Navigation groß; Linkdienst plus Plattformintegration mittel bis
groß; Rückweg mittel nach stabilem Vertrag. Dies sind relative Einschätzungen,
keine belastbaren Terminzusagen.

Prüfung dieser Analyse: Issue und Quellcode gelesen, GPX-/Plattformdokumentation
abgeglichen. Keine Laufzeit-, Geräte- oder automatisierten Funktionstests;
kein Funktionscode geändert und nichts auf GitHub veröffentlicht.
