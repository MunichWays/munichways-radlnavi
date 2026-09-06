# Qualitätsprüfung vor Commit: Direkte Route

Geprüft am 06.09.2026: gesamter Branch seit `main`, einschließlich der noch
uncommitteten Versionsänderungen; App-Code auf Commit `21f6bc4` nur gelesen.
Versionsdateien zum Abschluss: Backend, Routing und Frontend jeweils 2.3.0.
Die während der QA vorgenommenen Versionsangleichungen wurden beibehalten;
funktionale Frontend-Änderungen enthält dieser Branch weiterhin nicht.

## Gefundene und korrigierte Probleme

1. **Fähren mit fester Dauer waren im Direktprofil nicht befahrbar.** Das gemeinsame
   Profil setzt bei `duration=00:05` eine Dauer, aber keine Geschwindigkeit.
   Direkt setzte das Distanzgewicht bisher nur für Kanten mit Geschwindigkeit.
   Jetzt erhalten auch zugelassene Kanten mit fester Dauer eine Rate von 1.
   Gegen denselben Testfall mit befahrbaren Zu-/Abfahrten liefert das bisherige
   Profil `NoRoute`; die Korrektur liefert eine Route mit Gewicht in Metern und
   erhaltener Fährdauer. Das Standardprofil wurde nicht geändert.
2. **Fehler am OSRM-Zugang der separaten Direkt-API waren unstrukturierte 500.**
   Der optionale Gateway hatte bereits Fehlerbehandlung, der direkte Zugang nicht.
   Beide öffentlichen APIs liefern nun 504 bei Timeout und 503 bei Verbindungs-/
   Authentifizierungsfehlern. Regressionstests prüfen auch den erfolgreichen
   Folgeaufruf. Komfortfehler entfernen weder Route noch Navigationsschritte.
3. **Spätere Backend-Updates konnten die Direkt-API zurücklassen.** Die beiden
   API-Builds synchronisieren jetzt eine bereits aktivierte Direkt-API auf dasselbe
   Backend-Image, unter Erhalt ihres Profils und ihrer Routing-Konfiguration.
4. **Die Direkt-URL wurde ohne funktionalen Vertragscheck veröffentlicht.** Vor
   diesem Schritt prüft der Build jetzt echten Direkt-Modus, Distanzgewichtung,
   Navigationsschritte, Zwischenhalt und separate Analyse. Ein altes Standard-API-
   Image kann damit nicht unbemerkt als Direktdienst bekannt gegeben werden.
5. Routing-Version und Commit werden auch beim Direkt-Deployment gesetzt.

## Abgleich mit der App

