import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const root = path.dirname(fileURLToPath(import.meta.url));
const fields = ['osm_id', 'osm_name', 'osm_class_bicycle', 'osm_smoothness', 'osm_surface',
  'osm_highway', 'osm_lit', 'osm_bicycle', 'osm_width', 'osm_access', 'color',
  'munichways_id', 'munichways_name', 'munichways_current', 'munichways_target',
  'munichways_description', 'munichways_status_implementation', 'munichways_neuralgic_point',
  'munichways_net_type_plan', 'munichways_net_type_target', 'munichways_mw_rv_route',
  'munichways_route_link', 'munichways_measure_category_link', 'munichways_district_link',
  'munichways_links', 'munichways_mapillary_link'];

export function prepareSnapshot(raw, config, retrievedAt = new Date().toISOString()) {
  const snapshot = createHash('sha256').update(raw).digest('hex');
  if (snapshot !== config.sha256) throw new Error(`V20 SHA-256 mismatch: expected ${config.sha256}, received ${snapshot}. Review the new source before updating street-details-source.json.`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(config.createdAt || '') ||
      !Number.isFinite(Date.parse(config.createdAt)) || new Date(config.createdAt).toISOString().slice(0, 10) !== config.createdAt) {
    throw new Error('A valid source creation date is required in street-details-source.json');
  }
  const data = JSON.parse(raw.toString('utf8'));
  if (data.type !== 'FeatureCollection' || !Array.isArray(data.features) || !data.features.length) {
    throw new Error('V20 must be a nonempty FeatureCollection');
  }
  const ids = new Set();
  const features = [];
  const groups = {};
  const bbox = [180, 90, -180, -90];
  for (const feature of data.features) {
    const p = feature.properties;
    const osmId = String(p?.osm_id ?? '').trim();
    if (!/^\d+$/.test(osmId)) throw new Error('Missing or invalid OSM way ID');
    const id = `osm_${osmId}`;
    if (ids.has(id)) throw new Error(`Duplicate OSM way ID: ${osmId}`);
    ids.add(id);
    const geometry = feature.geometry;
    if (geometry?.type !== 'LineString' || !Array.isArray(geometry.coordinates) || geometry.coordinates.length < 2) {
      throw new Error(`Unsupported or invalid line geometry: ${id}`);
    }
    const coordinates = geometry.coordinates.map(c => {
      if (!Array.isArray(c) || c.length < 2 || !Number.isFinite(c[0]) || !Number.isFinite(c[1]) ||
          Math.abs(c[0]) > 180 || Math.abs(c[1]) > 90) throw new Error(`Invalid coordinate: ${id}`);
      bbox[0] = Math.min(bbox[0], c[0]); bbox[1] = Math.min(bbox[1], c[1]);
      bbox[2] = Math.max(bbox[2], c[0]); bbox[3] = Math.max(bbox[3], c[1]);
      return [c[0], c[1]];
    });
    // Only short display fields travel with the search geometry, never the full detail texts.
    const summary = {};
    for (const key of ['osm_name', 'munichways_name', 'osm_class_bicycle', 'color']) {
      if (typeof p[key] === 'string' || typeof p[key] === 'number') summary[key] = String(p[key]);
    }
    features.push({ type: 'Feature', id, properties: summary, geometry: { type: 'LineString', coordinates } });
    const group = osmId.slice(-2).padStart(2, '0');
    groups[group] ??= {};
    groups[group][id] = Object.fromEntries(fields.filter(key => typeof p[key] === 'string' || typeof p[key] === 'number')
      .map(key => [key, String(p[key])]));
  }
  return {
    manifest: { schemaVersion: 1, snapshot, sourceUrl: config.url, sourceCreatedAt: config.createdAt, retrievedAt, bbox,
      featureCount: features.length },
    geometry: { type: 'FeatureCollection', features }, groups,
  };
}

export async function buildSnapshot({ source, output = path.join(root, 'public/street-details') } = {}) {
  const config = JSON.parse(await readFile(path.join(root, 'street-details-source.json'), 'utf8'));
  let raw;
  if (source) raw = await readFile(source);
  else {
    const response = await fetch(config.url, { signal: AbortSignal.timeout(120000) });
    if (!response.ok) throw new Error(`V20 download failed: HTTP ${response.status}`);
    raw = Buffer.from(await response.arrayBuffer());
  }
  const { manifest, geometry, groups } = prepareSnapshot(raw, config);
  const versionDir = path.join(output, manifest.snapshot);
  await mkdir(path.join(versionDir, 'details'), { recursive: true });
  await writeFile(path.join(versionDir, 'geometry.json'), JSON.stringify(geometry));
  let largestGroupBytes = 0;
  for (const [group, entries] of Object.entries(groups)) {
    const content = JSON.stringify(entries);
    largestGroupBytes = Math.max(largestGroupBytes, Buffer.byteLength(content));
    await writeFile(path.join(versionDir, 'details', `${group}.json`), content);
  }
  // Publish the manifest last so partial/invalid downloads never advertise a new snapshot.
  await writeFile(path.join(output, 'manifest.json.tmp'), JSON.stringify(manifest));
  await rename(path.join(output, 'manifest.json.tmp'), path.join(output, 'manifest.json'));
  console.log(JSON.stringify({ ...manifest, geometryBytes: Buffer.byteLength(JSON.stringify(geometry)),
    detailGroups: Object.keys(groups).length, largestGroupBytes }, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  const options = {};
  for (let i = 0; i < args.length; i += 2) {
    if (!['--source', '--output'].includes(args[i]) || !args[i + 1]) throw new Error('Usage: node build_street_details.mjs [--source FILE] [--output DIR]');
    options[args[i].slice(2)] = args[i + 1];
  }
  await buildSnapshot(options);
}
