# Wiederverwendbare Kreuzungs-Sonderabläufe

Implementiert für K10 v4 / Wilramstraße in Backend 2.4.8 und im App-Branch.
Build, Deployment und Praxistest sind getrennte Schritte; diese Umsetzung startet keines davon.

## Daten statt ortsspezifischer App-Logik

Ein geprüftes Movement kann zusätzlich `sequence` tragen. Es enthält Version 1,
deutsche/englische Vorankündigung, kurzen Hinweistext und ein bis sechs geordnete
Checkpoints. Jeder Checkpoint bindet eine kurze Anweisung und einen Modifier an
eine Koordinate auf dem geprüften Korridor. Anfahrt und Weiterfahrt müssen jeweils
mindestens acht Meter gerichtete Evidenz auf demselben Korridor liefern. Punkte
müssen in der Kreuzungsfläche liegen und mindestens fünf Meter auseinanderliegen.

Die ausführliche Ansage ersetzt die bisherigen 120-/40-m-Makrotexte. Nur die
expliziten Checkpoints dürfen die ansonsten stumme Kreuzungsfläche unterbrechen.
Normale Schritte, Rohgeometrie, Routenwahl und Route-verlassen-Unterdrückung bleiben
unverändert. `uturn` ist nur für eine ausdrücklich geprüfte Sonderfolge erlaubt.

Die App enthält keine Prüfung auf „Wilramstraße“ oder eine bestimmte Kreuzungs-ID.
Weitere Fälle verwenden dasselbe Schema, benötigen aber eigene Geometriefreigabe,
echte legale Referenzrouten, geprüfte Anweisungen und Gegenfälle.

## Kompatibilität

- Opt-in bleibt `junction_guidance=true`.
- Neue Apps melden `X-Junction-Guidance-Version: 2` als HTTP-Header. Kein neuer
  unbekannter OSRM-Queryparameter: ältere Backends können weiter normal antworten.
- Der Variant-Gateway reicht nur diese Fähigkeit neben seinen eigenen
  Authentifizierungsheadern weiter; Routingparameter werden nicht verändert.
- Enthält die Antwort eine Sonderfolge, lautet die Metadatenversion
  `big-junctions-v2`; sonst bleibt es `big-junctions-v1`.
- Ohne Fähigkeitshinweis liefert das Backend für Sonderfälle keine Makrometadaten.
  Die unveränderten normalen Abbiegeschritte bleiben nutzbar. Normale Kreuzungen
  erhalten weiterhin v1-Metadaten.
- Die neue App prüft beide Versionen strikt. Ungültige Anker, Sprachen,
  Richtungen, Reihenfolge oder unbekannte Versionen fallen auf die Rohhinweise zurück.

## Ort und tatsächliche Richtung

Checkpoints werden einmal je Kreuzungsbesuch ausgelöst, innerhalb von zwölf Metern
vor der Stelle. Die App benötigt höchstens 15 m gemeldete GPS-Ungenauigkeit und
bestätigte aktuelle Bewegung. Sie sammelt dafür abhängig von der Genauigkeit
8–25 m Versatz; alte GPS-Pausen oder unplausible Sprünge erzeugen keine Richtung.
Die Anfahrt muss zum geprüften Eingangswinkel passen. Hinter einer Stelle gibt es
keine verspätete Nachholserie; übersprungene frühere Punkte werden beim nächsten
bestätigten Checkpoint abgeschlossen.

`alignedInstruction` erlaubt am ersten Entry-4→Wilram-Checkpoint „Hier geradeaus.“,
wenn der Nutzer bereits in Weiterfahrtrichtung ankommt. Dafür muss die tatsächliche
Richtung bis auf 25° mit der geprüften Weiterfahrt übereinstimmen. Eine gespeicherte
alte Richtung direkt an der Ecke oder eine widersprüchliche Anfahrtsseite genügt
nicht. Sonst gilt bei bestätigter regulärer Anfahrt „Hier rechts.“; bei Unsicherheit
bleibt der Zusatzhinweis stumm. Das ist eine GPS-Entscheidung, keine Änderung der Route.

## Nachweise und Wiederholung

- `prepare_wilram_sequences.py` baut aus den eingefrorenen fünf Routen einen
  separaten Vorschlag und Backend-/App-Vertragsdaten. Es aktiviert keinen Katalog.
- `backend/src/junction_sequences.py` prüft Übersetzungen, Anker und gerichtete
  Korridorevidenz. Routenanker werden auf den aktuellen Besuch begrenzt, damit
  wiederholte Kreuzungsbesuche nicht die Indizes des ersten Besuchs erhalten.
- Backend-Tests prüfen alle fünf Rohantworten, alte Clients, Opt-out, Schieben,
  fehlerhafte Konfiguration und Gateway-Authentifizierung/Fähigkeitsweitergabe.
- App-Tests simulieren alle fünf Fahrten, interne Einmalansagen, die alternative
  tatsächliche Anfahrt, GPS-Ausfall, Stillstand und falsche Richtung.

Die alternative Querung ist synthetisch geprüft. Ein Praxistest beider Anfahrten
bleibt erforderlich. Wilram→Exit-2 bleibt eine zusätzliche Rechtskontrolle außerhalb
der Fläche und erhält keine Sonderfolge.
