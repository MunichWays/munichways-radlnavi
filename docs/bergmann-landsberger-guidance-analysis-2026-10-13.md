# Fehlender Linksabbiegehinweis an der Landsberger Straße

Stand 13.10.2026. Analyse, reproduzierbarer Testfall und lokaler Profilfix.
Die früher gemeldeten Fälle ZOB und Maffeistraße
wurden nach einer fehlerhaften temporären Testinstallation erneut gefahren:
Ihre Ansagen waren korrekt. Schrammerstraße/Hofgraben wurde inzwischen in
OSM geändert. Diese alten Beobachtungen sind keine Grundlage für einen neuen
Winkel- oder Filterpatch.

## Reproduktion

Eingabe in **[Breite, Länge]**:

- Bergmannstraße `[48.138255, 11.537721]`
- Philipp-Loewenfeld-Straße `[48.140515, 11.538348]`

Die [vollständige produktive Antwort](osrm-standard-analysis/2026-10-13-bergmann-landsberger.json)
enthält die genaue URL und die gesnappten Punkte. Abfrage mit `steps=true`,
`geometries=geojson`, `overview=full`, `annotations=nodes,distance` und
`variant=standard`. Produktiv am 13.10.2026: Backend/Routing 2.3.4,
Routing-Commit `11482f35d84a221583fbe0be794a5bd4fe2c6719`, OSRM 26.6.5.
Die Direct-Variante lieferte dieselbe 270,3-m-Route und dieselbe Step-Folge.
Ein Telefon-/GPS-Replay wurde für diese Analyse nicht ausgeführt.

| Streckenmeter | Ort `[Länge, Breite]` | Rohdaten / Wegwahl |
| ---: | --- | --- |
| 0 | `[11.537719, 48.138255]` | `depart`, Bergmannstraße |
| 165,6 | `[11.538028, 48.139730]` | `turn/right`, ca. 88° nach rechts, auf Radweg; der nächste Step reicht von hier bis zum Ziel |
| ca. 181,1 | `[11.538233, 48.139716]` | **Kein eigener Step.** Die Route biegt hier ca. 90° nach links. In der `intersections`-Liste des Rechts-Step stehen zwei erlaubte Ausfahrten: nach Norden (`out=0`, Bearing 0°; gewählte Querung) und nach Osten (Bearing 90°; Weiterfahrt entlang der Landsberger Straße). Die eingehende Kante zeigt nach Westen (`in=2`, Bearing 270°). |
| 270,3 | `[11.538353, 48.140515]` | `arrive`, Philipp-Loewenfeld-Straße |

Die beiden tatsächlichen Richtungswechsel liegen nur etwa **15,3 m**
auseinander. Nach dem Rechtsmanöver meldet der API-Step noch **104,6 m**
bis zum Ziel; die fehlende Linksentscheidung liegt aber schon rund 15 m
später. Die vom Nutzer berichtete Fehlfahrt nach Osten ist damit anhand
der alternativen erlaubten Ausfahrt an genau diesem Knoten erklärbar.

