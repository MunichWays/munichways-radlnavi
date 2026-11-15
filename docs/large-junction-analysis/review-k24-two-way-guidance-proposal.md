# K24 v1 · Vorschlag für Ansagen an Zweirichtungsradwegen

Stand: Analyse nach Thomas' Anfrage vom 15.11.2026. Keine Geometriefreigabe, technische Fahrbeziehungsfreigabe oder Aktivierung abgeleitet. K24 bleibt als technisch geprüfter Entwurf offen; der Runtime-Katalog v10 mit 23 Kreuzungen und 199 Beziehungen bleibt unverändert. Die Implementierung ist für Backend 2.4.12 / Frontend 2.4.2 und App-Branch `feature/two-way-junction-instructions` vorbereitet.

## Sprachvorschlag

- Geradeaus: „An der großen Kreuzung geradeaus auf den Zweirichtungsradweg gegenüber fahren.“
- Vorne links: „An der großen Kreuzung vorne links auf den Zweirichtungsradweg abbiegen.“

Thomas' Klarstellung: Nur die Nutzung des Zweirichtungsradwegs auf der linken Straßenseite gegen die reguläre Fahrtrichtung der Straße ist ein Sonderfall. Auf der rechten Straßenseite in Fahrtrichtung bleibt die bisherige Standardansage bestehen, auch wenn der Radweg selbst zweirichtig ist. Eine zusätzliche Vorlage „gegenüber links“ wird nicht eingeführt.

## Geometrische Beispiele, noch keine Legalitäts-/Routenfreigabe

Grundlage: unverändertes Bild und eingefrorene OSM-Daten von K24 v1.

| Eingang → Ausgang | Lage / Vorschlag |
| --- | --- |
| Entry-1 → Exit-3 | Geradeaus auf dem östlichen Ring-Radweg über die Maximilianstraße; gegenüber weiter auf Zweirichtungsradweg |
| Entry-2 → Exit-3 | Vorne links zum südöstlichen Zweirichtungsradweg |
| Entry-4 → Exit-6 | Vorne links zum nordwestlichen Zweirichtungsradweg |
| Entry-4 → Exit-1 | Standard links: Exit-1 liegt für die anschließende Fahrt nach Norden auf der rechten Straßenseite. „An der großen Kreuzung links abbiegen.“ |
| Entry-3 → Exit-1 | Standard geradeaus: anschließende Fahrt nach Norden auf der rechten Straßenseite; Zweirichtungsfähigkeit allein erzeugt keine Sonderansage |

Die tatsächlich von Standardrouting benutzten Korridore und Querungsfolgen sind vor Umsetzung separat zu prüfen. Insbesondere kann derselbe Zielarm mehrere Radwegseiten haben. Verbindungsstücke im Inneren, die technische Seite der Einfahrt und die tatsächliche Anfahrtsrichtung gehören zum Nachweis. Gleiche Entry-/Exitnummern bilden kein Fahrbeziehungspaar.

## Umsetzungsvorschlag

1. Für jede K24-Fahrbeziehung die Nutzung relativ zur regulären Fahrtrichtung der Straße explizit prüfen. Rechte Straßenseite mit der regulären Fahrtrichtung: unverändert Standard. Linke Straßenseite gegen die reguläre Fahrtrichtung auf einem dafür erlaubten Zweirichtungsradweg: Sondervorlage gegenüber geradeaus oder vorne links. Zweirichtungsfähigkeit allein genügt nicht. Keine automatische Zuordnung allein aus Winkel, Arm oder OSM-Einbahn-Tag. `oneway:bicycle=no` wird vor `oneway` ausgewertet; bidirektionale Fahrbahnpunkte sind dadurch noch keine Zweirichtungsradwege.
2. Im Backend wenige wiederverwendbare Ansagevorlagen definieren. Im geprüften Bewegungseintrag eine Vorlagen-ID und die überprüfte Zielradwegseite hinterlegen. Die API liefert daraus deutsche/englische Ansage und einen kompakten Anzeigetext. Daten für Zielseite und Fahrbeziehung bleiben in RadlNavi; keine K24-Sonderliste in der App.
3. App und RadlNavi-Prüfansicht lesen denselben Backendtext. App weiterhin zwei Vorankündigungen bei 120/40 m vor Beginn der Fläche, ohne gesprochene Meter; die Webvorschau zeigt eine zusammengefasste Zeile. Standardanzeige kurz halten, z. B. „x m große Kreuzung vorne links“; vollständige Radwegbezeichnung in der Ansage.
4. Einfache Textvorlagen getrennt von den Wilram-Sequenzen behandeln. Deren aktuelles Schema verlangt interne Checkpoints; für eine bloß abweichende Vorankündigung keine künstlichen Checkpoints erzeugen. Bisherige Ruhefläche und Route-verlassen-Regeln übernehmen.
5. Fähigkeit der App zur neuen Vorlage explizit aushandeln. Eine ältere App darf für eine mehrdeutige Beziehung nicht auf die allgemeine Linksansage zurückfallen: für diese Beziehung reguläre Manöver beibehalten, andere bekannte Makros unverändert ausliefern.
6. Reale Standardrouten einfrieren und positive Zuordnung, falsche Zielradwegseite, Rechts-/Fußkontrollen, alte Clients und unveränderte Routendaten prüfen. Erst eindeutige bestandene Beziehungen aktivieren; einzelne unklare Beziehungen ausschließen. Ein Textvorschlag ist keine Aktivierungsfreigabe.

Noch offen: endgültige Formulierungen für die beiden Sondervorlagen; anschließend technische Prüfung der konkreten Beziehungen. Die Standardansage für Entry-4 → Exit-1 bleibt ausdrücklich erhalten. Unklare Sonderbeziehungen bleiben bei normalen Hinweisen.

## Implementierungsstand

Die Vorlagen `two-way-straight-opposite` und `two-way-left-near` liefern geprüfte deutsche/englische Ansage- und Anzeigetexte im Feld `instruction`, ohne Checkpoints. Der Client meldet `X-Junction-Guidance-Version: 3`; die Metadaten verwenden bei neuen Vorlagen `big-junctions-v3`. Version 3 unterstützt weiterhin Wilram-Sequenzen, alte Clients erhalten für die fünf Sonderbeziehungen normale Manöver. Standard-, Direkt- und Entdeckertour-Weiterleitung erhalten die Fähigkeitskennung.

22 echte K24-Standardrouten sind eingefroren: 15 Links-/Geradeausbeziehungen technisch bestanden, davon zehn Standard und fünf Sonderbeziehungen; sieben Rechtskontrollen ohne Makro. Die freigegebene Semantik Entry-4 nach Exit-1 bleibt Standard links, nach Exit-6 gilt vorne links. Für Entry-4 nach Exit-6 wurden legale Referenzpunkte 25 m außerhalb gewählt: Bei 45 m startet die Route vor der Herzog-Rudolf-Straße und umfährt K24. Der ursprüngliche Umweg bleibt als negative Regression gespeichert. Keine Flächenverschiebung oder Toleranzerweiterung.

Die exakten neuen API-Antworten werden gemeinsam in Backend-, Web- und App-Tests verwendet. Die bestehenden Ansageabstände, Ruhefläche und Route-verlassen-Logik der App bleiben bestehen. K24 ist noch nicht im Runtime-Katalog aktiviert; die konkrete Freigabe der K24-Fläche und Fahrbeziehungen erfolgt separat.
