# RadlNavi Backend

This is the routing backend for [radlnavi.de](https://www.radlnavi.de).

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
