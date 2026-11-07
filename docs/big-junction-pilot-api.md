# Große Kreuzungen: Katalog und API

Stand: 07.11.2026. Der Arnulf-Praxistest war erfolgreich. Der allgemeine
Katalog unterstützt mehrere Kreuzungen, links/geradeaus und wiederholte
Durchfahrten. Katalogfreigabe: **Arnulfstraße/Steubenplatz und
Balanstraße/Chiemgaustraße, jeweils alle acht Links-/Geradeausbeziehungen**.
Die vier schwierigen Fälle bleiben ausgeschlossen.
Siehe [Fahrbeziehungen und Prüfnachweise](large-junction-analysis/full-movements.md).

Neue App-Builds fragen die Zusatzdaten standardmäßig ab. RadlNavis
Einzelhinweise, Route und Geometrie bleiben unverändert. Der Backend-Endpunkt
bleibt opt-in; bestehende Clients ohne Parameter erhalten ihre bisherige Antwort.

## Einschalten pro Anfrage

Standardmäßig wird nichts ergänzt. Für die Kreuzungszuordnung
`junction_guidance=true` zusammen mit `steps=true`, `overview=full` und
`geometries=geojson` senden:

```text
GET /route/v1/bike/11.518913,48.150239;11.520477,48.150871?junction_guidance=true&steps=true&overview=full&geometries=geojson&alternatives=false
```

Nur der Standard-Worker mit Profil `bike` erzeugt Kreuzungsmetadaten. Direct
und Discovery bleiben ohne diese Ergänzung. Das neue Argument wird vor
dem Aufruf des OSRM-Diensts entfernt. `comfort=true` und die bisherige
Annotationenbehandlung bleiben kombinierbar.

Auch das ältere `/route` akzeptiert `junction_guidance=true` und liefert
die Metadaten unter `route.guidance`. Beim OSRM-kompatiblen Endpunkt liegen
sie unter `routes[i].guidance`, separat für jede Alternative.

## Zusätzliche Metadaten

```json
{
  "version": "big-junctions-v1",
  "catalogVersion": "munich-big-junctions-v2",
  "junctions": [{
    "id": "arnulf-steuben",
    "occurrenceId": "arnulf-steuben:west-north-left:leg:0:visit:0",
    "legIndex": 0,
    "movement": "left",
    "entryArm": "west",
    "exitArm": "north",
    "entry": {
      "location": [11.519927399, 48.150025514],
      "geometrySegmentIndex": 2,
      "segmentFraction": 0.76564517,
      "distanceAlongLegMeters": 78.88,
      "distanceAlongRouteMeters": 78.88
    },
    "exit": {
      "location": [11.520497358, 48.150378258],
      "geometrySegmentIndex": 20,
      "segmentFraction": 0.38210719,
      "distanceAlongLegMeters": 186.01,
      "distanceAlongRouteMeters": 186.01
    },
    "suppressedStepIndices": [1, 2, 3]
  }]
}
```

Das Beispiel ist gekürzt und gerundet: Jedes Durchfahrtsobjekt enthält
zusätzlich `polygon` als GeoJSON-Polygon mit der geprüften Bereichsgrenze.
Koordinaten sind `[Länge, Breite]`. Indizes sind nullbasiert;
`geometrySegmentIndex` verweist auf die **unveränderte Route-Geometrie**,
`segmentFraction` interpoliert zwischen diesem Punkt und dem Folgepunkt.
`suppressedStepIndices` referenziert die Steps innerhalb des angegebenen
Legs. Das Backend löscht oder verschiebt keine Steps.

Entfernungen werden geodätisch entlang der Geometrie summiert. Die App
gleicht ihren Routenfortschritt mit dem Einfahrtsanker ab.
Die Beispielroute beginnt nur ca. 79 m vor der Einfahrt; für die geplante
100-/60-m-Ansage ist eine längere Anfahrt nötig.

## Konservative Zuordnung

Die Laufzeitdaten liegen in `backend/src/big_junctions.json` und werden mit
dem Backend-Image ausgeliefert. Das Dokument enthält `schemaVersion`, eine
`version`, `junctions` und explizite `excluded`-Einträge. Jede Kreuzung hat
Kennung, Polygon, Review und eine Liste gerichteter `movements`. Aktivierung
verlangt sowohl an der Kreuzung als auch an der Fahrbeziehung `enabled: true`,
`review.status: approved` und einen Prüfnachweis. Kandidaten werden nicht aus
der Suchliste in diesen Katalog importiert. Die Offline-Prüfung lehnt unter
anderem Selbstüberschneidungen, doppelte Kennungen, ausgeschlossene Kennungen
und eine zum Anschlusswinkel widersprüchliche Fahrbeziehung ab.

