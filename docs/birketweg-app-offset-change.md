# Birketweg: gezielter Rückbau der App-Paarunterdrückung

Stand: 27.09.2026. Status: **Änderung vorbereitet, nicht in Flutter angewandt.**
Ergänzt den [Gesamtplan](osrm-standard-guidance-plan.md).

## Entscheidungsvorschlag

Die App darf ein normales Links-/Rechtsmanöver nicht allein deshalb löschen,
weil kurz darauf ein Gegenmanöver wieder ungefähr in die ursprüngliche
Fahrtrichtung führt. Als erster, kleiner Schritt soll die bestehende
Unterdrückung nur noch für **zwei `turn`-Manöver mit exakt entgegengesetzten
`slight`-Modifiern** zulässig sein. Die bisherigen zusätzlichen Bedingungen
(Abstand >0 und ≤30 m, Gesamtrichtungsänderung ≤25°) bleiben erforderlich.

Das schützt Birketweg und erhält rechnerisch den ausdrücklich getesteten
Balanstraße-Fall. Es ergänzt keine neue Winkelregel und verändert weder das
Routingprofil noch die API. Die allgemeine Unterscheidung zwischen harmloser
Verschwenkung und notwendiger Wegwahl ist damit noch nicht gelöst.

## Untersuchter Stand und Beleggrenzen

- RadlNavi: `3f2116ead9d59ff4c90b02f2ac2360382516594f`.
- App: `7e455fade2e4dc83e711aa08d40d0870f8038f8f` in
  `C:/Users/Thomas/dev/flutter/munich-ways-app`.
- `lib/ui/map/voice_guidance.dart` ist gegenüber dem in der ersten Analyse
  untersuchten App-Commit `c3ea3302574e367330854f750be92cd7460e5503` unverändert.
  Die lokale Änderung an `pubspec.yaml` wurde nicht angefasst.
- Verwendet wird die [gesicherte API-Antwort vom 26.09.2026](osrm-standard-analysis/birketweg.json).
  Es wurde keine neue Produktionsantwort abgerufen und keine installierte
  App-Version unterstellt.
- Balanstraße stammt aus dem vorhandenen App-Test
  `ignores the offset straight crossing at Balanstraße` in
  `test/ui/map/voice_guidance_test.dart:789`. Die
  [extrahierte Vergleichsfixture](osrm-standard-analysis/balanstrasse-app-test.json)
  ist ausdrücklich **keine API-Antwort**. Sie enthält nur Testgeometrie und
  zwei Testmanöver, in einer Hülle für das Geometrieskript.

Die Zahlen unten stammen aus einer lokalen Meterprojektion. Die App verwendet
bei der Projektion ebenfalls lokale Meter, beim Abtasten aber geodätische
Distanzen. Deshalb sind dies Näherungswerte, kein ausgeführter Dart-Test.

## Wo genau die Hinweise verschwinden

Eingabe: `[48.145395,11.520751]` → `[48.145413,11.522572]`
in Breite/Länge. Keine Zwischenziele an den Abbiegungen ergänzen.

| Stufe | Befund für Birketweg |
| --- | --- |
| API, vollständige Route | `depart`, `continue/left`, `turn/right`, `arrive`; alle Steps `cycling` |
| `RadlNaviApi`, `lib/api/radlnavi_api.dart` | Übernimmt Typ/Modifier; finale Fußzugangs-Kürzung greift bei dieser reinen Fahrradroute nicht |
| `VoiceGuidance.setRoute()`, ca. Zeile 385 | Projiziert Manöver nacheinander auf die Route; linkes Manöver ca. 47,13 m, rechtes ca. 59,37 m |
| `_adjustTurnModifierFromGeometry()`, ca. 1025 | `continue/left` wird prinzipiell nicht abgeschwächt; rechtes `turn/right` mit ca. 87,43° liegt außerhalb 15–50° |
| `_isRelevant()`, ca. 886 | Beide Richtungsmanöver bleiben erhalten; Start/Ziel werden separat behandelt |
| `_geometryTurns()`, ca. 1075 | Keine zusätzliche Ecke besteht alle Kriterien; beide existierenden Manöver bleiben erhalten |
| `_withoutStraightOffsetPairs()`, ca. 923 | Abstand ca. 12,23 m, Gesamtrichtungsänderung ca. 15,94°: Beide werden gelöscht |
| `display()` / `update()` | Die relevante Manöverliste ist leer. Für diese Abbiegungen gibt es weder Anzeige noch Ansagetext; Zielankunft wird separat behandelt |

Der entscheidende Fehler ist die Bedeutungsannahme der Paarregel:
**Eine kleine Netto-Richtungsänderung beweist keine unwichtige Wegentscheidung.**
Zwei deutliche Abbiegungen können dieselbe Gesamtwirkung haben wie eine sanfte
Verschwenkung. `_areOppositeTurns()` prüft heute nur `contains('left')` und
`contains('right')`. Stärke, Typ und Kreuzungsalternativen werden nicht geprüft.
Damit können grundsätzlich auch andere Manövertypen mit solchen Modifiern
in die Paarlöschung geraten.

