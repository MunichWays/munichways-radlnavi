const NS = 'http://www.w3.org/2000/svg';
const labels = {open: 'Offen', confirmed: 'Bestätigt', deferred: 'Zurückgestellt', excluded: 'Ausgeschlossen'};
const colors = {open: '#8450ac', confirmed: '#248060', deferred: '#bd8b1c', excluded: '#83818b'};
const EARTH_RADIUS = 6378137;
const WORLD = 2 * Math.PI * EARTH_RADIUS;
const mercatorY = lat => EARTH_RADIUS * Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));

export function projection(origin) {
  const scale = Math.cos(origin[1] * Math.PI / 180), y = mercatorY(origin[1]);
  return {to: p => [(p[0] - origin[0]) * WORLD / 360 * scale, (y - mercatorY(p[1])) * scale],
    from: p => [p[0] / (WORLD / 360 * scale) + origin[0],
      (2 * Math.atan(Math.exp((y - p[1] / scale) / EARTH_RADIUS)) - Math.PI / 2) * 180 / Math.PI]};
}

export function visibleTiles(box, origin, pixelWidth) {
  const scale = Math.cos(origin[1] * Math.PI / 180);
  const z = Math.max(0, Math.min(19, Math.round(Math.log2(WORLD * scale * Math.max(1, pixelWidth) / (256 * box[2])))));
  const count = 2 ** z, size = WORLD * scale / count;
  const worldX = (origin[0] + 180) / 360 * count;
  const worldY = (.5 - mercatorY(origin[1]) / WORLD) * count;
  const minX = Math.floor(worldX + box[0] / size), maxX = Math.ceil(worldX + (box[0] + box[2]) / size) - 1;
  const minY = Math.max(0, Math.floor(worldY + box[1] / size));
  const maxY = Math.min(count - 1, Math.ceil(worldY + (box[1] + box[3]) / size) - 1);
  const tiles = [];
  for (let x = minX; x <= maxX; x++) for (let y = minY; y <= maxY; y++) {
    const wrappedX = ((x % count) + count) % count;
    tiles.push({key: `${z}/${x}/${y}`, url: `https://tile.openstreetmap.org/${z}/${wrappedX}/${y}.png`,
      x: (x - worldX) * size, y: (y - worldY) * size, size});
  }
  return tiles;
}

export function moveVertex(polygon, index, position) {
  const result = polygon.map(p => [...p]);
  result[index] = position;
  if (index === 0) result[result.length - 1] = [...position];
  return result;
}

export function spreadLabels(items, gap, min, max) {
  const sorted = items.map(x => ({...x})).sort((a, b) => a.y - b.y);
  sorted.forEach((p, i) => p.labelY = Math.max(p.y, i ? sorted[i - 1].labelY + gap : min));
  for (let i = sorted.length - 1; i >= 0; i--) sorted[i].labelY = Math.min(sorted[i].labelY, i === sorted.length - 1 ? max : sorted[i + 1].labelY - gap);
  return sorted;
}

function el(tag, attrs = {}, text = null) {
  const node = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== null) node.textContent = text;
  return node;
}

function html(tag, attrs = {}, text = null) {
  const node = document.createElement(tag);
  Object.assign(node, attrs);
  if (text !== null) node.textContent = text;
  return node;
}

