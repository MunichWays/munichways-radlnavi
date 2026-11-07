# Testfahrten Batch 01

Zielstand: Backend 2.4.3 / Katalog v3, App 3.2.2+97 auf
`feature/big-conjunctions`. Den App-Stand aus VS Code starten. Die neuen
Freigaben erst nach bestätigtem Backend-Deployment testen und die Route dann
neu planen; eine bereits geladene Route übernimmt neue Metadaten nicht nachträglich.

## Pro Fahrt

1. Standardrouting von RadlNavi verwenden. Direkt- und Entdeckungsrouting
   behalten ihre bisherige Navigation ohne diese Zusatzmetadaten.
2. Die Route mindestens 150 Meter vor dem Entry beginnen und von dort anfahren.
3. Vor der Kreuzung: Hinweise ungefähr bei 100 und 60 Metern, mit der richtigen
   Aktion links/geradeaus; kein zusätzliches „Hier“ am Eintritt.
4. Innerhalb: auch bei langem Warten und abweichender Bewegung keine
   Einzelansagen oder verfrühte Abweichungsmeldung.
5. Richtige Ausfahrt: danach normale Navigation. Falsche Ausfahrt: nach
   bestätigtem Verlassen der Fläche wieder normale Abweichungsbehandlung.

Beim Start mitten in der Fläche wird die Ruhephase vorsorglich nicht ohne
beobachtete Anfahrt aktiviert. Zum Test der Vorankündigungen deshalb von außen
anfahren. Rechtsabbiegen bleibt eine Gegenprobe mit den bisherigen Hinweisen.

## Besonders aussagekräftige Fälle

| Standort | Prüfschwerpunkt |
| --- | --- |
| K03 Fürstenrieder / Gotthard | Kleine Radwegversätze vor der Fläche dürfen die Kreuzungs-Vorankündigung nicht blockieren. |
| K05 Westend / Zschokke / Tübinger | Gemeinsamer Entry-4 vor der Verzweigung; beide folgenden Radwegäste liegen innerhalb. Die gekrümmte Ost-West-Verbindung wird anhand ihrer tatsächlichen Richtung als links angekündigt. |
| K06 Nymphenburger / Waisenhaus / Lachner | Vier Beziehungen ohne Lachnerstraßen-Arm aktiv. Bei Fahrten von/zu Lachnerstraße bleiben vorerst die bisherigen Hinweise, weil die Routinggeometrie nicht zum bestätigten Fahrbahnpunkt passt. Rufinistraße bleibt ohne eigenen Entry. |
| K08 Arnulf / Hackerbrücke / Wrede | Entry-2 und Exit-3 liegen gemeinsam auf der Fahrbahn an der Ampel. |
| K10 Thomasiusplatz | Normaler südlicher Entry-2; Wilramstraße ohne eigene Guidance-Beziehung. |

K01, K02 und K04 haben jeweils acht geprüfte Beziehungen und eignen sich als
weitere Standardfälle. Arnulfstraße/Steubenplatz bleibt der Praxisbenchmark.
K07 Mars/Pappenheim bleibt zurückgestellt. K09 Landsberger/Barth ist dauerhaft
ausgeschlossen und muss nicht erneut geprüft werden.

Für eine Rückmeldung reichen Standort, Fahrtrichtung, beobachtete Ansage und
gegebenenfalls die ungefähre Position: etwa „K08 von Hackerbrücke links in
Arnulfstraße, nach langer Rotphase korrekt“. Bei einem Fehler nach Möglichkeit
auch notieren, ob die Route vor oder nach dem Deployment neu geplant wurde.

Technischer Umfang und alle aktiven Beziehungen:
[Freigabebericht](review-batch-01-release.md).
