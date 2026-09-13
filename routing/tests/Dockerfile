ARG OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:v26.6.5-debian
FROM ${OSRM_IMAGE}
ARG ROUTING_PROFILE=bike
ARG FIXTURE=tests/profile-fixture.osm

COPY bike.lua /opt/bike.lua
COPY direct.lua /opt/direct.lua
COPY conditional_access.lua /opt/conditional_access.lua
COPY ${FIXTURE} /data/profile-fixture.osm

RUN osrm-extract -p /opt/${ROUTING_PROFILE}.lua /data/profile-fixture.osm && \
    osrm-partition /data/profile-fixture.osrm && \
    osrm-customize /data/profile-fixture.osrm

CMD ["osrm-routed", "--algorithm", "mld", "--port", "8080", "/data/profile-fixture.osrm"]
