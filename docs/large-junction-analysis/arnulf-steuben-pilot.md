# Arnulfstraße / Steubenplatz: Pilot, Schritt 1

Fortschritt: Die [Backend-Zuordnung als Opt-in](../big-junction-pilot-api.md)
ist inzwischen vorbereitet. Der historische Geometrieentwurf unten bleibt
als Prüfbeleg erhalten; App-Verhalten und Deployment sind weiterhin offen.

Stand: 06.11.2026. Branch in RadlNavi und App: `feature/big-conjunctions`.
RadlNavi basiert auf dem aktuellen `origin/main` (`a18de0a`, einschließlich
des gemergten Fixture-Fixes). Der vorherige Fix-Branch bleibt erhalten.

**Umfang dieses Schritts: nur Polygonentwurf und Prüfung der vorhandenen
Route. Keine App-/Backend-Funktion, keine Aktivierung, kein Deployment.**

## Unterlagen

- [Polygonentwurf](arnulf-steuben-draft.geojson), ausdrücklich `enabled: false`.
- [Polygon, Linksroute, Grenzpunkte, API-Hinweise und Querungswege](arnulf-steuben-review.geojson)
  zum Öffnen in einem GeoJSON-Karteneditor, beispielsweise geojson.io.
- [Berechneter Prüfbericht](arnulf-steuben-report.json).

Es ist ausschließlich die gemeldete Beziehung **Arnulfstraße West →
Steubenplatz Nord, links** vorgesehen. Andere Richtungen und die vier
schwierigen Fälle bleiben außerhalb des Piloten.

## Geometrieprüfung

- Geschlossener, nicht selbstschneidender Polygonring, ungefähr 3350 m².
- Die vier Querungswege `35218338`, `35218359`, `61048819`, `379393437`
  liegen vollständig innerhalb des Entwurfs.
- Die Beispielroute schneidet die Grenze genau einmal hinein und einmal
  hinaus: Einfahrt West nach etwa **79 m**, Ausfahrt Nord nach etwa **186 m**
  ab dem gesnappten Beispielstart. Innerhalb liegen ungefähr **107 m** Route.
- Alle drei API-Hinweise (`end of road/right`, `continue/left`, `turn/left`)
  liegen innerhalb. Start und Ziel liegen außerhalb.
- Entfernungen sind geometrische Näherungen; für die spätere App zählen
  deren tatsächlicher Routenfortschritt und Distanzberechnung.

Die Grenze liegt vor dem westlichen Anschlussbogen und hinter dem
nördlichen Radweganschluss. Der Entwurf ist bewusst zur Sichtprüfung gedacht;
die Geometrieprüfung bestätigt noch keine korrekte mobile Ansage oder
Abweichungsbehandlung. Vor Freigabe insbesondere West-Einfahrt und Nord-
Ausfahrt in der Karte bzw. vor Ort prüfen.

Der gespeicherte Beispielstart liegt nur 79 m vor der Einfahrt. Für den
späteren 100-/60-m-Test eine Route mit Start deutlich weiter westlich verwenden;
mindestens 150–200 m Anfahrt zur Einfahrt sind sinnvoll. In diesem Schritt
wurde keine neue Route abgefragt.

## Nächster kleiner Umsetzungsschritt

Nach Prüfung der Grenze nur die Backend-Zuordnung für diese eine
Linksbeziehung vorbereiten: zusätzliche Metadaten für Ein-/Austritt und
Fahrbeziehung, bestehende Route und Steps unverändert. Standardmäßig
ausgeschaltet und mit Rückfall auf bisherige Guidance bei unklarem Treffer.
Erst danach App-Unterstützung, Replay und Testfahrt angehen.

Der spätere App-Pilot soll bei 100 und 60 m vor der Einfahrt ankündigen,
innerhalb die weiteren Navigations-/Abweichungsansagen unterdrücken und beim
falschen Austritt die bisherige Abweichungslogik wieder verwenden. Dieses
Verhalten ist **noch nicht implementiert**.

## Offline erneut prüfen

```powershell
python docs/large-junction-analysis/build_arnulf_pilot.py
```

Die Prüfung nutzt die bereits gesicherte Standardroute und den vorhandenen
OSM-Snapshot vom 06.11.2026. Keine Browser-, Telefon- oder Vor-Ort-Prüfung in
diesem Schritt. OSM-Daten: © OpenStreetMap contributors, ODbL.