Ein Type-only-Fix, der nur `continue` schützt, würde diesen Birketweg-Snapshot
zufällig reparieren. Ein normales `turn/left` mit identischer Geometrie wäre
weiter betroffen. Das ist kein ausreichend allgemeiner Schutz.

## Warum Balanstraße den vorgeschlagenen Rückbau verträgt

Die Prüfung muss **nach** der bestehenden Modifier-Anpassung stattfinden,
genau dort, wo heute die Paarlöschung sitzt:

| Fixture | Rohmanöver | Nach heutiger Winkelkorrektur | Abstand / Gesamtrichtung | Heute | Vorschlag |
| --- | --- | --- | --- | --- | --- |
| Birketweg | `continue/left`, `turn/right` | unverändert | 12,23 m / 15,94° | beide weg | beide bleiben |
| Balanstraße, vorhandener Test | `turn/left`, `turn/slight right` | `turn/slight left`, `turn/slight right` | 22,40 m / 20,32° | beide weg | beide weiterhin weg |
| Lenbachplatz, gespeicherte API | `turn/right`, `turn/left` | `turn/right`, `turn/slight left` | 10,20 m / 17,30° | beide weg | beide bleiben |

Am ersten Balanstraße-Manöver misst das 12-m-Fenster ungefähr 21,12°; die
vorhandene Abschwächung greift deshalb. Das zweite Manöver ist bereits `slight`.
Keine Änderung der Test-Erwartung „keine Anzeige/Ansage“ ist hierfür nötig.

Am Lenbachplatz bleibt das erste `right` bei ca. 54,36° normal; das zweite
`left` wird bei ca. 35,55° zu `slight left`. Der Vorschlag schützt das Paar,
löst aber nicht die offene Herkunft der vom Nutzer erinnerten Ansage
„leicht rechts“. Auch ist eine unverändert normale zweite Linksabbiegung
damit noch nicht erreicht.

## Vorbereitete Änderung

Der [Patch-Entwurf](osrm-standard-analysis/birketweg-offset-policy.patch)
ändert ausschließlich Kommentar, Helper und dessen Aufruf in
`lib/ui/map/voice_guidance.dart`:

```dart
static bool _areOppositeSlightTurns(RouteManeuver first, RouteManeuver second) {
  return first.type == 'turn' &&
      second.type == 'turn' &&
      ((first.modifier == 'slight left' &&
              second.modifier == 'slight right') ||
          (first.modifier == 'slight right' &&
              second.modifier == 'slight left'));
}
```

In `_withoutStraightOffsetPairs()` ersetzt dieser Helper den bisherigen
Aufruf `_areOppositeTurns(...)`. Keine Filterung oder Mutation der ursprünglichen
`CycleRoute.maneuvers`; weiterhin nur Aufbau der internen Guidance-Liste.
Schleifen, Abstände, Winkelberechnung und Indexfortschaltung bleiben bestehen.

`git apply --check` wurde gegen den oben genannten App-Stand erfolgreich
ausgeführt. **Der Patch ist nicht angewandt, nicht Dart-formatiert und noch
nicht mit Flutter getestet.** Er ist ein prüfbarer Implementierungsentwurf.

Alternativen und Entscheidung:

- Ganze Paarregel entfernen: stärkster Schutz der OSRM-Manöver, aber der
  vorhandene Balanstraße-Test würde seine gewollte Stille verlieren. Das wäre
  eine zusätzliche Produktentscheidung und ist für den ersten Schritt zu breit.
- Nur Roh-`slight` zulassen: würde Balanstraße ebenfalls verändern, weil dort
  das erste Rohmanöver `left` ist. Der Entwurf erhält bewusst die bestehende
  vorgeschaltete Abschwächung. Diese Abhängigkeit bleibt ein offener Prüfpunkt.
- Neue Abstands-/Winkelschwellen oder Koordinatenausnahmen: nicht nötig und
  durch diese wenigen Beispiele nicht ausreichend begründet.
- Topologiegestützte Erkennung: langfristige Option. Das heutige
  `RouteManeuver` enthält keine Intersections, Modus- oder Leg-ID. Eine solche
  Erweiterung wäre ein separates Vorhaben, kein nötiger Bestandteil dieses Fixes.

## Konkreter Auftrag an die spätere App-Umsetzung

1. App-`AGENTS.md`, Branch und Arbeitsbaum prüfen; gültigen HEAD festhalten.
   Bei aktiver Telefon-/Flutter-Sitzung zuerst deren Ende mit dem Nutzer klären,
   bevor automatisierte Flutter-Prüfungen starten.
2. Gesicherte Birketweg-Antwort als unveränderte JSON-Fixture in die App
   übernehmen. Im API-Test GeoJSON, alle Steps, Typen und Reihenfolge prüfen;
   über den echten Parser ein `CycleRoute` erzeugen und an `VoiceGuidance`
   übergeben. Nicht nur zwei künstliche Manöver ohne echte Geometrie testen.
