# Stadtbezirke in RadlNavi

## Darstellung

Der zusätzliche Schalter **Stadtbezirke** unter „Mehr“ ist standardmäßig aus
und unabhängig von „Alle Details / RadVorrang-Netz“.

Der Layer zeigt dezente, gestrichelte Bezirksgrenzen ohne Flächenfüllung.
Ab Zoom 12 steht je Bezirk genau ein kurzes Label **BA01 … BA25** in seiner
Hauptfläche. Lange Namen stehen im Tooltip beim Überfahren bzw. Fokussieren
des Labels. Klick, Antippen oder Enter öffnet eine kleine Bezirksinfo mit
vollständigem Namen, Region und dem Bezirkslink zu MunichWays.

Die Grenzflächen reagieren nicht auf Maus- oder Touch-Eingaben. Dadurch bleiben
die Strecken auf der Karte per Rechtsklick bzw. langem Drücken zugänglich.
Auch BA-Labels lassen den Rechtsklick zur Karte durch. Ein neuer Streckenaufruf
schließt offene Bezirks-Popups. Die Bezirks-Popups verschieben die Karte nicht
und liegen unter dem verschiebbaren Streckendetail-Fenster.

Beim Abschalten werden Grenzen, Labels und Popups entfernt. Ladefehler bieten
„Erneut laden“. Unter Zoom 12 bleiben nur die Grenzen sichtbar, damit sich die
Nummern in der Stadtübersicht nicht häufen.

## Fest hinterlegter Datenbestand

- [Gelieferte Quelldatei auf Google Drive](https://drive.google.com/file/d/1_NjCrffI3huQyR8Rryvz5r3oiVFPRzM7/view?usp=sharing)
- Einmalig importiert am **31.10.2026**; 94.040 Bytes.
- SHA-256 der Originaldatei:
  `4d93809219a67718e3a134a4225149afe29a8041f8d61c3dbdca6cbd52f72f88`.
- Original: 27 Features vom Typ MultiPolygon für alle 25 Stadtbezirke.
  BA18 und BA19 sind auf mehrere Features verteilt.
- Fester Auslieferungsbestand:
  [`frontend/public/data/stadtbezirke.geojson`](../frontend/public/data/stadtbezirke.geojson).
  Die App lädt nur diese lokale Datei und greift nicht auf Google Drive zu.

Der Import vereinigt gleichnamige Teilflächen zu je einem MultiPolygon pro BA.
Alle Koordinaten, Ringe und ursprünglichen Attribute bleiben erhalten.
`label_coordinate` ergänzt einen Punkt innerhalb der größten Teilfläche mit
Abstand zur Grenze. Ein reiner Mittelpunkt des Begrenzungsrechtecks könnte
bei konkaven Bezirken außerhalb der Fläche liegen. Der Import prüft die
BA-Nummern, geschlossene Ringe, Koordinaten und die Lage aller 25 Labelpunkte.

Reproduzierbarer Offline-Import mit Python-Standardbibliothek:

```powershell
python tools/import_districts.py PFAD_ZUR_ORIGINALDATEI frontend/public/data/stadtbezirke.geojson
```

Die bestehenden `modal_rad_2017`-Quelldaten bleiben in der Datei erhalten.
Die kompakte Bezirksinfo verwendet Name, Bezirksnummer, Region und Links.

## Geprüft

- Alle 27 ursprünglichen Polygone sind koordinatengleich im importierten Bestand
  enthalten; alle 25 Labelpunkte liegen innerhalb ihrer jeweiligen Hauptfläche.
- 98 Frontendtests in 14 Suites, TypeScript, striktes Lint und Produktionsbuild
  erfolgreich.
- Produktionsbundle mit realen Daten auf Desktop und in mobiler Touch-Emulation:
  standardmäßig ausgeschaltet, Laden vom lokalen Pfad, 25 Labels, Tooltip,
  Enter bzw. Antippen, vollständige Bezirksinfo und funktionierender Bezirkslink.
- Strecken-Rechtsklick und Touch-Halten schließen die Bezirksinfo und öffnen
  weiter die Streckenauswahl; echter Suchworker und Detailabruf funktionieren.
- Herauszoomen auf Zoom 11 blendet Labels aus und behält alle Grenzen;
  Hineinzoomen stellt die Labels wieder her. Abschalten entfernt Grenzen,
  Labels und Popups.

Der lokale Browsertest verwendet die CSS des installierten Leaflet-Forks mit
passender Prüfsumme, statt sie unter der abweichenden CDN-Prüfsumme auszuliefern.
Die Produktionskonfiguration der Leaflet-CSS bleibt unverändert.
