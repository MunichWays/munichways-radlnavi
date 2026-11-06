# Schwierige Kreuzungen: konservative Prüfung

Stand: 06.11.2026. Nutzeranforderung: Im Zweifel eine Kreuzung weglassen,
statt falsche vereinfachte Hinweise oder eine falsche Unterdrückung von
„Route verlassen“ zu riskieren.

## Ergebnis

**Alle vier gemeldeten Knoten passieren die bisherige Vierer-Punktabfrage.
Keiner der vier Kreuzungskomplexe wird für die vereinfachte Ansagelogik
freigegeben.** Für sie wurden keine aktiven Polygone angelegt.

Die [Entscheidungen](junction-review-decisions.json) halten den Ausschluss
fest. Diese Datei ist ein Analyse-/Katalogentwurf und wird noch nicht von der
produktiven Navigation gelesen. Auch der Balanstraße-Pilot bleibt ein
inaktiver Entwurf. An produktiven Ansagen oder Routing wurde nichts geändert.

| Fall | Ausgewählte Segmente am genannten Knoten | Befund | Entscheidung |
| --- | --- | --- | --- |
| Am Knie, `5693658006` | 4 | Vier Fahrbahnanschlüsse, aber uneinheitliche Radverkehrsführung; keine vollständig geprüfte Zuordnung der Radverkehrswege und Ausgänge | Vorerst ausschließen |
| Gabelsbergerstraße / Oskar-von-Miller-Ring, `12878607912` | 4 | Mehrere kurze interne Verbindungen, Kurven und Anschlüsse an Kraftfahrstraßen-/Tunnelzufahrten | Ausschließen |
| Kreillerstraße / Else-Rosenfeld-Straße, `17707826` | 4 | Der scheinbare vierte Arm ist ein kurzes Verbindungsstück zur anderen Richtungsfahrbahn der Kreillerstraße; T-Komplex | Ausschließen |
| Quiddestraße / Nawiaskystraße, `15687747` | 4 | Tatsächlich fünf Fahrbahnsegmente: Die residential-Straße wird im Filter nicht gezählt, zwei Anschlüsse auf der Ostseite dagegen schon; Kraftfahrstraßenrampen | Ausschließen |

Die Straßenbezeichnungen Kreillerstraße, Else-Rosenfeld-Straße und
Nawiaskystraße stammen aus den abgefragten OSM-Tags. Die vom Nutzer genannten
Knoten und Koordinaten wurden jeweils exakt wiedergefunden.

## 1. Am Knie

Am angegebenen Knoten treffen die folgenden OSM-Wege zusammen:

- `252549977`: Landsberger Straße, `tertiary`, `oneway=yes`,
  `bicycle=use_sidepath`.
- `598183665`: Landsberger Straße, `secondary`, `oneway=yes`,
  `bicycle=use_sidepath`.
- `598183663` und `1512198007`: Am Knie, jeweils `secondary`, `oneway=yes`;
  an diesen beiden Wegen keine explizite Radwegzuordnung wie an den
  Landsberger-Anschlüssen. Einer trägt `sidewalk=right`.

In der Umgebung existieren durchaus Radverkehrswege und mehrere Querungen.
Deren bloße Anzahl beweist aber keinen vollständigen, einfach zuzuordnenden
Ring für alle vier Straßenarme. Einige Wege sind zweirichtungsfähig,
andere einbahnig; hinzu kommen freigegebene Fußwege.

**Folgerung:** Der Nutzerhinweis auf die gemischte Führung ist ein relevanter
Prüfgrund. Aus fehlenden Radweg-Tags an einer Fahrbahn folgt weder ein
Radfahrverbot noch ein nachgewiesen geeigneter Anschluss. Für die erste
Freigabe weglassen, bis konkrete Ein-/Ausgänge und Fahrbeziehungen vollständig
geprüft sind. Keine pauschale Zusammenfassung der vorhandenen Einzelhinweise.

## 2. Gabelsbergerstraße / Oskar-von-Miller-Ring

Der Knoten besitzt vier ausgewählte Segmente, die aber zunächst nur lokale
Fahrbahnverbindungen beschreiben. Drei davon führen schon nach ungefähr
8–10 m zum nächsten Verzweigungsknoten:

- `739675291` nach `12255362696`, ca. 8,6 m entfernt.
- `1525507624` nach `340197468`, ca. 10,3 m entfernt. Dort schließen unter
  anderem `85004753` und `310971850` mit `motorroad=yes`, `bicycle=no` an.
- `1525507625` nach `12878607913`, ca. 7,8 m entfernt. Dort schließt
  `878572896` mit `motorroad=yes`, `bicycle=no` an.

Im lokalen Datensatz liegen außerdem die Altstadtringtunnel-Wege `144692953`
und `292960294`, jeweils mit `tunnel=yes`, `layer=-2`, `motorroad=yes` und
`bicycle=no`. Das sind andere Verbindungen als die umliegenden Radwege.

