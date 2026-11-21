import {addDrawingPoint, closeDrawing} from './drawing.js';
import {wait} from './api.js';

// Area interaction owns its drawing/request state; map and project views are injected.
export function initializeAreas({$, api, createMap, line, el, html, project, acceptProject, setBusy, isBusy, message}) {
  let savedProjects = [], renameTarget = null;
  let map, outline, verticesLayer, boundaries = [], selection = null, drawing = false, picking = false, drawn = [], task = null;
  const status = (text, error = false) => {
    $('area-status').textContent = text;
    $('area-status').classList.toggle('error', error);
  };
  function controls() {
    for (const id of ['project-select','open-project','rename-project','project-rename-name']) $(id).disabled = !!task;
    for (const node of $('area-panel').querySelectorAll('button,input,select')) node.disabled = !!task;
    $('cancel-area-task').hidden = !task;
    $('cancel-area-task').disabled = false;
    $('area-spinner').hidden = !task;
    $('area-panel').setAttribute('aria-busy', String(!!task));
    $('prepare-area').disabled = !!task || !selection;
    $('finish-area').hidden = !drawing;
    $('finish-area').disabled = !!task || drawn.length < 3;
    $('undo-area').hidden = !drawing;
    $('undo-area').disabled = !!task || !drawn.length;
    $('area-map').classList.toggle('drawing', drawing || picking);
  }
  async function run(label, action) {
    if (isBusy()) return;
    const current = {controller: new AbortController(), started: Date.now(), jobId: null};
    task = current; setBusy(true); controls();
    $('message').hidden = true;
    status(label); $('area-elapsed').textContent = '';
    const timer = setInterval(() => { $('area-elapsed').textContent = `${Math.floor((Date.now()-current.started)/1000)} s`; }, 1000);
    try { await action(current); }
    catch (error) {
      if (error.name === 'AbortError') status('Abgebrochen. Du kannst erneut suchen oder ein anderes Gebiet wählen.');
      else { status(error.message, true); message(error.message, true); }
    } finally {
      clearInterval(timer); task = null; setBusy(false); controls();
    }
  }
  async function projects(selectedId) {
    const list = await api('/api/projects');
    savedProjects = list;
    $('project-select').replaceChildren(...list.map(p => html('option', {value: p.id, selected: selectedId ? p.id === selectedId : p.active}, `${p.name} · ${p.count} Fälle`)));
  }
  $('rename-project').addEventListener('click',()=>{
    if(isBusy()) return;
    renameTarget=savedProjects.find(p=>p.id===$('project-select').value);
    if(!renameTarget) return;
    $('project-rename-name').value=renameTarget.name;
    $('project-rename-form').hidden=false;
    $('project-rename-name').focus();
  });
  $('cancel-project-rename').addEventListener('click',()=>{$('project-rename-form').hidden=true;renameTarget=null;});
  $('project-select').addEventListener('change',()=>{$('project-rename-form').hidden=true;renameTarget=null;});
  $('project-rename-form').addEventListener('submit',event=>{
    event.preventDefault();
    if(!renameTarget) return;
    const target=renameTarget, name=$('project-rename-name').value;
    return run('Projekt umbenennen …',async t=>{
      const data=await api('/api/projects/rename',{body:{id:target.id,name,expectedName:target.name},signal:t.controller.signal});
      if(data.workspaceId===project().workspaceId) {
        Object.assign(project().project,data.project);
        $('project-name').textContent=data.project.name;
      }
      $('project-rename-form').hidden=true;renameTarget=null;
      await projects(target.id);
      message(`Projekt umbenannt: ${data.project.name}`);
    });
  });
  function redrawDrawing(closed = false) {
    if (!map) return;
    const coords = closed && drawn.length ? [...drawn, drawn[0]] : drawn;
    outline.setAttribute('points', coords.map(p => map.project.to(p).join(',')).join(' '));
    verticesLayer.replaceChildren();
    drawn.forEach((p, i) => {
      const [x, y] = map.project.to(p);
      const group = el('g');
      group.append(el('circle', {cx:x, cy:y, r: 5 / map.svg.getScreenCTM().a, fill: i === 0 ? '#7d36a1' : 'white', stroke:'#7d36a1', 'stroke-width': 2, 'vector-effect':'non-scaling-stroke'}));
      group.append(el('title', {}, i === 0 ? 'Startpunkt anklicken zum Schließen' : `Eckpunkt ${i+1}`));
      verticesLayer.append(group);
    });
  }
  function paint(points = null, outlines = []) {
    const origin = points?.[0] || project().sites.find(s => s.origin)?.origin || [11.57,48.14];
    map = createMap($('area-map'), points || [origin], origin, points ? 150 : 2500);
    boundaries = outlines.map(coords => line(map, coords, {stroke:'#8a35ae','stroke-width':3,'vector-effect':'non-scaling-stroke'}));
    outline = el('polyline', {fill:'#9849b0','fill-opacity':.13,stroke:'#8837a8','stroke-width':3,'vector-effect':'non-scaling-stroke'});
    verticesLayer = el('g'); map.svg.append(outline, verticesLayer);
    map.svg.setAttribute('tabindex','0');
    map.svg.addEventListener('pointerdown', event => { if (drawing || picking) event.stopImmediatePropagation(); }, true);
    map.svg.addEventListener('click', async event => {
      if (isBusy() || event.button !== 0) return;
      if (picking) {
        const location = map.project.from(map.position(event)); picking = false;
        await run('Verwaltungsgebiete am Kartenpunkt suchen …', async t => {
          showResults(await api('/api/areas/at', {body:{location},signal:t.controller.signal}));
        });
        return;
      }
      if (!drawing || event.detail > 1) return;
      const result = addDrawingPoint(drawn, map.project.from(map.position(event)), Math.max(.3,8/map.svg.getScreenCTM().a));
      drawn = result.points;
      if (result.close) { finish(); return; }
      redrawDrawing(); controls();
      status(`${drawn.length} Eckpunkte gesetzt. Beliebig weitere Punkte setzen; zum Abschluss Startpunkt anklicken, doppelklicken oder „Fläche schließen“ wählen.`);
    });
    map.svg.addEventListener('dblclick', event => { if (drawing) { event.preventDefault(); finish(); } });
    map.svg.addEventListener('keydown', event => {
      if (!drawing || isBusy()) return;
      if (event.key === 'Enter') { event.preventDefault(); finish(); }
      if (['Backspace','Delete'].includes(event.key)) { event.preventDefault(); undo(); }
      if (event.key === 'Escape') { drawing = false; drawn = []; redrawDrawing(); controls(); status('Zeichnen abgebrochen.'); }
    });
  }
  function undo() {
    if (isBusy()) return;
    drawn.pop(); redrawDrawing(); controls();
    status(`${drawn.length} Eckpunkte. Weitere Punkte anklicken oder die Fläche schließen.`);
  }
  function removeBoundaries() {
    boundaries.forEach(node=>node?.remove()); boundaries = [];
  }
  function finish() {
    if (isBusy()) return;
    try {
      const coordinates = closeDrawing(drawn);
      selection = {name:'Gezeichnete Fläche',area:{type:'Polygon',coordinates:[coordinates]}};
      drawing = false; picking = false; redrawDrawing(true); controls();
      status(`Fläche mit ${coordinates.length-1} Eckpunkten ausgewählt. Jetzt „Sichtprüfung vorbereiten“ wählen.`);
    } catch (error) { status(error.message,true); }
  }
  async function choose(item) {
    await run(`Grenze für „${item.name}“ laden …`, async t => {
      const full = item.outlines?.length ? item : await api('/api/areas/boundary',{body:{id:item.id},signal:t.controller.signal});
      const b = full.bounds;
      selection = {relationId:item.id,name:item.name}; drawing = picking = false; drawn = [];
      paint([[b.minlon,b.minlat],[b.maxlon,b.maxlat]],full.outlines);
      for (const card of $('area-results').querySelectorAll('button')) card.classList.toggle('selected',card.dataset.id === String(item.id));
      status(`Ausgewählt: ${item.name}. Die Grenze ist lila. Jetzt „Sichtprüfung vorbereiten“ wählen.`);
    });
  }
  function showResults(results) {
    const container = $('area-results');
    container.hidden = false;
    container.replaceChildren(html('h3',{},results.length ? `${results.length} ${results.length === 1 ? 'Gebiet gefunden' : 'Gebiete gefunden'} – bitte auswählen` : 'Kein Gebiet gefunden'));
    if (!results.length) container.append(html('p',{},'Schreibweise prüfen, z. B. „Olching“. Alternativ den Ort auf der Karte wählen oder eine Fläche einzeichnen.'));
    for (const item of results) {
      const button = html('button',{type:'button',className:'area-result'});
      button.dataset.id = String(item.id);
      button.append(html('strong',{},item.name),html('span',{},`${item.description || item.name} · Verwaltungsebene ${item.level || '?'} · OSM ${item.id}`),html('span',{className:'result-action'},'Grenze anzeigen und auswählen →'));
      button.addEventListener('click',()=>choose(item)); container.append(button);
    }
    status(results.length ? 'Suche abgeschlossen. Einen der hervorgehobenen Treffer auswählen.' : 'Suche abgeschlossen: keine Treffer. Bitte die Schreibweise prüfen.');
    container.scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  $('area-panel').addEventListener('toggle',()=>{ if ($('area-panel').open && !map) paint(); });
  $('area-search').addEventListener('submit',event=>{
    event.preventDefault(); if (isBusy()) return;
    selection = null; drawing = picking = false;
    removeBoundaries(); drawn = []; redrawDrawing();
    $('area-results').replaceChildren(); $('area-results').hidden = true;
    return run('Stadt oder Stadtteil suchen … Bei hoher OSM-Auslastung kann dies länger dauern.',async t=>showResults(await api('/api/areas/search',{body:{name:$('area-name').value.trim()},signal:t.controller.signal})));
  });
  $('pick-area').addEventListener('click',()=>{
    if (isBusy()) return;
    if (!map) paint();
    selection = null; drawing = false; picking = true; drawn = []; redrawDrawing(); controls();
    removeBoundaries();
    status('Jetzt einmal in den gewünschten Stadtteil klicken. Danach aus den gefundenen Gebieten auswählen.');
  });
  $('draw-area').addEventListener('click',()=>{
    if (isBusy()) return;
    if (!map) paint();
    selection = null; drawn = []; drawing = true; picking = false; redrawDrawing(); controls();
    removeBoundaries();
    status('1. Eckpunkte nacheinander anklicken (mindestens drei, auch mehr). 2. Startpunkt anklicken, doppelklicken oder „Fläche schließen“ wählen.');
    map.svg.focus({preventScroll:true});
  });
  $('finish-area').addEventListener('click',finish);
  $('undo-area').addEventListener('click',undo);
  $('clear-area').addEventListener('click',()=>{
    if (isBusy()) return;
    selection = null; drawing = picking = false; drawn = [];
    removeBoundaries();
    redrawDrawing(); controls(); status('Auswahl zurückgesetzt. Karte verschieben, ein Gebiet suchen oder eine Fläche zeichnen.');
  });
  $('cancel-area-task').addEventListener('click',async()=>{
    if (!task) return;
    const current = task;
    // Preparation is a server job: cancel the import as well as browser polling.
    if (current.jobId) {
      try {
        const job = await api(`/api/jobs/${current.jobId}/cancel`,{body:{},timeout:10000});
        if (job.status === 'complete') { status('Vorbereitung war bereits abgeschlossen. Das Prüfprojekt wird geöffnet.'); return; }
      }
      catch (error) { status(`Abbruch konnte nicht bestätigt werden: ${error.message}`,true); return; }
    }
    current.controller.abort();
  });
  $('prepare-area').addEventListener('click',()=>run('Gebietsvorbereitung starten …',async t=>{
    if (!selection) throw new Error('Bitte zuerst ein Gebiet oder eine Fläche auswählen.');
    // Do not abort creation: remember the returned job before enabling cancel.
    $('cancel-area-task').disabled = true;
    const job = await api('/api/areas/prepare',{body:{selection},timeout:10000});
    await monitor(job,t);
  }));
  async function monitor(initial,t) {
    let job = initial;
    try { sessionStorage.setItem('junction-review:job',job.id); } catch { /* Optional. */ }
    t.jobId = job.id; $('cancel-area-task').disabled = false;
    while (job.status === 'running') {
      status(job.phase); await wait(500,t.controller.signal);
      job = await api(`/api/jobs/${job.id}`,{signal:t.controller.signal,timeout:10000});
    }
    try { sessionStorage.removeItem('junction-review:job'); } catch { /* Optional. */ }
    if (job.status === 'cancelled') throw new DOMException('Abgebrochen','AbortError');
    if (job.status !== 'complete') throw new Error(job.error || 'Die Vorbereitung ist fehlgeschlagen.');
    const data = await api('/api/project',{projectId:job.projectId,signal:t.controller.signal});
    acceptProject(data); await projects();
    $('area-panel').open = false;
    message(`${data.sites.length} Kreuzungen im Prüfprojekt. ${data.source.rejected?.length || 0} T-/Kreisverkehrsfälle aussortiert. Vorhandene Entscheidungen bleiben erhalten.`);
  }
  $('open-project').addEventListener('click',()=>run('Prüfprojekt öffnen …',async t=>{
    const data = await api('/api/projects/select',{body:{id:$('project-select').value},signal:t.controller.signal});
    acceptProject(data); await projects(); status(`${data.project.city}: ${data.sites.length} Fälle geöffnet.`);
  }));
  projects().then(async()=>{
    let remembered;
    try { remembered = sessionStorage.getItem('junction-review:job'); } catch { /* Optional. */ }
    if (!remembered || isBusy()) return;
    let job;
    try { job = await api(`/api/jobs/${encodeURIComponent(remembered)}`); }
    catch {
      try { sessionStorage.removeItem('junction-review:job'); } catch { /* Optional. */ }
      status('Der frühere Auftrag ist nicht mehr verfügbar, möglicherweise wurde der Server neu gestartet. Gespeicherte Projekte bleiben erhalten.');
      return;
    }
    if (job.status === 'running' || job.status === 'complete') {
      $('area-panel').open = true;
      await run('Laufende Vorbereitung wieder aufnehmen …',t=>monitor(job,t));
    } else {
      try { sessionStorage.removeItem('junction-review:job'); } catch { /* Optional. */ }
    }
  }).catch(error=>message(error.message,true)); controls();
}
