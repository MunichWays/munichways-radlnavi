# Technische Prüfung aus der Kreuzungsapp

Prüfnummern ab 900 dienen nur diesem Bericht; die Projekte behalten ihre bisherigen P-Nummern.
Unveränderte freigegebene Geometrien, aktuelle echte Standardrouten, gerichtete OSM-Korridore und Produktionsprüfung.
Keine Aktivierung und kein Deployment. Neue Ergebnisse ersetzen keine Live-Verifikation.

| Projekt / Kreuzung | Links / geradeaus bestanden | Rechtskontrollen bestanden |
| --- | --- | --- |
| area-f5bdef90f8af4365 · Elsenheimerstraße / Hansastraße / Westendstraße | 8/12 | 4/6 |

## Ausgenommene oder nicht nachgewiesene Beziehungen

- Elsenheimerstraße / Hansastraße / Westendstraße · Entry-5 → Exit-1: Standardrouting führt über den ausdrücklich gleichwertigen Entry-4; diese reale Route erhält die gleiche Kreuzungsansage über dessen geprüfte Beziehung.
- Elsenheimerstraße / Hansastraße / Westendstraße · Entry-5 → Exit-2: Standardrouting führt über den ausdrücklich gleichwertigen Entry-4; diese reale Route erhält die gleiche Kreuzungsansage über dessen geprüfte Beziehung.
- Elsenheimerstraße / Hansastraße / Westendstraße · Entry-5 → Exit-3: ValueError: Wrong entry gate
- Elsenheimerstraße / Hansastraße / Westendstraße · Entry-1 → Exit-4: ValueError: Wrong exit gate
- Elsenheimerstraße / Hansastraße / Westendstraße · Entry-2 → Exit-4: ValueError: Wrong exit gate
- Elsenheimerstraße / Hansastraße / Westendstraße · Entry-3 → Exit-4: ValueError: Wrong exit gate

## Nachweise

- Innere Straßenverbinder: exakte IDs im Supportbericht, nur erlaubte gerichtete Segmente vollständig innerhalb der freigegebenen Fläche.
- Elsenheimerstraße / Hansastraße / Westendstraße: Nicht benutzungspflichtiger Radweg neben der Fahrbahn: Radfahrende wählen frei zwischen Radweg und Straße, daher gleiche Ansage für beide Anschlüsse (Regel der Kreuzungsapp, wie Arcisstraße).