| Ziel | Backend-Stand | Erforderliche App-Anpassung |
| --- | --- | --- |
| Standard zuerst sichtbar | Ohne Variante unveränderter Standardpfad; Direkt hat eigene API/Analyse/OSRM | Standard nicht auf Variantenabfrage, Direkt oder Komfort warten lassen; Variantenabfrage im Hintergrund bzw. zwischenspeichern |
| Beide Varianten vorladen und schnell wechseln | Gleicher OSRM-Vertrag mit Geometrie, Distanz, Dauer und allen Legs | Ein gemeinsamer Planungszustand mit zwei Varianten; je Variante Route, Analysezustand und Herkunft behalten; Wechsel auf geladene Route ohne Neuberechnung |
| Separate API verwenden | `/routing_variants` liefert vollständige `direct.base_url` | `RadlNaviApi` baut heute `Uri.https(baseUrl, ...)` aus einem Hostnamen; auf vollständige URIs umstellen, inkl. lokalem HTTP/Port |
| Hinweise und Ansage gleichwertig | Manöver aller Legs samt Typ, Modifier, Straße, Ausfahrt und Modus vorhanden | Gemeinsamen RadlNavi-Parser und vorhandene Navigation nutzen; heutige BRouter-Direkt-Auswahl und Hinweis „ohne Ansage“ ersetzen; Stimmen-/Timerzustand beim Wechsel prüfen |
| Komfort zur richtigen Route | Separate Analyse mit `variant`, Legs, Distanzen und Endpunkten | `RouteAnalysisContext` um Variante/API-Herkunft, `distance`, `start`, `end` erweitern; Analyse über den erzeugenden Provider aufrufen |
| Schleifen, Teilkanten und Zwischenziele | Analyse bewahrt Reihenfolge und einzelne Legs | Heute werden nur Nodes angefordert und beim POST zusammengefügt; auf `annotations=nodes,distance` und unveränderte Leg-Liste umstellen |
| Späte Antworten ignorieren | Anfragen unabhängig, keine gemeinsamen Routencaches | Bestehende Planungsrevision/Request-Identität pro Variante verwenden; Antworten einer inaktiven Variante dürfen diese aktualisieren, aber nicht die aktive Navigation ersetzen |
| Fehler beeinträchtigen Standard nicht | Getrennte Dienste, explizite Fehlercodes, Komfort optional | `_requestRoute()` setzt heute die einzige Route sofort auf LOADING/ERROR; Direkt-Vorladen und fehlgeschlagener Wechsel müssen die bisherige aktive Route erhalten |
| Neuberechnung | Gleicher Route-Endpunkt für jede Koordinatenliste | Aktive Variante und verbleibende Zwischenziele verwenden; zuerst deren neue Route anzeigen, alternative Variante erst danach aktualisieren |
| Niedrige Abdeckung | `index=null` und `sufficientCoverage=false` regulär vorhanden | Bestehende Anzeige kann bereits „52 % bewertet“ darstellen; dieser Zustand darf keinen Providerwechsel auslösen |
| Offline, unbekannte Varianten-API, Direkt ausgefallen | Alte Clients bleiben kompatibel, keine automatische Direkt-Anforderung | Standard/BRouter-Fallback erhalten; Direkt nicht stillschweigend als Standard ausgeben; BRouter-Fallback ohne Ansage entsprechend kennzeichnen |

Relevante App-Dateien: `lib/api/radlnavi_api.dart`, `lib/model/route.dart`,
`lib/routing/routing_service.dart`, `lib/ui/map/map_screen_model.dart`,
`lib/ui/map/map_overlay/map_navigation_header_bar.dart` und
`lib/ui/map/map_overlay/map_route_comfort_summary.dart`.

## Nachweise und Grenzen

- 53 Backend-/Deployment-Tests: Varianten, Fehler und Wiederherstellung,
  Komfortfehler, Kapazitätsbegrenzung, Abbruch, Vertragscheck und Image-Synchronisierung.
- Echte OSRM-Regression: kürzer, aber langsamer; Sperren, Rad-Einbahn-Ausnahme,
  Abbiegeverbote, Pflicht-Radweg, zwei Zwischenziele, Rückfahrt, Neuberechnung und
  jetzt auch Fähre mit fester Dauer. Vorher-/Nachher-Nachweis des Fährfehlers.
- Neuer Deployment-Vertragscheck erfolgreich gegen die laufende lokale Direkt-API.
- Versionsdateien, Python-Formatierung, Deployment-YAML, Build-Abhängigkeiten und
  Diff-Prüfung. Keine Builds des großen Kartenbestands erforderlich.
- Keine Flutter-Änderungen oder Flutter-Prüfläufe; Ansage und Wechsel auf dem Gerät
  bleiben Teil der App-Umsetzung. Keine Produktionsanfragen oder Deployments in
  dieser QA. Cloud-IAM ist erst beim echten Rollout prüfbar.

## Nächste Abnahme

Nach Merge zuerst Standard-Backend und Standard-Routing deployen, dann den
expliziten Direkt-Build. Der funktionale Vertragscheck muss bestehen. Danach wie
vereinbart wenige Produktionsrouten und ein begrenzter Lastvergleich über die
separate Direkt-API; kein Sättigungstest. Die bisherigen lokalen Rohdaten belegen
keine unveränderte Standard-p95. Die Aussage „Standard wird nicht langsamer“ bleibt
bis zur Messung unter definierter Produktionslast offen.

Routing-Graph und Analyse-Datenbank werden weiterhin getrennt aktualisiert. Das
ist ein bestehender Restpunkt aus dem Gesamtkonzept; beide Varianten nutzen nach
dem vollständigen Rollout dieselbe Routing-PBF bzw. dasselbe Analyse-Image.
Schema- und Datenupdates beider APIs sind sequenziell, daher müssen Folge-Releases
auch während des Rollouts kompatibel bleiben.
