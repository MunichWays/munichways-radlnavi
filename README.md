# radlnavi.de

This project has the code basis for frontend and backend of radlnavi.de. A webpage for regional bike navigation in and around Munich. The routing algorithm takes into account the `class:bicycle` information given by OpenStreetMap and navigates preferably via good rated route segments.

Routing is done via the [backend service](./backend/), is based on the open source projekt OSRM (Open Source Routing Machine) and uses the rules and speeds given in the [bike.lua](./routing/bike.lua) file.

The [frontend service](./frontend/) interacts with the user and also features an overlay of the different route segments that have been annotated with `class:bicycle`. Therefor, the script [load_munichways.mjs](./frontend/load_munichways.mjs) needs to be executed, while development or eventually, when a new version of the frontend is build via docker.

# Development

There are two different ways to run RadlNavi locally. Choose the workflow based
on which services you changed.

## Test frontend changes only

Use this workflow when only files in `frontend/` have changed. It starts the
React development server locally and uses the currently deployed MunichWays
production backend for routing and route analysis. A local backend, routing
engine, and Docker are not required.

Prerequisites:

- Node.js and npm
- Internet access to the production backend

From the repository root, run:

```powershell
cd frontend
npm install --legacy-peer-deps
npm start
```

Open <http://localhost:3000> if the browser does not open automatically.

In development, API and MunichWays vector-tile requests use relative URLs. The
proxy in `frontend/src/setupProxy.js` forwards:

- `/route`, `/tag_distribution`, and `/version` to the deployed MunichWays API
- `/layers/munichways` to the deployed MunichWays frontend, which provides the
  generated rating tiles

This makes both routing and the colored MunichWays ratings available locally
without browser CORS restrictions. The development proxy is used only by
`npm start`; it does not affect production builds.

Run `npm install --legacy-peer-deps` only after the initial checkout or when the
dependencies have changed. The option is currently required because the
Leaflet fork used by the project does not satisfy `leaflet.vectorgrid`'s peer
dependency declaration. For subsequent starts, `npm start` is sufficient.

## Test frontend together with backend or routing changes

Use this workflow when `backend/` or `routing/` has changed, or when an
end-to-end test of all local services is required. Docker Compose builds and
starts the local frontend, backend, and OSRM routing service together.

Prerequisites:

- Docker with Docker Compose

From the repository root, run:

```powershell
docker compose up --build
```

Open <http://localhost>. The service connections in this setup are:

- Frontend: <http://localhost>
- Backend API: <http://localhost:8000>
- Routing service: <http://localhost:8080>

The Docker frontend is built with `BACKEND_URL=http://localhost:8000`, so it
uses the local backend rather than the production backend. The local backend in
turn connects to the routing container through the Docker network.

Stop all services with `Ctrl+C`. To remove the stopped containers afterwards,
run:

```powershell
docker compose down
```

## Radl-Komfort API

Clients can request the centrally calculated Radl-Komfort metadata together
with an OSRM-compatible route by adding `comfort=true`:

```text
GET /route/v1/bike/{coordinates}?comfort=true&annotations=false&...
```

The backend requests node and distance annotations internally and analyzes each
leg separately, including partially traversed boundary edges. Internally added
annotations are removed before returning the response, including after an
analysis error. Each entry in `routes` receives a `comfort` object:

```json
{
  "index": 78,
  "coverage": 82,
  "sufficientCoverage": true,
  "distribution": {
    "black": 2,
    "red": 7,
    "yellow": 18,
    "green": 68,
    "unrated": 5
  }
}
```

`index` is a length-weighted value from 0 to 100. It is `null` when less than
70 percent of the analyzed route is rated. `coverage` and all values in
`distribution` are integer percentages; the distribution always sums to 100.
Unknown `class:bicycle` values are included in `unrated`.

The option is explicitly opt-in: requests without `comfort=true` remain an
unchanged OSRM proxy without comfort-analysis overhead. If optional comfort
analysis fails, the valid routing response is still returned without the
`comfort` field.

The existing `POST /tag_distribution` response also contains the same
backend-calculated `comfort` object for the RadlNavi web frontend.

The original `{ "node_ids": [...] }` request remains supported. For exact
partial-edge lengths, clients can instead send `{ "legs": [...] }`. Each leg
contains OSRM's `annotation.nodes` as `nodes`, `annotation.distance` as
`distance`, and optional snapped `start`/`end` coordinates in longitude/latitude
order. Never flatten these arrays across intermediate stops. The `/route`
wrapper supplies this context as `route.analysis_legs`; the web client forwards
it to the existing analysis endpoint.

Analysis uses ordered edge occurrences and a per-request pair index. Loops and
return journeys retain every traversal. Competing OSM ways remain unrated;
missing nodes never create shortcut edges. Highlight geometries stay separate
for disconnected visits. Keys in `TagInfo.ways` identify occurrences: the first
visit uses the OSM way ID, further visits use `wayId:legIndex:segmentIndex`.
Consumers should iterate the values, as the web frontend already does.

Responses include `analysis` metadata (`comfortAnalysis` on enriched routes),
with version `segments-v2`, distance basis and unresolved-segment counts.
Node-only requests still use distances between bounding OSM nodes; they cannot
recover snapped endpoints or lost leg boundaries. See the
[implementation notes and benchmark](docs/routing-performance-segments.md)
for compatibility limits and deliberate corrections to previous results.

## Local build versions

Frontend, backend, and routing are built and deployed independently. The
frontend displays all three build versions and the OSRM version. To label local
Docker images with the currently checked-out Git commit in PowerShell, run:

```powershell
$env:VERSION = git rev-parse --short HEAD
docker compose build frontend backend routing
docker compose up -d --no-build --force-recreate frontend backend routing
```

The backend also exposes the same information as JSON at
`http://localhost:8000/version`. Without the `VERSION` environment variable,
local images are identified as `local`.

# Release

Each service (frontend and backend) have their own `build.sh` script that builds the respective docker container. The full system can be build via the [root build.sh](./build.sh) script. Since currently the webpage is hosted via Google's Cloud Run service, whenever new images are built, these need to be pushed to the Cloud Run registry and deployed via the Google Cloud Console.
