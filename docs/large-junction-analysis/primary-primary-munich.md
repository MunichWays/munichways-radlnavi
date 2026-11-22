# München: Primary/Primary-Suchbestand

OSM-Abfrage vom 16.11.2026. Vier benannte Kandidatenkomplexe, davon einer bereits live und drei neu. Dies ist keine Bestätigung von vier geeigneten großen Radverkehrskreuzungen.

| Kreuzungskomplex | Bisheriger Stand | Vorschlag |
| --- | --- | --- |
| Menzinger Straße / Wintrichring / Maria-Ward-Straße | K12, live | Bereits bearbeitet |
| Frankfurter Ring / Ingolstädter Straße | Neu | Als nächstes Geometrie und Radverkehrsanschlüsse prüfen |
| Landsberger Straße / Trappentreustraße | Neu | Zunächst Brücke und Rampen von der eigentlichen Kreuzung abgrenzen |
| Berg-am-Laim-Straße / Leuchtenbergring / Ampfingstraße | Neu | Zunächst oberirdische Kreuzung, Tunnel und Rampen getrennt analysieren |

Die stadtweite Abfrage liefert 45 Verknüpfungsknoten. Zwölf davon verbinden mindestens zwei unterschiedlich benannte `highway=primary`-Straßen. Nahe Kontakte mit mindestens zwei gemeinsamen Straßennamen werden innerhalb von 80 Metern vorläufig zusammengefasst; dadurch entstehen vier Komplexe. Die übrigen Knoten sind keine belegten Kreuzungen zweier benannter Primary-Straßen, sondern haben nur einen Straßennamen oder unbenannte Verbindungen. Für unbenannte Straßen wird keine Vollständigkeit behauptet.

`primary_link`, `trunk`, `secondary` und `tertiary` sind in dieser Auswahl nicht enthalten. Ein Straßenzug kann an der Kreuzung Namen oder Straßenklasse wechseln. Die Zahl vier ist deshalb eine Suchpriorisierung, keine automatische Vierarmigkeits-, Geometrie- oder Fahrbeziehungsfreigabe. Vorhandene dauerhafte Ausschlüsse bleiben bestehen. Für eine größere nächste Runde wäre Primary/Secondary sinnvoller als die Beschränkung auf Primary/Primary.

Quellen: [Overpass-Abfrage](primary-primary-munich.overpassql), eingefrorene Antwort `primary-primary-munich-osm.json.gz` und vier kleine offizielle OSM-Kartenausschnitte `primary-primary-context-osm.json.gz`. [Maschinenlesbare Zählung](primary-primary-munich-inventory.json).

Offline reproduzieren: `python docs/large-junction-analysis/count_primary_primary.py`.

Keine Änderung am Laufzeitkatalog, keine Aktivierung, kein Commit oder Deployment.