Die Zuordnung verlangt:

- Vollständige, zusammenhängende GeoJSON-Step-Geometrien, die exakt die
  Route-Geometrie rekonstruieren. Doppelte aufeinanderfolgende Punkte in
  der Route-Geometrie werden wegen sonst mehrdeutiger Indizes abgelehnt.
- Die für die Fahrbeziehung freigegebenen Ein- und Ausgänge, höchstens 2,5 m
  vom geprüften Grenzpunkt entfernt; Start und Ziel des Legs außerhalb.
- Mindestens 10 m Anfahrt und Weiterfahrt außerhalb der Fläche, deren
  Richtungen höchstens 30° von den geprüften Anschlussrichtungen abweichen.
- Den geprüften inneren Wegverlauf, beidseitig höchstens 2,5 m Abweichung.
  Die Prüfung tastet den Verlauf in höchstens 2-m-Abständen ab und lehnt
  Rückwärtsverlauf bzw. innere Schleifen ab.
- Ausschließlich `cycling`-Steps im betroffenen Leg und eindeutig gepaarte
  Grenzübertritte. Geradeausfahrten dürfen ohne inneren Einzelhinweis sein;
  dann ist `suppressedStepIndices` leer. Wiederholte
  vollständige Durchfahrten erhalten getrennte `occurrenceId`-Werte und
  Step-Intervalle. Mehrere Kreuzungen und Legs werden in Routenreihenfolge
  ausgegeben. Überlappende/mehrdeutige Zuordnungen verwerfen die Zusatzdaten
  dieser Routenalternative.

Andere Ein-/Ausgänge, Gegenrichtung, Abkürzungen, Umwege, Schiebeabschnitte,
Start/Ziel in der betreffenden Fläche, unvollständige oder unklare Geometrien erhalten
keine Kreuzungsmetadaten. Das gilt ebenso für die vier zuvor ausgeschlossenen
schwierigen Kreuzungen.

**Die derzeitige Freigabe gilt nur für die geprüfte innere Route.** Andere
Querungsvarianten sind noch nicht freigegeben. Für eine freie Querungswahl
im späteren App-Pilot müssen diese Varianten und das Wiederanknüpfen an die
Route gesondert geprüft werden.

Ein nicht passender Treffer oder Fehler der optionalen Anreicherung liefert
die gültige bisherige Routingantwort zurück. Ohne Treffer fehlt `guidance`.
Routenwahl, Geometrie, Dauer, Gewicht, Distanz, Steps und Annotationen werden
von diesem Modul nicht verändert. Die Anreicherung erfolgt nach dem bereits
vorhandenen Schiebezugang am Anfang/Ende der Route.

## Prüfung

Die gespeicherte produktive Standardantwort dient als unveränderte Fixture
in `backend/tests/fixtures/arnulf-steuben-route.json`. Herkunft:
[Routenaufnahme und Geometrieprüfung](large-junction-analysis/arnulf-steuben-pilot.md).
Die Tests prüfen positive Zuordnung, falsche Richtungen und Anschlusswinkel,
Schleifen/Umwege/Abkürzungen, Teilrouten, Alternativen, Leg-/Geometrieindizes,
Unveränderlichkeit, Opt-in, beide API-Wege, Comfort und Fehler-Rückfall.

```powershell
backend/.venv/Scripts/python.exe backend/check_big_junction_catalog.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests
```

Der bisherige Arnulf-Pilot wurde live und auf dem Telefon erfolgreich
geprüft. Die verallgemeinerte Technik wird vor Deployment erneut getestet.

## Stadtweite Erfassung

Die separate `docs/large-junction-analysis/munich-review-queue.geojson` enthält
495 Kandidatenpunkte im Münchner Verwaltungsgebiet, keine freigegebenen
Polygone. Ein Kreuzungskomplex kann mehrere Punkte haben; Vierergrad allein
schließt falsche T-Komplexe oder Rampen nicht aus. Jeder Kandidat bleibt bis
zur Polygon- und Fahrbeziehungsprüfung inaktiv. Neue geprüfte Katalogeinträge
benötigen keine App-Änderung bei unverändertem API-Vertrag.

Siehe [Ausbau und Freigabeverfahren](big-junction-rollout.md).
