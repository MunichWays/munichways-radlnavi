# Große Kreuzungen: Identifikation und Ansagemodell

Stand: 06.11.2026. Schritt 1: Analyse und Entscheidungsvorschlag. Keine Änderung
an Routing, API-Vertrag oder App-Verhalten. Die sechs gemeldeten Routen wurden
neu gegen die öffentliche Standard-API abgefragt und vollständig gesichert.

## Empfehlung

Pilot in kleinen Schritten: Der [Arnulfstraße-/Steubenplatz-Entwurf](arnulf-steuben-pilot.md)
enthält zunächst nur Polygon und Routenprüfung für die gemeldete
Linksbeziehung. Er bleibt inaktiv; App und Backend erhalten noch keine
Verhaltensänderung.

Ergänzung: Die [Prüfung vier schwieriger Fälle](difficult-cases.md) zeigt,
dass alle vier trotz ungeeigneter oder ungeklärter Struktur durch die
Vierer-Punktabfrage kommen. Sie bleiben ausgeschlossen. Vereinfachte Ansagen
und die Unterdrückung von „Route verlassen“ benötigen eine explizit geprüfte
Freigabe für die konkrete Kreuzungsdurchfahrt; ein Kandidatenpunkt reicht nie.

Eine große Kreuzung als **manuell geprüfte Fläche mit gerichteten Ein- und
Ausgängen** erfassen. Ein Mittelpunkt dient zum Auffinden und Beschriften.
Für die Ansage zählt die konkrete Einfahrt entlang der gefahrenen Route.
Einzelne Punkte oder ein fester Radius um die Kreuzungsmitte reichen dafür
nicht aus.

Die Erkennung der Kreuzung und ihrer Fahrbeziehung gehört in das
RadlNavi-Backend. Die App erhält eine bereits zugeordnete Kreuzungsdurchfahrt
mit `left` oder `straight`, Beginn und Ende. Sie muss nur deren Darstellung
und Ansage unterstützen sowie interne Detailhinweise in diesem Abschnitt
unterdrücken. Eine kleine App-Anpassung ist erforderlich, insbesondere für
„an der großen Kreuzung“ und das Weglassen von „Hier“.

Für den Einstieg einen versionierten GeoJSON-Katalog im Repository pflegen,
keine Koordinaten-Sonderfälle verteilt über Lua, Backend und App. Zuerst die
gemeldeten Orte prüfen; später weitere Kandidaten halbautomatisch vorschlagen.
Die Annahme einer überschaubaren Zahl in ganz München ist noch nicht durch
eine stadtweite Erhebung belegt.

## 1. Was die aktuellen Beispiele zeigen

Alle Eingabekoordinaten in [cases.json](cases.json) sind **[Breite, Länge]**.
API-URLs und Geometrien verwenden **[Länge, Breite]**. Die Links in der Tabelle
führen zu vollständigen Rohantworten mit URL und Abrufzeit. Entfernungen in
der Manöverspalte sind aufsummierte API-Step-Distanzen ab dem gesnappten Start,
keine vermessenen Kreuzungseinfahrten.

