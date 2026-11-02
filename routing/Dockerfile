ARG OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:v26.6.5-debian
ARG MAP_SOURCE=download

FROM alpine:latest AS download

ARG REGION="europe/germany/bayern/oberbayern"
ARG MAP_SNAPSHOT=local

RUN mkdir /data && printf '%s' "$MAP_SNAPSHOT" > /data/snapshot && \
    wget "https://download.geofabrik.de/${REGION}-latest.osm.pbf" -O /data/map.osm.pbf

# Build this stage once and supply its image as MAP_SOURCE to both profiles.
FROM ${MAP_SOURCE} AS map

FROM python:3.12-alpine AS discovery-data
ARG ROUTING_PROFILE=bike
ARG V20_SNAPSHOT=local
COPY build_secret_tips.py /build_secret_tips.py
RUN printf '%s\n' "$V20_SNAPSHOT" > /v20-snapshot && \
    if [ "$ROUTING_PROFILE" = discovery ]; then \
      python /build_secret_tips.py --output /secret_tips.lua; \
    else printf 'return {}\n' > /secret_tips.lua; fi

FROM ${OSRM_IMAGE} AS builder

ARG RADLNAVI_ROUTING_DATE
ARG ROUTING_PROFILE=bike
ARG BUILD_THREADS=2
ENV RADLNAVI_ROUTING_DATE=$RADLNAVI_ROUTING_DATE
ENV TZ=Europe/Berlin

COPY --from=map /data/map.osm.pbf /data/map.osm.pbf
COPY bike.lua /opt/bike.lua
COPY direct.lua /opt/direct.lua
COPY discovery.lua /opt/discovery.lua
COPY --from=discovery-data /secret_tips.lua /opt/secret_tips.lua
COPY conditional_access.lua /opt/conditional_access.lua
COPY guidance_way_type.lua /opt/guidance_way_type.lua
COPY cycling_attributes.lua /opt/cycling_attributes.lua
RUN test "$ROUTING_PROFILE" = bike -o "$ROUTING_PROFILE" = direct -o "$ROUTING_PROFILE" = discovery && \
    cp /opt/secret_tips.lua /data/secret_tips.lua && \
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