Aktuelle OSM-Daten nahe dem zweiten Knoten zeigen einen benannten
`highway=path`-Seitenweg entlang der Landsberger Straße sowie die nach
Norden führende `highway=cycleway`-Querung mit `cycleway=crossing`,
`crossing=traffic_signals` und `oneway=yes`. Der [eingefrorene OSM-Ausschnitt](../routing/tests/fixtures/bergmann-landsberger-2026-10-13.osm)
stammt vom 13.10.2026 aus der [OSM-API](https://api.openstreetmap.org/api/0.6/map?bbox=11.53755,48.1381,11.5386,48.1407).
Nur Bearbeiter-Metadaten wurden entfernt; Geometrie und Tags blieben erhalten
(© OpenStreetMap-Mitwirkende, ODbL; SHA-256
`dc54222a4ca50b46041c663c15eadad6a75e00b3e3cde60b9789ad30605f9ddf`).
Das Einfrieren ist wichtig, weil spätere OSM-Änderungen sonst die
Reproduktion verändern können.

### Kontrollierter OSRM-Vergleich

Den Ausschnitt lokal jeweils mit `osrm-extract`, `osrm-partition` und
`osrm-customize` verarbeitet und dieselben Koordinaten mit `steps=true`
abgefragt. Im **Ausgangsstand vor der neuen Profilregel** liefern alle vier
Kombinationen die **gleiche Route (270,3 m)** und nur `depart`,
`turn/right`, `arrive`:

| OSRM | Profil | Fehlender Links-Step? |
| --- | --- | --- |
| 26.6.5 | bisheriges RadlNavi `bike.lua` | ja; identisch zur produktiven Antwort |
| 26.6.5 | unverändertes `/opt/bicycle.lua` | ja |
| 26.10.0 | unverändertes `/opt/bicycle.lua` | ja |
| 26.10.0 | bisheriges RadlNavi `bike.lua` | ja |

Somit sind ein veralteter Produktionsgraph, eine bloße Änderung von
Wegeklassifikation/Kosten im Fahrradprofil und ein Update auf OSRM 26.10.0
als **alleinige Lösung** für diesen Fall widerlegt. Der
lokale OSM-Ausschnitt ist klein; die exakte Übereinstimmung der Route und
Step-Folge mit Produktion macht ihn für diesen Test dennoch aussagekräftig.

### Gefundene OSRM-Ursache und Profiländerung

OSRM setzt für `max_collapse_distance` standardmäßig **30 m**. Diese
Profiloption steuert mehrere Regeln, die kurze Guidance-Schritte
zusammenfassen (siehe [Profilstandard](https://github.com/Project-OSRM/osrm-backend/blob/v26.10.0/include/extractor/profile_properties.hpp)
und [Aufruf der Guidance-Nachbearbeitung](https://github.com/Project-OSRM/osrm-backend/blob/v26.10.0/include/engine/api/route_api.hpp)).
Mit dem unveränderten OSM-Ausschnitt und dem RadlNavi-Profil
liefert OSRM 26.6.5 bei **15 m** weiterhin nur rechts, bei **10 m** und
**0 m** dagegen rechts bei 165,6 m und links bei 180,9 m, jeweils mit
270,3 m Gesamtroute. Das Problem entsteht somit **nach** der Manöver-Erkennung
bei der OSRM-Nachbearbeitung. Der 10-m-Wert wäre kein ausreichender Grundsatz
für noch kürzere Richtungsentscheidungen. Deshalb setzt `routing/bike.lua`
`max_collapse_distance = 0`; `direct.lua` übernimmt diese Eigenschaft aus
`bike.lua`. Die OSM-Daten und das eigentliche Routing bleiben dabei gleich.

Eine lokale OSRM-`type=maneuver`-Relation wurde ebenfalls geprüft: Nach dem
Aufteilen des betroffenen OSM-Wegs am Abzweig erkannte `osrm-extract` die
Override-Relation, die 30-m-Nachbearbeitung entfernte den Links-Step trotzdem.
Ein einzelner OSM-Override ist hier daher keine ausreichende Lösung.

Auch mit `0` bleiben einige andere, von dieser Option unabhängige
OSRM-Zusammenfassungen aktiv (etwa spezielle Regeln für versetzte oder
getrennte Kreuzungen). Die Einstellung ist also kein Beweis, dass OSRM nie
wieder einen wichtigen Schritt auslässt. Der neue Routentest schützt genau
diesen reproduzierten Fall.

Lokale Gegenproben auf aktuellen OSM-Ausschnitten mit 30 m und 0 m:

| Route | 30 m | 0 m |
| --- | --- | --- |
| Bergmannstraße → Philipp-Loewenfeld-Straße | rechts | rechts, links |
| Birketweg → Radweg Reitknechtstraße | links, rechts | links, rechts, zusätzlich geradeaus |
| Waisenhausstraße, U-Bahn-Aufgänge | leicht links | unverändert |
| Ständlerstraße über Balanstraße | links, leicht rechts | unverändert |

Das zusätzliche `turn/straight` am Birketweg liegt etwa 20,5 m nach dem
Rechtsabbiegen. Ob diese und andere neue Hinweise beim Fahren nützlich sind,
muss noch im Prüffenster und auf dem Telefon beurteilt werden. Die kleine
Vergleichsauswahl ersetzt keine Prüfung auf dem vollständigen Oberbayern-Graphen.

## Wo das Manöver verloren geht

1. Der normale API-Proxy in `backend/src/app.py` reicht die OSRM-Antwort
   unverändert durch. Die zweite Kreuzung ist als `intersection` vorhanden,
   aber OSRM liefert dort bei der bisherigen 30-m-Grenze keinen eigenen
   `RouteStep.maneuver`. Mit `max_collapse_distance = 0` erscheint der
   Links-Step. Die Ursache ist damit auf die entfernungsabhängige
   OSRM-Nachbearbeitung eingegrenzt.
2. Die Flutter-App `RadlNaviApi.route()` übernimmt Manöver **nur aus Steps**.
   Die Intersections werden bisher lediglich für den Wegtyp-Zusatz genutzt.
   Deshalb entsteht kein `RouteManeuver` für den linken Abzweig.
3. `VoiceGuidance._geometryTurns()` würde die ca. 90°-Ecke grundsätzlich
   erkennen. Sie verwirft sie aber doppelt: Das Segment nach dem Knoten
   misst nur ca. **4,7 m** statt der verlangten 7 m, und das bestehende
   Rechtsmanöver ist nur **15,3 m** statt mindestens 25 m entfernt.
   Beide Schranken schützen an anderen Stellen vor erfundenen oder
   doppelten Hinweisen; sie pauschal zu senken wäre riskant.
4. Das vorhandene App-Format für kurze Manöverfolgen verkettet zwei
   Hinweise innerhalb von **35 m** automatisch mit „danach sofort“.
   Der Abstand passt bereits. Eine Änderung des Sprechformats ist nicht
   nötig, sobald ein sicheres zweites Manöver vorhanden ist.

Der aktuelle App-Code sollte am ersten Knoten ein normales „rechts
abbiegen, auf Radweg“ behalten: Der 12-m-Geometriewinkel beträgt dort
ca. 88° und löst keine Abschwächung zu „leicht“ aus. Die fehlende
Linksansage ist damit **kein Fall der bisherigen Paarunterdrückung**.

## Weitere Korrekturen, falls nötig

**Bei weiterer Auslassung OSRM-Guidance untersuchen:** Die Reproduktion ist
mit dem eingefrorenen OSM-Ausschnitt vorhanden. Mit 0 m bleibt das Manöver
erhalten. Falls andere wichtige Entscheidungen trotz dieser Einstellung
fehlen, an der betreffenden `intersection` die verbliebenen OSRM-Regeln
isolieren. `process_turn()` steuert vor allem Kosten; eine bloße Änderung
seiner 45°-Kostenbedingungen ist kein direkter Ansageschalter.

**Falls eine OSRM-Korrektur nicht praktikabel ist:** Eine enge
Normalisierung bei RadlNavi anhand von `intersections`, `in/out`, erlaubten
Alternativen und Routengeometrie prüfen. Die zusätzliche Linksabbiegung muss
am tatsächlichen Knoten liegen, als normale Linksentscheidung gelten und
für Standard und Direct gleich funktionieren. Ein OSRM-kompatibles
Step-Splitting müsste Geometrie, Entfernungen, Zeiten, Intersection-Listen
und Way-Type-Wechsel konsistent halten. Alternativ wäre ein eigenes
Guidance-Feld möglich, das App und Prüffenster explizit verwenden.

**App-Fallback:** Nur wenn die zentrale Korrektur nicht machbar ist,
Intersections als echte Entscheidungspunkte in die App übernehmen und dort
fehlende deutliche Abbiegungen ergänzen. Reine Polygonwinkel reichen dafür
nicht: Eine 90°-Kurve ohne alternative befahrbare Richtung braucht oft keine
Ansage. Das bloße Herabsetzen von 7 m oder 25 m in `_geometryTurns()` ist
kein sicherer Fix.

## Abnahme vor einer Freigabe

- Für diesen exakten Request erscheinen rechts bei ca. 166 m und links
  bei ca. 181 m als zusammenhängende, korrekte Folge: „rechts abbiegen,
  danach sofort links abbiegen“ (ggf. mit „auf Radweg“ nach dem ersten
  Manöver). Die erste Ansage kommt rechtzeitig **vor** dem Rechtsabbiegen.
- Beide Varianten sowie die Anzeige „Hinweise prüfen“ und die App
  zeigen dieselbe Entscheidung. Die Route selbst und die Gesamtdistanz
  bleiben konsistent.
- Gegenbeispiele wie Balanstraße, Waisenhausstraße und der Birketweg
  erzeugen keine erfundenen Abbiegungen oder einseitig abgeschnittenen
  Manöverfolgen. Tests müssen sowohl OSRM-Rohsteps als auch die
  tatsächlich in Flutter gesprochene Folge abdecken.

Die [OSRM-Testanleitung](https://github.com/Project-OSRM/osrm-backend/blob/master/docs/testing.md)
weist darauf hin, dass Turns und ausgegebene Instructions wegen
Nachbearbeitung nicht eins zu eins sein müssen. Die sichtbare
`intersections`-Liste allein beweist daher keine bestimmte interne
OSRM-Unterdrückungsregel.
