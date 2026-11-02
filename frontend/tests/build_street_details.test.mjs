import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { prepareSnapshot, buildSnapshot } from '../build_street_details.mjs';

const feature = (id = '123', properties = {}) => ({ type: 'Feature', properties: { osm_id: id,
  osm_name: 'Testweg', munichways_id: 'shared', munichways_current: 'Text', ...properties },
geometry: { type: 'LineString', coordinates: [[11.5, 48.1], [11.6, 48.2]] } });

test('keeps Jahnstraße in Olching red without class:bicycle or MunichWays details', async () => {
  const jahnstrasse = JSON.parse(await readFile(new URL('../src/fixtures/street-olching-jahnstrasse.json', import.meta.url)));
  const result = prepare([jahnstrasse]);
  assert.equal(result.geometry.features[0].id, 'osm_8059921');
  assert.equal(result.geometry.features[0].properties.color, 'red');
  assert.equal(result.geometry.features[0].properties.osm_class_bicycle, undefined);
  assert.equal(result.groups['21'].osm_8059921.munichways_id, '');
  assert.equal(result.priorityNetwork.features.length, 0);
});
function prepare(features, modifyConfig = {}) {
  const raw = Buffer.from(JSON.stringify({ type: 'FeatureCollection', features }));
  return prepareSnapshot(raw, { url: 'https://example.org/v20', lastModified: 'Mon, 26 Oct 2026 18:55:33 GMT', ...modifyConfig }, '2026-10-31T10:00:00Z');
}

