# Stand der Kreuzungsprüfung

Stand: 08.11.2026. Gezählt werden eindeutig benannte Standorte aus Prüfrunden und Backendkatalog; Kandidatenpunkte sind keine weiteren geprüften Fälle.

| Kategorie | Anzahl |
| --- | --- |
| Geometrisch bestätigt, aktuelle Prüffassung einschließlich Piloten | 20 |
| Kreuzungen im Backendkatalog des Branches | 17 |
| K11–K17 live und mit vielen Fahrbeziehungen praxiserprobt | 7 |
| Ausgeschlossen | 7 |
| Offen, einschließlich zurückgestellter Fälle und neuer Entwürfe | 1 |
| Insgesamt erfasste Standorte | 28 |

K01–K17: 15 bestätigt, einschließlich der nach Praxistest freigegebenen K05-v3-Fläche. K07 bleibt zurückgestellt, K09 dauerhaft ausgeschlossen.
Zusätzlich: zwei aktive Piloten (Arnulf/Steubenplatz und Balan/Chiemgau) sowie vier frühere technische Ausschlussfälle.

BA09-Prüfrunde K18–K22: K19 und K21 v2 sind geometrisch freigegeben; technische Fahrbeziehungsprüfung ausstehend. K20 und K22 sind auf ausdrücklichen Wunsch von Thomas dauerhaft ausgeschlossen und geschlossen. K18 v3: Entry-2 entfernt; laut Thomas ist der frühere Guntherstraßen-Radweg inzwischen reiner Fußweg und in OSM korrigiert. Übrige Punktnamen bleiben erhalten; Geometrie v3 inzwischen ausdrücklich freigegeben; technische Prüfung ausstehend. Alle fünf sind inaktiv. Die 32 Punkte der eingefrorenen BA09-Abfrage sind vollständig und ohne Doppelzählung neun vorhandenen und diesen fünf verbleibenden Standorten zugeordnet; dies belegt nur die Abdeckung dieser Abfrage.

Vorheriger Live-Stand: Backend 2.4.5, Commit 32df25b, Katalog v4 mit 74 Beziehungen. Damals bestanden alle 120 Live-Testfälle einschließlich ausgeschlossener und rechter Fahrbeziehungen; Routenantworten blieben unverändert. Diese historischen Belege bestätigen nicht den neuen 2.4.6-Stand. [Historische Live-Belege](review-batch-01-live-check.json).

Backend 2.4.6 ist live, Commit d3c8b55, Katalog v5: 17 aktive Kreuzungen und 144 aktive Beziehungen. K11–K17 wurden von Thomas mit vielen Fahrbeziehungen erfolgreich in der Praxis getestet; dokumentiert in review-field-tests.json. Es wird nicht behauptet, dass jede einzelne Beziehung gefahren wurde. K13 Entry-2 → Exit-5 und Entry-3 → Exit-5 (jeweils links) bleiben ausdrücklich deaktiviert und verwenden Standardhinweise. [Technischer Bericht](review-batch-02-ba09-technical.md).

Münchenweiter vorläufiger Suchumfang: 495 OSM-Kandidatenpunkte, eingefrorener Datenstand 06.11.2026. Noch keine bereinigte Zahl eigenständiger Kreuzungskomplexe: getrennte Fahrbahnen können mehrere Punkte liefern; ungeeignete Fälle passieren teils den Filter, andere geeignete Fälle fehlen. Eine belastbare Gesamtzahl der Münchner Kreuzungen im fachlichen Scope ist noch nicht bestimmt.

Frühere Ausschlussfälle: Am Knie, Gabelsberger/Oskar-von-Miller-Ring, Kreiller/Else-Rosenfeld, Quidde/Nawiasky. Diese sind konservativ ausgeschlossen; allein K09 ist ausdrücklich dauerhaft geschlossen.

BA09: K11–K17 sind bestätigt, live und praxiserprobt. K18/K19/K21 sind geometrisch bestätigt und K20/K22 dauerhaft ausgeschlossen. [Bildrunde](review-batch-03-ba09-remaining-images/index.html).

[Alle Prüfbilder](kreuzungspruefung/index.html)

09.11.2026: K19 v2 technisch geprüft und sechs von acht Links-/Geradeausbeziehungen für Backend 2.4.7 im Branch aktiviert; vier Rechtskontrollen bestanden. Entry-1 nach Exit-3 und nach Exit-4 bleiben gesperrt (Testwege queren die Fläche nicht). Branchkatalog v6: 18 aktive Kreuzungen, 150 Beziehungen. Noch nicht deployed; K20/K22 bleiben dauerhaft ausgeschlossen. K18/K21 technisch weiterhin offen. Commit/Push durch Thomas.
