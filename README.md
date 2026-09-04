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
