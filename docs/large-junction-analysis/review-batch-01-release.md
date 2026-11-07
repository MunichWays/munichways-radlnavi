# Batch 01 release: catalog v3

Backend 2.4.3; eight newly reviewed junctions, 60 additional active movements.
Total: 10 active junctions, 76 active movements, five explicit exclusions.

Geometry approved by Thomas, including K05/K06/K08/K10 v2. Runtime matching and routing are unchanged.
Each active movement has a real API fixture, independently checked directed OSM support, production-matcher acceptance and unchanged routing data.

| Junction | Active left/straight movements |
| --- | --- |
| Ständlerstraße / Balanstraße | 8/8 |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | 8/8 |
| Fürstenrieder Straße / Gotthardstraße | 8/8 |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | 8/8 |
| Westendstraße / Zschokkestraße / Tübinger Straße | 8/8 |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | 4/8 |
| Arnulfstraße / Hackerbrücke / Wredestraße | 8/8 |
| Thomasiusplatz / Balanstraße / Werinherstraße | 8/8 |

## Important limits for field testing

- K07 Mars/Pappenheim remains deferred pending the OSM update; no runtime entry.
- K09 Landsberger/Barth is permanently excluded and closed, including future candidate refreshes.
- Rufinistrasse (K06) and Wilramstrasse (K10) remain excluded approaches.
- K06: all four candidate movements involving the Lachnerstrasse carriageway remain disabled. The live routing graph snaps to a different adjacent path and fails the directed OSM/gate verification. They keep ordinary navigation; approved drawing alone does not authorize different routing geometry.
- K05: curved arms use verified 40m approach/departure references. The east-to-west connection is classified as left from its actual directions, not automatically straight from opposite arm labels. Existing runtime heading and corridor tolerances are unchanged.
- No new App behavior is required to receive this catalog. The generic App code previously used in the successful benchmark is included in the requested App commit/build.

## Reference movements

| Junction | Entry / exit arm | Action | Active |
| --- | --- | --- | --- |
| Ständlerstraße / Balanstraße | north / east | left | True |
| Ständlerstraße / Balanstraße | north / south | straight | True |
| Ständlerstraße / Balanstraße | east / south | left | True |
| Ständlerstraße / Balanstraße | east / west | straight | True |
| Ständlerstraße / Balanstraße | south / west | left | True |
| Ständlerstraße / Balanstraße | south / north | straight | True |
| Ständlerstraße / Balanstraße | west / north | left | True |
| Ständlerstraße / Balanstraße | west / east | straight | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | north / east | left | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | north / south | straight | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | east / south | left | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | east / west | straight | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | south / west | left | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | south / north | straight | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | west / north | left | True |
| Fürstenrieder Straße / Agnes-Bernauer-Straße | west / east | straight | True |
| Fürstenrieder Straße / Gotthardstraße | north / east | left | True |
| Fürstenrieder Straße / Gotthardstraße | north / south | straight | True |
| Fürstenrieder Straße / Gotthardstraße | east / south | left | True |
| Fürstenrieder Straße / Gotthardstraße | east / west | straight | True |
| Fürstenrieder Straße / Gotthardstraße | south / west | left | True |
| Fürstenrieder Straße / Gotthardstraße | south / north | straight | True |
| Fürstenrieder Straße / Gotthardstraße | west / north | left | True |
| Fürstenrieder Straße / Gotthardstraße | west / east | straight | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | north / east | left | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | north / south | straight | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | east / south | left | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | east / west | straight | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | south / west | left | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | south / north | straight | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | west / north | left | True |
| Landsberger Straße / Elsenheimerstraße / Friedenheimer Brücke | west / east | straight | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | north / east | left | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | north / south | straight | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | east / south | left | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | east / west | left | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | south / west | left | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | south / north | straight | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | west / north | left | True |
| Westendstraße / Zschokkestraße / Tübinger Straße | west / east | straight | True |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | north / east | left | True |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | north / south | straight | False |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | east / south | left | False |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | east / west | straight | True |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | south / west | left | False |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | south / north | straight | False |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | west / north | left | True |
| Nymphenburger Straße / Waisenhausstraße / Lachnerstraße | west / east | straight | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | north / east | left | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | north / south | straight | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | east / south | left | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | east / west | straight | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | south / west | left | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | south / north | straight | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | west / north | left | True |
| Arnulfstraße / Hackerbrücke / Wredestraße | west / east | straight | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | north / east | left | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | north / south | straight | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | east / south | left | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | east / west | straight | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | south / west | left | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | south / north | straight | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | west / north | left | True |
| Thomasiusplatz / Balanstraße / Werinherstraße | west / east | straight | True |

Backend validation: 144 unit tests, including every enabled real route, 40 total right-turn controls and rejected K06 routes.
The deployment is verified afterwards with `check_review_batch_live.py`; a successful build alone does not establish live guidance availability.
