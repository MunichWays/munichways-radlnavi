# Module versions and releases

RadlNavi versions its independently deployable modules separately:

- `frontend/VERSION`
- `backend/VERSION`
- `routing/VERSION`

The files contain semantic versions (`MAJOR.MINOR.PATCH`) and are the source
for the versions displayed in the frontend. Docker images continue to use the
Git commit as their immutable image tag, so every deployed build remains
traceable.

Before deploying a changed module, update its `VERSION` file:

- `PATCH` for compatible fixes and small improvements
- `MINOR` for compatible new behavior
- `MAJOR` for incompatible changes or a substantial migration

After merging the release commit, create a matching Git tag when the module is
released, for example `frontend-v1.0.1`, `backend-v1.1.0`, or
`routing-v2.0.0`.
