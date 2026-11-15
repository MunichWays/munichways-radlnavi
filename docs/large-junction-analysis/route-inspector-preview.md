# Hinweise in RadlNavi und App vergleichen

Unter **Hinweise prüfen** liefert jede Zeile den bisherigen RadlNavi-Text und darunter eine App-Vorschau. Standard, Direkt und Entdeckertour fragen dieselben optionalen Kreuzungsmetadaten wie die App an: `junction_guidance=true`, Header `X-Junction-Guidance-Version: 2`. Die Rohroute bleibt unverändert; der Download enthält die komplette Antwort inklusive Metadaten.

Große Kreuzungen werden aus dem aktiven Backend-Katalog abgeleitet, nicht aus einer separaten Frontend-Liste. Die Vorschau zeigt die Ansagen bei 120/40 Metern bis zum Kreuzungsbeginn und die kompakte App-Anzeige. Bei kurzem Start oder dicht folgenden Kreuzungen entfällt eine bereits verpasste Vorankündigung. Die zusätzlichen Zeilen verweisen auf der Karte auf den Kreuzungsbeginn beziehungsweise den internen Checkpoint. Einzelhinweise innerhalb der Kreuzung bleiben als RadlNavi-Rohhinweise sichtbar, sind bei App aber als unterdrückt markiert. Ausgeschlossene Fahrbeziehungen behalten normale Hinweise.

Sonderfolgen wie Wilram liefern ihre geprüften internen Texte. Eine alternative Anfahrt wird als zweite Möglichkeit angezeigt; beim Vorlesen gilt die geplante Anfahrt. Ohne beobachtete GPS-Bewegung kann die Vorschau zwischen diesen Varianten nicht entscheiden. Interne Hinweise werden in der App bereits bis zu zwölf Meter vor der Stelle ausgelöst; die Prüfliste ordnet sie dem Checkpoint zu.

Normale deutsche Abbiegetexte orientieren sich an `VoiceGuidance._action` und `formatManeuver` der Flutter-App, einschließlich Straßennamen, Wegwechseln und enger Folgen bis 35 Metern. Sie zeigen die Hier-Ansage als Textbeispiel. Vollständige Start-/GPS-Zustände, Versatzfilter, wiederholte Strecken, Geschwindigkeitsvorhersage, Zwischenzielnamen und tatsächliche Sprechzeitpunkte werden nicht nachgebildet. Diese Vorschau prüft Texte und Zuordnung; GPS-Verhalten bleibt Gegenstand von Praxistests.

RadlNavi und App lassen sich getrennt vorlesen. Der frühere Auswahlwert „Automatisch aus Routendaten“ entfällt. Die verbliebenen manuellen Wegwechsel-Zusätze verändern nur die RadlNavi-Textvorschau, nicht die App-Auswertung oder Rohdaten.

Regressionen verwenden eingefrorene Backend-Antworten für K19, Wilram und die ausgeschlossene K21-Beziehung. Ungültige Metadaten fallen auf normale Hinweise zurück und werden im Prüffenster gemeldet. Bei Änderungen an Flutter-Textregeln die Vorschau und ihre Vertragsbeispiele gemeinsam prüfen.
