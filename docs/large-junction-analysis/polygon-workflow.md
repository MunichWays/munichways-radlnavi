# Von Straßenknoten zu Kreuzungsflächen

Stand: 06.11.2026. Ziel dieses Schritts ist eine überprüfbare Kandidatenkarte
in Overpass Turbo. Die gefundenen Punkte sind noch keine freigegebenen
Kreuzungsflächen.

Der [erste konkrete Polygonentwurf für Balanstraße/Chiemgaustraße](balan-chiemgau-pilot.md)
liegt jetzt mit beiden Beispielrouten und acht Radweg-Grenzübertritten zur
Sichtprüfung vor. Er ist noch nicht aktiviert.

Die [anschließende Prüfung schwieriger Fälle](difficult-cases.md) bestätigt:
Die Vierer-Punktabfrage ist nur eine Suchhilfe. Alle vier dort untersuchten
Komplexe bleiben vorsorglich von der vereinfachten Guidance ausgeschlossen.

## 1. Straßenklassen: sinnvolle Suche, aber breiter als primary/secondary

Die gemeinsamen OSM-Knoten größerer Straßen sind ein guter Einstieg. Nicht
nach bloßen geometrischen Linienüberschneidungen suchen: Eine Brücke über
einer Straße ist dadurch noch keine Kreuzung. Für eine Netzverbindung müssen
die Wege einen OSM-Knoten teilen.

Nur Verbindungen innerhalb von `primary` und `secondary` zu betrachten, reicht
für die gemeldeten Fälle nicht. Die vorhandene [OSM-Stichprobe](osm-examples.json)
enthält folgende Straßenklassen; separat gezeichnete Radwege sind hier nicht
mitgezählt:

| Ort | Größere Straße | Weitere relevante Straßen |
| --- | --- | --- |
| Thomasiusplatz | Werinherstraße / Claudius-Keller-Straße: `secondary` | Balanstraße: `tertiary`, Wilramstraße: `residential` |
| Balanstraße / Chiemgaustraße | Chiemgaustraße: `primary` | Balanstraße: `tertiary` |
| Arnulfstraße / Steubenplatz | Arnulfstraße: `primary`, Wilhelm-Hale-Straße: `secondary` | Steubenplatz: `tertiary` |
| Ständlerstraße / Balanstraße | Ständlerstraße: `secondary` | Balanstraße: `tertiary` |
| Rudolf-Vogel-Bogen / Otto-Hahn-Ring | Carl-Wery-Straße: `secondary` | Otto-Hahn-Ring: `tertiary`, Rudolf-Vogel-Bogen: `residential`; zusätzliche Link-Wege |

Festlegung des Nutzers: **Kreuzungen innerhalb von primary, secondary und
tertiary berücksichtigen, einschließlich der jeweiligen `_link`-Wege.**
Damit zählen auch `tertiary`/`tertiary`-Verbindungen; eine Beteiligung von
primary oder secondary ist nicht mehr erforderlich. `unclassified`,
`residential` und `living_street` sind in dieser Kandidatenabfrage nicht
enthalten. Die Detailabfrage zeigt weiterhin alle Highway-Wege im Umfeld.
Straßenklasse, Zahl der Fahrspuren und tatsächliche Größe der
Radverkehrskreuzung sind unterschiedliche Eigenschaften.

## 2. Abfragen in Overpass Turbo

