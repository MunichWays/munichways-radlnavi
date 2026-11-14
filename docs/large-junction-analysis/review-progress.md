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

14.11.2026: K19 v3 als Entwurf nach Norden erweitert, legale interne Fahrbahnkurve aufgenommen. Offline 8/8 Links-/Geradeausbeziehungen und 4/4 Rechtskontrollen bestanden; exakte v2-Freigabe archiviert, Runtime weiter v2 mit sechs aktiven Beziehungen. K18: Wiedervorlage frühestens Montag, 16.11.2026, erneute OSM-Abfrage vor Wiederherstellung Entry-2; v3 unverändert. K10 v3: Wilram-Anschluss als Entwurf mit Entry-5/Exit-5 vorbereitet; sechs Sonderabläufe in review-k10-wilram-plan.json festgehalten. Interne Hier-Hinweise, alternative Querung und Wende benötigen neue Backend-/App-Unterstützung; nicht aktiviert.

14.11.2026: K10 v4: Exit-2 auf Weg 71390770 um 14,4 m nach Westen versetzt, 5 m vor Knoten 506771454. Östliche Flächenkante eingerückt; komplette Querstraße Thomasiusplatz (145178206) außerhalb. Alle anderen Gates aus v3 unverändert; Runtime weiterhin v2.

14.11.2026: K07 v2 neu gezeichnet, ausschließlich K07 mit frischem offiziellen OSM-Ausschnitt. Wredestraßen-Korrektur cycleway:right=lane nachgewiesen. Vier neue Fahrstreifen-Gates ergänzt: Mars Entry-1/Exit-2, Pappenheim Entry-4, Wrede Exit-3. Separate Gegenrichtungsradwege erhalten. Fläche und vier bisherige Gatepositionen unverändert; explizite Umnummerierung für vollständige Uhrzeigerfolge. Fahrstreifen-Gates als OSM-Fahrbahnachsenpunkte gekennzeichnet, keine erfundene seitliche Streifenlage. Sichtfreigabe/technische Fahrbeziehungen offen; nicht aktiviert.

14.11.2026: Thomas hat K07 v2, K10 v4 und K19 v3 ausdrücklich freigegeben; Geometrie-Fingerabdrücke gepinnt. Technische Prüfung: je 8/8 reguläre Links-/Geradeausbeziehungen und 4/4 Rechtskontrollen bestanden. Fünf zusätzliche Wilram-Sonderfolgen geometrisch belegt, aber Ansagen-/Checkpoint-Logik inkl. alternativer Querung nicht implementiert. Wilram nach Exit-2 ist eine legale Standardroute außerhalb der Kreuzungsfläche. 42 echte Standardrouten eingefroren und offline reproduzierbar; Gesamtvorschlag mit Fuß-/Rechtskontrollen geprüft. Keine Runtime-Änderung oder Deployment. Übersicht: 28 gesamt, 21 geometrisch bestätigt, 0 offen, 7 ausgeschlossen; technische/Implementierungsstände bleiben separat.

14.11.2026: Wilram-Sonderabläufe als wiederverwendbare Backend-/App-Erweiterung implementiert. Backend 2.4.8, Katalog v7: K10 v4 im Branch mit 8 regulären + 5 Sonderbeziehungen, insgesamt 155 Beziehungen/18 Kreuzungen. K07 und K19 bleiben am bisherigen Aktivierungsstand (K07 noch inaktiv, K19 v2 mit sechs Beziehungen); ihre neuen Vorschläge sind technisch bereit. Sequenzen werden nur an Apps mit Header X-Junction-Guidance-Version: 2 ausgegeben. Legacy-Clients behalten Standardhinweise für die fünf Wilram-Fälle. Checkpoints sind routenverankert, richtungs-/genauigkeitsbestätigt und einmalig; Entry-4 kann am ersten Punkt zwischen rechts/geradeaus unterscheiden. Alternative Querung synthetisch GPS-geprüft, Praxistest ausstehend. Kein Commit/Push oder Deployment.


### Aktivierung K07 / K19 am 14.11.2026
K07 v2 (acht Beziehungen) und K19 v3 (acht statt sechs Beziehungen) sind zusammen mit K10 v4 im Runtime-Katalog v8, Backend 2.4.8, aktiviert: 19 Kreuzungen, 165 aktive Beziehungen. Die beiden K13-Sperren bleiben unverändert. Deployment erfolgt durch Thomas; die Live-Momentaufnahme bleibt bis zur Serverprüfung unverändert. K18 wartet weiterhin bis Montag, 16.11.2026, auf die erneute OSM-Prüfung.


### Buildkorrektur 2.4.9: fehlendes Sequenzmodul
Live-Abgleich: Backend 2.4.8 / c5a1a9c lief tatsächlich; bei allen zwölf K19-Referenzrouten fehlten Kreuzungsmetadaten. Ursache war `junction_sequences.py`, das die explizite COPY-Liste im Produktions-Dockerfile nicht enthielt. Die Katalogprüfung schlug deshalb für alle Kreuzungen fehl. Die Datei wird jetzt kopiert und der tatsächlich paketierte Katalog bereits im Docker-Build validiert. Ein isolierter Paketierungstest reproduziert den Importfehler vor der Korrektur und prüft danach K07, K19 sowie eine Wilram-Sonderfolge mit unveränderter Rohroute. Katalog v8 / 165 Beziehungen bleiben unverändert. Backend 2.4.9 benötigt ein erneutes Deployment und anschließenden Live-Abgleich.


### K21 v2 technisch geprüft
18 echte Standardrouten neu eingefroren: 12/12 Links-/Geradeausbeziehungen und 6/6 Rechtskontrollen bestanden. Ganzer Vorschlagskatalog, unveränderte Rohroute und Schiebekontrollen geprüft. Ergebnis in review-batch-03-ba09-routes.json; separater review-k21-proposed-catalog.json. Runtime-Katalog unverändert, K21 weiterhin nicht aktiviert oder deployed.


### K21 v2 aktiviert, zwei Makros ausdrücklich ausgeschlossen
Auf Wunsch von Thomas zehn Beziehungen aktiviert. Entry-4 nach Exit-2 und Entry-3 nach Exit-2 bleiben mit Begründung gesperrt: Die Makroansage unterscheidet Exit-2 nicht eindeutig von Exit-3. Normale Abbiegehinweise bleiben erhalten; beide Beziehungen zu Exit-3 bleiben aktiviert. Alle 18 Referenzrouten inklusive sechs Rechtskontrollen offline geprüft. Backend 2.4.10, Katalog v9: 20 Kreuzungen / 175 aktive Beziehungen. Noch nicht deployed.
