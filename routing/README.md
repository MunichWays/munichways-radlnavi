# RadlNavi Backend

## Routing- und Ansageanalyse

Die [Analyse zur OSRM-Standardbasis](../docs/osrm-standard-guidance-plan.md)
dokumentiert konkrete Münchner Problemstellen und die Zuständigkeiten von
Routing und App. Für die [Bergmannstraße/Landsberger Straße](../docs/bergmann-landsberger-guidance-analysis-2026-10-13.md)
setzt `bike.lua` die OSRM-Zusammenfassungsgrenze für kurze Manöver auf 0 m;
`direct.lua` übernimmt sie. So bleibt das Linksabbiegen 15,3 m nach dem
Rechtsabbiegen als eigener Step erhalten. Der Routing-Graph muss dafür neu
mit `osrm-extract`, `osrm-partition` und `osrm-customize` gebaut werden.

This is the routing backend for [radlnavi.de](https://www.radlnavi.de).

## Cycleway surface and smoothness

Both Standard and Direct prefer `cycleway:surface` over `surface` and
`cycleway:smoothness` over `smoothness`. Each attribute falls back independently
to its general tag only when the cycleway-specific tag is absent. The existing
surface speed limits and smoothness factors apply to the resolved values;
Direct also uses the resolved surface for its route-selection cost.

Standard and Direct also resolve `cycleway:left/right/both:surface` and
`:smoothness` independently for each direction. `cycleway:surface:left/right/both`
and the corresponding smoothness order are supported as compatibility aliases;
the canonical side-first key wins on a conflict. Side attributes override `both`,
then the unsided cycling attribute, then the general road attribute. Empty values
fall through; unrecognized nonempty values retain precedence and receive no
table-based adjustment.

Side selection follows OSM way order, driving side, road oneway and explicit
cycleway oneway tags. A one-sided two-way cycleway can supply both directions.
Explicit `no`/`separate` sides do not supply attributes to the carriageway.
Attributes never grant access. Pushing uses the general way attributes.
`surface:left/right` without the cycleway prefix is not interpreted as travel
direction: it can describe physical halves of a shared path. Width can be
resolved for inspection but has no effect on access, speeds or selection costs.

The backend uses the same contract for the existing surface distribution and
keeps return journeys separate when their surfaces differ (`segments-v3`).
See the [Munich analysis and measured acceptance results](../docs/issue-22-analysis/README.md).

Profile changes require rebuilding both OSRM datasets, starting with
`osrm-extract`; restarting the servers with old datasets is insufficient.

The synthetic regression suite checks precedence, independent fallbacks,
travel times, selection weights and route choices in both directions. After
building and starting both test profiles (ports 18081 and 18082), run:

```shell
python routing/tests/test_cycleway_tags.py
```

Shared Lua/Python resolver cases run with
`python routing/tests/test_cycling_attributes.py` (`lupa==2.6`) and the backend
unit suite. Build both profiles with
`--build-arg FIXTURE=tests/fixtures/cycling-attributes.osm`, start them on
18089/18090, then run `python routing/tests/test_sided_cycleway_tags.py`.
This checks directional speeds, weights, route choice, width neutrality,
oneway protection and the original Gerner Straße. Regenerate that fixture with
`python routing/tests/build_cycling_fixture.py` after changing shared cases.

It also checks the original Ludwigsbrücke and Golo-Mann-Weg OSM geometries;
see [fixture provenance](tests/fixtures/README.md#cycleway-attribute-examples).

## Seasonal bicycle access

The bicycle profile observes recurring seasonal prohibitions such as
`bicycle:conditional=no @ (Jul 01 - Oct 22)`. This example applies to the
Theresienwiese, which is closed to bicycle traffic in connection with the
Oktoberfest. The condition is evaluated when `osrm-extract` builds the static
routing graph. The regular monthly RadlNavi build refreshes the evaluated
restriction after a seasonal boundary.

Only `no @ (Mon DD - Mon DD)` month/day ranges are currently supported.
Unsupported conditions (for example weekdays, times, explicit years, or
weather) are ignored rather than risking an incorrect road closure.

For reproducible imports, set `RADLNAVI_ROUTING_DATE=YYYY-MM-DD` during
`osrm-extract`. If it is not set, the current date is used.

Run the focused unit tests from this directory with
`lua test_conditional_access.lua`.

The synthetic profile regressions exercise surface speeds, avoided ways, and
barrier handling on a small deterministic OSM fixture:

```shell
docker build -t radlnavi-routing-profile-tests \
  -f routing/tests/Dockerfile routing
docker build --build-arg ROUTING_PROFILE=direct \
  -t radlnavi-routing-direct-profile-tests \
  -f routing/tests/Dockerfile routing
docker run --rm -d -p 18081:8080 \
  --name radlnavi-profile-tests radlnavi-routing-profile-tests
docker run --rm -d -p 18082:8080 \
  --name radlnavi-direct-profile-tests radlnavi-routing-direct-profile-tests
python routing/tests/test_profile_regressions.py
python routing/tests/test_direct_profile.py
python routing/tests/test_cycleway_tags.py
python routing/tests/test_guidance_classes.py
docker stop radlnavi-profile-tests radlnavi-direct-profile-tests
```

## OSRM version and migration smoke test

The routing image uses the official
`ghcr.io/project-osrm/osrm-backend:v26.6.5-debian` image for both data
preprocessing and the routing server. Keeping both stages on the same pinned
version is required because OSRM datasets are version-specific.

Before building the full Oberbayern dataset, the complete MLD pipeline can be
checked quickly with the small Monaco extract:

```shell
docker build \
  --build-arg REGION=europe/monaco \
  --build-arg RADLNAVI_ROUTING_DATE=2026-08-24 \
  -t radlnavi-routing:osrm-26.6.5-smoke \
  -f routing/Dockerfile routing

docker run --rm -p 18080:8080 radlnavi-routing:osrm-26.6.5-smoke
```

The running server can then be checked with a route request such as:

```text
http://localhost:18080/route/v1/bike/7.42056,43.73114;7.42620,43.73840?overview=false&steps=true
```

## Munich route regressions

The data-driven regression suite records stable street corridors and broadly
tolerated distances for sensitive Munich routes. Run it against a locally
started full Oberbayern routing image with:

```shell
python routing/tests/test_route_regressions.py --endpoint http://localhost:8080
```

It can also be run against the current production baseline:

```shell
python routing/tests/test_route_regressions.py \
  --endpoint https://api.radlnavi.munichways.de
```

Distance tolerances deliberately allow ordinary OSM data changes. A changed
street sequence or a substantial detour fails and must be reviewed before an
OSRM migration is deployed.
