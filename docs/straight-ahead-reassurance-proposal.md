# Zwischenansage auf langen geraden Abschnitten

Stand: 28.09.2026. **Grundregel in der Flutter-App lokal umgesetzt, noch
nicht committed oder auf einem Gerät geprüft.** Bei mehr als 500 m bis zum
nächsten relevanten Hinweis wird einmal ungefähr in der Abschnittsmitte
angesagt. Wiederholungen innerhalb eines Abschnitts sind nicht vorgesehen.

## Wunsch

Bei längerem Geradeausfahren gelegentlich bestätigen, dass die Navigation
weiterläuft: „Weiter geradeaus. In x Metern …“.
Dadurch muss man auf langen Abschnitten seltener auf die Karte schauen.

## Umgesetzte Grundregel

- Bei einem geeigneten Abschnitt **länger als 500 m** einmal ungefähr in der
  Mitte eine zusätzliche Ansage ausgeben.
- Abschnitt bedeutet die Strecke entlang der Route zwischen zwei relevanten
  Navigationshinweisen, einschließlich Routenstart bis zum ersten Hinweis.
  Einzelne OSM-Kanten oder API-Steps sind dafür keine geeignete Einheit.
- Beispiel: Nächste Abbiegung nach 800 m. Nach etwa 400 m:
  „Weiter geradeaus. In 400 Metern rechts abbiegen.“
- Die gesprochene Entfernung ist die **aktuell verbleibende Routendistanz**
  zum nächsten Manöver, sinnvoll gerundet. Sie ist nicht fest die Hälfte
  der ursprünglichen Abschnittslänge und auch keine Luftlinie.
- Im letzten Abschnitt stattdessen gegebenenfalls:
  „Weiter geradeaus. In 400 Metern erreichst du dein Ziel.“

Ein Abschnitt ohne Abbiegehinweise ist nicht automatisch gerade. Vor einer
Umsetzung muss festgelegt werden, wann der Verlauf „Weiter geradeaus“
rechtfertigt. Bei deutlichen Kurven wäre etwa „Dem Weg weiter folgen“
passender. Fehlende Manöver dürfen durch diese Ansage nicht verdeckt werden.

## Richtige Stelle: App

Das ist eine Ergänzung der zeitlichen Sprachausgabe in der Flutter-App.
OSRM-Manöver, Fahrradprofil und RadlNavi-API müssen dafür nicht geändert werden.
Ansatzpunkt ist `lib/ui/map/voice_guidance.dart` im App-Repository.

Die Zwischenansage verwendet einen eigenen Zustand pro Routenabschnitt. Sie
markiert weder ein Manöver als erledigt noch dessen normale Voransage als
bereits gesprochen. Beim Einschalten der Sprachausgabe genau in der Mitte
unterbleibt eine unmittelbar doppelte Zwischenansage.

## Weiterführende Anforderungen für spätere Umsetzung mit LLMs

1. Zuerst vorhandene Fortschritts-, Entfernungs- und Sprachformatierung prüfen
   und wiederverwenden. Keine zweite Berechnung mit abweichenden Distanzen bauen.
2. Beim erstmaligen Überschreiten der Abschnittsmitte auslösen; keine exakte
   GPS-Position voraussetzen. Sprünge nahe an die nächste Abbiegung dürfen
   keine verspätete Zwischenansage auslösen.
3. Pro Abschnitt höchstens einmal sprechen, auch bei GPS-Schwankungen,
   Anhalten oder erneutem Öffnen der Navigationsansicht. Wiederkehrende Orte
   in Schleifen als unterschiedliche Abschnittsvorkommen behandeln.
4. Nur bei aktiver Sprachnavigation und verlässlicher Position auf der Route
   ausgeben. Abbiege-, Ziel- und Abweichungshinweise haben Vorrang; keine
   veraltete Zwischenansage nachträglich aus einer Warteschlange abspielen.
5. Bei Neuberechnung alte ausstehende Ansagen verwerfen und den Abschnitt neu
   bewerten. Wiederholungen unmittelbar nach Neuberechnung vermeiden.
6. Bestehende Vor- und Sofortansagen unverändert erhalten. Den nächsten Hinweis
   mit der bestehenden Sprachformatierung erzeugen, einschließlich kombinierter
   Abbiegungen und Zielankunft.
7. Für die Prüfung einen deterministischen Verlauf des Routenfortschritts
   verwenden und die tatsächlichen App-Sprachausgaben protokollieren.
   Der Webprüfer zeigt bislang API-Manöver und Browsertexte; eine zusätzliche
   App-Ansage wäre dort ohne App-Replay nicht nachgewiesen.

## Noch zu entscheiden

- Ist 500 m die richtige Mindestlänge? Einmal in der Mitte oder auf sehr
  langen Abschnitten wiederholt, beispielsweise nach Distanz oder Zeit?
- Welche Geometrie gilt als ausreichend gerade, und wann wird neutral
  „Dem Weg weiter folgen“ verwendet?
- Standardmäßig aktiv oder als einstellbare Ansagehäufigkeit?
- Mindestabstand zu anderen Ansagen sowie Verhalten bei Einstieg mitten
  in einen Abschnitt, Wiederaufnahme und Neuberechnung.

## Abnahmefälle

- 499 m und genau 500 m: keine Zwischenansage bei der vorgeschlagenen Regel.
- 501 m und 800 m: einmal beim Überschreiten der Mitte; Entfernung entspricht
  dem tatsächlichen Fortschritt und wird verständlich gerundet.
- Mehrere Kilometer: im ersten Versuch weiterhin nur einmal; Wiederholung
  erst nach ausdrücklicher Festlegung ergänzen.
- GPS pendelt um die Mitte, Pause/Wiederaufnahme: keine doppelte Ansage.
- Positionssprung bis kurz vor die Abbiegung: normale Abbiegeansage hat Vorrang.
- Neuberechnung, Routenabweichung, stummgeschaltete Navigation und Ankunft:
  keine unpassende oder veraltete Zwischenansage.
- Kurviger Weg ohne Manöver: keine irreführende Geradeausbehauptung.
- Birketweg mit zwei nahen Abbiegungen: beide normalen Hinweise und deren
  kombinierte Ansage bleiben erhalten.

Die lokale App-Änderung liegt in `lib/ui/map/voice_guidance.dart`, mit Tests
in `test/ui/map/straight_ahead_reminder_test.dart`. Statische Analyse und
53 gezielte Navigationstests liefen erfolgreich. Die gesamte Testsuite und
ein Gerätetest wurden dafür nicht ausgeführt. Die übrigen Abnahmefälle sind
weiterhin geplante Prüfungen.
