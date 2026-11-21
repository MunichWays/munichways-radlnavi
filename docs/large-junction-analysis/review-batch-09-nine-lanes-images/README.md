# K47–K50: Neun ausgehende Fahrspuren

Stand 20.11.2026: K47 von Thomas dauerhaft ausgeschlossen. K48–K50 geometrisch freigegeben und technisch geprüft: jeweils acht geeignete Beziehungen. K48 Entry-1/Exit-2 bleiben physisch erhalten und verwenden normale Ansagen. K50 Entry-1/Entry-2 nach Exit-4 bleiben wegen Mehrdeutigkeit zum benachbarten Exit-5 ohne Makro. Alle 47 echten Routen einschließlich acht K48-Normalkontrollen und zwei K50-Ausschlusskontrollen bestehen; zusätzlich 24 Fußkontrollen. Nur Vorschlag, keine Aktivierung, kein Deployment. [Technischer Bericht](../review-batch-09-nine-lanes-technical.md).

[Bildprüfung öffnen](index.html). Vier offene Inventarkandidaten, OSM-Abzug vom 18.11.2026. Noch keine Geometriefreigabe, technische Fahrbeziehungsprüfung oder Aktivierung.

- K47: Am Hüllgraben / An der Point / Olof-Palme-Straße / Paul-Henri-Spaak-Straße. Vier Arme, im Nordosten zwei parallele Zweirichtungswege.
- K48: Effnerplatz. Vier Straßenarme und ein zusätzlicher Zweirichtungsweg nach Osten. Prüffrage: Entry-1 / Exit-2 mit einbeziehen?
- K49: Frankfurter Ring / Föhringer Ring / Ungererstraße. Östlicher Zweirichtungsweg; Autobahnzufahrt ist kein Radverkehrsarm.
- K50 v2: Lerchenauer Straße / Moosacher Straße. Südwestlicher Seitenweg außerhalb der Fläche, westlicher Zweirichtungsweg enthalten.

Bitte Fläche, Wartebereiche und Entry-/Exit-Punkte prüfen; einzelne Routen müssen für diese Geometrieprüfung nicht verfolgt werden. Nummerierung im Uhrzeigersinn, gemeinsame Punkte mit Stern markiert.

Offline reproduzieren: `python docs/large-junction-analysis/prepare_nine_lane_review.py`. Der eingefrorene OSM-Abzug bleibt unverändert. Neue Daten nur explizit mit `--collect` abrufen.

21.11.2026: K48-K50 auf ausdruecklichen Wunsch im Branch aktiviert (24 Beziehungen, Backend 2.4.18). Noch nicht deployed; K47 und alle beschriebenen Ausnahmen bleiben ausgeschlossen.
