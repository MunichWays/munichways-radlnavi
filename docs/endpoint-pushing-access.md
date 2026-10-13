# Schiebeanbindung am Start und Ziel (Issue #19)

Die öffentliche API ergänzt kurze Schiebewege an den beiden äußeren Endpunkten.
Die Fahrradroute dazwischen wird von den unveränderten OSRM-Profilen berechnet.
Insbesondere bleiben deren Schiebeaufschlag, Einbahnen, saisonale Sperren,
Seitenwegpflicht und Fährenausschluss erhalten. Zwischenziele bleiben Teil der
normalen Fahrradroute.

## Funktionsweise

`backend/src/endpoint_access.py` verwendet die bereits vorhandenen OSM-Knoten
und Wege in `geo.db`. Ein beim Import gebauter räumlicher Index findet ganze
Wege auch dann, wenn ihre beiden begrenzenden Knoten nicht in unmittelbarer
Nähe des angefragten Punkts liegen.

Eine Anbindung wird nur untersucht, wenn der Endpunkt näher an einem zulässigen
Schiebeweg als an einem fahrbaren Weg liegt. Das gilt auch ohne optionale
OSRM-Steps oder bei bereits passendem Snap auf einen Schiebeweg. Ein gewöhnlicher
Fahrrad-Startpunkt löst keine zusätzlichen OSRM-Abfragen aus. Auch bei
`NoRoute`, beispielsweise wegen einer verbotenen Gegenrichtung, wird ein
Fahrradpunkt nicht einfach auf einen benachbarten Fußweg versetzt.

Der lokale Fußwegegraph enthält öffentliche `footway`, `pedestrian` und
`steps` sowie `path` mit `bicycle=no` oder `dismount`. Für den deutschen
Datenbestand gilt auf diesen öffentlichen Wegen: `bicycle=no` sperrt Fahren,
aber eine Fuß-/Schiebeanbindung kann bestehen. Das ist ausdrücklich keine
weltweite Auslegung des Tags und öffnet keine solchen Wege im Fahrradgraphen.
Explizite Fuß-/Schiebeverbote, private oder andere eingeschränkte Zugänge,
physische Fahrradverbote und nicht passierbare Hindernisse werden ausgeschlossen.
`bicycle=no` an einem Hindernis erfordert eine ausdrückliche Schiebefreigabe.
Ein verschlossenes Fahrzeugtor ist nur mit ausdrücklichem öffentlichem
Fußzugang passierbar. Bedingte Zugänge und zeitlich eingeschränkte Hindernisse
ohne hier unterstützte Auswertung werden konservativ ausgeschlossen.

Der Suchradius für den tatsächlichen Endpunkt beträgt höchstens 20 m. Vom
projizierten Punkt werden ausschließlich verbundene Fußwege bis zu 500 m
Länge durchsucht. Fahrbare Straßen werden nicht als Schiebeabkürzungen genutzt.
`oneway:foot` und richtungsbezogene Fuß-Zugänge gelten auch für die Zielanbindung.
Treppen werden mit 2 km/h, andere Schiebewege mit 4 km/h berechnet.

`backend/src/endpoint_routes.py` vergleicht erreichbare Übergänge zum Fahrradnetz.
Eine Näherung aus Schiebezeit und Luftlinien-Untergrenze priorisiert höchstens
sechs OSRM-Abfragen aus bis zu 64 lokalen Übergängen je Endpunkt. Die Suche
speichert Vorgänger statt vollständiger Pfadkopien je Knoten. Die endgültige
Auswahl verwendet das tatsächliche Gewicht
der normalen Fahrradroute plus die Schiebezeit; Standard behält dabei den
üblichen Basisfaktor 0,55 bei. Der zusätzliche Faktor 10 gilt weiterhin für
Schieben innerhalb der OSRM-Fahrradroute, nicht für die ergänzten Endstücke.
Beim Absteigen am Ende bleibt der Moduswechsel-Aufschlag von 30 im Suchgewicht.
Die zusätzlichen Anfragen teilen sich den Authentifizierungs-Token und ein
Zeitbudget von acht Sekunden. Es handelt sich um eine begrenzte Kandidatensuche,
nicht um eine Garantie des global günstigsten Übergangs.

