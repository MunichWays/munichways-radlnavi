import test from 'node:test';
import assert from 'node:assert/strict';
import {pairOptions, technicalBlocker} from '../junction_review/web/technical-ui.js';

const site = {status: 'confirmed', decisionCurrent: true, geometryMode: 'editable',
  gates: [{label: 'Entry-1', kind: 'entry'}, {label: 'Entry-2', kind: 'entry'}, {label: 'Exit-1', kind: 'exit'}, {label: 'Exit-2', kind: 'exit'}],
  evidenceCurrent: true, evidence: {movements: [{entryLabel: 'Entry-1', exitLabel: 'Exit-1', kind: 'right'}, {entryLabel: 'Entry-1', exitLabel: 'Exit-2', kind: 'left'}]},
  movementExclusions: [{entryLabel: 'Entry-2', exitLabel: 'Exit-1', reason: 'x'}]};
const ready = {available: true, dirty: false, busy: false, running: false};

test('technical check only for a saved, current confirmation', () => {
  assert.equal(technicalBlocker(site, ready), '');
  assert.match(technicalBlocker({...site, decisionCurrent: false}, ready), /bestätigen/);
  assert.match(technicalBlocker({...site, status: 'open'}, ready), /bestätigen/);
  assert.match(technicalBlocker(site, {...ready, dirty: true}), /speichern/);
  assert.match(technicalBlocker(site, {...ready, running: true}), /läuft/);
  assert.match(technicalBlocker(site, {...ready, available: false}), /Repository/);
});

test('exclusion choices skip right turns and existing exclusions and name the kind', () => {
  assert.deepEqual(pairOptions(site).map(p => p.text), ['Entry-1 → Exit-2 · links', 'Entry-2 → Exit-2']);
});
