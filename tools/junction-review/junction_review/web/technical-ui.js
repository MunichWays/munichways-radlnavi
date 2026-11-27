// Technical check of one confirmed junction from the app, plus explicit pair exclusions.
// The check runs on the local server as a background job; nothing is activated or deployed.
import {wait} from './api.js';

const STAGE_HINT = {
  topology: 'Straßenarme prüfen; ggf. Sonderregel durch Nachbearbeitung.',
  'polygon-crossing': 'Echte Route nutzt diese Beziehung nicht (Umweg?). Ggf. ausschließen.',
  'directed-corridor': 'Innerer Weg nicht eindeutig belegt; Nachbearbeitung.',
  'gate-matching': 'Route trifft anderen Anschluss; Geometrie oder Gleichwertigkeit prüfen.',
  'reference-sampling': 'Zufahrt zu kurz/verzweigt; Nachbearbeitung.',
  'response-continuity': 'Routingantwort ungewöhnlich; Nachbearbeitung.',
  'runtime-matching': 'Produktionsprüfung lehnt ab; Nachbearbeitung.',
};

export function technicalBlocker(site, {available, dirty, busy, running}) {
  if (!available) return 'Nur im RadlNavi-Repository verfügbar.';
  if (!site) return 'Keine Kreuzung gewählt.';
  if (site.status !== 'confirmed' || !site.decisionCurrent) return 'Erst die Geometrie bestätigen und speichern.';
  if ((site.geometryMode || 'editable') !== 'editable') return 'Keine bearbeitbare Geometrie.';
  if (dirty) return 'Erst die Änderungen speichern oder verwerfen.';
  if (running) return 'Eine technische Prüfung läuft bereits.';
  if (busy) return 'Bitte warten.';
  return '';
}

export function pairOptions(site) {
  const entries = site.gates.filter(g => g.kind === 'entry').map(g => g.label);
  const exits = site.gates.filter(g => g.kind === 'exit').map(g => g.label);
  const excluded = new Set((site.movementExclusions || []).map(m => `${m.entryLabel}|${m.exitLabel}`));
  const kinds = new Map((site.evidenceCurrent ? site.evidence?.movements || [] : []).map(m => [`${m.entryLabel}|${m.exitLabel}`, m.kind]));
  const word = {left: 'links', straight: 'geradeaus', right: 'rechts'};
  return entries.flatMap(entry => exits.map(exit => ({entry, exit, key: `${entry}|${exit}`, kind: kinds.get(`${entry}|${exit}`)})))
    .filter(p => !excluded.has(p.key) && p.kind !== 'right')
    .map(p => ({...p, text: `${p.entry} → ${p.exit}${p.kind ? ' · ' + (word[p.kind] || p.kind) : ''}`}));
}

