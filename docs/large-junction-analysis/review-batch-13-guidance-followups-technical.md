# P2 Maximilianstraße, P7 Königsplatz und K06 Lachnerstraße

Prüfnummern ab 101 dienen nur diesem Bericht; die Projekte behalten ihre bisherigen P-Nummern.
Unveränderte freigegebene Geometrien, aktuelle echte Standardrouten, gerichtete OSM-Korridore und Produktionsprüfung.
Keine Aktivierung und kein Deployment. Neue Ergebnisse ersetzen keine Live-Verifikation.

| Projekt / Kreuzung | Links / geradeaus bestanden | Rechtskontrollen bestanden |
| --- | --- | --- |
| area-603b6d7ec04db77e · 1455393266 / Maximilianstraße | 8/8 | 3/4 |
| area-8c7276beba7eaf73 · Arcisstraße / Brienner Straße / Katharina-von-Bora-Straße / Königsplatz | 16/18 | 8/8 |
| munich · Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | 8/8 | 4/4 |

## Ausgenommene oder nicht nachgewiesene Beziehungen

- 1455393266 / Maximilianstraße · Entry-4 → Exit-4: ValueError: Route does not cross polygon exactly once
- 1455393266 / Maximilianstraße · Entry-1 → Exit-1: Human-reviewed connection uses ordinary guidance only. 45m: No unambiguous 45m legal gate continuation; 35m: No unambiguous 45m legal gate continuation; 25m: No unambiguous 45m legal gate continuation; 15m: No unambiguous 45m legal gate continuation; 12m: No unambiguous 45m legal gate continuation
- 1455393266 / Maximilianstraße · Entry-2 → Exit-1: Human-reviewed connection uses ordinary guidance only. 45m: No unambiguous 45m legal gate continuation; 35m: No unambiguous 45m legal gate continuation; 25m: No unambiguous 45m legal gate continuation; 15m: No unambiguous 45m legal gate continuation; 12m: No unambiguous 45m legal gate continuation
- 1455393266 / Maximilianstraße · Entry-3 → Exit-1: Human-reviewed connection uses ordinary guidance only. 45m: No unambiguous 45m legal gate continuation; 35m: No unambiguous 45m legal gate continuation; 25m: No unambiguous 45m legal gate continuation; 15m: No unambiguous 45m legal gate continuation; 12m: No unambiguous 45m legal gate continuation
- 1455393266 / Maximilianstraße · Entry-4 → Exit-1: Human-reviewed connection uses ordinary guidance only. 45m: No unambiguous 45m legal gate continuation; 35m: No unambiguous 45m legal gate continuation; 25m: No unambiguous 45m legal gate continuation; 15m: No unambiguous 45m legal gate continuation; 12m: No unambiguous 45m legal gate continuation
- Arcisstraße / Brienner Straße / Katharina-von-Bora-Straße / Königsplatz · Entry-1 → Exit-3: Standardrouting führt über den ausdrücklich gleichwertigen Entry-2; diese reale Route erhält die gleiche Kreuzungsansage über dessen geprüfte Beziehung.
- Arcisstraße / Brienner Straße / Katharina-von-Bora-Straße / Königsplatz · Entry-1 → Exit-4: Standardrouting führt über den ausdrücklich gleichwertigen Entry-2; diese reale Route erhält die gleiche Kreuzungsansage über dessen geprüfte Beziehung.

## Nachweise

- Innere Straßenverbinder: exakte IDs im Supportbericht, nur erlaubte gerichtete Segmente vollständig innerhalb der freigegebenen Fläche.
- 1455393266 / Maximilianstraße: Nördlicher Nebenarm auf der Straße ist ein Sonderfall mit Standardhinweisen (Exit-1). Der parallele Isarradweg (Exit-2) erhält die normale große-Kreuzung-Ansage.
- Arcisstraße / Brienner Straße / Katharina-von-Bora-Straße / Königsplatz: Entry-1/Entry-2 und Exit-1/Exit-2 im Norden sowie Entry-4/Entry-5 und Exit-4/Exit-5 im Süden sind ausdrücklich bestätigte gleichwertige Radweg-/Straßenvarianten desselben Arms. Nicht benutzungspflichtige Radwege: dieselbe Ansage ist korrekt. Keine pauschale Ausnahme für alle secondary/tertiary-Straßen.

## K06: Ursache der fehlenden Lachnerstraßen-Ansagen

Im mit dem produktiven Backend-Commit f8add936 übereinstimmenden Katalog sind alle vier Links-/Geradeausbeziehungen von/zu Lachnerstraße deaktiviert. Aktuelle längere Alltagsrouten treffen die freigegebenen Anschlüsse, erhalten live aber keine Makrometadaten. Kurze Referenzen zwischen 12 und 45 m schnappen etwa 7,5–8,2 m auf einen parallelen Gehweg (teilweise pushing bike). Der aktuelle OSM-Weg 152093782 entspricht dem eingefrorenen Straßenverlauf. Referenzen 120 m entlang derselben legal verbundenen Lachnerstraße bestehen dagegen alle Prüfungen: 8/8 Links-/Geradeausbeziehungen, 4/4 Rechtskontrollen. Unveränderte Geometrie und unveränderte 5-m-Snappinggrenze; nur äußere Referenzpunkte geändert. Die vier zusätzlichen Beziehungen sind technisch bereit, aber noch nicht aktiviert.