In [Overpass Turbo](https://overpass-turbo.eu/) den Kartenausschnitt auf den
zu prüfenden Münchner Bereich einstellen, Abfrage einfügen und **Ausführen**
wählen. `{{bbox}}` steht für den sichtbaren Kartenausschnitt. Nach Verschieben
oder Zoomen erneut ausführen.

- [Nur primary/secondary einschließlich ihrer Links](candidates-primary-secondary.overpassql):
  Vergleich für die engere Hypothese.
- [Vierfach verbundene Punkte ohne Kreisverkehre](candidates-four-way-points.overpassql):
  aktuelle strengere Auswahl des Nutzers. Nur Punkte mit genau vier
  angeschlossenen Segmenten innerhalb von primary/secondary/tertiary
  einschließlich Links. Knoten auf `junction=roundabout`/`circular` und
  `highway=mini_roundabout` werden ausgeschlossen.
- [Breite Vergleichssuche bis tertiary](candidates-major-road.overpassql):
  Verbindungen ab drei angeschlossenen Segmenten; gibt auch Straßen aus.
- [Detailansicht der Umgebung](junction-detail.overpassql): Für einen einzelnen
  Kandidaten weit hineinzoomen. Zeigt Highway-Wege, Ampeln, Querungsknoten und
  vorhandene `junction=yes`-Objekte. Zum Einstieg Balanstraße/Chiemgaustraße
  bei `[48.10845, 11.6040]` verwenden.

Die neue Viererabfrage gibt ausschließlich rote Punkte aus. Die bisherigen
Vergleichsabfragen zeigen auch beteiligte Straßen grau. In der
Detailansicht sind Fuß-/Radwege blau, als `footway=crossing` oder
`cycleway=crossing` markierte Wege türkis und Ampeln rot. Die blaue Farbe
bezeichnet die Wegart, nicht eine geprüfte Erlaubnis zum Radfahren.

Die bisherige breite Kandidatensuche verwendet `way_link:3-`: mindestens drei
angeschlossene Straßensegmente. Das erfasst auch T-Kreuzungen und Verzweigungen.
Die neue Punktabfrage verwendet **`way_link.roads:4`**, also genau vier Segmente
aus der vorher ausgewählten Menge `.roads`. `4-` würde mindestens vier bedeuten.
Anders als
das Zählen von OSM-Wegen zählt es eine reine Wegteilung mit nur zwei
angeschlossenen Segmenten nicht als Kreuzung. Normale dreifach verbundene
T-Knoten fallen aus der neuen Auswahl heraus. **Vier Segmente sind allerdings
nicht immer vier logische Straßenarme:** Eine große Kreuzung mit getrennten
Richtungsfahrbahnen kann aus mehreren dreifach verbundenen Knoten bestehen
und deshalb fehlen. Umgekehrt kann ein T-Komplex durch getrennte Fahrbahnen
oder Abbiegespuren vier Segmente an einem Teilknoten haben. Die strenge
Punktabfrage ist daher ein Sichtprüffilter; für eine zuverlässige Auswahl
vierarmiger Kreuzungskomplexe müssen später zusammengehörige Teilknoten
gruppiert und die äußeren Straßenarme gezählt werden.
[Quelle: Overpass QL, way_link](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#Recurse_(way_cnt,_way_link)).

Die Erkennung verlangt eine geteilte Knotennummer. Eine bloße Überführung
ohne gemeinsamen Knoten wird nicht getroffen. Fehlerhafte OSM-Verbindungen,
weitere Sonderformen sowie Kreuzungen ausschließlich kleinerer Straßen
bleiben Grenzen dieser Suche. Ohne stadtweite Sichtprüfung ist das keine
vollständige Liste aller großen Kreuzungen.

## 3. So wird aus Punkten ein Polygon

1. **Knoten einem Kreuzungskomplex zuordnen.** Bei getrennten Fahrbahnen
   gehören oft mehrere rote Punkte zu einer Kreuzung. Straßenverläufe,
   Inseln, Verbindungsstücke und Furten gemeinsam prüfen. Nahe Punkte nicht
   allein aufgrund ihres Abstands zusammenfassen: Das könnte benachbarte
   Einmündungen verschmelzen.
2. **Radverkehrsbereich ansehen.** In der Detailansicht die Außenkanten der
   Radwege, alle Querungswege und die früheste notwendige Wegentscheidung
   bestimmen. Die Ampeln an der Kfz-Fahrbahn sind Orientierungshilfen, nicht
   automatisch die Flächengrenze.
3. **Polygon zeichnen.** In einem GeoJSON-Editor, beispielsweise
   [geojson.io](https://geojson.io/), mit einer leeren FeatureCollection beginnen
   und den Bereich als Polygon einzeichnen. Die umgebenden Radwege und
   versetzten Furten müssen innerhalb liegen. Die Grenze schneidet jede
   Zufahrt vor der ersten inneren Wegentscheidung und jede Ausfahrt erst
   hinter der letzten inneren Wegentscheidung. Am Thomasiusplatz gehört die
   gemeldete frühe Gabelung deshalb zur Prüfung.
4. **Jeden Randdurchtritt prüfen.** Auf jeder relevanten Radwegseite ergibt
   der Schnitt mit dem Polygon ein gerichtetes Ein- oder Ausgangstor. Prüfen,
   dass alle vorgesehenen Querungswege vollständig innerhalb liegen und
   fremde Abzweige bzw. Nachbarkreuzungen außerhalb bleiben. Bei schrägen oder
   versetzten Wegen ist ein unregelmäßiges Polygon besser als ein großes Rechteck.
5. **Speichern und gegen Routen prüfen.** GeoJSON als FeatureCollection
   speichern, Kreuzungs-ID, Namen, Prüfdatum und vorläufigen Status ergänzen.
   Koordinatenreihenfolge ist `[Länge, Breite]`. Danach alle zulässigen
   Links-/Geradeausbeziehungen und die falschen Ausgänge gegen dieses Polygon
   abspielen. Erst nach Abnahme im späteren Katalog aktivieren.

Zum Pilotieren zuerst **Balanstraße/Chiemgaustraße** abgrenzen. Die beiden
gesicherten Routen haben dieselbe Einfahrt und verschiedene Zielrichtungen.
Damit lässt sich prüfen, ob die Fläche beide Querungsfolgen einschließt und
trotzdem unterscheidbare Ausgänge besitzt.

## 4. Warum die Fläche nicht einfach aus den Straßenlinien berechnet wird

Aus den Kreuzungsknoten allein fehlen die Außengrenzen der Radverkehrswege.
Eine konvexe Hülle der Straßenknoten wäre oft zu klein; ein großzügiger Puffer
könnte fremde Wege einschließen. Die Hülle ganzer OSM-Wege wäre wiederum zu
groß, weil ein einzelner Weg weit über die Kreuzung hinausreichen kann.

Später lässt sich ein **Polygonentwurf** aus lokal begrenzten Furten,
Radwegverbindungen und Zufahrtsverzweigungen berechnen und manuell korrigieren.
Für die fünf ersten Orte ist direktes Einzeichnen und Prüfen überschaubarer.
Ein Puffer zur Darstellung von Kandidaten darf nicht versehentlich die
produktive Fläche zur Unterdrückung von Ansagen und Routenabweichungen werden.

Die Grenze hat hier eine funktionale Bedeutung: Bis zur Einfahrt werden die
100-/60-m-Hinweise ausgelöst, innerhalb bleiben Navigationsansagen und „Route
verlassen“ unterdrückt. Erst ein bestätigter Austritt in falscher Richtung
aktiviert wieder die bisherige Abweichungsbehandlung. Ein zu großes Polygon
würde diese Behandlung zu lange verzögern, ein zu kleines zu früh auslösen.

## 5. Prüfung der Abfragen

Die ausführbaren Turbo-Vorlagen enthalten MapCSS für die Darstellung. Für
den API-Test entfernt [check_candidates.py](check_candidates.py) den Style,
ersetzt `{{bbox}}` durch ein festes Testrechteck und speichert die tatsächlich
ausgeführte Abfrage zusammen mit der Antwort platzsparend als `.json.gz`.

Die API-Abfragen wurden am 06.11.2026 erfolgreich ausgeführt. Im festgelegten
Testrechteck liefert die enge Suche 594 Knoten und die festgelegte Suche
einschließlich tertiary 878 Knoten.
Diese Zahlen enthalten Verzweigungen, Einmündungen und mehrere Punkte je
Kreuzung; sie sind keine Anzahl großer Kreuzungen. Die Detailabfrage enthält
vier Ampelknoten an Balanstraße/Chiemgaustraße.

Die anschließend getestete reine Vierer-Punktabfrage ohne Kreisverkehrsknoten
liefert **338 Knoten und keine Wege** im selben Testrechteck. An allen fünf
Beispielorten bleiben passende Straßenknoten erhalten. Auch diese Zahl zählt
Punkte, nicht bereits zusammengefasste Kreuzungskomplexe.

| Beispielort | Nur primary/secondary | Primary/secondary/tertiary |
| --- | --- | --- |
| Thomasiusplatz | Kein Kandidat im 120-m-Prüfumkreis | Passende Straßenknoten gefunden |
| Balanstraße / Chiemgaustraße | Kein Kandidat im 120-m-Prüfumkreis | Passender Straßenknoten gefunden |
| Arnulfstraße / Steubenplatz | Straßenknoten gefunden | Passende Straßenknoten gefunden |
| Ständlerstraße / Balanstraße | Kein Kandidat im 120-m-Prüfumkreis | Passende Straßenknoten gefunden |
| Rudolf-Vogel-Bogen / Otto-Hahn-Ring | Kein Kandidat im 120-m-Prüfumkreis | Passende Straßenknoten gefunden |

Das belegt die Abdeckung dieser fünf Beispiele, nicht Vollständigkeit oder
Trennschärfe der Suche. Beispielsweise erscheint nahe Arnulfstraße/Steubenplatz
auch die Einmündung der Wendl-Dietrich-Straße: Ein reines räumliches Zusammenfassen
aller Punkte im Prüfumkreis wäre falsch.

Das Kandidaten-Testrechteck ist `[48.08, 11.50, 48.16, 11.66]` in der
Reihenfolge Süd, West, Nord, Ost und enthält die fünf Beispielorte. Das ist
**nicht das gesamte Münchner Stadtgebiet**. Die Detailabfrage verwendet einen
kleineren Ausschnitt um Balanstraße/Chiemgaustraße. Mehrere Knoten können zu
einer Kreuzung gehören; Knotenzahlen sind keine Zahl großer Kreuzungen.

Gespeicherte Antworten offline auswerten:

```powershell
python docs/large-junction-analysis/check_candidates.py
```

Öffentliche Overpass-Abfragen nacheinander neu ausführen und Antworten ersetzen:

```powershell
python docs/large-junction-analysis/check_candidates.py --refresh
```

Die Ausgabe listet Kandidaten bis 120 m um jeden Beispielort und die beteiligten
Straßennamen. Nähe allein beweist noch keine korrekte Kreuzungsgruppierung;
sie dient zur Sichtprüfung der Abdeckung. Die API-Prüfung umfasst die
Overpass-QL-Abfragen, nicht die Darstellung des Styles im Turbo-Browser.

OSM-Daten: © OpenStreetMap contributors,
[ODbL](https://www.openstreetmap.org/copyright).