3. Vor Patch reproduzieren: beide API-Manöver vorhanden, aber `display()`
   und `update()` am gesnappten Routenstart liefern keinen Abbiegehinweis.
   Test als neue gewünschte Erwartung rot laufen lassen.
4. Entwurf anwenden und formatieren. Nach Patch bei Geschwindigkeit 0 am
   gesnappten Start ungefähr `In 50 m links` anzeigen und
   `In 50 Metern links abbiegen, danach sofort rechts abbiegen.` ausgeben.
   Diese exakten Strings sind **vorgesehene Test-Erwartungen**, noch kein
   ausgeführtes Ergebnis. Distanz nach echter App-Berechnung bestätigen.
5. Zusätzlichen Aufruf am selben Standort prüfen: keine doppelte
   Annäherungsansage. Mit frischer Guidance-Instanz unmittelbar vor dem ersten
   Manöver die kombinierte Sofortansage und deutsche/englische Richtung prüfen.
6. Gegenproben unten ausführen; anschließend gemäß App-Regeln statische
   Analyse und relevante Tests sequenziell, vor einem beauftragten Push die
   vollständige Suite. Keine Erwartung entfernen, nur um Tests grün zu machen.

## Gegenproben und Abnahme

| Fall | Erwartung des Entwurfs |
| --- | --- |
| Birketweg `continue/left` + `turn/right` | Beide bleiben; erste Sprachansage enthält links und danach sofort rechts |
| Dieselbe Geometrie mit `turn/left` + `turn/right` | Ebenfalls erhalten; schützt vor einem bloßen Type-Sonderfall |
| Normales oder scharfes Manöver zusammen mit Gegenmanöver | Keine Paarlöschung, unabhängig von Reihenfolge |
| Zwei leichte `turn`-Manöver, entgegengesetzt | Nur bei weiterhin erfüllten Abstand-/Gesamtrichtungsbedingungen unterdrücken |
| Zwei leichte Manöver gleicher Richtung | Erhalten |
| `continue`, `fork`, Kreisverkehr mit beliebigen Modifiern | Durch diese Paarregel nicht unterdrücken; übrige Behandlung unverändert |
| Balanstraße-Test | Anzeige/Ansage weiterhin leer wie heute |
| Lautensackstraße-Test | Vorhandene Abschwächung und erwarteter leichter Hinweis unverändert |
| Lenbachplatz | Normales Rechtsmanöver bleibt; gefiltertes Paar bleibt erhalten; zweite Abschwächung separat sichtbar |
| Schrammerstraße / Waisenhausstraße | Keine Verbesserung durch diesen Patch erwarten: nur ein relevantes Rohmanöver |
| Drei oder mehr dicht aufeinanderfolgende Manöver | Nur ein tatsächlich zulässiges Paar löschen; normales Nachbarmanöver nicht überspringen |
| Grenzfälle: Abstand 0, >30 m oder Gesamtwinkel >25° | Keine Paarlöschung; vorhandene Grenzwertsemantik erhalten |
| Route ersetzen, Off-route und Rückkehr, Startfreigabe | Bestehende Recovery-/Ansagezustände bleiben funktionsfähig |

Zusätzlicher Befund für den Fahrtest: `_advancePastManeuvers()` schaltet erst
25 m nach einem Manöver weiter. Bei 12,2 m Abstand kann deshalb die erste
Anweisung noch aktiv sein, wenn das zweite Manöver bereits erreicht ist.
Die kombinierte Vorankündigung ist hier besonders wichtig. Der Entwurf
ändert diese Fortschrittsregel nicht; eine eigenständige zweite Sofortansage
oder ein sofortiger Wechsel des Pfeils ist damit nicht zugesichert.
Den ersten Patch anhand der kombinierten Ansage abnehmen, danach diesen
separaten Fortschrittsbefund bei 10/20/30 km/h und GPS-Schwankungen untersuchen.

## Verbleibende Risiken und Nachweis

Auch zwei leichte Abbiegungen können echte Wegentscheidungen sein. Außerdem
kann die vorhandene Winkelkorrektur zuvor normale Abbiegungen abschwächen.
Die neue Vorbedingung reduziert die Menge unterdrückbarer Paare, beweist aber
keine gefahrlose Verschwenkung. Sie ist ein begrenzter erster Rückbau.
Auf anderen Routen können dadurch mehr Hinweise entstehen. Fällt eine
zusätzliche Ansage negativ auf, als Fixture dokumentieren statt sofort
die allgemeine Paarlöschung wieder zu erweitern.

Reproduzierbare rechnerische Gegenprobe:

```powershell
python docs/osrm-standard-analysis/compare_offset_policy.py
```

Sie zeigt Roh- und angepasste Modifier, Abstände, Winkel sowie alte/neue
Löschentscheidung für Birketweg, Balanstraße-Test und Lenbachplatz. Für diese
Fixtures gibt es keine zusätzlichen Kandidaten aus `_geometryTurns()`.
Das Skript führt weder den Flutter-Parser noch die Dart-Zustandsmaschine,
das Start-Gate oder TTS aus. Ein echter App-Replay bleibt Abnahmevoraussetzung.
