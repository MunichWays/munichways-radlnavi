# Oberbayern V20 snapshot review, 2026-11-01

The mutable source URL changed after the previously approved 2026-10-26
snapshot. This caused the frontend Docker build to stop at its SHA-256 guard.
The guard and all structural checks remain unchanged.

Reviewed source: `https://www.munichways.de/App/IST_RadlVorrangNetz_Oberbayern_V20.geojson`

- HTTP Last-Modified: `Sun, 01 Nov 2026 22:42:14 GMT`.
- Size: 36,559,882 bytes.
- SHA-256: `45dcebccd9eab74c022a6b3050fad8134ca96a46255492c307dce1848784e7a9`.
- Existing `prepareSnapshot` validation passes for all 27,356 features:
  unique numeric OSM way IDs, LineString geometry and valid WGS84 coordinates.
- Bounds: longitude 10.8345697 to 12.7159446; latitude 47.6244279 to 48.4052503.
- 6,528 priority-network features; 100 detail groups.

Only the approved hash and source date in `street-details-source.json` change.
A future source update still requires review before its new hash is approved.
