# K42–K46 · Zentrale Kreuzungen

[Galerie](index.html) · [Kontaktübersicht](overview.png) · [Gesamtübersicht](../kreuzungspruefung/index.html)

OSM-Daten vom 17.11.2026 sind in `../review-batch-08-central-osm.json.gz` eingefroren.
Die Auswahl folgt Thomas' fünf Favoriten; die bisherigen Freigaben bleiben unverändert.

| Fall | Kreuzung | Stand |
| --- | --- | --- |
| K42 v1 | Anzinger Straße / Aschheimer Straße / Bad-Schachener-Straße / Melusinenstraße | Acht Radwegpunkte |
| K43 v1 | Chiemgaustraße / Schwanseestraße | Acht Radwegpunkte |
| K44 v2 | Marsstraße / Seidlstraße | Radfahrstreifen einbezogen, acht Punkte; Denisstraße außerhalb |
| K45 v2 | Stiglmaierplatz | Acht Punkte, Brienner Straße ausgehend auf Radfahrstreifen; Schleißheimer Einmündung außerhalb |
| K46 v2 | Orleansstraße / Rosenheimer Straße | Neun Punkte, davon gemeinsame Fahrbahnpunkte im Nordwesten/Südwesten; zwei südöstliche Zufahrten |

Bitte Fläche, richtige Wegseite, Richtung und Vollständigkeit der Punkte prüfen.
Fahrbahnpunkte liegen auf der OSM-Mittellinie; seitliche Radfahrstreifenpositionen sind nicht vermessen.
Die Nummerierung läuft im Uhrzeigersinn; Entry und Exit gleicher Nummer sind kein Fahrbeziehungspaar.
Die automatisch erzeugten ersten Entwürfe K44–K46 wurden vor der Sichtvorlage korrigiert.

Offline reproduzieren:

```text
python docs/large-junction-analysis/prepare_central_review.py
powershell -NoProfile -ExecutionPolicy Bypass -File docs/large-junction-analysis/render_review_images.ps1 -BatchDirectory review-batch-08-central-images
```

Thomas hat K42 v1, K43 v1 sowie K44/K45/K46 v2 am 17.11.2026 geometrisch freigegeben.
K46 Entry-1 ist eine reine Rechtszufahrt nach Exit-1; links nach Exit-3 und geradeaus
nach Exit-4 bleiben ausdrücklich ausgeschlossen.

Die technische Prüfung besteht für K42/K43/K45 mit je 8/8 und K44 mit 7/8
Links-/Geradeausbeziehungen. K46 besteht mit 7/8 der verbleibenden zulässigen
Beziehungen; Entry-3 nach Exit-4 bleibt ohne Makro, weil die Standardroute
den Gehweg 1017221653 ohne belegte Fahrradfreigabe nutzt. K44 Entry-3 → Exit-1 bleibt ohne Kreuzungsansage:
Die echte Standardroute fährt über Lämmerstraße/Hirtenstraße und quert die
Fläche mehrfach. Normale Hinweise bleiben. Keine dauerhafte Schließung beschlossen.
Auf diesem Umweg sind die zwei tatsächlich gefahrenen Geradeausquerungen weiterhin
korrekt als separate große Kreuzungen erkennbar; es kommt keine Links-Makroansage.

K44 Entry-3 → Exit-1: Thomas hat die OSM-Linksabbiegebeschränkung um `except=bicycle`
ergänzt. Wiedervorlage ab **23.11.2026**: OSM-Relation und Routing-Datenimport
prüfen, dann dieselbe reale Standardroute erneut testen. Bis dahin deaktiviert.

38 positive Routen, 21 Rechts- und 38 Fußverkehrskontrollen im Gesamtkatalog
bestanden; eingefrorene Routen sind offline reproduzierbar mit:

```text
python docs/large-junction-analysis/verify_central_movements.py
```

Backend 2.4.17 / Katalog v17: 38 neue Beziehungen im Branch aktiviert.
Insgesamt 39 Kreuzungen / 319 Beziehungen. Am 18.11.2026 als live bestätigt: Backend 2.4.17 / Commit 72957c6,
61 echte Live-Routen bestanden. Wiedervorlagen und reine Rechtszufahrt bleiben ausgeschlossen.

17.11.2026: K46 Entry-3 → Exit-4 ebenfalls zur Wiedervorlage ab **23.11.2026**. Thomas hat die Linksabbiegebeschränkung in OSM um `except=bicycle` ergänzt. OSM-Relation, Routing-Datenimport und dieselbe Standardroute erneut prüfen; die bisherige Gehweg-Diagnose bezieht sich auf den alten Routingstand. Bei bestandenem Nachweis ist die normale Ansage „An der großen Kreuzung links abbiegen“ vorgesehen. Bis dahin deaktiviert. Entry-1 bleibt unabhängig davon eine reine Rechtszufahrt.
