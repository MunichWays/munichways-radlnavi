# Technische Prüfung K07 / K10 / K19

**Historischer Stand der reinen Routenprüfung.** Anschließend wurde K10 v4 mit acht regulären und fünf Sonderfahrbeziehungen im Backend-Branch 2.4.8 aktiviert. Die Sonderansagen benötigen die neue App mit Protokoll v2; Deployment und Praxistest stehen noch aus. K07 v2 und K19 v3 sind inzwischen ebenfalls im Branch aktiviert (je acht Beziehungen); Deployment steht aus. Aktueller Stand: [Sonderabläufe](junction-sequences.md), [Implementierungsnachweis](review-wilram-sequences-implementation.json).

Die folgenden Abschnitte dokumentieren den vorherigen Prüfschritt.

Geometrien von Thomas am 14.11.2026 ausdrücklich freigegeben. 42 echte Standardrouten eingefroren; offline mit `python docs/large-junction-analysis/verify_review_updates.py` reproduzierbar. Runtime-Katalog, Build und Deployment bleiben unverändert.

| Kreuzung | Geometrie | Reguläre Links-/Geradeausbeziehungen | Reguläre Rechtskontrollen | Ergebnis |
| --- | --- | --- | --- | --- |
| K07 Mars-/Pappenheimstraße | v2 | 8/8 | 4/4 ohne Makro | Technisch bereit; noch nicht aktiviert |
| K10 Thomasiusplatz | v4 | 8/8 | 4/4 ohne Makro | Reguläre Beziehungen belegt; Wilram-Sonderansagen noch nicht implementiert |
| K19 Romanplatz Nord | v3 | 8/8 | 4/4 ohne Makro | Auch Entry-1 nach Exit-3/Exit-4 jetzt belegt; noch nicht aktiviert |

Der gesamte vorgeschlagene Katalog wurde gegen diese Routen geprüft. Bei allen 24 regulären positiven Beziehungen bleiben Rohroute und Schritte unverändert; Fuß-/Schiebekontrollen erzeugen keine Kreuzungsansage. Die bisherigen Runtime-Kataloge behalten ihre alten Geometrien, insbesondere K19 v2 mit sechs Beziehungen.

## K10: Wilram gesondert behandeln

Fünf zusätzliche Sonderabläufe sind geometrisch und auf gerichteten legalen OSM-Wegen belegt. Die folgenden Aussagen sind **keine Ansagen-/Aktivierungsfreigabe**:

- Entry-3 / Entry-4 nach Exit-5 (Wilram): Die berechneten Routen enthalten den Rechtsknick bei [48.115690, 11.602406] und den Linksknick in Wilramstraße bei [48.115448, 11.602413]. Diese Stellen sind innerhalb der neuen Fläche und würden heute stumm geschaltet.
- Die frühere alternative Linksquerung ist damit noch nicht als tatsächlich gefahrene Variante/GPS-Auswahl bestätigt. Die Entscheidung zwischen internem rechts/geradeaus muss eigens abgesichert werden.
- Entry-5 (Wilram) nach Exit-1, Exit-4 und Exit-3: Die vorgeschaltete Rechtskurve und der anschließende Verlauf sind geometrisch belegt. Zusammengesetzte Ansagen und Wenden sind im aktuellen Makro-Schema noch nicht implementiert.
- Entry-5 nach Exit-2 ist die sechste zusätzliche Kontrolle: Die echte Standardroute fährt auf der bewusst ausgeschlossenen Querstraße Thomasiusplatz (Weg 145178206) vollständig außerhalb der Fläche. Sie bleibt normales Rechtsabbiegen ohne Makro.

Details: [42 Routen und Einzelergebnisse](review-updates-2026-11-14-routes.json), [sechs gewünschte Wilram-Abläufe](review-k10-wilram-plan.json). Ein gesonderter Vorschlagskatalog enthält nur die 24 technisch belegten regulären Beziehungen dieser drei Kreuzungen, keine unfertigen Wilram-Sonderansagen. Er wird nicht automatisch in den Runtime-Katalog übernommen.
