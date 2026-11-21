# Stand der Kreuzungsprüfung

21.11.2026: Auf ausdruecklichen Wunsch K48-K50 im Branch aktiviert: 24 neue, insgesamt 343 aktive Fahrbeziehungen an 42 Kreuzungen. Backend 2.4.18, Katalog munich-big-junctions-v18. K47 dauerhaft ausgeschlossen; K48 Entry-1/Exit-2 und die beiden K50-Exit-4-Beziehungen bleiben ohne Makro. Noch kein Push und kein Deployment; letzter verifizierter Live-Stand unveraendert Backend 2.4.17 mit 39 Kreuzungen / 319 Beziehungen.

20.11.2026: K47 dauerhaft ausgeschlossen; K48-K50 im neuen Kartenwerkzeug von Thomas bestaetigt. Technische Pruefung abgeschlossen: je 8 geeignete Links-/Geradeausbeziehungen, zusammen 24. K48 Entry-1/Exit-2 nur normale Hinweise (8 reale Negativkontrollen). K50 Entry-1/Entry-2 nach Exit-4 bewusst ohne Makro wegen mehrdeutiger Auswahl gegenueber Exit-5; beide realen Kontrollrouten ohne Makro. 13 Rechts- und 24 Fusskontrollen bestanden. Nur Vorschlag, keine Aktivierung, kein Deployment. Aktuelle Fallzahlen: 98 gesamt, 42 bestaetigt, 41 offen, 15 ausgeschlossen/zurueckgestellt. Live unveraendert 39/319. [Pruefbericht](review-batch-09-nine-lanes-technical.md).

Stand: 18.11.2026. Maßgeblich sind die [Prüfungsübersicht](kreuzungspruefung/index.html) und der verifizierte Produktionsstand.

| Kategorie | Anzahl |
| --- | --- |
| Erfasste Standorte | 98 |
| Geometrisch bestätigt | 42 |
| Offen | 41 |
| Ausgeschlossen / zurückgestellt | 15 |
| Aktive Kreuzungen live | 39 |
| Aktive Fahrbeziehungen live | 319 |

