# RadlNavi Frontend

This is the frontend for [radlnavi.de](https://www.radlnavi.de).

## Hinweise und Ansagen am Rechner prüfen

Frontend mit `npm start` starten und `http://localhost:3000` öffnen.
Im Seitenmenü **Hinweise prüfen** wählen. GPS und eine laufende Navigation
sind dafür nicht erforderlich.

1. Beim Öffnen werden die aktuellen Start-/Zielkoordinaten der Kartenansicht
   übernommen und ihre Hinweise automatisch geladen. Alternativ eines der vier
   Beispiele auswählen oder Start/Ziel als `Breite, Länge`
   eingeben, dann **Route prüfen**. Auch eine auf der Karte geplante
   Route mit **Aktuelle Kartenroute übernehmen** verwenden.
2. Alle Manöver der Reihe nach lesen oder einzeln/gesamt vorlesen lassen.
   Die Meterangabe ist die Position des Manövers ab Routenstart, die Distanz
   danach gehört zum anschließenden Wegstück. Auch nahe Doppelabbiegungen,
   Start/Ziel und sämtliche gelieferten Legs bleiben sichtbar.
3. **Hinweis … auf Karte** markiert den Manöverort und das folgende Wegstück
   orange. Das Prüffenster bleibt dabei geöffnet, die Karte bleibt bedienbar.
   Am Titel lässt sich das Fenster verschieben (auch per Pfeiltasten nach
   Fokussieren des Titels), an der unteren rechten Ecke in der Größe ändern.
   **Verkleinern** reduziert es auf die Titelleiste; **Öffnen** zeigt den Inhalt wieder.
4. **Rohantwort herunterladen** sichert die API-Antwort samt Abfrage-URL und
   Abrufzeit. Bei übernommener Kartenroute wird das bereits gelieferte
   Route-Objekt des Web-Wrappers mit Übernahmezeit exportiert.

Die Prüfansicht verwendet die konfigurierte Backend-Adresse; lokal leitet
der Entwicklungsproxy an das produktive Backend weiter. `?variant=direct`
aktiviert wie in der Kartenansicht die Direktvariante. Die Auswahl eines
Beispiels befüllt nur die Eingabe; eine neue Abfrage erfolgt über **Route prüfen**.

Die API liefert strukturierte Manöver. Deutsche Texte erzeugt wie im
Webfrontend `osrm-text-instructions`; vorgelesen wird mit der Browserstimme.
Das ist keine Simulation der Flutter-Filter, Verkettung, GPS-Fortschrittslogik
oder tatsächlichen Ansagezeitpunkte. Roh-Typ und Modifier stehen deshalb neben
jedem übersetzten Hinweis; die vollständigen Step-Daten lassen sich aufklappen.
