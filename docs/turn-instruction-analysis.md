# Analyse: normale und leichte Abbiegehinweise

Stand 12.09.2026. Nur Analyse; keine Änderung an Ansage- oder Winkelregeln.

## Befund aus der App

Die App übernimmt zunächst `maneuver.type` und `maneuver.modifier` aus der
OSRM-Antwort unverändert (`lib/api/radlnavi_api.dart`). Danach verändert
`VoiceGuidance.setRoute()` diese Einordnung an einer Stelle selbst:
`_adjustTurnModifierFromGeometry()` in `lib/ui/map/voice_guidance.dart`.

* Nur `turn` mit `right` oder `left` wird betrachtet.
* Die Richtungen werden aus interpolierten Punkten entlang der Route jeweils
  12 Meter vor und nach dem Manöver ermittelt.
* Bei 15 bis einschließlich 50 Grad wird ein normales Abbiegen in
  `slight right` bzw. `slight left` umgewandelt.
* Bereits vom Backend gelieferte `slight`-Manöver werden umgekehrt nicht zu
  normalen Abbiegehinweisen korrigiert.
* Sowohl der sichtbare Hinweis als auch die Sprachausgabe verwenden anschließend
  das korrigierte Manöver. Änderungen an dieser Stelle betreffen deshalb beides.

Diese Korrektur sollte flache Übergänge auf versetzte Radwege verständlicher
machen. Ein bestehender Test sichert ausdrücklich den Fall Lautensackstraße:
Das Backend liefert `right`, die App sagt dafür „leicht rechts“.
Sie ist somit keine bloße Übersetzung des Backend-Textes.

Konkreter Kandidat aus der bereits gespeicherten produktiven Direkt-Antwort
für den Arbeitsweg mit zwei Zwischenzielen: bei Breite/Länge
`[48.145548, 11.519868]` liefert das Backend `turn/right`. Eine geometrische
Gegenprobe entlang der geordneten Step-Geometrie ergibt ungefähr 17,9 Grad
bei 12 Metern und 71,3 Grad bei 30 Metern Abstand auf beiden Seiten. Die
bisherige App-Regel würde anhand des kurzen Fensters abschwächen. Die Rechnung
verwendet lokal projizierte Meter und ist eine Diagnose am gespeicherten
Datensatz, keine protokollierte Ansage auf dem Telefon. Im gespeicherten
Standard-Arbeitsweg fand diese Gegenprobe keinen entsprechenden Kandidaten
(kurzes Fenster 15–50 Grad, langes Fenster über 55 Grad).

Zusätzlich ergänzt `_geometryTurns()` fehlende markante Abzweige. Diese zweite
Regel betrachtet unmittelbare benachbarte Geometriesegmente, verlangt mindestens
7 Meter für jedes Segment und einen Winkel zwischen 60 und 135 Grad. Bei
vielen kurzen Teilstücken einer gezeichneten Kurve kann diese Ergänzung ausfallen.
Sie repariert keine bereits vorhandene, zu leichte Anweisung.

## Bedeutung kurzer OSM-Teilstücke

Die bestehende 12-Meter-Regel zählt keine OSM-Punkte, sondern interpoliert über
die Streckenlänge. Die bloße Anzahl der Punkte ist dort nicht die Ursache.
Das betrachtete Stück kann aber zu kurz sein: Eine ausgerundete Abzweigung
ändert ihre Richtung über beispielsweise 25–40 Meter. Ihre ersten 12 Meter
bilden dann nur einen Teil des eigentlichen Abbiegens ab.

Das erklärt einen plausiblen Fehlermechanismus, belegt aber ohne konkrete
beanstandete Abzweigkoordinaten noch nicht jeden gemeldeten Fall. Es muss jeweils
unterschieden werden zwischen bereits falschem Backend-Modifier und einer erst
durch die App abgeschwächten Anweisung.

## Ort der Korrektur

**Zuerst die vorhandene App-Korrektur eingrenzen.** Sie ist ein konkreter,
zusätzlicher Einfluss auf die Anzeige und Ansage und kann gezielt korrigiert
werden, ohne die Routenwahl, Fahrzeiten oder Routing-Graphen zu verändern.
Ein pauschaler größerer Winkelbereich für „leicht“ wäre kontraproduktiv.

Vorschlag für eine spätere Umsetzung:

1. Für gemeldete Abzweige Backend-Typ/Modifier, App-Modifier sowie geometrische
   Richtungsänderung über 12 und über etwa 25–40 Meter vergleichen.
2. Nur dann ein normales Abbiegen abschwächen, wenn sowohl die lokale als auch
   die weiter vorausliegende Richtung einen flachen Übergang bestätigen.
3. Das längere Fenster vor dem nächsten eigenständigen Manöver begrenzen;
   sonst könnten zwei echte, nahe Abzweige oder eine S-Kurve verrechnet werden.
   Kurven über Distanz zusammenfassen, nicht über eine feste Anzahl OSM-Punkte.
4. Die tatsächliche Vorkommensposition entlang der Route verwenden; Kreuzungen,
   Schleifen und doppelt befahrene Wege dürfen nicht über einen bloßen räumlich
   nächsten Punkt vermischt werden. Bestehende Erholungs-/Ansagezustände erhalten.
5. Regressionen: ausgerundeter 90-Grad-Abzweig mit vielen kleinen Segmenten,
   Lautensackstraße als echter flacher Übergang, nahe Doppelabbiegung, S-Kurve,
   Kreisverkehr, Start/Ziel und dieselbe Kurve in Gegenrichtung.

**Wenn bereits RadlNavi `slight` falsch liefert, gehört die grundlegende
Korrektur langfristig in RadlNavi/OSRM**, damit Frontend und App dieselben
Manöver erhalten. In der API sind Richtungs-Modifier Teil des Manövers:
[OSRM HTTP-Vertrag](https://github.com/Project-OSRM/osrm-backend/blob/master/docs/http.md#stepmaneuver-object).
Die Lua-Funktion `process_turn` dient dagegen der Gewichtung und Fahrzeit
von Abbiegungen; sie ist nicht der einfache Schalter für deren Textkategorie:
[OSRM Profil-Schnittstelle](https://github.com/Project-OSRM/osrm-backend/blob/master/docs/profiles.md#process_turnprofile-turn).
Ein globaler Eingriff in diese Gewichte wäre für dieses Anzeigeproblem der
falsche Ansatz und könnte die gewählte Strecke verändern.

Empfehlung: kleine, anhand echter Fälle geprüfte Begrenzung der App-Abschwächung
als erster Schritt; eine zusätzliche zentrale Korrektur nur für nachgewiesene
Backend-Fehlklassifikationen. Keine parallelen, widersprüchlichen Winkelregeln
in beiden Systemen einführen.
