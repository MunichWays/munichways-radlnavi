FROM node:18.16-buster AS builder

RUN git clone https://github.com/mapbox/tippecanoe.git
RUN cd tippecanoe && make -j && make install && cd -

ARG BACKEND_URL="https://backend.radlnavi.de"
ARG VERSION="local"
ARG COMMIT=""
ARG REGION="europe/germany/bayern/oberbayern"

COPY package.json package.json
COPY package-lock.json package-lock.json
COPY tsconfig.json tsconfig.json

RUN npm install --verbose --force

COPY public public
COPY load_munichways.mjs load_munichways.mjs

# build class:bicycle map overlay
RUN wget "https://download.geofabrik.de/${REGION}-latest.osm.pbf" -O ./map.osm.pbf
RUN wget "https://download.geofabrik.de/${REGION}.poly" -O ./map.poly
RUN node load_munichways.mjs
RUN mkdir ./public/layers
RUN ./tippecanoe/tippecanoe --maximum-zoom=19 --no-tile-compression -e ./public/layers/munichways ./public/munichways.json

COPY src src

RUN REACT_APP_BACKEND_URL="$BACKEND_URL" REACT_APP_VERSION="$VERSION" REACT_APP_COMMIT="$COMMIT" npm run build

FROM ubuntu/nginx

ARG VERSION="local"
LABEL org.opencontainers.image.revision=$VERSION

ENV PORT 80

COPY --from=builder build /var/www/html

EXPOSE 80

CMD ["nginx","-g","daemon off;"]