function createMap(container, points, origin, padding = 30) {
  container.disposeMap?.();
  container.replaceChildren();
  const project = projection(origin);
  const xy = points.map(project.to);
  const xs = xy.map(p => p[0]), ys = xy.map(p => p[1]);
  const minX = Math.min(...xs) - padding, maxX = Math.max(...xs) + padding;
  const minY = Math.min(...ys) - padding, maxY = Math.max(...ys) + padding;
  const aspect = container.clientWidth / container.clientHeight || 1.5;
  const width = Math.max(maxX - minX, (maxY - minY) * aspect);
  const height = Math.max(maxY - minY, width / aspect);
  const initial = [(minX + maxX - width) / 2, (minY + maxY - height) / 2, width, height];
  let box = [...initial];
  const svg = el('svg', {viewBox: box.join(' '), role: 'img', 'aria-label': 'Kreuzungskarte, Norden oben'});
  container.append(svg);
  const tileLayer = el('g', {'pointer-events': 'none', 'aria-hidden': 'true'});
  svg.append(tileLayer);
  const tileNodes = new Map();
  let background = true;
  try { background = localStorage.getItem('junction-review:osm') !== 'off'; } catch { /* Storage is optional. */ }
  container.classList.toggle('osm-background', background);
  const tileNotice = html('span', {className: 'tile-notice', hidden: true}, 'Hintergrundkarte teilweise nicht geladen. Offline-Wege bleiben sichtbar.');
  const attribution = html('div', {className: 'map-attribution'});
  attribution.append(document.createTextNode('© '), html('a', {href: 'https://www.openstreetmap.org/copyright', target: '_blank', rel: 'noopener'}, 'OpenStreetMap-Mitwirkende'));
  container.append(tileNotice, attribution);
  const tools = html('div', {className: 'map-tools'});
  let tileTimer;
  function renderTiles() {
    if (!svg.isConnected) return;
    const tiles = background ? visibleTiles(box, origin, container.clientWidth) : [];
    const keys = new Set(tiles.map(t => t.key));
    for (const [key, node] of tileNodes) if (!keys.has(key)) { node.remove(); tileNodes.delete(key); }
    function notice() { tileNotice.hidden = ![...tileNodes.values()].some(n => n.dataset.failed === 'true'); }
    for (const tile of tiles) {
      if (tileNodes.has(tile.key)) continue;
      const image = el('image', {x: tile.x, y: tile.y, width: tile.size, height: tile.size,
        preserveAspectRatio: 'none', href: tile.url});
      image.addEventListener('error', () => { image.dataset.failed = 'true'; notice(); });
      image.addEventListener('load', () => { delete image.dataset.failed; notice(); });
      tileNodes.set(tile.key, image); tileLayer.append(image);
    }
    notice();
  }
  function apply() {
    svg.setAttribute('viewBox', box.join(' '));
    clearTimeout(tileTimer); tileTimer = setTimeout(renderTiles, 150);
  }
  function zoom(factor, center = [box[0] + box[2] / 2, box[1] + box[3] / 2]) {
    const newWidth = box[2] * factor;
    if (newWidth < initial[2] / 15 || newWidth > initial[2] * 8) return;
    box = [center[0] + (box[0] - center[0]) * factor, center[1] + (box[1] - center[1]) * factor, newWidth, box[3] * factor];
    apply();
  }
  for (const [text, title, action] of [['+', 'Vergrößern', () => zoom(.75)], ['−', 'Verkleinern', () => zoom(1.3)], ['↺', 'Ausschnitt zurücksetzen', () => {
    const ratio = container.clientWidth / container.clientHeight;
    const w = Math.max(maxX - minX, (maxY - minY) * ratio), h = w / ratio;
    box = [(minX + maxX - w) / 2, (minY + maxY - h) / 2, w, h]; apply();
  }]]) {
    const button = html('button', {type: 'button', title, ariaLabel: title}, text);
    button.addEventListener('click', action); tools.append(button);
  }
  const toggle = html('button', {type: 'button', title: 'OSM-Hintergrundkarte ein- oder ausblenden'}, 'OSM');
  toggle.setAttribute('aria-pressed', String(background));
  toggle.addEventListener('click', () => {
    background = !background; toggle.setAttribute('aria-pressed', String(background));
    container.classList.toggle('osm-background', background);
    try { localStorage.setItem('junction-review:osm', background ? 'on' : 'off'); } catch { /* Optional. */ }
    renderTiles();
  });
  tools.prepend(toggle);
  container.append(tools);
  function position(event) {
    const p = svg.createSVGPoint(); p.x = event.clientX; p.y = event.clientY;
    const result = p.matrixTransform(svg.getScreenCTM().inverse()); return [result.x, result.y];
  }
  svg.addEventListener('wheel', event => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.15 : .87, position(event)); }, {passive: false});
  let pan = null;
  svg.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.target.closest('[data-no-pan]')) return;
    pan = position(event); svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener('pointermove', event => {
    if (!pan) return;
    const p = position(event); box[0] += pan[0] - p[0]; box[1] += pan[1] - p[1]; apply();
  });
  const end = () => { pan = null; };
  svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);
  let lastWidth = container.clientWidth, lastHeight = container.clientHeight;
  const resize = new ResizeObserver(() => {
    const w = container.clientWidth, h = container.clientHeight;
    if (!svg.isConnected || !w || !h || (w === lastWidth && h === lastHeight)) return;
    const unitsPerPixel = box[3] / lastHeight;
    const center = [box[0] + box[2] / 2, box[1] + box[3] / 2];
    box = [center[0] - w * unitsPerPixel / 2, center[1] - h * unitsPerPixel / 2, w * unitsPerPixel, h * unitsPerPixel];
    lastWidth = w; lastHeight = h;
    apply();
  });
  resize.observe(container);
  container.disposeMap = () => { resize.disconnect(); clearTimeout(tileTimer); };
  renderTiles();
  return {svg, project, width, height, initial, position};
}