Wenn beide Endpunkte im selben kleinen Fußwegenetz liegen, ist auch eine
vollständig geschobene Route möglich. Eine Luftlinie zum Fahrradnetz wird nicht
erfunden. Übergänge müssen an echten gemeinsamen OSM-Knoten liegen und durch
OSRM mit höchstens 0,75 m Versatz als Fahrradverbindung bestätigt werden.
Bei unpassenden Kartenständen, fehlendem Index oder fehlender Anbindung bleibt
die bisherige OSRM-Antwort erhalten.

## API und Darstellung

Die Ergänzung gilt für `/route` und `/route/v1/bike/…` in beiden Varianten.
Die Schiebeteile erscheinen als echte `pushing bike`-Steps, fließen in
Gesamtdistanz/-zeit ein und enthalten echte OSM-Annotationsknoten. Die Zahl der
Legs und der benutzerdefinierten Wegpunkte bleibt erhalten. Komfortanalyse und
`analysis_legs` berücksichtigen den vollständigen Weg. GeoJSON, Polyline und
Polyline6 sowie die üblichen Ausgabeoptionen bleiben unterstützt.
Explizite Snap-Hints und die fortgeschrittene Auswahl einzelner Ausgabe-Wegpunkte
werden unverändert an OSRM weitergegeben; dafür wird keine Anbindung ergänzt.
An ersetzten Endpunkten werden interne Snap-Radien auf 0,75 m begrenzt und
Fahrrad-Bearings/Anfahrtsseiten zurückgesetzt; Vorgaben für Zwischenziele bleiben
erhalten. Der ursprüngliche Snap-Radius begrenzt weiterhin die Fußwegprojektion.

Die React-Webkarte zeichnet anhand der geordneten Step-Geometrie getrennte
Fahr- und Schiebeabschnitte. Schieben wird blau gestrichelt dargestellt.
Komfort-, Beleuchtungs- und Oberflächenlinien werden auf Fahrabschnitte begrenzt,
damit sie die Strichlücken nicht ausfüllen. Vollständig geschobene Routen bleiben
sichtbar. Die Flutter-App erhält die üblichen Schiebe-Steps und kann ihre
bereits vorhandene Darstellung nach Step-Modus weiter verwenden.

## Tests und Bereitstellung

Die Backend-Tests prüfen Zugänge, Hindernisse, Richtung, Suchgrenzen, Ausgabeformate,
unveränderte Fahrradteile und beide öffentlichen APIs. Die Frontend-Tests prüfen
insbesondere erste/letzte und vollständige Schiebeabschnitte sowie die Überlagerungen.

```powershell
cd backend
poetry run python -m unittest discover -s tests
cd ../frontend
npm test -- --watchAll=false --runInBand
```

Die CI baut zusätzlich die unveränderten Fahrradprofile auf
`routing/tests/fixtures/munich-endpoint-access.osm` und führt
`routing/tests/test_endpoint_access.py` aus. Die eingefrorenen Beispiele ergeben:

| Beispiel | Hinweg | Rückweg |
| --- | --- | --- |
| Hofgarten A | 109,1 m vollständig Schieben | 109,1 m vollständig Schieben |
| Hofgarten B | 105,1 m über die nahe Torverbindung | 70,1 m über die andere nahe Verbindung |
| Alter Botanischer Garten | 326,1 m, davon etwa 108 m Schieben am Anfang | 364,0 m, Schieben am Ende |

Beide Varianten bestehen diese Tests. Richtungsabhängige Unterschiede im
Fahrradnetz bleiben bewusst bestehen. Der Hauptbahnhof benötigt weiterhin einen
konkreten Start-/Zielpunkt für einen zusätzlichen Regressionstest.

Für Produktion müssen **Backend samt neu erzeugter `geo.db` und Web-Frontend**
aus diesem Branch gebaut und bereitgestellt werden. Die normalen API-Builds
erzeugen den räumlichen Index automatisch; die direkte API muss dasselbe neue
Backend-Image erhalten. Ein alleiniger Routing-Build aktiviert diese Funktion
nicht. Die OSRM-Profile und Graphen benötigen für diese Änderung keinen Neubau.
Möglichst denselben OSM-Datenstand für API-Datenbank und Routing verwenden.
