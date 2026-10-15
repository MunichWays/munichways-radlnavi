# GPX-Routenübergabe: geprüfter Stand

## Nachbesserungen RadlNavi am 15. Oktober 2026

Der Live-Linkfehler wurde als HTTP 503 mit `Route sharing is not configured`
reproduziert. In der API fehlten `SHARED_ROUTES_BUCKET` und
`SHARE_PUBLIC_BASE_URL`; der private Bucket existierte noch nicht. Die einmalige
Einrichtung wurde ausgeführt: Bucket in `europe-west3`, 90-Tage-Löschregel für
`routes/`, Objektzugriff für das bestehende API-Dienstkonto. Beim ersten Lauf
wurde zudem ein Windows-PowerShell-Fehler im Einrichtungsskript behoben: Ein
404 beim Prüfen des noch fehlenden Buckets brach bisher vor dessen Erstellung ab.

Live geprüft wurden Linkerstellung (201), CORS für die Web-Domain, unverändertes
Zurücklesen (200), der Domainname des Links und das Ablaufdatum nach 90 Tagen.
Die ausschließlich hierfür erzeugten synthetischen Testobjekte wurden entfernt.
Die neue Deployment-Prüfung bestätigt zusätzlich lesend den Speicherzugriff.
Cloud Build setzt künftig die Sharing-Konfiguration ausdrücklich und meldet
einen fehlenden Speicherzugriff als Deploymentfehler.

Das Planungsfenster wurde kompakter angeordnet und erhält einen gemeinsamen
Scrollbereich einschließlich Kopf. GPX-Import steht über dem Start;
„Entfernen“ steht links. Zusatzfunktionen liegen im aufklappbaren „Mehr“.
Der Hinweis zur importierten Originalstrecke steht nur noch im gekürzten
Übernahmedialog. Ein Integrationstest bestätigt Import und unveränderte
Übernahme ohne neue Routinganfrage.

Backend: 86 Tests bestanden. Frontend: 51 Tests bestanden. Nach Korrektur eines
TypeScript-Typfehlers in der neuen Testabfrage wurden die vier Import-/Routing-
Integrationstests erneut erfolgreich ausgeführt. Der Produktionsbuild ist
erfolgreich; bestehende ESLint-/Browserslist-Hinweise bleiben sichtbar.
Die Cloud-Build-YAML wurde syntaktisch geprüft; der Deployment-Lesecheck besteht
gegen die Live-API. Der Bucket hat Public Access Prevention und einheitlichen
IAM-Zugriff aktiviert.
Eine Sichtprüfung im Browser war nicht verfügbar (keine verbundene
Browseroberfläche). Es wurden keine App-, Flutter- oder Geräteaktionen gestartet.
Die Oberflächenänderungen sind für den Live-Test über die Backend- und Frontend-
Workflows aus `feature/gpx-route-transfer` vorbereitet; ein Routing-Deployment
ist dafür nicht erforderlich. Beide API-Dienste wurden live auf 1 GiB RAM
gesetzt. Die Deployment-Dateien schreiben jeweils `--memory=1Gi` fest; der
separate Direkt-Routing-Dienst bleibt bei 2 GiB.

## Vorheriger Prüfstand

14. Oktober 2026, Feature-Branch `feature/gpx-route-transfer` in Web/Backend und App.
Android-Testbuild **65**, App-Version 3.2.1+79; RadlNavi 2.3.5.

| Prüfung | Ergebnis |
| --- | --- |
| Flutter 3.47.6: statische Analyse | Keine Fehler oder Warnungen |
| Vollständige App-Testsuite | 669 bestanden; 1 opt-in Livetest nicht aktiviert |
| Tatsächlicher Web-GPX-Export → App-Parser | Gemeinsame GPX-Testdatei erfolgreich importiert; Geometrie, 2 Zwischenziele und alle 6 Manöver erhalten |
| Snapshot-Persistenz und Wiederherstellung | Originalstrecke erhalten; gleiche Namen ersetzen keine anderen Importe; Index wird ohne Geometrien geladen |
| Verspätete Antworten und Speicherfehler | Neue Auswahl nicht überschrieben; fehlender Snapshot blockiert die normale Routenberechnung nicht |
| Android-Testbuild | Erfolgreich erzeugt; keine Installation oder App-Ausführung durch den Agenten |
| Frontend | 50 Tests bestanden; Produktionsbuild erfolgreich |
| Backend | 84 Tests bestanden |
| Eingabeprüfung mit Python `-O` | 5 gezielte Linkdiensttests bestanden; Validierung unabhängig von Python-Assertions |
| Echter lokaler HTTP-Test | Teilen/Lesen desselben Snapshots und CORS erfolgreich; Testserver beendet |
| Nginx im tatsächlichen Basisimage | Syntaxprüfung und HTTP-Aufruf von `/r/<id>` erfolgreich; fehlende statische Dateien liefern HTTP 404; Testcontainer beendet |
| Diff-/Formatprüfung | Beide Repositories ohne Whitespacefehler; geänderte Dart-Dateien formatiert |

