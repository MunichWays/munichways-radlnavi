import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {districtName, districtOutlines, districtSelection} from '../junction_review/web/districts.js';

const data = JSON.parse(await readFile(new URL('../junction_review/web/stadtbezirke.geojson', import.meta.url)));
test('all Munich districts have the requested BA labels and stable offline selection', () => {
  assert.equal(data.features.length,25);
  const codes = data.features.map(feature => districtSelection(feature).districtId).sort();
  assert.deepEqual(codes,Array.from({length:25},(_,i) => `BA${String(i+1).padStart(2,'0')}`));
  const ba04 = data.features.find(feature => feature.properties.bezirk_nummer==='BA04');
  assert.equal(districtName(ba04),'BA04 Schwabing-West');
  assert.deepEqual(districtSelection(ba04),{districtId:'BA04',name:'BA04 Schwabing-West'});
});
test('boundary drawing retains every disjoint polygon ring', () => {
  for (const id of ['BA18','BA19']) {
    const feature = data.features.find(feature => feature.properties.bezirk_nummer===id);
    assert.equal(districtOutlines(feature).length,2);
    assert.deepEqual(districtOutlines(feature),feature.geometry.coordinates.flat());
  }
});
