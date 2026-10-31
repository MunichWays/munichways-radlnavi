import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { prepareSnapshot } from '../build_street_details.mjs';

const feature = (id = '123', properties = {}) => ({ type: 'Feature', properties: { osm_id: id,
  osm_name: 'Testweg', munichways_id: 'shared', munichways_current: 'Text', ...properties },
geometry: { type: 'LineString', coordinates: [[11.5, 48.1], [11.6, 48.2]] } });
function prepare(features, modifyConfig = {}) {
  const raw = Buffer.from(JSON.stringify({ type: 'FeatureCollection', features }));
  return prepareSnapshot(raw, { url: 'https://example.org/v20', sha256: createHash('sha256').update(raw).digest('hex'), ...modifyConfig }, '2026-10-31T10:00:00Z');
}

test('keeps distinct OSM ways sharing a MunichWays ID and partitions details without copying text into geometry', () => {
  const result = prepare([feature('123'), feature('224')]);
  assert.equal(result.manifest.featureCount, 2);
  assert.deepEqual(result.manifest.bbox, [11.5, 48.1, 11.6, 48.2]);
  assert.equal(result.groups['23'].osm_123.munichways_current, 'Text');
  assert.equal(result.groups['24'].osm_224.munichways_id, 'shared');
  assert.equal(result.geometry.features[0].properties.munichways_current, undefined);
});
test('keeps zero and drops unrecognized structured properties', () => {
  const result = prepare([feature('1', { osm_class_bicycle: 0, ignored: { html: 'x' } })]);
  assert.equal(result.groups['01'].osm_1.osm_class_bicycle, '0');
  assert.equal(result.groups['01'].osm_1.ignored, undefined);
});
test('rejects changed snapshot, missing/duplicate IDs and unsupported/invalid coordinates', () => {
  assert.throws(() => prepare([feature()], { sha256: '0'.repeat(64) }), /SHA-256 mismatch/);
  assert.throws(() => prepare([feature('')]), /ID/);
  assert.throws(() => prepare([feature(), feature()]), /Duplicate/);
  assert.throws(() => prepare([{ ...feature(), geometry: { type: 'MultiLineString', coordinates: [] } }]), /geometry/);
  assert.throws(() => prepare([{ ...feature(), geometry: { type: 'LineString', coordinates: [[200, 48], [11, 48]] } }]), /coordinate/);
});