Die Builds melden bestehende React-Lint-/Browserslist- und Android-Kotlin-
Migrationshinweise. Die Prüfungen wurden nicht deaktiviert. Die debouncten MUI-
Oberflächentests haben begründete Zeitlimits für langsame CI-/Build-Rechner.

Vor Übergabe wurden Gradle beendet und verbliebene Flutter-/Dart-/Build-/Run-
Prozesse kontrolliert; kein laufender Prozess für diese Arbeitsbereiche.

Nicht geprüft: iOS-Build, native iPhone-Abläufe und Android-Fahrtest mit Ansagen.
Die unten dokumentierten Android-Dateirundläufe wurden manuell bestätigt. Hosting und GCS-
Speicher wurden noch nicht veröffentlicht; App-/Universal-Links benötigen diese
Veröffentlichung sowie den zusätzlichen Play-App-Signing-Fingerabdruck. Die
vorbereitete Domainzuordnung enthält zunächst das lokale Android-Debug-Zertifikat.

Abschlussprüfung vor dem ausdrücklich beauftragten Commit und Push beider Repositories.
Versionsänderungen und lokale Docker-Befehle werden wie gewünscht mitgenommen.
Der Nutzer hat den abschließenden Android-Handytest erfolgreich bestätigt;
Lauf beendet und USB getrennt. Android-Releasebuild mit R8 erfolgreich.

Die Dateien `implementation-refinements.py` und `route-import-dialog.refinement.dart`
sind historische Implementierungsentwürfe, keine Laufzeitbestandteile.
Das Patchskript nicht erneut ausführen: es enthält einmalige Quelltextänderungen.

Testschritte und Einrichtung: [Umsetzungsdokument](gpx-route-transfer-implementation.md).

## Erster Android-Handytest am 14. Oktober 2026

Der Nutzer hat den APK-Testbuild manuell installiert. Bestätigt wurden lokale
Webplanung mit zwei Zwischenzielen und Export sowie Import der synthetischen
Testdatei in die App, Speichern, App-Neustart und erneuter Export.

Die bereitgestellte `munichways-route.gpx` enthält dieselben vier Trackpunkte,
denselben Plan und die vollständig identische MunichWays-Erweiterung wie die
Testdatei. Die gerade Linie ist deren beabsichtigte synthetische Geometrie;
sie ist kein Beispiel einer auf dem Straßennetz berechneten Route.

Nach bewusster Änderung und Neuberechnung, anschließendem Zurücksetzen der
Planungsorte und erneuter Berechnung wurde `munichways-route (2).gpx` exportiert.
Sie enthält dieselben vier Planungsorte, aber einen neu berechneten Verlauf mit
296 Trackpunkten, drei Legs und 42 Steps. Die Routingdistanz beträgt 5.962 m,
die berechnete Dauer etwa 23 Minuten. Der Standard-GPX-Track entspricht jeweils
der Geometrie im Navigationssnapshot.

Damit sind Originalerhalt beim Dateirundlauf und die bewusste Neuberechnung auf
dem Handy praktisch bestätigt. Noch ausstehend ist der vollständige Rundlauf
einer tatsächlich im Web berechneten Straßenroute zur App und zurück sowie ein
Fahrtest mit deren Ansagen. Bei dieser Prüfung wurden nur die gelieferten Dateien
gelesen; keine App-Änderungen, Flutter-Prüfungen oder Geräteaktionen gestartet.

## Android-Rundlauf einer Straßenroute am 14. Oktober 2026

Der Nutzer hat die lokal in RadlNavi berechnete Route
`GreenCity-über-Hackerbrücke.gpx` in die App importiert, gespeichert, die App
neu gestartet, als `munichways-route (3).gpx` exportiert und erneut importiert.
Route und Zwischenziel blieben dabei wie erwartet erhalten.

Der Dateivergleich bestätigt identische 273 Trackpunkte, denselben Plan mit
Start, einem Zwischenziel an der Hackerbrücke und Ziel sowie identische
Navigationsdaten mit zwei Legs und 32 Steps. Die Routingdistanz beträgt
5.590,678 m, die berechnete Dauer etwa 22 Minuten. Die gesamte native
MunichWays-Erweiterung ist in beiden Dateien identisch. Der Standard-GPX-Track
entspricht jeweils der Snapshot-Geometrie; auch die Manövergeometrien ergeben
denselben Streckenverlauf. Die unterschiedlichen Dateigrößen entstehen durch
die XML-Serialisierung, ohne Verlust der Routen- oder Navigationsdaten.

Damit ist auch der zuvor ausstehende vollständige Rundlauf einer echten
Web-Straßenroute bestätigt. Offen bleiben der Fahrtest mit Ansagen, der
produktive Link-/QR-Ablauf und die iOS-Prüfung. Für diesen Dateivergleich wurden
keine Flutter-, Build- oder Geräteaktionen gestartet.
