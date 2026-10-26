# Routing regression fixtures

## Directional cycling attributes (#22)

`cycling-attributes.osm` combines the synthetic cases from
`../cycling-attribute-cases.json`, a route-choice diamond, and the 13 original
Munich ways with 58 nodes frozen at 2026-10-26T17:30:00Z. The original data and
retrieval queries are in [the issue analysis](../../../docs/issue-22-analysis/README.md).
Contributor names/IDs were removed; tags, way order and coordinates were retained.
The shortcut's `cycleway:both:width=0.1` deliberately verifies that width cannot
create any routing preference or exclusion.

Rebuild with `python routing/tests/build_cycling_fixture.py`; the Lua contract
suite checks that the committed fixture matches its inputs. Test both real
OSRM profiles with `test_sided_cycleway_tags.py`. Original OSM data:
© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL.

## Bergmannstraße/Landsberger Straße guidance

`bergmann-landsberger-2026-10-13.osm` was downloaded on 2026-10-13 from the
[OpenStreetMap map API](https://api.openstreetmap.org/api/0.6/map?bbox=11.53755,48.1381,11.5386,48.1407).
Contributor metadata was removed; coordinates, ways and tags remain unchanged.
The exact route from Bergmannstraße across Landsberger Straße has a right turn
followed 15.3 m later by a left turn onto the cycleway crossing. With OSRM's
default `max_collapse_distance` of 30 m the second maneuver disappears.
`test_bergmann_guidance.py` checks that Standard and Direct keep both turns.

Data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the Open Database License (ODbL).

## Munich one-way regression map

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

## Endpoint pushing access

`munich-endpoint-access.osm` freezes the Hofgarten and Alter Botanischer Garten
examples from Issue #19. It was obtained on 2026-10-13 from the official OSM map
API with bounding boxes `11.576,48.141,11.583,48.145` and
`11.560,48.140,11.568,48.146`. Only highway ways, their nodes and complete turn
restrictions were retained; contributor metadata was removed. All retained
access tags are original, including `bicycle=no`; the fixture is not modified
to make the bicycle profile accept them.

`test_endpoint_access.py` builds the same spatial database index as production
and checks endpoint-only backend composition against both unchanged OSRM
profiles, including reverse routes, intermediate stops and ordinary bike endpoints.
The map is cropped, so these distances are regression expectations for this
fixture rather than guarantees for the full regional graph.

Data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the Open Database License (ODbL).

## Cycleway attribute examples

The otherwise synthetic `../profile-fixture.osm` also contains two original
OSM ways and their nodes, retrieved on 2026-10-12 through the OSM API:

- [Ludwigsbrücke foot/cycle path, way 23457803](https://www.openstreetmap.org/way/23457803)
- [Golo-Mann-Weg, way 513653294](https://www.openstreetmap.org/way/513653294)

All way/node tags and coordinates were retained; contributor metadata was
removed. Adjacent ways and relations are omitted to test these attributes on
the isolated original geometry. This fixture checks their physical travel
time and selection weight, rather than the surrounding Munich network.
`test_cycleway_tags.py` runs both examples with Standard and Direct in both
directions. Both original ways have `highway=path`, whose base speed is
18 km/h. Golo-Mann-Weg uses `cycleway:smoothness=intermediate` (16.2 km/h),
while Ludwigsbrücke uses `excellent` (18 km/h, unchanged from the baseline).

These examples are also © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright),
available under the Open Database License (ODbL).
