# Gegenrichtungen und Schiebeverbindungen – September 2026

Die Produktionsantworten vom 11.09.2026 reproduzieren beide Meldungen:
Direkt verwendet auf Arnulfstraße ca. 405 m im Modus `pushing bike`; am
Lenbachplatz kommen Schiebeabschnitte auf Elisenstraße und dem gemeinsamen
Fuß-/Radweg hinzu. Die gesnappten Start-/Zielpunkte sind je Beispiel bei
Standard und Direkt gleich. Das Problem entsteht im gemeinsamen Profil:
Die nachgelagerte Schiebefunktion öffnet zuvor gesperrte Einbahnrichtungen;
Direkt bewertet Schieben anschließend wie einen normalen Streckenmeter.
Auf Arnulfstraße/Elisenstraße ist teilweise zusätzlich `foot=use_sidepath`
gesetzt. Diese Kennzeichnung wurde beim Schieben bislang ignoriert.

## Änderung

Routing 2.3.2 bewahrt die Einbahnrichtungen nach dem Anwenden expliziter
Fahrrad-Gegenrichtungsfreigaben. Der automatische Wechsel auf Schieben öffnet
sie nicht wieder. `foot=no` und `foot=use_sidepath` dürfen ebenfalls keine
Schiebeverbindung auf dieser Kante erzeugen. Die Regel gilt für beide Profile.
Das ist eine Routingentscheidung gegen Gegenrichtungs-Abkürzungen, keine
Behauptung, dass Fußgänger generell an Fahrrad-Einbahnregeln gebunden wären.

Zulässiges Schieben bleibt möglich, wird aber mit Faktor **10** bewertet:
100 m Schieben kosten wie mindestens 1 km normale Strecke, bei Standard mit
derselben Komfortbewertung. Treppen behalten Faktor **20**. Die Faktoren werden
nicht multipliziert; es gilt die stärkere Abwertung. ETA und tatsächliche
Distanz bleiben getrennt davon, typischerweise 4 km/h beim Schieben und höchstens
2 km/h auf Treppen. Ein sehr langer fahrbarer Umweg kann daher weiterhin eine
kurze zulässige Schiebeverbindung unattraktiver machen als das Schieben selbst.

## Prüfung

Die synthetischen OSRM-Regressionen prüfen beide Einbahnrichtungen, explizite
Gegenrichtungsfreigaben, gemeinsame Fuß-/Radwege, Absteigen, echte Zugangsverbote,
Treppen und Fähren. Zusätzliche Alternativrouten prüfen: Ein fahrbarer Umweg
von etwa siebenfacher Länge wird dem Schieben vorgezogen; bei etwa dreißigfacher
Länge bleibt die Schiebeverbindung sinnvoll und wird gewählt.

Der eingefrorene OSM-Ausschnitt unter `routing/tests/fixtures/` enthält beide
realen Münchner Strecken. Die neue Regression erkennt in den aufgenommenen
Produktionsantworten Gegenrichtungsabschnitte auf neun bzw. fünf Einbahn-Wegen.
Mit dem neuen Profil darf kein solcher rückwärts durchlaufener Abschnitt mehr
auftreten. Der Ausschnitt ist vom 11.09.2026; er ist kein identischer Abzug des
älteren produktiven PBF. Ein vollständiger Oberbayern-Neubau ist lokal nicht
Teil dieser kleinen Regression.

Abschlussprüfung erfolgreich: bisherige Standard- und Direkt-Profilregressionen,
neue Schiebe-/Einbahnregressionen sowie beide realen Beispiele. Standard ergibt
707,4 / 532,5 m, Direkt 661,6 / 532,5 m, jeweils ohne verbotene Gegenrichtung.
Frontend-TypeScript-Prüfung (`tsc --noEmit`) erfolgreich. Produktionsstand wurde
nicht geändert; weder Commit noch Push oder Deployment wurden ausgeführt.

## Direkt auf der RadlNavi-Karte testen

Frontend 2.3.1 bietet einen Testmodus per URL, ohne Variantenwechsel während
einer laufenden Berechnung:

* Lokal nach Neubau: `http://localhost/?variant=direct`
* Nach Frontend-Deployment: `https://radlnavi.munichways.de/?variant=direct`
* Ohne Parameter: Standard.

Die blaue Kennzeichnung „Direkte Route (Testmodus)“ muss sichtbar sein. Beide
Requests, Route und nachgelagerte Komfortanalyse, übergeben `variant=direct`.
Der Testmodus verwendet den bestehenden Standard-API-Proxy zur Direkt-API;
er ist für visuelle Tests gedacht, nicht als neuer Lasttestpfad der App.

Beispiele (Breite, Länge), Start/Ziel auf der Karte setzen:

* Arnulfstraße: `[48.142131, 11.554569]` → `[48.141745, 11.562248]`
* Elisenstraße/Lenbachplatz: `[48.140805, 11.565394]` → `[48.141976, 11.571082]`

Beide Routing-Graphen und das Frontend müssen neu gebaut werden. Der Parameter
allein aktiviert den Modus in einer noch alten Frontend-Version nicht.

## Nachtrag: lokaler Direkt-Test und Fehlerbehandlung (12.09.2026)

Beim gemeldeten weißen Bildschirm liefen nur die drei Standard-Container.
`/routing_variants` meldete `direct.available=false`; `/route?variant=direct`
lieferte HTTP 503. Das Frontend übernahm die Fehlerantwort ungeprüft und griff
in einem verzögerten React-State-Updater auf `results.route.distance` zu.

Frontend 2.3.2 prüft HTTP-Status und Routenstruktur vor dem Setzen des Zustands.
Bei einem Fehler bleiben Karte und Auswahl sichtbar, mit einer Fehlermeldung
und „Erneut versuchen“. Fehler der optionalen Analyse verhindern keine gültige
Route. Geänderte Start-/Zielpunkte brechen alte Route-/Analyseanfragen ab;
verspätete Antworten dürfen nicht die neue Auswahl überschreiben.

Prüfung: acht API-/Fehlerregressionen und ein React-Integrationstest für
„Route hierhin“, HTTP 503, Wiederholen und anschließend fehlgeschlagene Analyse
bestanden. TypeScript-Prüfung und Docker-Produktionsbuild erfolgreich; bestehende
Lint-Warnungen sind weiterhin vorhanden. Lokal laufen nun auch Direkt-Routing
und Direkt-Backend aus den vorhandenen Images. Veraltete Direkt-Container mit
Verweis auf ein gelöschtes Docker-Netzwerk wurden neu erstellt. Direkt-Route
und -Analyse funktionieren über den Standard-API-Proxy. Das neue Frontend wird
unter localhost ausgeliefert. Kein Produktionsdeployment oder Routing-Neubau
in diesem Nachtrag.

Für zukünftige lokale Starts beide Compose-Dateien verwenden:

```powershell
docker compose -f compose.yaml -f compose.direct.yaml up -d --no-build
```

Nur `compose.yaml` konfiguriert die Standard-API ohne Direkt-Anbindung.