export function initializeTechnical({$, html, api, project, selected, isDirty, isBusy, replaceSite, message}) {
  let running = null;
  const nonce = () => project()?.workspaceId;

  function render() {
    const site = selected();
    const blocker = technicalBlocker(site, {available: !!project()?.technicalCheckAvailable, dirty: isDirty(), busy: isBusy(), running: !!running});
    $('run-technical').disabled = !!blocker;
    $('run-technical').title = blocker || 'Echte Standardrouten abrufen und alle Fahrbeziehungen prüfen. Aktiviert nichts.';
    $('technical-progress').hidden = !running || running.siteId !== site?.id;
    $('technical-panel').hidden = !site || site.geometryMode === 'none';
    if (!site) return;
    renderResult(site);
    renderExclusions(site);
  }

  function renderResult(site) {
    const check = site.evidenceCurrent ? site.evidence?.appCheck : null;
    const box = $('technical-result');
    if (!check) {
      box.replaceChildren(html('p', {className: 'muted'}, site.evidenceCurrent ? 'Technischer Stand aus früherer Nachbearbeitung (siehe Details unten).'
        : 'Noch keine technische Prüfung für diesen Geometriestand.'));
      return;
    }
    const rows = [html('p', {className: check.standard ? 'technical-standard' : 'warning'},
      `${check.standard ? 'Standardfall – fertig geprüft' : 'Sonderfall – Nachbearbeitung nötig'}: ` +
      `${check.passed}/${check.attempted} links/geradeaus, ${check.rightVerified}/${check.rightAttempted} Rechtskontrollen.`)];
    if (check.connectors?.length) rows.push(html('p', {className: 'muted'}, `Automatisch zugelassene innere Verbinder (OSM): ${check.connectors.join(', ')}`));
    const variants = [...(check.variants?.exit || []), ...(check.variants?.entry || [])];
    if (variants.length) rows.push(html('p', {className: 'muted'},
      `Gleiche Ansage für Radweg/Fahrbahn (Radweg nicht benutzungspflichtig): ${variants.map(g => g.join(' = ')).join(', ')}`));
    if (check.coveredByVariant?.length) rows.push(html('p', {className: 'muted'},
      `Standardroute umfährt die Kreuzung, gleichwertige Ausfahrt geprüft: ${check.coveredByVariant.map(m => `${m.entryLabel} → ${m.exitLabel} (über ${m.partner})`).join(', ')}`));
    if (check.bypassingRights?.length) rows.push(html('p', {className: 'muted'},
      `Rechtskontrolle umfährt die Kreuzung (gültig, kein Makro möglich): ${check.bypassingRights.map(m => `${m.entryLabel} → ${m.exitLabel}`).join(', ')}`));
    for (const issue of check.issues) {
      const pair = issue.entryLabel ? `${issue.entryLabel} → ${issue.exitLabel} (${issue.kind}): ` : '';
      rows.push(html('p', {className: 'recheck-link'}, `${pair}${issue.text}. ${STAGE_HINT[issue.stage] || ''}`));
    }
    rows.push(html('p', {className: 'muted'}, `Geprüft ${check.checkedAt ? new Date(check.checkedAt).toLocaleString('de-DE') : ''} · Unterlagen: ${check.folder}`));
    box.replaceChildren(...rows);
  }

  function renderExclusions(site) {
    const list = site.movementExclusions || [];
    $('exclusion-list').replaceChildren(...(list.length ? list.map((m, index) => {
      const row = html('div', {className: 'exclusion-row'});
      const remove = html('button', {type: 'button', className: 'secondary', disabled: isBusy() || !!running}, 'Aufheben');
      remove.addEventListener('click', () => saveExclusions(list.filter((_, i) => i !== index), 'Ausschluss aufgehoben. Gilt ab der nächsten technischen Prüfung.'));
      row.append(html('span', {}, `${m.entryLabel} → ${m.exitLabel}: ${m.reason}`), remove);
      return row;
    }) : [html('p', {className: 'muted'}, 'Keine ausdrücklich ausgeschlossenen Fahrbeziehungen.')]));
    const options = pairOptions(site);
    const old = $('exclusion-pair').value;
    $('exclusion-pair').replaceChildren(...options.map(p => html('option', {value: p.key, selected: p.key === old}, p.text)));
    for (const id of ['exclusion-pair', 'exclusion-reason', 'add-exclusion']) $(id).disabled = isBusy() || !!running || !options.length;
  }

  async function saveExclusions(exclusions, done) {
    const site = selected();
    try {
      const result = await api(`/api/sites/${encodeURIComponent(site.id)}/exclusions`,
        {body: {expectedVersion: site.editVersion, exclusions: exclusions.map(({entryLabel, exitLabel, reason}) => ({entryLabel, exitLabel, reason}))}});
      replaceSite(result); message(done);
    } catch (error) { message(error.message, true); }
  }

  async function follow(job) {
    running = job; render();
    const workspace = nonce();
    try {
      while (job.status === 'running') {
        $('technical-phase').textContent = job.phase;
        await wait(1500, new AbortController().signal);
        job = await api(`/api/jobs/${job.id}`, {timeout: 10000});
        running = job;
      }
      if (job.status === 'complete') {
        message(job.standard ? 'Technische Prüfung abgeschlossen: Standardfall, fertig geprüft. Nichts aktiviert.'
          : `Technische Prüfung abgeschlossen: Sonderfall mit ${job.issues} Punkt(en) zur Nachbearbeitung. Nichts aktiviert.`);
      } else if (job.status === 'failed') message(job.error || job.phase, true);
      else message(job.phase);
      if (nonce() === workspace) {
        const data = await api('/api/project', {projectId: workspace});
        const site = data.sites.find(s => s.id === job.siteId);
        if (site) replaceSite(site);
      }
    } catch (error) { message(error.message, true); }
    finally { running = null; render(); }
  }

  $('run-technical').addEventListener('click', async () => {
    const site = selected();
    if (technicalBlocker(site, {available: !!project()?.technicalCheckAvailable, dirty: isDirty(), busy: isBusy(), running: !!running})) return;
    try { await follow(await api(`/api/sites/${encodeURIComponent(site.id)}/technical`, {body: {}})); }
    catch (error) { message(error.message, true); running = null; render(); }
  });
  $('cancel-technical').addEventListener('click', async () => {
    if (!running) return;
    try { await api(`/api/jobs/${running.id}/cancel`, {body: {}, timeout: 10000}); } catch (error) { message(error.message, true); }
  });
  $('exclusion-form').addEventListener('submit', event => {
    event.preventDefault();
    const site = selected(), [entry, exit] = $('exclusion-pair').value.split('|'), reason = $('exclusion-reason').value.trim();
    if (!entry || !reason) { message('Bitte Fahrbeziehung und Grund angeben.', true); return; }
    saveExclusions([...(site.movementExclusions || []), {entryLabel: entry, exitLabel: exit, reason}],
      `${entry} → ${exit} ausgeschlossen. Gilt ab der nächsten technischen Prüfung; normale Ansagen bleiben.`)
      .then(() => { $('exclusion-reason').value = ''; });
  });
  // Resume a check that is still running after a page reload.
  api('/api/jobs/current?kind=technical', {timeout: 10000}).then(job => {
    if (job && job.projectId === nonce()) follow(job);
  }).catch(() => {});
  return {render, running: () => !!running};
}
