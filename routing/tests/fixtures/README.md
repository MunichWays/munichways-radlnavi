# Munich one-way regression map

`munich-oneway.osm` was obtained on 2026-09-11 from the OpenStreetMap map API,
bounding box `11.554,48.140,11.572,48.144` (longitude/latitude).
Only highway/ferry ways, their nodes and turn restrictions were retained;
contributor metadata was removed. This is a frozen current-map regression,
not the exact PBF used for the production deployment.

Data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the Open Database License (ODbL).

The fixture covers the reported Arnulfstraße and Elisenstraße/Lenbachplatz
routes. `test_munich_oneway.py` checks route annotation edges against the mapped
cycling one-way directions while allowing explicit bicycle counterflow.
