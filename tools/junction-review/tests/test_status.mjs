import test from 'node:test';
import assert from 'node:assert/strict';
import {specialCase, viewStatus} from '../junction_review/web/app.js';

const confirmed = {status: 'confirmed', evidenceCurrent: false, technicalStatus: 'not-run'};
test('a confirmation counts as technically checked only with current evidence', () => {
  assert.equal(viewStatus(confirmed), 'confirmed');
  assert.equal(viewStatus({...confirmed, evidenceCurrent: true, technicalStatus: '8/8 Links-/Geradeausbeziehungen technisch bestanden'}), 'checked');
  // Changed geometry: old evidence is no longer current.
  assert.equal(viewStatus({...confirmed, evidenceCurrent: false, technicalStatus: 'not-run', evidence: {technical: 'alt'}}), 'confirmed');
  assert.equal(viewStatus({status: 'open', evidenceCurrent: true, technicalStatus: 'x'}), 'open');
  assert.equal(viewStatus({status: 'excluded', evidenceCurrent: true, technicalStatus: 'Keine Aktivierung vorgesehen: ausgeschlossen'}), 'excluded');
});
test('live only for the current geometry, branch activation stays checked', () => {
  const current = {...confirmed, evidenceCurrent: true, technicalStatus: '8/8 bestanden'};
  assert.equal(viewStatus({...current, deploymentStatus: 'live'}), 'live');
  assert.equal(viewStatus({...current, deploymentStatus: 'branch-ready'}), 'checked');
  assert.equal(viewStatus({...current, technicalStatus: 'not-run', deploymentStatus: 'live'}), 'live');
  assert.equal(viewStatus({...confirmed, deploymentStatus: 'older-geometry'}), 'confirmed');
  assert.equal(viewStatus({status: 'excluded', evidenceCurrent: true, deploymentStatus: 'live'}), 'excluded');
  assert.equal(specialCase({...current, deploymentStatus: 'live', evidence: {appCheck: {standard: false}}}), false);
});
test('special cases stay visible among checked junctions', () => {
  const checked = {...confirmed, evidenceCurrent: true, technicalStatus: '3/8 … · Sonderfall'};
  assert.equal(specialCase({...checked, evidence: {appCheck: {standard: false}}}), true);
  assert.equal(specialCase({...checked, evidence: {appCheck: {standard: true}}}), false);
  assert.equal(specialCase({...checked, technicalStatus: 'Technisch zurückgestellt: 5 Richtungen', evidence: {}}), true);
  assert.equal(specialCase(confirmed), false);
});