test('keeps distinct OSM ways sharing a MunichWays ID and partitions details without copying text into geometry', () => {
  const result = prepare([feature('123'), feature('224')]);
  assert.equal(result.manifest.featureCount, 2);
  assert.equal(result.manifest.sourceCreatedAt, '2026-10-26');
  assert.equal(result.manifest.retrievedAt, '2026-10-31T10:00:00Z');
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

test('keeps MunichWays-only lines, including separate geometries with the same master ID', () => {
  const first = feature('', { munichways_id: 'LHM_42', osm_class_bicycle: '-', munichways_color: 'gelb', munichways_mw_rv_route: 'Standard' });
  const second = { ...first, geometry: { type: 'LineString', coordinates: [[11.6, 48.2], [11.7, 48.3]] } };
  const result = prepare([feature('123'), first, second]);
  assert.equal(result.geometry.features.length, 3);
  assert.equal(result.munichWaysOnly.features.length, 2);
  const [a, b] = result.munichWaysOnly.features;
  assert.match(a.id, /^mw_[a-f0-9]{64}$/);
  assert.notEqual(a.id, b.id);
  assert.equal(prepare([first]).geometry.features[0].id, a.id);
  assert.equal(result.groups[`mw-${a.id.slice(-2)}`][a.id].munichways_id, 'LHM_42');
  assert.equal(a.properties.munichways_color, 'gelb');
  assert.deepEqual(result.priorityNetwork.features.map(f => f.id), [a.id, b.id]);
  assert.throws(() => prepare([first, first]), /Duplicate/);
});
test('rejects missing/duplicate IDs and unsupported/invalid coordinates', () => {
  assert.throws(() => prepare([null]), /feature/);
  assert.throws(() => prepare([{ ...feature(), properties: [] }]), /properties/);
  assert.throws(() => prepare([feature('', { munichways_id: '-' })]), /ID/);
  assert.throws(() => prepare([feature(), feature()]), /Duplicate/);
  assert.throws(() => prepare([{ ...feature(), geometry: { type: 'MultiLineString', coordinates: [] } }]), /geometry/);
  assert.throws(() => prepare([{ ...feature(), geometry: { type: 'LineString', coordinates: [[200, 48], [11, 48]] } }]), /coordinate/);
});

test('priority membership matches the App sentinel rule, including compound values', () => {
  const values = [undefined, null, '', '-', 'Standard', 'Premium', 'Standard,-', '-,-'];
  const result = prepare(values.map((value, i) => feature(String(i + 1), { munichways_mw_rv_route: value })));
  assert.deepEqual(result.priorityNetwork.features.map(f => f.id), ['osm_5', 'osm_6', 'osm_7', 'osm_8']);
  assert.equal(result.geometry.features.length, 8);
  assert.equal(result.geometry.features[4].properties.munichways_mw_rv_route, undefined);
});


test('weekly content changes get fresh content hashes without a pinned approval', () => {
  const first = prepare([feature('1')]);
  const next = prepare([feature('2')], { lastModified: 'Sun, 01 Nov 2026 22:42:14 GMT' });
  assert.notEqual(first.manifest.snapshot, next.manifest.snapshot);
  assert.equal(next.manifest.sourceCreatedAt, '2026-11-01');
  assert.equal(prepare([feature('2')]).manifest.snapshot, next.manifest.snapshot);
  for (const lastModified of [undefined, '', 'invalid', 'Tue, 31 Feb 2026 00:00:00 GMT']) {
    assert.equal(prepare([feature('2')], {lastModified}).manifest.sourceCreatedAt, null);
  }
});

test('valid weekly downloads publish matching artifacts; failure preserves the old manifest and retry recovers', async t => {
  const output = await mkdtemp(path.join(tmpdir(), 'v20-build-test-'));
  t.after(() => rm(output, { recursive: true, force: true }));
  const publish = (features, status = 200) => buildSnapshot({ output, fetchImpl: async (url, options) => {
    assert.match(url, /Oberbayern_V20/);
    assert.equal(options.cache, 'no-store');
    return new Response(JSON.stringify({type:'FeatureCollection',features}), {
      status, headers: {'Last-Modified':'Sun, 01 Nov 2026 22:42:14 GMT'},
    });
  }});
  await publish([feature('1')]);
  const readManifest = () => readFile(path.join(output, 'manifest.json'), 'utf8');
  const original = await readManifest();
  await assert.rejects(publish([feature('1'),feature('1')]), /Duplicate/);
  assert.equal(await readManifest(), original);
  await assert.rejects(publish([], 503), /HTTP 503/);
  assert.equal(await readManifest(), original);
  await assert.rejects(buildSnapshot({output, fetchImpl: async () => { throw new Error('offline'); }}), /offline/);
  assert.equal(await readManifest(), original);
  await publish([feature('2')]);
  const manifest = JSON.parse(await readManifest());
  assert.notEqual(manifest.snapshot, JSON.parse(original).snapshot);
  const version = path.join(output, manifest.snapshot);
  const geometry = JSON.parse(await readFile(path.join(version, 'geometry.json')));
  const details = JSON.parse(await readFile(path.join(version, 'details/02.json')));
  assert.equal(geometry.features[0].id, 'osm_2');
  assert.equal(details.osm_2.osm_name, 'Testweg');
  assert.equal(manifest.sourceCreatedAt, '2026-11-01');
  const raw = Buffer.from(JSON.stringify({type:'FeatureCollection',features:[feature('2')]}));
  assert.equal(manifest.snapshot, createHash('sha256').update('street-details-v2\0').update(raw).digest('hex'));
  await publish([feature('3'), feature('', { munichways_id: 'MW_ONLY', color: 'yellow' })]);
  const withMw = JSON.parse(await readManifest());
  const mwVersion = path.join(output, withMw.snapshot);
  const onlyMw = JSON.parse(await readFile(path.join(mwVersion, 'munichways-only-v1.json')));
  assert.equal(onlyMw.features.length, 1);
  const mwId = onlyMw.features[0].id;
  const mwDetails = JSON.parse(await readFile(path.join(mwVersion, 'details', `mw-${mwId.slice(-2)}.json`)));
  assert.equal(mwDetails[mwId].munichways_id, 'MW_ONLY');
});