function line(map, coordinates, attrs) {
  const points = coordinates.map(p => map.project.to(p).join(',')).join(' ');
  const node = el('polyline', {points, fill: 'none', ...attrs}); map.svg.append(node); return node;
}

function cycling(way) {
  const t = way.tags;
  return t.highway === 'cycleway' || ['designated', 'yes', 'permissive'].includes(t.bicycle);
}

function roads(map, sites, detailed) {
  const ways = new Map(sites.flatMap(s => s.ways).map(w => [w.id, w]));
  for (const way of ways.values()) {
    const t = way.tags, bike = cycling(way);
    const major = ['primary', 'secondary', 'tertiary', 'trunk'].includes(t.highway);
    line(map, way.coordinates, {stroke: bike ? '#416d63' : major ? '#d6d6da' : '#e3e1e7',
      class: bike ? 'cycleway-overlay' : 'road-overlay',
      'stroke-width': detailed ? (bike ? 1 : major ? 5 : 1) : (major ? 3 : 1),
      'vector-effect': 'non-scaling-stroke'});
  }
  if (!detailed) return;
  const named = new Set();
  for (const way of ways.values()) {
    if (!way.tags.name || named.has(way.tags.name) || cycling(way)) continue;
    const p = map.project.to(way.coordinates[Math.floor(way.coordinates.length / 2)]);
    const b = map.initial;
    if (p[0] < b[0] + 25 || p[0] > b[0] + b[2] - 25 || p[1] < b[1] + 15 || p[1] > b[1] + b[3] - 15) continue;
    named.add(way.tags.name);
    map.svg.append(el('text', {class: 'road-overlay', x: p[0], y: p[1] - 3, fill: '#85808b', 'font-size': map.width / 85, 'text-anchor': 'middle', 'paint-order': 'stroke', stroke: 'white', 'stroke-width': .7}, way.tags.name));
  }
}

let projectData, selected, draft, busy = false, dirty = false, formDirty = false, editMode = false;
const $ = id => document.getElementById(id);

function message(text, error = false) {
  $('message').textContent = text; $('message').hidden = false; $('message').className = error ? 'error' : '';
}

function setBusy(value) {
  busy = value;
  for (const id of ['save-review', 'save-geometry', 'reset-geometry', 'edit-mode']) $(id).disabled = value;
  const editable = selected && (selected.geometryMode || 'editable') === 'editable';
  for (const id of ['save-geometry', 'reset-geometry', 'edit-mode']) $(id).disabled = value || !editable;
}

function siteLabel(site) { return site.number ? `K${site.number}` : (site.geometryMode === 'reference' ? 'Pilot' : 'Ohne Nummer'); }
function rechecks(site) { return site.evidenceCurrent ? (site.evidence?.rechecks || []) : []; }
function recheckText(item) { return `${item.entry} → ${item.exit} · ab ${item.date.split('-').reverse().join('.')}`; }

