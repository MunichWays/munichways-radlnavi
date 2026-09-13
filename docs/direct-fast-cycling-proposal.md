# Direkt: zügiges Radfahren ohne Komfortgewichtung

Stand: 13.09.2026. Die eindeutig festgelegten Profil- und API-Anteile sind
implementiert. Dieser Entwurf ersetzt das bisherige Ziel der kürzesten
befahrbaren Strecke.
Name und API-Variante bleiben `Direkt` / `direct`.

## Ziel und Entscheidung

Direkt soll eine zügig fahrbare Alternative ohne Bevorzugung komfortabler Wege
liefern. Hauptstraßen dürfen genutzt werden, werden aber nicht allein deshalb
bevorzugt, weil sie stressig sind. Der Komfort-Index wird anschließend unverändert
berechnet. Eine schlechtere Bewertung und eine kürzere Strecke sind mögliche
Ergebnisse, keine künstlich erzwungenen Eigenschaften.

OSRM und die getrennten Direkt-Dienste bleiben erhalten. Ersetzt wird die
distanzbasierte Gewichtung durch eine zeitbasierte Gewichtung mit Regeln für
gut fahrbare Radverbindungen. Ein Wechsel der Routing-Engine ist dafür unnötig.

## Vorbilder und Grenzen

Das [aktuelle OSRM-Fahrradprofil](https://github.com/Project-OSRM/osrm-backend/blob/master/profiles/bicycle.lua)
verwendet standardmäßig Dauer als Gewicht, unterstützt aber auch Schieben und
hat andere Geschwindigkeitsannahmen. Es ist deshalb kein unverändert passender
Ersatz. Diese Aussage bezieht sich auf den eingesehenen Upstream-Master, nicht
auf einen geprüften Stand unseres gebauten Images.

[BRouter fastbike](https://github.com/abrensch/brouter/blob/master/misc/profiles2/fastbike.brf)
ist ein passendes konzeptionelles Vorbild für zügiges Fahren mit geringer
Verkehrsvermeidung. Für Treppen und Schieben verwenden wir unsere gemeinsamen
starken Aufschläge; Fähren bleiben ausgeschlossen. Auch sein eigenes Fahrzeitmodell
übernehmen wir nicht: Vergleichbarkeit mit Standard hat Vorrang.

[Komoot beschreibt Rennrad als Präferenz für asphaltierte Straßen](https://support.komoot.com/hc/en-us/articles/4402857453722-Planning-Tours-on-the-website).
Daraus folgt keine belegte generelle Bevorzugung des offiziellen OSM-Radnetzes
durch Komoot oder Google. Radnetz-Relationen sind vorerst kein zusätzliches
Gewicht; eine spätere Ergänzung benötigt konkrete Vergleichsfälle.

## Gemeinsame Regeln, getrennte Auswahl

Gemeinsam bleiben echte Zugangsverbote, Einbahnregeln einschließlich expliziter
Radfreigaben, Abbiegebeschränkungen, Pflicht-Radweg-Regeln und das physische
Fahrzeitmodell. Fähren bleiben ausgeschlossen.

Direkt ignoriert `class:bicycle` vollständig für die Routenauswahl, auch den
heute separat gesperrten Wert -3. Echte Verbote müssen aus Zugangsregeln stammen;
ein Bewertungstag allein darf Direkt nicht sperren. Die Komfortanalyse darf
denselben Tag weiterhin bewerten.

Nach der Klarstellung im Qualitätscheck bleiben Treppen und Schiebeverbindungen
in beiden Profilen als letzte Verbindung erhalten. Gemeinsame Suchaufschläge:
Faktor 10 für Schieben, Faktor 20 für Treppen gegenüber normalem Fahren bei
20 km/h Referenzgeschwindigkeit, ohne Multiplikation beider Faktoren. Standard
berücksichtigt zusätzlich Komfort. Gehwege können nur entsprechend den gemeinsamen
Zugangsregeln, gegebenenfalls im Schiebemodus, genutzt werden. Rechtlich und tatsächlich
befahrbare gemeinsame Geh-/Radwege und eigenständige Radwege bleiben möglich;
ein pauschales Verbot von `highway=path` würde gute Verbindungen entfernen.
Oberfläche und Befahrbarkeit bestimmen die Eignung, nicht allein die Straßenklasse.
Der konkrete Umgang mit schlechten Oberflächen wird an Testfällen festgelegt.

Letzte Meter zum Ziel bleiben eine gesonderte Darstellung. Ein Zwischenziel auf
einem nicht befahrbaren Gehweg darf weder stillschweigend übersprungen werden
noch verbotene Durchfahrt erzwingen. Der bisherige Test über die Hausdurchfahrt
Falkensteinstraße prüft damit auch eine bewusst erzwungene Schiebeverbindung.

## Fahrzeit und Suchgewicht

Für beide Varianten gilt dasselbe Modell:

`Angezeigte Fahrzeit = Zeit aus gemeinsamen Geschwindigkeiten + Abbiegezeit + Wartezeit`

Für Direkt gilt als Ausgangspunkt:

`Suchgewicht = Fahrzeit + Abbiegekosten + alpha * Ampelwartezeit + Eignungsaufschläge`

`alpha < 1` setzt die gewünschte geringere Bedeutung von Ampeln bei der Auswahl
um. Der implementierte und mit OSRM-Fixtures geprüfte Wert ist 0,25. Seine
fachliche Kalibrierung anhand realer Strecken bleibt offen. Stop-Hindernisse und
Bahnübergänge erhalten keinen Rabatt, auch bei gleichzeitig vorhandener Ampel. Rechtliche
Sperren bleiben unabhängig von diesem Gewicht hart.
Die ausgegebene `duration` darf niemals aus diesem reduzierten Suchgewicht
abgeleitet werden. Ein eigener Gewichtsname kennzeichnet die neue Semantik.

Aktuell enthält `bike.lua` sechs Sekunden Signalaufschlag und Ausnahmen für
bestimmte Rechtsabbiegungen. Stärkere Wartezeiten müssen für beide Varianten
gemeinsam eingeführt werden. Da Standard derzeit Dauer auch für Suchgewichte
nutzt, darf eine ETA-Kalibrierung nicht unbemerkt seine Routenauswahl verändern.
Zuerst Auswahl und Zeitschätzung explizit trennen; stärkere Ampelwartezeiten
anschließend anhand konkreter Kreuzungen bestimmen. Keine pauschale Erhöhung
der Direkt-Geschwindigkeit zur Verschönerung der Minutenanzeige.

Gleiche Teilstrecken unter denselben Bedingungen erhalten gleiche Fahrzeiten.
Verschiedene Strecken müssen nicht proportional zu ihrer Länge dauern. Weniger
Ampelgewicht bei der Auswahl kann sogar eine kürzere, aber langsamer angezeigte
Direkt-Route ergeben. Sonntags-/Nachtverkehr wird ohne zusätzliches Zeitmodell
nicht automatisch anders geschätzt.

## Umsetzung in begrenzten Schritten

1. Gemeinsame Befahrbarkeit und Fahrzeit von Komfort- und Direkt-Gewichtung
   trennen. Standard anhand bestehender Fixtures unverändert absichern.
2. Direkt auf zeitbasierte Auswahl umstellen, Bewertungseinfluss vollständig
   entfernen und Treppen sowie Schiebeverbindungen stark abwerten. Vor einem großen
   Kartenbuild kleine Profil-Fixtures testen.
3. Metadatum `objective` in `/routing_variants`, Deployment-Prüfung auf den
   bisherigen Gewichtsname `distance`, Profiltests und Dokumentation anpassen.
4. App-Rückfall auf `BRouterProfile.shortest` für Direkt ersetzen. Bis ein
   kompatibler Ersatz geprüft ist, Direkt als nicht verfügbar behandeln und
   Standard nutzbar lassen. Bestehende Standard-Fallbacks bleiben erhalten.
5. Gemeinsame Ampelzeit-Kalibrierung separat prüfen. Geänderte Profile benötigen
   neu aufgebaute Routing-Graphen; bei gemeinsamen Änderungen beide Varianten.

Die vorhandene Variantenverwaltung, Navigation, Leg-Zuordnung, nachgeladene
Komfortanalyse und Dienst-Isolation werden weiterverwendet. Ein anderes
Suchgewicht behebt keine Cold Starts oder verzögerte Analyseantworten; deren
Messung bleibt ein eigener Teil der Abnahme.

## Abnahme

- Gleicher OSM-Datenstand für Standard, bisheriges Direkt und den Kandidaten.
- Nur `class:bicycle` in einer Fixture verändern: Direkt-Geometrie und ETA
  bleiben gleich, Komfort darf sich ändern.
- Gemeinsame Kanten, Abbiege- und Ampelsituationen haben identische Dauer;
  reduziertes Ampel-Suchgewicht reduziert nicht die ausgegebene Wartezeit.
- Keine Fähren oder verbotenen Gegenrichtungen. Treppen und Schieben werden
  vermieden, bleiben aber bei sehr großen Umwegen oder fehlenden Alternativen nutzbar.
  Explizite Fahrradfreigaben und geeignete eigenständige Radwege bleiben nutzbar.
- Arnulfstraße und Lenbachplatz als Gegenrichtungsregression; Starnberger See
  als Fährtest; Arbeitsweg mit und ohne die Unterführungs-Zwischenziele.
- Lange Route mit zwei Zwischenzielen: 48.156304,11.540013 über
  48.102548,11.568796 und 48.120477,11.655645 nach 47.991860,11.828568.
- Stadtstrecken mit vielen Ampeln und Außenbezirke: Geometrie, Kilometer,
  Fahrzeit, Komfort und Befahrbarkeit gemeinsam bewerten. Kürzer ist keine
  universelle Bestehensbedingung.
- Standard-Latenzen unter gleicher Last vergleichen; Direkt und Komfort separat
  messen, warme Antworten und Cold Starts getrennt ausweisen.

Die kleinen Profil-Fixtures wurden mit OSRM 26.6.5 gebaut und erfolgreich geprüft:
Standard-Regressionssuite, Direkt-Profil einschließlich gleicher Fahrzeiten und
getrenntem Ampel-/Bahnübergangsgewicht sowie Arnulfstraße und Lenbachplatz in beiden
Varianten. Produktion wurde nicht geändert. Ein großer Kartenbuild und eine
erneute Lastmessung bleiben Teil der anschließenden Abnahme.

Auch der echte lokale HTTP-Vertrag mit zwei API-Diensten, Zwischenzielen,
Navigation und nachgeladener Komfortanalyse ist erfolgreich geprüft. Die
vollständige Backend-Suite besteht mit 63 Tests im Container. App-Anpassungen
und deren BRouter-Rückfall bleiben ein separater Schritt.

Nach dem ersten Praxistest wurden vorsichtige Direkt-Suchaufschläge für
Wohnstraßen (8 Prozent) und Oberflächen ergänzt. Die Werte und der neue
Fixture-Testumfang stehen in [Direkte Route](direct-route.md). Standard und die
gemeinsame Fahrzeitberechnung wurden dabei nicht geändert. Der erneute Vergleich
der beiden vollständigen Münchner Strecken benötigt einen neuen Direkt-Graphen.
