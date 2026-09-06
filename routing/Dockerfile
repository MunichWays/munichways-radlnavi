ARG OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:v26.6.5-debian
ARG MAP_SOURCE=download

FROM alpine:latest AS download

ARG REGION="europe/germany/bayern/oberbayern"
ARG MAP_SNAPSHOT=local

RUN mkdir /data && printf '%s' "$MAP_SNAPSHOT" > /data/snapshot && \
    wget "https://download.geofabrik.de/${REGION}-latest.osm.pbf" -O /data/map.osm.pbf

# Build this stage once and supply its image as MAP_SOURCE to both profiles.
FROM ${MAP_SOURCE} AS map

FROM ${OSRM_IMAGE} AS builder

ARG RADLNAVI_ROUTING_DATE
ARG ROUTING_PROFILE=bike
ARG BUILD_THREADS=2
ENV RADLNAVI_ROUTING_DATE=$RADLNAVI_ROUTING_DATE
ENV TZ=Europe/Berlin

COPY --from=map /data/map.osm.pbf /data/map.osm.pbf
COPY bike.lua /opt/bike.lua
COPY direct.lua /opt/direct.lua
COPY conditional_access.lua /opt/conditional_access.lua
RUN test "$ROUTING_PROFILE" = bike -o "$ROUTING_PROFILE" = direct && \
    sha256sum /data/map.osm.pbf > /data/map.sha256 && \
    osrm-extract --threads ${BUILD_THREADS} -p /opt/${ROUTING_PROFILE}.lua /data/map.osm.pbf
RUN osrm-partition --threads ${BUILD_THREADS} /data/map.osm.pbf
RUN osrm-customize --threads ${BUILD_THREADS} /data/map.osm.pbf

FROM ${OSRM_IMAGE}

ARG VERSION="local"
LABEL org.opencontainers.image.revision=$VERSION

COPY --from=builder /data /data

ENV PORT=8080

CMD ["osrm-routed", "--algorithm", "mld", "--port", "8080", "/data/map.osrm"]