async function post(action, body) {
  const response = await fetch(`/api/sites/${encodeURIComponent(selected.id)}/${action}`, {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Review-Token': projectData.token}, body: JSON.stringify(body)});
  const data = await response.json(); if (!response.ok) throw new Error(data.error); return data;
}

function navigation() {
  const counts = {open: 0, confirmed: 0, excluded: 0, deferred: 0};
  projectData.sites.forEach(s => counts[s.status]++);
  $('counts').replaceChildren(...[[projectData.sites.length, 'Gesamt'], [counts.confirmed, 'Bestätigt'], [counts.open + counts.deferred, 'Offen'], [counts.excluded, 'Ausgeschl.']].map(([n, title]) => {
    const div = html('div'); div.append(html('strong', {}, n), document.createTextNode(title)); return div;
  }));
  const search = $('search').value.toLocaleLowerCase();
  const groups = [['confirmed', 'Bestätigt'], ['open', 'Offen'], ['deferred', 'Zurückgestellt'], ['excluded', 'Ausgeschlossen']];
  const oldOpen = new Set([...$('groups').querySelectorAll('details[open]')].map(d => d.dataset.status));
  const first = !$('groups').children.length;
  $('groups').replaceChildren(...groups.map(([status, title]) => {
    const sites = projectData.sites.filter(s => s.status === status && (`${siteLabel(s)} ${s.name}`).toLocaleLowerCase().includes(search)).sort((a, b) => (b.number || 0) - (a.number || 0) || (b.outgoingLanes || 0) - (a.outgoingLanes || 0) || a.name.localeCompare(b.name, 'de'));
    const details = html('details', {open: first ? status === 'open' : oldOpen.has(status) || !!search}); details.dataset.status = status;
    details.append(html('summary', {}, `${title} · ${sites.length}`));
    for (const s of sites) {
      const a = html('a', {href: `#${encodeURIComponent(s.id)}`, className: `site-link${selected?.id === s.id ? ' active' : ''}`});
      a.append(html('small', {}, `${siteLabel(s)} · ${s.geometryMode === 'none' ? 'noch ohne Geometrie' : 'v' + s.geometryRevision}${s.outgoingLanes ? ' · ' + s.outgoingLanes + ' Fahrspuren' : ''}${s.deploymentStatus === 'live' ? ' · LIVE' : ''}`), document.createTextNode(s.name)); details.append(a);
    }
    return details;
  }));
  const pending = projectData.sites.flatMap(s => rechecks(s).map(item => ({site: s, item})));
  $('rechecks').replaceChildren(...pending.map(({site, item}) => html('a', {href: `#${encodeURIComponent(site.id)}`, className: 'recheck-link'}, `${siteLabel(site)} · ${recheckText(item)}`)));
}

function overview() {
  const filter = $('map-status').value, search = $('search').value.toLocaleLowerCase();
  const sites = projectData.sites.filter(s => s.origin && (filter === 'all' || s.status === filter || (filter === 'open' && s.status === 'deferred')) && `${siteLabel(s)} ${s.name}`.toLocaleLowerCase().includes(search));
  if (!sites.length) { $('overview-map').disposeMap?.(); $('overview-map').replaceChildren(html('p', {className: 'notice'}, 'Keine verorteten Fälle für diese Auswahl.')); return; }
  const points = sites.map(s => s.origin);
  const origin = [points.reduce((n, p) => n + p[0], 0) / points.length, points.reduce((n, p) => n + p[1], 0) / points.length];
  const map = createMap($('overview-map'), points, origin, 700);
  roads(map, sites, false);
  for (const site of sites) {
    const [x, y] = map.project.to(site.origin);
    const a = el('a', {href: `#${encodeURIComponent(site.id)}`, 'data-no-pan': '', 'aria-label': `${siteLabel(site)} ${site.name}`});
    a.append(el('circle', {cx: x, cy: y, r: map.width / 110, fill: site.geometryMode === 'none' ? 'white' : colors[site.status], stroke: site.geometryMode === 'none' ? colors[site.status] : 'white', 'stroke-width': map.width / 650}));
    if (site.number) a.append(el('text', {x, y: y - map.width / 65, 'text-anchor': 'middle', fill: '#46374f', 'font-size': map.width / 65, 'font-weight': 700, 'paint-order': 'stroke', stroke: 'white', 'stroke-width': map.width / 300}, siteLabel(site)));
    a.append(el('title', {}, site.name)); map.svg.append(a);
  }
}

function detailMap() {
  if (!draft.origin) { $('detail-map').disposeMap?.(); $('detail-map').replaceChildren(html('p', {className: 'notice'}, 'Keine gespeicherte Position vorhanden.')); return; }
  const map = createMap($('detail-map'), draft.polygon.length ? draft.polygon : [draft.origin], draft.origin, draft.polygon.length ? 40 : 100);
  roads(map, [draft], true);
  const shape = draft.polygon.length ? line(map, draft.polygon, {fill: '#9861bc', 'fill-opacity': '.13', stroke: '#80429f', 'stroke-width': 1.6, 'vector-effect': 'non-scaling-stroke'}) : null;
  const size = map.width / 65;
  map.svg.append(el('text', {x: map.initial[0] + map.width - 15, y: map.initial[1] + 12, 'font-size': size, fill: '#4e4059'}, 'N ↑'));
  const gates = draft.gates.map(g => { const [x, y] = map.project.to(g.location); return {...g, x, y}; });
  for (const side of [-1, 1]) {
    const items = gates.filter(g => (g.x < 0 ? -1 : 1) === side);
    for (const g of spreadLabels(items, size * 1.45, map.initial[1] + 20, map.initial[1] + map.height - 15)) {
      const color = g.kind === 'entry' ? '#19785b' : '#2466b5';
      const labelX = side === -1 ? map.initial[0] + 5 : map.initial[0] + map.width - 5;
      map.svg.append(el('line', {x1: g.x, y1: g.y, x2: labelX - side * size * .4, y2: g.labelY, stroke: color, 'stroke-width': .25}));
      map.svg.append(el('circle', {cx: g.x, cy: g.y, r: size / 3, fill: 'white', stroke: color, 'stroke-width': .5}));
      map.svg.append(el('text', {x: labelX, y: g.labelY - size * .3, 'text-anchor': side === -1 ? 'start' : 'end', 'font-size': size, fill: color, 'paint-order': 'stroke', stroke: 'white', 'stroke-width': .8}, g.label + (g.shared ? ' *' : '')));
    }
  }
  if (!editMode || (draft.geometryMode || 'editable') !== 'editable') return;
  draft.polygon.slice(0, -1).forEach((p, index) => {
    const [x, y] = map.project.to(p);
    const handle = el('circle', {cx: x, cy: y, r: size * .5, fill: '#fff', stroke: '#793b9e', 'stroke-width': .8, 'data-no-pan': '', tabindex: 0, 'aria-label': `Flächeneckpunkt ${index + 1}`});
    handle.append(el('title', {}, `Eckpunkt ${index + 1} ziehen`));
    let dragging = false, before;
    handle.addEventListener('pointerdown', event => { if (busy || event.button !== 0) return; event.stopPropagation(); dragging = true; before = structuredClone(draft); handle.setPointerCapture(event.pointerId); });
    handle.addEventListener('pointermove', event => {
      if (!dragging) return;
      const xy = map.position(event), position = map.project.from(xy);
      draft.polygon = moveVertex(draft.polygon, index, position); handle.setAttribute('cx', xy[0]); handle.setAttribute('cy', xy[1]);
      shape.setAttribute('points', draft.polygon.map(q => map.project.to(q).join(',')).join(' '));
    });
    handle.addEventListener('pointerup', async () => {
      if (!dragging) return; dragging = false; setBusy(true);
      try {
        draft = await post('preview', {expectedVersion: selected.editVersion, polygon: draft.polygon});
        dirty = draft.geometryFingerprint !== selected.geometryFingerprint; $('dirty').hidden = !dirty;
      } catch (error) { draft = before; message(error.message, true); }
      finally { setBusy(false); detailMap(); }
    });
    handle.addEventListener('pointercancel', () => { if (dragging) { dragging = false; draft = before; detailMap(); } });
    map.svg.append(handle);
  });
}

function detail() {
  $('detail-number').textContent = `${siteLabel(selected)} · GEOMETRIEPRÜFUNG`;
  $('detail-title').textContent = selected.name;
  $('detail-status').textContent = labels[selected.status]; $('detail-status').className = `badge ${selected.status}`;
  $('revision').textContent = selected.geometryMode === 'none' ? 'Noch ohne Geometrie' : `Geometrie v${selected.geometryRevision}`;
  $('technical-stage').textContent = selected.technicalStatus === 'not-run' ? 'Technik: ausstehend' : 'Technik: dokumentiert (siehe Details)';
  $('deployment-stage').textContent = selected.evidenceCurrent ? selected.evidence.deployment : (selected.deploymentStatus === 'older-geometry' ? 'LIVE: früherer Geometriestand' : 'Deployment: nicht ermittelt');
  $('site-note').textContent = selected.note; $('site-note').hidden = !selected.note;
  $('decision').value = selected.status;
  $('note').value = selected.decision?.note || '';
  $('deferred-until').value = selected.decision?.deferredUntil || '';
  $('stale').hidden = !selected.decision || selected.decisionCurrent;
  $('edit-mode').checked = editMode; $('edit-help').hidden = !editMode; $('dirty').hidden = !dirty;
  const noGeometry = selected.geometryMode === 'none';
  $('decision').querySelector('[value="confirmed"]').disabled = noGeometry;
  const membership = new Map(Object.entries({...selected.logicalArms, ...(selected.evidenceCurrent ? selected.evidence.logicalArms : {})}).flatMap(([arm, gates]) => gates.map(g => [g, arm])));
  const ordinary = selected.evidenceCurrent ? selected.evidence.normalGuidanceGates || [] : [];
  $('gate-list').replaceChildren(...selected.gates.map(g => html('div', {className: `gate-row ${g.kind}`}, `${g.label}${g.shared ? ' *' : ''} · ${ordinary.includes(g.label) ? 'nur normale Ansagen' : membership.get(g.label) || 'Straßenarm noch zuordnen'} · OSM ${g.osmWayId}`)));
  $('history').replaceChildren(...(selected.history.length ? [...selected.history].reverse().map(h => html('li', {}, `${new Date(h.at).toLocaleString('de-DE')} · ${h.action} ${h.decision ? '· ' + labels[h.decision.status] + (h.decision.note ? ': ' + h.decision.note : '') : ''}`)) : [html('li', {}, 'Noch keine Änderungen im Prüfprojekt.') ]));
  if (selected.decision?.origin === 'legacy-overview') $('history').prepend(html('li', {}, 'Bisherige dokumentierte Prüfentscheidung übernommen; keine neue Freigabe erteilt.'));
  $('detail-rechecks').replaceChildren(...rechecks(selected).map(item => html('p', {className: 'recheck-link'}, `${recheckText(item)}. ${item.reason} Normale Ansagen bleiben aktiv.`)));
  const evidence = selected.evidence;
  $('evidence-panel').hidden = !evidence;
  $('evidence-body').replaceChildren();
  if (evidence) {
    $('evidence-body').append(html('p', {}, `${selected.evidenceCurrent ? '' : 'Historischer Stand, gilt nicht für die geänderte Geometrie. '}${evidence.technical}`),
      html('p', {}, `${evidence.deployment} · Backend ${evidence.backendVersion || 'unbekannt'} · letzter Abgleich: ${evidence.checkedAt || 'unbekannt'}`));
    for (const test of evidence.fieldTests) $('evidence-body').append(html('p', {}, `Praxistest ${test.date}: ${test.coverage}`));
    for (const m of evidence.movements) {
      if (m.kind === 'right') continue;
      const pending = rechecks(selected).find(r => r.entry === m.entryLabel && r.exit === m.exitLabel);
      const text = `${m.entryLabel} → ${m.exitLabel}: ${{left: 'links', straight: 'geradeaus', special: 'Sonderfolge', standard: 'normale Ansagen'}[m.kind] || m.kind} · ${m.enabled || (m.normalGuidanceOnly && m.verified) ? 'technisch bestanden' : 'ohne Kreuzungsansage: ' + (m.reason || 'bewusst ausgenommen')}${pending ? ' · ' + recheckText(pending) : ''}`;
      $('evidence-body').append(html('p', {className: pending ? 'recheck-link' : 'movement-result'}, text));
    }
  }
  if (noGeometry) $('gate-list').append(html('p', {className: 'muted'}, 'Inventarkandidat: Fläche und Anschlüsse müssen erst vorbereitet werden. Du kannst kommentieren, zurückstellen oder ausschließen.'));
  if (selected.geometryMode === 'reference') $('gate-list').append(html('p', {className: 'muted'}, 'Übernommene Pilotfläche; ohne editierbare Anschlussdaten. Die bestehende Freigabe und der Live-Stand bleiben dokumentiert.'));
  setBusy(busy);
  detailMap();
}

function route() {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { id = ''; }
  const next = projectData.sites.find(s => s.id === id);
  if (busy) { history.replaceState(null, '', selected ? `#${encodeURIComponent(selected.id)}` : location.pathname); return; }
  if ((dirty || formDirty) && !window.confirm('Ungespeicherte Änderungen verwerfen?')) { history.replaceState(null, '', selected ? `#${encodeURIComponent(selected.id)}` : location.pathname); return; }
  selected = next; draft = next ? structuredClone(next) : null; dirty = false; formDirty = false;
  $('overview').hidden = !!selected; $('detail').hidden = !selected;
  navigation(); if (selected) detail(); else overview();
  window.scrollTo(0, 0);
}

async function save(withDecision) {
  if (busy) return;
  if (!withDecision && !dirty) { message('Die Fläche ist unverändert.'); return; }
  setBusy(true);
  try {
    const body = {expectedVersion: selected.editVersion};
    if (dirty) body.polygon = draft.polygon;
    if (withDecision) Object.assign(body, {status: $('decision').value, note: $('note').value, deferredUntil: $('deferred-until').value});
    const result = await post('save', body);
    projectData.sites[projectData.sites.findIndex(s => s.id === result.id)] = result;
    selected = result; draft = structuredClone(result); dirty = false; formDirty = false;
    detail(); navigation(); message('Gespeichert. Die Entscheidung gilt für diesen Geometrie- und Datenstand.');
  } catch (error) { message(error.message, true); }
  finally { setBusy(false); }
}

async function start() {
  try {
    let sidebarCollapsed = window.matchMedia('(max-width: 720px)').matches;
    try { const saved = localStorage.getItem('junction-review:sidebar'); if (saved !== null) sidebarCollapsed = saved === 'collapsed'; } catch { /* Optional. */ }
    function setSidebar() {
      $('sidebar').hidden = sidebarCollapsed;
      document.body.classList.toggle('sidebar-collapsed', sidebarCollapsed);
      $('toggle-sidebar').setAttribute('aria-expanded', String(!sidebarCollapsed));
      $('toggle-sidebar').setAttribute('aria-label', sidebarCollapsed ? 'Kreuzungsliste einblenden' : 'Kreuzungsliste ausblenden');
    }
    setSidebar();
    $('toggle-sidebar').addEventListener('click', () => {
      sidebarCollapsed = !sidebarCollapsed; setSidebar();
      try { localStorage.setItem('junction-review:sidebar', sidebarCollapsed ? 'collapsed' : 'expanded'); } catch { /* Optional. */ }
    });
    const response = await fetch('/api/project'); projectData = await response.json();
    if (!response.ok) throw new Error(projectData.error);
    $('project-name').textContent = [projectData.project.city, projectData.project.district].filter(Boolean).join(' · ');
    $('source').textContent = `${projectData.source.attribution} · OSM bis ${projectData.source.osmRetrievedAt?.slice(0, 10) || 'Datum unbekannt'}${projectData.source.liveCheckedAt ? ' · Live-Abgleich ' + projectData.source.liveCheckedAt.slice(0, 10) : ''} · Lokal gespeichert`;
    $('search').addEventListener('input', () => { navigation(); if (!selected) overview(); });
    $('map-status').addEventListener('change', overview);
    $('review-form').addEventListener('submit', event => { event.preventDefault(); save(true); });
    $('review-form').addEventListener('input', () => { formDirty = true; });
    $('save-geometry').addEventListener('click', () => save(false));
    $('reset-geometry').addEventListener('click', () => { draft = structuredClone(selected); dirty = false; formDirty = false; detail(); });
    $('edit-mode').addEventListener('change', () => { editMode = $('edit-mode').checked; $('edit-help').hidden = !editMode; detailMap(); });
    window.addEventListener('hashchange', route);
    window.addEventListener('beforeunload', event => { if (dirty || formDirty || busy) { event.preventDefault(); event.returnValue = ''; } });
    route();
  } catch (error) { message(error.message, true); }
}

if (typeof document !== 'undefined') start();
