ARG OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:v26.6.5-debian

FROM alpine:latest AS map

ARG REGION="europe/germany/bayern/oberbayern"

RUN wget "https://download.geofabrik.de/${REGION}-latest.osm.pbf" -O /opt/map.osm.pbf

FROM ${OSRM_IMAGE} AS builder

ARG RADLNAVI_ROUTING_DATE
ENV RADLNAVI_ROUTING_DATE=$RADLNAVI_ROUTING_DATE
ENV TZ=Europe/Berlin

COPY --from=map /opt/map.osm.pbf /data/map.osm.pbf
COPY bike.lua /opt/bike.lua
COPY conditional_access.lua /opt/conditional_access.lua
RUN osrm-extract -p /opt/bike.lua /data/map.osm.pbf
RUN osrm-partition /data/map.osm.pbf
RUN osrm-customize /data/map.osm.pbf

FROM ${OSRM_IMAGE}

ARG VERSION="local"
LABEL org.opencontainers.image.revision=$VERSION

COPY --from=builder /data /data

ENV PORT=8080

CMD ["osrm-routed", "--algorithm", "mld", "--port", "8080", "/data/map.osrm"]
