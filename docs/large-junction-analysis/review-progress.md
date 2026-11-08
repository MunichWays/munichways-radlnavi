# Stand der Kreuzungsprüfung

Stand: 08.11.2026. Gezählt werden eindeutig benannte Standorte aus Prüfrunden und Backendkatalog; Kandidatenpunkte sind keine weiteren geprüften Fälle.

| Kategorie | Anzahl |
| --- | --- |
| Geometrisch bestätigt, aktuelle Prüffassung einschließlich Piloten | 17 |
| Kreuzungen im Backendkatalog des Branches | 17 |
| Neue Kreuzungen für nächstes Deployment freigegeben | 7 |
| Ausgeschlossen | 5 |
| Zurückgestellt | 1 |
| Insgesamt klassifizierte Standorte | 23 |

K01–K17: 15 bestätigt, einschließlich der nach Praxistest freigegebenen K05-v3-Fläche. K07 bleibt zurückgestellt, K09 dauerhaft ausgeschlossen.
Zusätzlich: zwei aktive Piloten (Arnulf/Steubenplatz und Balan/Chiemgau) sowie vier frühere technische Ausschlussfälle.

Live-Backend 2.4.5, Commit 32df25b, Katalog v4: 74 Links-/Geradeausbeziehungen; K05 mit sechs und K06 mit vier Beziehungen, die anderen acht aktiven Kreuzungen mit je acht. Quelle: Serverversion und Katalog des exakten Produktionscommits; Abgleichzeit in der Prüfungsübersicht. Alle 120 Live-Testfälle bestanden, einschließlich ausgeschlossener und rechter Fahrbeziehungen; Routenantworten bleiben unverändert. [Live-Belege](review-batch-01-live-check.json).

Für Backend 2.4.6 freigegeben und im Branch aktiviert: K11–K17 mit 70 von 72 Links-/Geradeausbeziehungen, 36 Rechtskontrollen ohne Makro. K11, K12, K14, K15, K16 und K17 v6 vollständig; K13 16/18. K13 Entry-2 → Exit-5 und Entry-3 → Exit-5 (jeweils links) bleiben ausdrücklich deaktiviert und verwenden Standardhinweise; die Testwege durchqueren die Fläche nicht. Ansagerichtung anhand geprüfter Armreihenfolge, unveränderte lokale Richtungs- und Korridorprüfung; eng begrenzte Toleranz für terminale Zielmarker. Der vorbereitete Katalog v5 enthält 17 Kreuzungen und 144 aktive Beziehungen. Build/Deployment startet Thomas selbst; Live-Stand danach erneut abgleichen. [Technischer Bericht](review-batch-02-ba09-technical.md).

Frühere Ausschlussfälle: Am Knie, Gabelsberger/Oskar-von-Miller-Ring, Kreiller/Else-Rosenfeld, Quidde/Nawiasky. Diese sind konservativ ausgeschlossen; allein K09 ist ausdrücklich dauerhaft geschlossen.

BA09: Die sieben Standorte der aktuellen Runde sind geometrisch bestätigt. Romanplatz und weitere komplexe Restkandidaten sind noch keine abschließend geprüften Fälle und nicht in obiger Summe enthalten.

[Alle Prüfbilder](kreuzungspruefung/index.html)
