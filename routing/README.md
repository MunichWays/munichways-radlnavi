# RadlNavi Backend

This is the routing backend for [radlnavi.de](https://www.radlnavi.de).

## Seasonal bicycle access

The bicycle profile observes seasonal prohibitions such as
`bicycle:conditional=no @ (Jul 01 - Oct 22)`. This example applies to the
Theresienwiese, which is closed to bicycle traffic in connection with the
Oktoberfest. The condition is evaluated when `osrm-extract` builds the static
routing graph, so the routing image must be rebuilt when a seasonal restriction
starts or ends.

For reproducible imports, set `RADLNAVI_ROUTING_DATE=YYYY-MM-DD` during
`osrm-extract`. If it is not set, the current date is used.