Die vier kurzen Segmente am Referenzknoten dürfen deshalb nicht als Beweis
vier gleichwertiger Radverkehrsarme gelten. Auch ein größerer Winkelvergleich
am einzelnen Knoten löst die Kurven-/Tunnelzuordnung nicht zuverlässig.

**Folgerung:** Den gesamten Komplex für den ersten Stand ausschließen.
Ein späterer Sonderfall müsste Oberfläche, Tunnelzufahrt, Radverkehrswege
und Ausgänge separat zuordnen. Eine bloße Fläche in der Kartenebene darf
dabei nicht jede Route unter derselben Koordinate erfassen.

`layer` beschreibt die relative Höhenlage sich überlagernder Objekte;
`tunnel` kennzeichnet die unterirdische Führung. Diese Tags ersetzen nicht
die Prüfung der tatsächlichen Netzverbindung.
[OSM layer](https://wiki.openstreetmap.org/wiki/Key:layer),
[OSM tunnel](https://wiki.openstreetmap.org/wiki/Key:tunnel).

## 3. Kreillerstraße / Else-Rosenfeld-Straße

Hier lässt sich die Fehlinterpretation des Viererfilters besonders konkret
belegen. Am Referenzknoten hängen zwei Abschnitte der Kreillerstraße sowie
zwei unter Else-Rosenfeld-Straße benannte Abschnitte:

- `132236428` führt zur eigentlichen Else-Rosenfeld-Straße im Süden weiter.
- **`37666177` führt nach Norden nur bis `428737`, etwa 18,2 m vom
  Referenzknoten entfernt.** Dort endet es an der anderen Kreiller-
  Richtungsfahrbahn (`420680106` und `1557802370`).

Das kurze Stück über den Mittelbereich ist ein Bestandteil derselben
Einmündung. Es ergibt keinen eigenständigen vierten Straßenarm nördlich
der gesamten Kreillerstraße. Der Knoten besitzt geometrisch trotzdem vier
ungefähr kreuzförmige Segmente. Damit würde auch ein einfacher Filter auf
vier verschiedene lokale Richtungswinkel den Fall nicht zuverlässig lösen.

**Folgerung:** Wie vom Nutzer gewünscht als T-Kreuzung ausschließen.
Für die spätere automatische Prüfung müssen geteilte Fahrbahnen zuerst zu
einem Kreuzungskomplex zusammengefasst und erst dessen äußere Arme gezählt
werden. Straßennamen allein reichen hierfür ebenfalls nicht.

## 4. Quiddestraße / Nawiaskystraße

Der Viererfilter zählt am Referenzknoten:

- Quiddestraße Nord und Süd, `258942648` und `1424949179`, jeweils `secondary`.
- Zwei namenlose, einbahnige `secondary_link`-Wege `4265490` und `43082827`
  auf der Ostseite. Sie liegen zunächst in Richtung ca. 114° bzw. 80°.

**Nicht mitgezählt wird `851607377`, Nawiaskystraße, `residential`, westlich
des Knotens.** Zählt man alle angeschlossenen Kfz-Straßensegmente, sind es
fünf statt vier. Die Filterzahl vier ist hier also kein vierarmiger Grundriss.

Die sekundären Link-Wege sind am Anfang sogar mit `bicycle=yes` markiert.
Das darf nicht auf den ganzen östlichen Anschluss übertragen werden. Der
Datensatz enthält die anschließenden Rampen als `trunk_link` mit
`motorroad=yes`, beispielsweise `4265489`, `4265491` und `92434946`;
die Ständlerstraße ist hier `trunk`, teils mit `bridge=yes`, `layer=1`.

Der Übergang ist konkret nachvollziehbar: Über `49609567` und
`1364204799` gelangt die Kfz-Verbindung zu `165636083` (`trunk_link`,
`motorroad=yes`); in der Gegenrichtung verbindet `1364204798` die
Kraftfahrstraßenrampe `258942651` mit `165636090`. An den Knoten `684335829`
und `684335830` ist zugleich der Radverkehrsweg `54265458` angeschlossen.
Es gibt also Radwegabzweige vor dem Kraftfahrstraßenabschnitt. Aus dem
Rampenbefund folgt **nicht**, dass die gesamte östliche Richtung für Radfahrer
unbenutzbar wäre; deren vollständige Zuordnung ist hier nicht abgenommen.

Der Nutzer beschreibt eine Autobahnrichtung. In den abgefragten OSM-Daten
ist der betreffende Komplex genauer als `trunk`/`trunk_link` und
`motorroad=yes` erfasst, nicht als `highway=motorway`.

**Folgerung:** Den Rampenkomplex ausschließen. Ein `bicycle=yes` auf einem
kurzen Verbindungsstück genügt nicht als Nachweis eines durchgehend passenden
vierten Radverkehrsarms. Erst die vollständige Verbindung bis außerhalb des
Kreuzungskomplexes wäre zu prüfen.

## Was wir aus diesen Fällen ändern

Die bisherige Punktabfrage bleibt als **Suchhilfe zur Sichtprüfung** erhalten.
Sie darf keine Aktivierung von Polygonen oder vereinfachten Ansagen auslösen.
Insbesondere reichen folgende Kriterien allein nicht:

- Vier ausgewählte Fahrbahnsegmente oder vier lokale Winkel.
- Vier Ampeln oder eine bestimmte Anzahl Rad-/Fußwege in einem Suchradius.
- Unterschiedliche Straßennamen oder ein `bicycle=yes` auf einem Teilstück.
- Ein gezeichneter Bereich, der äußerlich die ganze Kreuzung einschließt.

Für den ersten Stand gilt stattdessen:

1. **Explizite Freigabeliste.** Unbekannte, ungeprüfte oder widersprüchliche
   Fälle bleiben ausgeschaltet. Alle vier untersuchten Orte sind ausgeschlossen.
2. **Vier äußere, zusammengehörige Radverkehrsarme nachweisen.** Zunächst
   geteilte Fahrbahnen und innere Verbindungen zu einem Komplex zuordnen.
   Dabei auch niedrigere Straßenklassen, Rampen, Höhenlage und Anschlusskurven
   ansehen, obwohl die Suchhilfe nur primary bis tertiary zählt.
3. **Alle verwendeten Ein-/Ausgänge und Fahrbeziehungen prüfen.** Die
   berechnete Radroute einschließlich Richtung, Zugangsregeln und eventuellem
   Schiebeabschnitt muss zur freigegebenen Beziehung passen. Für den ersten
   einfachen Polygonansatz gemischte oder unklare Führungen weglassen.
4. **Keine pauschale Unterdrückung allein wegen GPS innerhalb einer Fläche.**
   Sie darf nur für eine aktivierte, der konkreten Route zugeordnete
   Kreuzungsdurchfahrt gelten. Bei unbekannter oder nicht freigegebener
   Fahrbeziehung die bisherigen Einzelhinweise und Abweichungslogik verwenden.
5. **Katalog und Zuordnung müssen eindeutig sein.** Bei einer nicht mehr
   passenden Karte, unklaren Toren oder Konflikten die vereinfachte Guidance
   für diese Durchfahrt nicht erzeugen. Keine geschätzte Richtungsansage.

Eine bloße Sperrliste der vier Referenzknoten wäre unzureichend: Am Knie,
Gabelsbergerstraße und Quiddestraße gibt es weitere Viererknoten im selben
Komplex. Der Ausschluss betrifft den Ort, nicht nur eine Knotennummer.

`bicycle=use_sidepath` beschreibt die Nutzung eines separat gezeichneten
Radwegs. Solche Fahrbahn-Tags sind kein genereller Grund, die ganze Kreuzung
auszuschließen; sie verlangen die Zuordnung zum tatsächlichen Radweg. Sonst
würde auch der Balanstraße-Pilot unnötig herausfallen.
[OSM use_sidepath](https://wiki.openstreetmap.org/wiki/Tag:bicycle%3Duse_sidepath).

Ebenso darf ein beliebiger privater Durchgang oder eine entfernte Brücke
im 180-m-Suchradius nicht pauschal den Ausschluss einer benachbarten
Kreuzung begründen. Entscheidend ist die Zugehörigkeit zum Komplex; im
Zweifel wird vorerst nicht freigegeben.

## Belege und Reproduzierbarkeit

- [Eingabefälle](difficult-cases.json).
- [Ausgewerteter Bericht](difficult-cases-report.json), einschließlich
  Segmentrichtungen, weiterer Anschlüsse an kurzen Wegenden und relevanter Tags.
- Vollständige komprimierte OSM-Antworten: `difficult-am-knie.json.gz`,
  `difficult-gabelsberger-oskar-von-miller.json.gz`,
  `difficult-kreiller-els-rosenfeld.json.gz` und
  `difficult-quidde-nawiasky.json.gz`. Jede enthält die ausgeführte Abfrage
  und Abrufzeit; die OSM-Basiszeiten liegen am 06.11.2026 um 12:15–12:17 UTC.

Offline erneut auswerten:

```powershell
python docs/large-junction-analysis/inspect_difficult_cases.py
```

Öffentliche Overpass-Abfragen nacheinander neu ausführen:

```powershell
python docs/large-junction-analysis/inspect_difficult_cases.py --refresh
```

Es wurden OSM-Topologie und Tags untersucht, keine mobilen Ansagen getestet
und keine vollständigen Alternativrouten für diese Orte abgenommen. Der
Zugangsresolver in dieser Diagnose wird bewusst nicht nachgebaut; die spätere
Routenprüfung muss die tatsächlichen RadlNavi-Routen zugrunde legen. Eine
Quelle kann älter oder neuer sein als der produktive Routinggraph.

OSM-Daten: © OpenStreetMap contributors,
[ODbL](https://www.openstreetmap.org/copyright).