| Fall | Aktuelle API-Manöver ohne Start/Ziel | Folgerung |
| --- | --- | --- |
| [Thomasiusplatz, links](thomasiusplatz-left.json) | Bei 77,9 m `fork/slight left`, bei 112,5 m `turn/left`, bei 145,7 m `turn/right` | Schon die Gabelung auf dem Zufahrtsradweg muss bei der Abgrenzung geprüft werden. Die Folge erstreckt sich über 67,8 m. |
| [Balanstraße → Chiemgaustraße, links](balan-chiemgau-left.json) | Bei 117,4 m `turn/left`, bei 121,2 m `turn/left`, bei 153,1 m `turn/slight right` | Der Abstand zwischen den ersten zwei Hinweisen beträgt nur 3,8 m; bis zum dritten sind es insgesamt 35,7 m. |
| [Arnulfstraße → Steubenplatz, links](arnulf-steuben-left.json) | Bei 92,2 m `end of road/right`, bei 98,9 m `continue/left`, bei 129,0 m `turn/left` | Die beabsichtigte Linksbeziehung beginnt mit einem lokalen Rechtsmanöver. Aus dem ersten Modifier lässt sie sich nicht ableiten. |
| [Ständlerstraße über Balanstraße, geradeaus](staendler-balan-straight.json) | Bei 127,1 m `turn/left`, bei 152,7 m `turn/slight right` | Zwei lokale Richtungsänderungen beschreiben eine übergeordnete Geradeausbeziehung. |
| [Balanstraße über Chiemgaustraße, geradeaus](balan-chiemgau-straight.json) | Bei 117,4 m `turn/left`, bei 121,2 m `turn/slight right` | Der erste Hinweis liegt am selben Ort wie beim Linksabbiegen. Erst der spätere Ausgang unterscheidet die Absicht. |
| [Gemeldet als Rolf-Vogel-Bogen → Otto-Hahn-Ring](rolf-vogel-otto-hahn.json) | Bei 61,5 m einziges Zwischenmanöver `fork/slight left` | Sonderfall: Nicht ungeprüft „große Kreuzung geradeaus“ daraus machen. Die gemeldete Rechts-/Linksfolge muss am Verlauf separat eingeordnet werden. |

Alle sechs Antworten enthalten ausschließlich `cycling`-Steps. Die größte
gemeldete Snap-Entfernung beträgt 3,88 m. Das beweist nicht, dass jeweils die
gewünschte Wegseite getroffen wurde. Die gerundeten Steps können außerdem von
der Route-Gesamtdistanz um 0,1 m abweichen.

Die [Versionsauskunft](version.json) beim Abruf nennt Backend/Routing 2.4.0,
OSRM 26.6.5, Backend-Commit `29846553f85f2b074cc28764747b1c6041b2f200`
und Routing-Commit `a18de0a0eda92cdc412903aae9617f492550781c`.
Analysierter RadlNavi-Checkout: `1cce700288ae8891cfb733ac391b89cba70bf46f`.
Die sechs Antworten bestätigen die gemeldeten Backend-Folgen; eine tatsächliche
Sprachausgabe auf einem Telefon wurde damit nicht reproduziert.

## 2. Lassen sich die Orte direkt aus OSM erkennen?

**Es gibt brauchbare Hinweise, aber kein hier nachgewiesenes vollständiges
Kennzeichen für die gewünschte Kategorie „große Radverkehrskreuzung“.**