Backend **2.4.17**, Commit `72957c626d0f6673870bfe75d3beaffd754a3b9a`, Katalog **munich-big-junctions-v17** ist am 18.11.2026 als live bestätigt. [Backend-Workflow 44183789239](https://github.com/MunichWays/munichways-radlnavi/actions/runs/44183789239) erfolgreich. 61 reale Live-Routen entsprechen exakt dem lokalen Katalog; normale Routendaten unverändert. [Live-Belege](review-release-2.4.17-central-live-checks.json). K42–K46 mit 38 neuen Beziehungen live; die vier Ausnahmen bleiben deaktiviert. Die beiden Wiedervorlagen K44 Entry-3 → Exit-1 und K46 Entry-3 → Exit-4 sind in der Übersicht gelb und zusätzlich oben in Offen markiert, ab 23.11.2026. Kein neuer Praxistest behauptet.

Neue Bildrunde K47-K50: die vier noch offenen Kandidaten mit neun ausgehenden Kfz-Fahrspuren. OSM vom 18.11.2026 eingefroren, Bilder kontrolliert, 74 Review-Tests bestanden. K48: zusaetzlicher oestlicher Zweirichtungsweg zur Sichtentscheidung markiert. K50 v2: suedwestlichen Seitenweg aus der Hauptflaeche ausgegrenzt. Keine Geometriefreigabe, technische Fahrbeziehungspruefung oder Aktivierung. Noch 41 offene Inventarkandidaten ohne Geometrie. [Bildrunde](review-batch-09-nine-lanes-images/index.html).

Frauenstraße / Isartorplatz am 17.11.2026 auf Wunsch von Thomas ungeprüft als Sonderfall zurückgestellt. Keine Geometrie oder technische Prüfung, keine Aktivierung; normale Ansagen bleiben. Keine dauerhafte Schließung beschlossen.

Neue Bildrunde K42–K46: Anzinger/Aschheimer, Chiemgau/Schwansee, Mars/Seidl, Stiglmaierplatz sowie Orleans/Rosenheimer. OSM vom 17.11.2026 eingefroren, fünf Flächen mit vier logischen Armen vorbereitet; Radfahrstreifen und gemeinsame Fahrbahnpunkte ausgewiesen. 41 weitere offene Fälle bleiben ohne Geometrie. K42–K46 von Thomas freigegeben. K46 Entry-1 ausschließlich rechts; links nach Exit-3 und geradeaus nach Exit-4 ausdrücklich ausgeschlossen. K42/K43/K45 jeweils 8/8, K44 und K46 jeweils 7/8 zulässige Links-/Geradeausbeziehungen technisch bestanden. K46 Entry-3 → Exit-4 ohne Makro: Standardroute nutzt Gehweg 1017221653 ohne belegte Fahrradfreigabe. K43 verwendet 25m/15m lange Referenzansätze auf denselben Radwegen gegen falsches Snapping. K44 Entry-3 → Exit-1 bleibt ohne Links-Makro: Standardroute über Lämmerstraße/Hirtenstraße mit mehrfacher Flächenquerung. K44 Entry-3 → Exit-1: Thomas hat die Linksabbiegebeschränkung in OSM um except=bicycle ergänzt; Wiedervorlage frühestens ab 23.11.2026 (OSM-Relation und Routing-Datenimport prüfen). Bis dahin kein Links-Makro. 38 positive Routen, 21 Rechts- und 38 Fußkontrollen bestanden, offline reproduziert. Noch keine Aktivierung, Runtime unverändert. [Bildrunde](review-batch-08-central-images/index.html).

Historischer Live-Nachweis vom 16.11.2026: Backend **2.4.16**, Commit `2916970044ff07df03edb21694b71ea641aae565`, Katalog **munich-big-junctions-v16** ist nachgewiesen live. [Backend-Workflow 43912335393](https://github.com/MunichWays/munichways-radlnavi/actions/runs/43912335393) erfolgreich, einschließlich Direct und Entdeckertour.

K18 v5 (8 Beziehungen), K34 (8), K35 West (5), K36 (8), K37 Ost (5), K38 (8), K40 (8), K41 (6) sind jetzt live. K39 dauerhaft ausgeschlossen; die beiden K18-Entry-3- und K41-Entry-1-Ausnahmen sowie K13/K21 bleiben deaktiviert. Standardhinweise bleiben für diese Beziehungen erhalten. Entry-5 bei K18 ist ausgeschlossen, Exit-4 erhalten.

91 Live-Referenzrouten des neuen Rollouts bestanden, einschließlich kombinierter K35/K37-Routen und unveränderter Standardrouten. Zusätzlich 45 bisherige Live-/Legacy-Kontrollen bestanden. [Rollout-Belege](review-release-2.4.16-rollout-live-checks.json) · [Bisherige Kontrollen](review-release-2.4.16-live-checks.json). 173 Backend-Tests, 69 Review-Tests und sieben Frontend-Routingtests bestanden. Dies ersetzt keine Praxistest-Freigabe.

41 weitere Kandidaten stehen als reine Texteinträge ohne Geometrie/Bildlink offen. Die 145 uneindeutigen Kontaktgruppen bleiben im Rohinventar und sind keine bestätigten Vierarmknoten. [Priorität nach Fahrspuren](outgoing-lanes-munich.html).

## Historischer Stand und Arbeitsverlauf vor dem Release 2.4.16

Die nachfolgenden Zwischenstände sind historisch; aktuelle Zahlen stehen oben.

Backend **2.4.15**, Commit `701896122a18dcf2cbf279adf0a581bf8bab859a`, Katalog `munich-big-junctions-v13` ist nachgewiesen live. Der Backend-Workflow 43758056013 ist erfolgreich abgeschlossen, einschließlich Direct und Entdeckertour. K24 (15 Beziehungen), K30 (3) und K33 (8) sind jetzt live.

45 Live-Prüfungen für K24/K30/K33 bestanden, einschließlich Rechtskontrollen, ausgeschlossener Beziehungen und Legacy-Rückfall. Die optionalen Kreuzungsdaten ändern die normale Live-Route nicht. [Live-Belege](review-release-2.4.15-live-checks.json). 168 Backend-Tests und 57 Review-Prüfungen bestanden. Das ersetzt keine Praxistest-Freigabe der neuen Kreuzungen.

K30 Entry-4 nach Exit-3 bleibt ausdrücklich ohne Kreuzungsansage. K31 und K32 sind dauerhaft ausgeschlossen; die bestehenden Ausschlüsse K13/K21 bleiben erhalten. Einzelne ausgesparte Fahrbeziehungen verwenden weiterhin Standardhinweise.

K34 v1, K35 v3 (West), K36 v1 und K37 v2 (Ost) sind technisch geprüft und im lokalen Branch für Backend **2.4.16**, Katalog **v14**, aktiviert: **30 Kreuzungen / 251 Beziehungen**. Noch kein Commit und kein Deployment. Neue Beziehungen: 8 + 5 + 8 + 5 = 26. Alle 38 einzelnen Standardrouten, 26 Fußkontrollen und zwei durchgehende Routen durch beide Teilkreuzungen bestanden; normale Routendaten bleiben unverändert. [Technischer Bericht](review-batch-06-primary-technical.md). Der nachgewiesene Live-Stand bleibt 2.4.15 / 26 Kreuzungen / 225 Beziehungen.

Primary/Secondary-Prioritätsliste: Alle 55 bisher nicht zugeordneten Vierarm-Kandidaten sind offen erfasst, ohne bestehende Freigaben oder Ausschlüsse zu ändern. K38–K41 haben ungeprüfte Flächen/Bilder (12, 11, 10, 10 ausgehende Kfz-Spuren). Die übrigen 51 Einträge sind reine Texte ohne Geometrie oder Bildlink. 13 der 55 Kandidaten fehlen noch vollständige Richtungs-Spurzahlen. Die 145 weiteren uneindeutigen Kontaktgruppen bleiben im Rohinventar und sind keine als Vierarmknoten identifizierten Kreuzungen. [Neue Bildrunde](review-batch-07-lanes-images/index.html). Aktueller Aktivierungsstand siehe nachfolgend.

K38 v2, K40 v1 und K41 v2 von Thomas geometrisch freigegeben. K39 v1 dauerhaft ausgeschlossen: komplexe Wegebeziehungen und Zweirichtungsradwege, 2026 im Umbau. Technische Pruefung: K38 und K40 jeweils 8/8 Links-/Geradeausbeziehungen bestanden; K41 6/8. Entry-1 nach Exit-3/Exit-4 sind von Thomas dauerhaft ausgeschlossen: class:bicycle=-3 (Unter allen Umstaenden vermeiden) auf der Zufahrt. Das Routing weicht auf andere Anschluesse aus; normale Ansagen bleiben. Anschliessend von Thomas ausdruecklich aktiviert: K38 acht, K40 acht, K41 sechs Beziehungen. Lokaler Branch fuer Backend 2.4.16, Katalog v15: 33 aktive Kreuzungen / 273 Beziehungen. K39 und beide K41-Ausschluesse unveraendert. Noch kein Commit/Deployment.

K18 am 16.11.2026 erneut aus OSM geladen: v4-Entwurf stellt Guntherstrassen-Entry-2 auf Weg 1391209196 wieder her (bicycle=designated, cycleway:oneway=yes). Kein neuer Exit; Flaeche und alle bisherigen Gates unveraendert. v3-Freigabe archiviert, v4 zur Sichtpruefung offen und nicht aktiviert. Andere Kreuzungen unveraendert.

K18 anschliessend als v5 von Thomas bestaetigt: Entry-5 entfernt (nur rechts), Exit-4 bleibt. Entry-2/Entry-3 sind derselbe logische Suedarm mit geradeaus zu Exit-1 und links zu Exit-4. Technisch 8/10 Links-/Geradeausbeziehungen und 5/5 Rechtskontrollen bestanden. Die beiden Entry-3-Referenzen kehren ausserhalb der Flaeche um und queren ueber Entry-2, auch bei naeherem Start und angefragter Nordrichtung. Sie bleiben im Vorschlag einzeln unbestaetigt; normale Ansagen bleiben. Kein Runtime-Katalog geaendert. [Technischer Bericht](review-k18-technical.md).

## Historischer Verlauf vor diesem Release

Die folgenden Einträge dokumentieren frühere Zwischenstände; aktuelle Zahlen und Deployment-Nachweise stehen oben.

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


### BA01 Altstadt-Radlring, 15.11.2026

Thomas hat K23 v1, K25 v1 und K28 v1 als Standard freigegeben und die Aktivierung nach technischer Prüfung autorisiert. Alle 24 Links-/Geradeausbeziehungen, zwölf Rechtskontrollen und 24 Fußkontrollen im Gesamtkatalog bestanden; 36 reale Standardrouten eingefroren und offline reproduziert. Backend 2.4.11 / Katalog v10: 23 aktive Kreuzungen, 199 aktive Fahrbeziehungen. Alle bisherigen 20 Katalogeinträge unverändert, einschließlich K13-/K21-Sperren. K24 bleibt offen; K26/K27 dauerhaft ausgeschlossen, K29 dauerhaft zurückgestellt bis zu konkreten Praxisproblemen. Geprüfte Gesamtfälle: 35, davon 24 geometrisch bestätigt, ein Fall offen, zehn ausgeschlossen/zurückgestellt. Neue Beziehungen im Branch aktiviert, noch nicht deployed; Backend-Workflow startet Thomas.

17.11.2026: K46 Entry-3 → Exit-4 ebenfalls zur Wiedervorlage ab **23.11.2026**. Thomas hat die Linksabbiegebeschränkung in OSM um `except=bicycle` ergänzt. OSM-Relation, Routing-Datenimport und dieselbe Standardroute erneut prüfen; die bisherige Gehweg-Diagnose bezieht sich auf den alten Routingstand. Bei bestandenem Nachweis ist die normale Ansage „An der großen Kreuzung links abbiegen“ vorgesehen. Bis dahin deaktiviert. Entry-1 bleibt unabhängig davon eine reine Rechtszufahrt.

17.11.2026: Backend 2.4.17 / Katalog v17 für Deployment vorbereitet: K42–K46 mit 38 neuen Beziehungen im Branch aktiviert, insgesamt 39 Kreuzungen / 319 Beziehungen. K44 Entry-3 → Exit-1 und K46 Entry-3 → Exit-4 bleiben bis zur Wiedervorlage ab 23.11.2026 deaktiviert; K46 Entry-1 links/geradeaus bleibt ausgeschlossen. Alle bisherigen Katalogeinträge unverändert. Live-Stand weiterhin 2.4.16 bis zum verifizierten Deployment.
