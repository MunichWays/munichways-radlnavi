ARG OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:v26.6.5-debian
FROM ${OSRM_IMAGE}

COPY bike.lua /opt/bike.lua
COPY conditional_access.lua /opt/conditional_access.lua
COPY tests/profile-fixture.osm /data/profile-fixture.osm

RUN osrm-extract -p /opt/bike.lua /data/profile-fixture.osm && \
    osrm-partition /data/profile-fixture.osrm && \
    osrm-customize /data/profile-fixture.osrm

CMD ["osrm-routed", "--algorithm", "mld", "--port", "8080", "/data/profile-fixture.osrm"]