`junction=yes` kann eine Kreuzung als Punkt oder Fläche bezeichnen. Nach der
OSM-Dokumentation sind normale Kreuzungen bereits durch gemeinsame Straßenknoten
definiert; eine explizite Markierung ist nicht allgemein erforderlich.
Eine vorhandene Fläche kann deshalb übernommen und geprüft werden, ihre
Abwesenheit darf einen Ort aber nicht ausschließen.
[Quelle: OSM junction=yes](https://wiki.openstreetmap.org/wiki/Tag:junction%3Dyes).

Der [OSM-Snapshot](osm-examples.json) enthält 264 Objekte: 244 Highway-Wege
und 20 Ampelknoten, Datenstand `2026-11-06T10:25:06Z`. In jedem der fünf
abgefragten Ausschnitte liegen vier `highway=traffic_signals`-Knoten, aber
kein abgefragtes Objekt mit `junction=yes`. Die Ausschnitte und Filter stehen
in [examples.overpassql](examples.overpassql). Das ist eine lokale Stichprobe;
andere Kennzeichnungen und die Vollständigkeit ganz Münchens wurden nicht erhoben.

Auch die Wege sind uneinheitlich modelliert. Die gesicherte Rolf-Vogel-Route
führt beispielsweise über `highway=path` mit `bicycle=designated`; die
Querung auf OSM-Weg `1026802750` trägt `cycleway=crossing`. Der benannte
Zufahrtsweg heißt im Snapshot **Rudolf-Vogel-Bogen**, die große Querstraße
**Carl-Wery-Straße**. Diese Namen und die genaue Zuordnung des Sonderfalls
bei der manuellen Erfassung prüfen.

Die Suche darf daher nicht nur `highway=cycleway` berücksichtigen. OSM erlaubt
sowohl separat gezeichnete Radwege als auch `cycleway:*`-Attribute an Straßen.
[Quelle: OSM cycleway](https://wiki.openstreetmap.org/wiki/Key:cycleway).

Ampelknoten allein liefern ebenfalls keine Kreuzungsfläche oder aktuelle
Ampelphase. OSM beschreibt verschiedene Möglichkeiten, Signale an einem
zentralen Knoten oder an einzelnen Zufahrten zu verorten.
[Quelle: OSM traffic_signals](https://wiki.openstreetmap.org/wiki/Tag:highway%3Dtraffic_signals).

**Halbautomatischer Suchvorschlag für später:**

1. Ampeln und signalgeregelte Rad-/Fußquerungen entlang größerer Straßen
   sammeln. Straßen mit getrennten Richtungsfahrbahnen räumlich und anhand
   ihrer Netzverbindungen zu einem Kreuzungskomplex gruppieren.
2. Straßenarme außerhalb dieses Komplexes bestimmen. Vier logische Arme und
   Radverkehrsverbindungen an mehreren Seiten erhöhen die Priorität.
   Rohe Knotengrade oder die Anzahl gezeichneter Wege sind dafür ungeeignet.
3. Für jede Zufahrt Links- und Geradeausrouten ansehen. Mehrere kurze
   Richtungsmanöver, getrennte Furten und Inseln sind zusätzliche Hinweise.
   Die sechs Beispiele zeigen, weshalb dies keine feste 30-m-Regel sein darf.
4. Kandidaten in der Karte prüfen: Bereich, erste Wegentscheidung, Furten,
   Wegseiten, zulässige Richtungen und Nachbarkreuzungen. Erst danach aktivieren.

Die Entfernungsgrenzen für die Kandidatensuche müssen an mehreren Orten
kalibriert werden. Eine dichte Ampelgruppe kann auch aus mehreren getrennten
Kreuzungen bestehen. Eine vollständig automatische Zusammenfassung wäre mit
dem bisherigen Nachweis zu unsicher.

## 3. Fläche oder Punkte?

Ergänzung: Der [konkrete Polygon-Workflow mit drei Overpass-Turbo-Abfragen](polygon-workflow.md)
prüft die Kandidatensuche über Straßenknoten. Er berücksichtigt auch die als
`tertiary` erfasste Balanstraße und beschreibt die anschließende manuelle
Abgrenzung der Radverkehrsflächen.

| Modell | Vorteil | Grenze |
| --- | --- | --- |
| Mittelpunkt | Einfacher Suchindex und Kartenmarker | Keine richtungsspezifische Einfahrt, falscher Bezug für die Entfernung |
| Mittelpunkt mit Radius | Schnell zu erfassen | Schließt bei asymmetrischen Kreuzungen zu viel oder zu wenig ein; benachbarte Wege können hineinragen |
| Einzelne Ein-/Ausgangspunkte | Beschreiben die benutzte Zufahrt | Punkt muss nicht exakt auf der aktuellen Route liegen; ohne Flächenbezug fehlt der zusammengehörige Innenbereich |
| Polygon allein | Begrenzt den gesamten Kreuzungskomplex | Liefert noch keine Fahrbeziehung und kann bloß vorbeiführende Routen schneiden |
| **Polygon + gerichtete Ein-/Ausgangstore** | Bereich, Straßenarm, Wegseite und Beginn gemeinsam erfassbar | Etwas mehr manuelle Prüfung; für die erste kleine Auswahl vertretbar |

Ein Tor ist eine kurze Linie quer zum jeweiligen Radweg an der Grenze des
Bereichs, mit zugehörigem Straßenarm und erlaubter Durchfahrtsrichtung. Ein
Punkt mit Richtung und Toleranz kann intern als einfachere Variante dienen;
die Torlinie macht das Schneiden mit der Routengeometrie eindeutiger.
Ein Tor sollte vor der ersten zusammenzufassenden Wegentscheidung bzw. Furt
liegen. Es ist nicht zwangsläufig der Ampelknoten auf der Autostraße.

Die Fläche umfasst den zusammengehörigen Radverkehrsbereich einschließlich
versetzter Furten und erforderlicher Zufahrtsverzweigungen. Sie ist keine
Behauptung über eine amtliche Kreuzungsgrenze. Am Thomasiusplatz darf sie zum
Beispiel nicht erst hinter der bereits gemeldeten Gabelung beginnen.

**Vier Richtungen bedeuten vier Straßenarme, nicht vier physische Punkte.**
Bei getrennten Radwegen gibt es typischerweise je Arm eine Einfahrt und eine
Ausfahrt, also acht gerichtete Tore. Bei Zweirichtungsradwegen können Ein- und
Ausfahrt dieselbe Lage teilen; weitere Wege können zusätzliche Tore erfordern.

Die vorgeschlagenen **acht Fahrbeziehungen insgesamt** stimmen für eine
reguläre vierarmige Kreuzung, wenn jede der vier Zufahrten links und geradeaus
bekommt. Nicht acht pro Richtung:

| Einfahrt von | Geradeaus nach | Links nach |
| --- | --- | --- |
| Nord | Süd | Ost |
| Ost | West | Süd |
| Süd | Nord | West |
| West | Ost | Nord |

Diese Tabelle beschreibt logische Zielarme. Sie sagt noch nichts darüber,
welche konkreten Querungswege dafür erlaubt oder sinnvoll sind. Einmündungen,
schräge Straßenarme und der Rudolf-Vogel-Sonderfall dürfen mehr oder weniger
Beziehungen haben. Rechtsabbiegen bleibt zunächst außerhalb der Zusammenfassung.

## 4. Katalog und Zuordnung zur Route

Vorgeschlagene Datenstruktur, noch kein implementierter API-Vertrag:

| Bestandteil | Inhalt |
| --- | --- |
| Identität | Stabile Kreuzungs-ID, Name, Katalogversion, Prüfdatum |
| Bereich | GeoJSON-Polygon, Mittelpunkt optional für Suche/Anzeige |
| Straßenarme | Stabile lokale IDs; Bezeichnung und äußere Fahrtrichtung |
| Tore | Linie, Arm-ID, Ein-/Ausgang, Wegseite, Richtung; optionale OSM-Referenzen |
| Fahrbeziehungen | Geprüftes Eingang-/Ausgangspaar mit `left` oder `straight` |
| Querungsvarianten | Bei Bedarf mehrere getrennt geprüfte Wegfolgen für dieselbe logische Fahrbeziehung |
| Freigabe | Aktiv nur für geprüfte Beziehungen; ungeprüfte bleiben bei normalen Hinweisen |

OSM-Weg- und Knoten-IDs sind hilfreiche Referenzen, aber wegen möglicher
Wegteilungen nicht die alleinige Identität. Beim Kartenupdate prüfen, ob Tore
noch die erwarteten Wege schneiden. Ein nicht mehr eindeutiger Treffer fällt
auf normale OSRM-Hinweise zurück.

Zuordnung im Backend:

1. Kandidaten über die Routen-Bounding-Box vorfiltern.
2. Die **geordnete Routengeometrie** mit dem Bereich und dessen Toren schneiden,
   auch wenn zwischen zwei Geometriepunkten eine Grenze überquert wird.
3. Eine zusammenhängende Durchfahrt mit Eintritt und Austritt bestimmen.
   Straßenarm, Fahrtrichtung, Wegseite und geprüfte Fahrbeziehung abgleichen.
4. `left` oder `straight` aus diesem Paar übernehmen. Die lokalen OSRM-Modifier
   innerhalb des Bereichs entscheiden das übergeordnete Manöver nicht.
5. Eintritt, Austritt und interne Steps für dieses konkrete Routenvorkommen
   als zusätzliche Guidance-Metadaten zurückgeben.

Jede Alternative und jedes Leg wird separat behandelt. Schleifen können
dieselbe Kreuzung mehrfach durchfahren; eine Kreuzungs-ID allein identifiziert
kein Ereignis. Start, Ziel oder Zwischenhalt innerhalb der Fläche ergeben
keine vollständige Durchfahrt und erhalten zunächst die normalen Hinweise.
Dasselbe gilt bei bloßer Berührung, falscher Richtung, unklaren Toren,
überlappenden Bereichen oder einer nicht freigegebenen Beziehung.

Für einen ersten Piloten Balanstraße/Chiemgaustraße wählen: Zwei gemeldete
Routen haben dieselbe Einfahrt, aber unterschiedliche Ausfahrten. Daran lässt
sich das Kernprinzip mit wenigen Daten prüfen. Anschließend Thomasiusplatz
und Arnulfstraße für größere und asymmetrische Bereiche, Ständlerstraße für
Geradeaus. Den Rudolf-Vogel-Fall gesondert abnehmen. In diesem Schritt wurden
noch keine produktiven Polygone oder Torpositionen festgelegt.

## 5. Entfernung und Ansage

Der Backend-Treffer enthält die Eintrittsposition als Segmentindex mit Anteil
auf der geordneten Route und als Entfernung ab Leg-Beginn. Der Segmentbezug
verhindert Verwechslungen bei wiederholten Koordinaten und Schleifen. Die
Position liegt auf der Route, auch wenn sie kein vorhandener OSM-Knoten ist.

Die App verwendet ihren bestehenden Routenfortschritt:

```text
x = verbleibende Strecke entlang der Route bis zum Eintrittstor
```

Keine Luftlinie und keine Entfernung zum Mittelpunkt, zweiten Ampelmast oder
ersten zufällig gelieferten Step. Die Entfernung wird während der Anfahrt
aktualisiert und nach den vorhandenen Sprachregeln gerundet.

Ergänzung des Nutzers: **zwei Vorhinweise bei 100 m und 60 m; innerhalb der
Kreuzungsfläche keine weiteren Navigationsansagen und keine Meldung „Route
verlassen“.** Eine Routenabweichung wird erst beim Verlassen der Fläche in
falscher Richtung wieder nach dem bisherigen Verfahren behandelt.

| Phase | Hinweis/Ansage |
| --- | --- |
| 100 m vor der Einfahrt | „In 100 Metern an der großen Kreuzung links abbiegen.“ bzw. „In 100 Metern an der großen Kreuzung geradeaus fahren.“ |
| 60 m vor der Einfahrt | Dieselbe Anweisung mit „In 60 Metern …“ |
| Ab Eintritt in die Kreuzungsfläche | Keine weitere Kreuzungs-, Detailabbiege- oder „Hier“-Ansage; „Route verlassen“ unterdrücken |
| Austritt über einen zur Fahrbeziehung passenden Ausgang | Normale Navigation auf der anschließenden Route fortsetzen |
| Austritt über einen falschen Ausgang oder in falscher Richtung | Unterdrückung beenden; Routenabweichung und „Route verlassen“ wie bisher behandeln |

Es gibt damit **keine zusätzliche Sofortansage an der Einfahrt**. Die
Kreuzungsanweisung kann innerhalb des Bereichs als Orientierung sichtbar
bleiben, ohne neue gesprochene Hinweise auszulösen oder „Hier“ einzublenden.
Warten an der Ampel löst keine Wiederholung aus.

Vorgeschlagene technische Randfallregeln: Jede Schwelle pro Durchfahrt nur
einmal beim Unterschreiten auslösen, ohne eine exakte GPS-Messung bei 100 oder
60 m vorauszusetzen. Bei verspätetem Einstieg oder einem Positionssprung keine
beiden Ansagen nachholen; nur einen noch passenden Hinweis mit der tatsächlich
verbleibenden, gerundeten Entfernung geben. Innerhalb der Fläche auch keine
verspätete Voransage abspielen. Schwellenzustand bei GPS-Pendeln, Pause oder
Neuberechnung nicht unbeabsichtigt zurücksetzen.

Für das Ende der Unterdrückung zählt die tatsächliche Position relativ zur
Fläche, nicht allein der Fortschritt auf der ursprünglich berechneten Linie.
Ein abweichender Querungsweg darf also weder einen vorzeitigen Austritt noch
eine endlose Stummschaltung verursachen. Austritt und Richtung durch mehrere
verlässliche Positionsmessungen bzw. eine kleine Grenztoleranz bestätigen;
ein einzelner GPS-Ausreißer reicht nicht. Die genaue Toleranz bleibt in der
Umsetzung zu bestimmen.

## 6. Möglichst viel in RadlNavi, kleine App-Anpassung

Im aktuellen Backend ist `get_endpoint_routing_response()` in
[`backend/src/app.py`](../../backend/src/app.py) die gemeinsame Stelle für
`/route/v1/...` und das ältere `/route`. Dort wird bereits der optionale
Schiebezugang nachverarbeitet. Eine Kreuzungsanreicherung sollte nach dieser
finalen Routengeometrie erfolgen und in Standard, Direct und Discovery denselben
Katalog verwenden. Die Zuordnung selbst bleibt variantenabhängig, weil die
Routen unterschiedlich verlaufen können.

Die erste Untersuchung deckt nur die sechs Standardrouten ab. Direct,
Discovery, Gegenrichtungen, weitere Zufahrten und die tatsächlichen mobilen
Anfragen sind vor Freigabe separat zu prüfen.

OSRM liefert einzelne Steps und darin lokale `intersections`. Das sind keine
fertigen übergeordneten Kreuzungskomplexe. Ein Step beschreibt das Manöver
und die Fahrt **danach** bis zum nächsten Step. Einfaches Verschieben oder
Löschen solcher Steps würde auch Geometrie-, Distanz- und Intersection-Bezüge
betreffen. Deshalb rohe OSRM-Steps zunächst erhalten und die Zusammenfassung
als optionale Metadaten anbieten.
[Quelle: OSRM HTTP-Vertrag v26.6.5](https://github.com/Project-OSRM/osrm-backend/blob/v26.6.5/docs/http.md).

Vorschlag: `routes[].guidance` mit eigener Version und einer Liste erkannter
Durchfahrten. Jede enthält Kreuzungs-ID, Leg-/Vorkommensbezug, `movement`,
Eintritts- und Austrittsposition sowie Referenzen auf die enthaltenen Steps.
Die genaue Benennung bleibt der Umsetzung vorbehalten. Fehler der optionalen
Zuordnung dürfen eine gültige Route nicht verhindern. Alte Clients ignorieren
die zusätzlichen Daten und behalten ihre bisherigen Hinweise.

Ein Eingriff in Lua-`process_turn` wäre dafür nicht die passende erste Ebene:
Die Schnittstelle beeinflusst Abbiegekosten und Fahrzeit und verfügt nicht
über eine fertig gewählte vollständige Kreuzungsdurchfahrt.
[Quelle: OSRM Profilvertrag v26.6.5](https://github.com/Project-OSRM/osrm-backend/blob/v26.6.5/docs/profiles.md).

Die aktuelle Flutter-App wurde **nur lesend** geprüft, Checkout
`ef9efd82ddba0078c11a7f95b0e57e9340a71fab`, die drei untersuchten Dateien
ohne lokale Änderungen:

- `lib/api/radlnavi_api.dart`, `parseResponse()`: Übernimmt Typ, Modifier,
  Straßenname und Wegtyp in `RouteManeuver`; noch kein Kreuzungskontext.
- `lib/model/route.dart`, `RouteManeuver`: Noch keine Eintritts-/Austrittsintervalle
  oder Makromanöver-Metadaten.
- `lib/ui/map/voice_guidance.dart`, `setRoute()`: Projiziert Hinweise auf die
  Route, ergänzt `_geometryTurns()` und filtert flache Gegenmanöver mit
  `_withoutStraightOffsetPairs()`. Deshalb könnte ein rein serverseitiges
  Entfernen von Steps ungewollt wieder durch Geometriehinweise ergänzt werden.
- `formatManeuver()`, `_formatDisplay()` und die Startvorschau erzeugen „Hier“
  selbst. Ein API-Text allein erreicht die gewünschte Ausgabe nicht.

Kleinster sinnvoller App-Umfang: optionale Metadaten einlesen, ein geschütztes
Makromanöver mit den Vorhinweisen bei 100 und 60 m verwenden und innerhalb
der Kreuzungsfläche Detail-/Geometriehinweise sowie Abweichungsansagen
unterdrücken. Dazu muss die App die Fläche und die zur Fahrbeziehung passenden
gerichteten Ausgänge erhalten; das Routenintervall allein reicht bei einer
abweichenden Querungsfolge nicht. Die Ausnahme endet beim bestätigten Austritt.
Die fachliche Identifikation bleibt im Backend. Der App-Umfang umfasst damit
auch Zustand, Bereichserkennung und Abweichungsbehandlung, nicht nur Textformatierung.
Auch die Web-Prüfansicht muss die neue Guidance getrennt von den Roh-Steps
anzeigen können; deren heutige Browsertexte belegen keine mobile Ansage.

## 7. Freie Querungswahl nach Ampelphase

Die übergeordnete Ansage lässt die Reihenfolge der inneren Querungen offen.
Sie liefert aber weder aktuelle Ampelphasen noch automatisch eine andere
zulässige Route. Rechts-/Linksfolgen dürfen nicht allein deshalb gleichgesetzt
werden, weil sie geometrisch in dieselbe Richtung enden.

Mit der Ergänzung gilt die Unterdrückung von „Route verlassen“ **innerhalb
der gesamten zugeordneten Kreuzungsfläche**, auch wenn Nutzer von der
berechneten inneren Querungsfolge abweichen. Die Stummschaltung ist keine
Aussage über die Zulässigkeit eines Wegs; sie lässt die Wahl der Querungsfolge
für die Ansage offen. Sie beginnt erst mit der tatsächlichen Einfahrt in eine
erkannte Kreuzungsdurchfahrt, nicht schon bei der 100-m-Voransage und nicht
bei beliebigen Routen in der Nähe.

Als Umsetzungsvorschlag auch die automatische, durch innere Abweichung
ausgelöste Neuberechnung bis zum Austritt zurückstellen. Sonst könnte eine
stille Neuberechnung den vorgesehenen Ausgang ändern, den Kreuzungszustand
zurücksetzen oder neue Hinweise erzeugen. Beim passenden Ausgang an die
anschließende Route anknüpfen. Beim falschen Ausgang die Ausnahme beenden
und die bisherige Abweichungs- und Neuberechnungslogik wieder anwenden.

„Falsche Richtung“ wird anhand des zur Fahrbeziehung passenden Ausgangs und
seiner Fahrtrichtung bestimmt, nicht anhand der momentanen Fahrtrichtung
innerhalb der Kreuzung. Dort gehören Rechts-/Linksschwenks gerade zum
Problem. Auch Umkehren und Verlassen über die Einfahrt beendet die Ausnahme.
Außerhalb darf ein Aufenthalt in einem anderen Teil derselben Kreuzung nicht
erneut pauschal stummschalten; dafür ist eine neu zugeordnete Durchfahrt nötig.

Zulässige Querungsvarianten und das Wiederanknüpfen am richtigen Ausgang
müssen weiterhin geprüft werden. Mit dieser Ergänzung gehört das
Fortschritts-/Abweichungsverhalten bereits zur ersten Umsetzung; es ist nicht
mehr nur eine spätere optionale Erweiterung der Ansage.

## 8. Abnahme für den nächsten Schritt

- Die sechs gespeicherten Fälle liefern das gewünschte Makromanöver nur nach
  manueller Freigabe ihrer konkreten Beziehung; der Sonderfall wird eigenständig
  bewertet. Rechtsabbiegen behält die bisherigen Hinweise.
- Pro regulärer Kreuzung alle acht logischen Beziehungen prüfen, sofern
  zulässig, und die tatsächlichen Torpaare einschließlich Wegseiten testen.
- Start/Ziel im Bereich, Halt als Zwischenziel, bloßes Vorbeifahren,
  Gegenrichtung, Schleife und zwei nahe Kreuzungen: keine falsche Zusammenfassung.
- Mehrere kurze interne Steps, fehlender API-Step und zusätzliche App-Geometrieecke:
  dieselbe übergeordnete Anweisung bei 100 und 60 m, keine weiteren Ansagen
  an der Einfahrt oder innerhalb der Fläche.
- Beide Vorhinweise messen bis zum Eintrittstor; Stillstand und GPS-Pendeln
  wiederholen sie nicht. Anzeige und Startvorschau enthalten kein „Hier“.
  Bei verspätetem Einstieg keine veralteten oder unmittelbar doppelten Ansagen.
- Raw-Steps, Route, Gewichte, Dauer, Distanz und Annotationen bleiben bei einer
  reinen Metadatenanreicherung gleich. Ungültiger Katalogtreffer erhält die
  ursprüngliche Guidance. Beide API-Wege und alle drei Varianten prüfen.
- Für freie Querungswahl: beide erlaubten Wege per App-Replay und vor Ort
  prüfen. Innerhalb der Fläche auch abseits der berechneten Linie keine
  Navigationsansage und keine Meldung „Route verlassen“.
- Passender Ausgang: ohne falsche Abweichungsmeldung die normale Navigation
  fortsetzen. Falscher Ausgang, falsche Ausfahrtrichtung oder Umkehr durch die
  Einfahrt: nach bestätigtem Austritt die bisherige Abweichungslogik aktivieren.
- Warten auf der Grenze, GPS-Ausreißer, Pause und Neuberechnung: kein
  vorzeitiges Ende der Unterdrückung, keine Wiederholung der Vorhinweise und
  keine Stummschaltung nach tatsächlichem Verlassen der Fläche.

## Belege erneut auswerten

Ohne Netzwerk die sechs gespeicherten Antworten zusammenfassen:

```powershell
python docs/large-junction-analysis/collect.py
```

Die Rohantworten bewusst durch aktuelle öffentliche Abfragen ersetzen:

```powershell
python docs/large-junction-analysis/collect.py --refresh
python docs/large-junction-analysis/collect.py --osm
```

`--refresh` ruft die Version und sechs Standardrouten ab. `--osm` ersetzt den
OSM-Snapshot für die fünf Ausschnitte. OSM und die produktiven Routinggraphen
können unterschiedliche Datenstände haben; der Overpass-Zeitstempel ist kein
Nachweis des im Routing verwendeten OSM-Stands. OSM-Daten: © OpenStreetMap
contributors, [ODbL](https://www.openstreetmap.org/copyright).

Die Auswertung der eingefrorenen Antworten und Datenkonsistenz wurden lokal
geprüft. Es wurde kein verändertes Routing gebaut und kein Telefonlauf
durchgeführt. Frühere App-Analysen im Repository dokumentieren andere
Code-Stände und ersetzen die aktuelle Prüfung nicht.
