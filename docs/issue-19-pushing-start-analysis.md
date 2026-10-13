# Issue #19: fehlender erster Fuß-/Schiebeabschnitt

Prüfung am 2026-10-13 zu
[Issue #19](https://github.com/MunichWays/munichways-radlnavi/issues/19).
Quellstand: `4d56bd7`, beide Routing-Profile; keine Änderung am Routing-Code.
Die kompakten Messdaten stehen in
[measurements-2026-10-13.json](issue-19-analysis/measurements-2026-10-13.json).

Die anschließende [Umsetzung der Endpunkt-Anbindung](endpoint-pushing-access.md)
ergänzt die API, ohne die Fahrradprofile zu ändern. Ihre Bereitstellung benötigt
ein neues Backend samt Datenbank und das Web-Frontend, keinen neuen OSRM-Graphen.

## Produktive API

Abgefragt wurde `https://api.radlnavi.munichways.de/route/v1/bike/…`
mit `variant=standard` beziehungsweise `direct`, `overview=full`,
`geometries=geojson`, `steps=true`, `annotations=nodes,distance` und
`alternatives=false`. Beide Varianten lieferten für diese Beispiele dieselben
Geometrien, Distanzen und Zeiten.

| Beispiel | Start → Ziel (Breite, Länge) | Versatz am Start | Route |
| --- | --- | --- | --- |
| Hofgarten A | 48.143125, 11.579101 → 48.142766, 11.578120 | 69,2 m | 12,7 m, ausschließlich Schieben |
| Hofgarten B | 48.142871, 11.578351 → 48.142715, 11.578114 | 8,9 m | 741,4 m, großer Umweg |
| Alter Botanischer Garten | 48.141857, 11.563519 → 48.143933, 11.565723 | 47,4 m zur Elisenstraße | 616,1 m |

Hofgarten A liefert aktuell `code=Ok` und eine kurze Route. Die im Issue
beschriebene leere Route ist so nicht reproduziert; der weit versetzte Start
und der fehlende Weg vom ursprünglichen Standort sind dagegen nachweisbar.
Die API-Antwort beginnt bereits am versetzten Punkt, bevor ein Client sie zeichnet.

## Ursache 1: Wege werden vollständig ausgeschlossen

Die nächsten OSM-Wege an den gemeldeten Starts sind Fußwege mit `bicycle=no`:

- Hofgarten A: Wege `3791705` und `3790922`, etwa 0,1 beziehungsweise 1,3 m entfernt.
- Hofgarten B: Weg `3790920`, etwa 0,1 m entfernt.
- Alter Botanischer Garten: Weg `22907590`, etwa 2,1 m entfernt, zusätzlich
  `foot=designated`.

In `routing/bike.lua` lehnt `handle_bicycle_tags` einen gefundenen
Fahrrad-Zugangswert aus der Blacklist bereits vor `bike_push_handler` ab.
Zusätzlich setzt `process_way` bei `bicycle=no` beide Geschwindigkeiten auf null.
Eine Änderung nur an einer dieser Stellen genügt deshalb nicht.

Startpunkte im Modus `pushing_bike` sind ausdrücklich erlaubt. Die originale
OSRM-Funktion `WayHandlers.startpoint` berücksichtigt diese Einstellung.
Fußwege ohne `bicycle=no` erscheinen auch in der produktiven Antwort bereits als
`pushing bike`. Ein genereller Ausschluss aller Schiebe-Startpunkte ist daher
nicht die Ursache.

## Ursache 2: Schiebeaufschlag beeinflusst die Wahl des Ausgangs

Auf zwei kleinen, aktuellen OSM-Ausschnitten wurden temporäre lokale Graphen
mit OSRM 26.6.5 erstellt. Als diagnostischer Gegenversuch wurde in einer Kopie
der Daten `bicycle=no` auf öffentlichen Fuß-/Gehwegen ohne explizites
Fußgänger-/allgemeines Zugangsverbot durch `bicycle=dismount` ersetzt.
Es wurden weder OSM bearbeitet noch Repository-Profile geändert.

Mit dieser Datenkopie beginnen die Routen auf den betroffenen Wegen:

- Hofgarten A: 109,2 m, vollständig Schieben; Startversatz praktisch null.
- Hofgarten B: 105,1 m über die nahe Verbindung am Tor; etwa 47 m Schieben
  am Anfang statt des langen Umwegs.
- Alter Botanischer Garten: Startversatz 2,1 m und 52,5 m Schieben am Anfang,
  anschließend dennoch über die Elisenstraße; insgesamt 653,0 m.

Für einen weiteren Gegenversuch wurde ausschließlich in einer temporären
Profilkopie `pushing_distance_penalty` von 10 auf 1 gesetzt. Physische
Geschwindigkeiten blieben unverändert. Im Alten Botanischen Garten wählen dann
beide Profile 326,2 m mit 107,7 m Schieben am Anfang, anschließend Sophienstraße
und Katharina-von-Bora-Straße. Die Zeit beträgt 167,1 statt 187,7 Sekunden.
Das belegt einen zusätzlichen Einfluss des Schiebeaufschlags.

Die Ausschnitte sind keine vollständigen Produktionskarten. Insbesondere am
Hofgarten beeinflussen abgeschnittene Verbindungen und Komponenten die
unveränderten lokalen Vergleichsrouten. Die experimentellen Distanzen sind
deshalb keine zugesicherten Produktionswerte. Der Hauptbahnhof ist mangels
konkreter Koordinaten im Issue noch nicht geprüft.

## Umsetzungsvorschlag

1. Fahrradfahren und Schiebezugang getrennt auswerten. Zulässige Fuß-/Schiebewege
   müssen als `pushing_bike` im Graphen erhalten bleiben und als Start/Ziel
   verwendbar sein. Fußgänger-Zugang, echte Mitnahmeverbote und Hindernisse
   separat beachten. Die Gegenrichtungs- und Seitenwegschutzregeln erhalten.
2. Die Behandlung von `bicycle=no` ausdrücklich festlegen. Der Wert allein
   beantwortet die Schiebefrage nicht international eindeutig; `bicycle=dismount`
   ist die ausdrückliche Freigabe zum Schieben. Der diagnostische Austausch ist
   daher noch keine allgemein gültige Zugangsregel.
   Siehe [OSM-Dokumentation](https://wiki.openstreetmap.org/wiki/Tag:bicycle%3Ddismount).
3. Unvermeidbare Schiebeabschnitte am Start/Ziel gezielt bewerten. Faktor 10
   nicht ohne Regressionen global entfernen: Er wurde bewusst eingeführt,
   damit das Routing keine unnötigen Schiebeabkürzungen nutzt. Eine gesonderte
   Endpunkt-Anbindung muss echte Wege und mehrere erreichbare Übergänge prüfen;
   ein frei gezeichneter Luftlinienverbinder ersetzt das nicht.
4. Die in OSRM gelieferten Schiebe-Steps einschließlich des ersten Steps
   gestrichelt darstellen und in Distanz/Zeit aufnehmen. Die Flutter-App hat
   bereits eine Darstellung nach Step-Modus; das React-Frontend zeichnet
   seine gestrichelten Overlays derzeit nach Komfortklassen. Die Behandlung
   vollständig geschobener Routen und des letzten Fußabschnitts mitprüfen.

## Erforderliche Regressionen

- Die drei konkreten Koordinatenpaare als eingefrorene OSM-Fixtures, beide Profile.
- Start und Ziel auf Fuß-/Schiebeweg, nur Schieben, sowie Übergang Schieben/Fahren.
- Kleine Startversätze, erster Step `pushing bike`, vollständige Geometrie und
  korrekte Distanz/Zeit; am Hofgarten B die nahe Torverbindung statt des Umwegs.
- Fußgänger-/allgemeine Sperren, Mitnahmeverbote, Hindernisse, saisonale Sperren,
  Einbahnen und `use_sidepath` bleiben wirksam.
- Kurze Endpunkt-Anbindung gegenüber langer Fahrradschleife; gleichzeitig
  unnötige Schiebeabkürzungen innerhalb einer normalen Fahrradroute vermeiden.
- Client-Test: erster Schiebeabschnitt gestrichelt und vollständig sichtbar;
  vollständige Schieberoute bleibt planbar.

Nach einer Profiländerung müssen beide OSRM-Graphen neu aufgebaut werden.
