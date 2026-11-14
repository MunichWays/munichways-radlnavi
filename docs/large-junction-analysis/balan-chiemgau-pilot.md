# Balanstraße / Chiemgaustraße: Polygonentwurf v1

Fortschritt 07.11.2026: Der Nutzer hat dieses Polygon und alle Tore anhand
der Diagnosegrafik bestätigt. Alle acht Links-/Geradeausbeziehungen sind
inzwischen geprüft und im Laufzeitkatalog freigegeben. Der historische
Entwurfsstand unten bleibt als Beleg erhalten. Aktuelle
[Fahrbeziehungen und Prüfnachweise](full-movements.md).

Stand: 06.11.2026. **Entwurf zur Sichtprüfung, nicht freigegeben oder aktiviert.**
Keine Änderung an Routing, Navigation, Rerouting oder produktiven Diensten.

## Ergebnis

Das [Polygon](balan-chiemgau-draft.geojson) umfasst den Ring der vier separat
gezeichneten Rad-/Fußquerungen und die Anschlussbögen an seinen Ecken.
Die Fläche beträgt in lokaler Meterprojektion ungefähr **3200 m²**. Das ist
eine für die Navigation entworfene Bereichsgrenze, keine amtliche Vermessung.

Die Grenze schneidet die zulässigen, einbahnig erfassten Radverkehrswege an
acht Stellen. Die folgenden Bezeichnungen entsprechen den Straßenarmen,
nicht der momentanen Blickrichtung des Radfahrers:

| Tor | Straßenarm | Richtung gemäß OSM | OSM-Weg |
| --- | --- | --- | --- |
| G1 | Balanstraße Süd | Ausfahrt | 138347229 |
| G2 | Balanstraße Süd | Einfahrt | 134138908 |
| G3 | Chiemgaustraße West | Einfahrt | 63534658 |
| G4 | Chiemgaustraße Ost | Ausfahrt | 138347230 |
| G5 | Chiemgaustraße West | Ausfahrt | 63534665 |
| G6 | Chiemgaustraße Ost | Einfahrt | 52792924 |
| G7 | Balanstraße Nord | Einfahrt | 341311854 |
| G8 | Balanstraße Nord | Ausfahrt | 147718914 |

Das sind berechnete **Grenzübertrittspunkte**, noch keine separat vermessenen
Torlinien. Die Zuordnung zur Ein-/Ausfahrt folgt hier `oneway=yes` und der
Reihenfolge der OSM-Weggeometrie. Eine vollständige Prüfung aller erlaubten
Fahrbeziehungen ist damit noch nicht erfolgt.

## Prüfung mit den beiden gemeldeten Routen

| Route | Einfahrt | Ausfahrt | Strecke innerhalb der Fläche, ungefähr |
| --- | --- | --- | --- |
| Balanstraße Nord → Chiemgaustraße Ost, links | G7 | G4 | 95 m |
| Balanstraße Nord → Balanstraße Süd, geradeaus | G7 | G1 | 62 m |

Beide Routen treten nach ungefähr **72 m ab dem gemeldeten Startpunkt** in
die Fläche ein. Der erste API-Abbiegehinweis kommt dagegen erst bei 117,4 m.
Die neue Grenze beginnt also etwa 46 m davor und umfasst bereits die erste
Querung auf der westlichen Kreuzungsseite.

Alle drei inneren API-Manöver der Linksroute und beide der Geradeausroute
liegen innerhalb. Jede Beispielroute hat genau einen Eintritt und einen
Austritt. Es werden auch Grenzübertritte zwischen vorhandenen Geometriepunkten
berechnet, nicht nur Punkte gezählt, die innerhalb liegen.

Die 100-m-Voransage lässt sich mit diesen kurzen Beispielrouten nicht
vollständig abspielen: Der Start liegt nur etwa 72 m vor der Einfahrt.
Für einen späteren Sprachtest braucht es deshalb einen weiter nördlich
liegenden Start. Die 100/60 m beziehen sich weiterhin auf G7, nicht auf den
ersten API-Abbiegepunkt. Die Distanzangaben hier sind lokale geometrische
Näherungen; endgültige Sprachdistanzen verwenden den Routenfortschritt der App.

## Unterlagen zur Sichtprüfung

- [Nur das Polygon als GeoJSON](balan-chiemgau-draft.geojson).
- [Polygon, beide Routen, acht Tore und vier Querungswege als GeoJSON](balan-chiemgau-review.geojson),
  zum Öffnen in einem GeoJSON-Editor.
- [Statische Geometrievorschau](balan-chiemgau-diagnostic.png).
- [Berechnete Zuordnungen und Quelldaten](balan-chiemgau-review.json).

Die Inline-Karte erlaubt die Auswahl von links/geradeaus/beiden Routen und
den Wechsel zwischen Kreuzungsdetail und vollständigen Beispielrouten.
Die Basiskarte besteht aus den gesicherten tatsächlichen OSM-Highway-Geometrien;
es werden keine Kartentiles nachgeladen. Symbole und Linien sind zur
Lesbarkeit vergrößert und zeigen keine vermessenen Wegbreiten.

Zu prüfen sind insbesondere der Verlauf der Nordgrenze vor der Querung,
die Ausfahrtsgrenze im Osten nach dem letzten Anschlussbogen und die
Südgrenze zwischen Anschlussbogen und Bushaltestellenbereich. Die geprüften
vier Querungen liegen vollständig innerhalb. Nachbarkreuzungen werden vom
Entwurf nicht umfasst. Geprüft werden müssen noch die weiteren Zufahrten,
die jeweiligen Links-/Geradeausbeziehungen und tatsächliche Alternativwege.

## Reproduzierbarkeit und Grenzen

[build_balan_pilot.py](build_balan_pilot.py) erzeugt die Review-Daten und die
Inline-Karte offline aus dem manuell entworfenen Polygon, dem gesicherten
OSM-Snapshot und den beiden API-Antworten:

```powershell
python docs/large-junction-analysis/build_balan_pilot.py
powershell -NoProfile -File docs/large-junction-analysis/render_balan_diagnostic.ps1
```

Geprüft: geschlossener, nicht selbstschneidender Polygonring mit GeoJSON-
Orientierung; alle vier Querungen vollständig im Bereich; acht Radweg-
Grenzübertritte, je eine Ein- und Ausfahrt pro Arm; die beiden vollständigen
Durchfahrten; interne API-Manöver innerhalb; Übereinstimmung der Route-/OSM-
Grenzpunkte bis auf höchstens 0,5 m. Die statische Geometrievorschau wurde
visuell geprüft, die Karten-JavaScript-Syntax geprüft.

Die Browser-Sichtprüfung konnte wegen eines Computer-Use-Zugriffstimeouts
nicht abgeschlossen werden. Die lokale Bildvorschau bestätigt die Geometrie;
sie ersetzt keinen Browser-Interaktionstest. Keine Fahrt vor Ort oder mobile
Ansage geprüft. Der Katalogeintrag bleibt ausdrücklich `enabled: false`.

OSM-Daten: © OpenStreetMap contributors,
[ODbL](https://www.openstreetmap.org/copyright). OSM-Datenstand und API-URLs
stehen in den gesicherten Quelldateien; sie sind nicht zwingend derselbe
Kartendatenstand wie im produktiven Routinggraphen.
