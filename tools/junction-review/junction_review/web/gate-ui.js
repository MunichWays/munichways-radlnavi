// Gate edits are staged with their boundary; one save commits the complete draft.
export const geometryOf = site => Object.fromEntries(['polygon','gates','logicalArms'].map(k=>[k,structuredClone(site[k])]));

export function armLabel(site, arm, labels) {
  const info=site.armDescriptions?.[arm];
  const compass=['Nord','Nordost','Ost','Südost','Süd','Südwest','West','Nordwest'];
  const description=info ? `${(info.names || []).join(' / ') || 'Straße'} nach ${compass[Math.round(((info.bearing%360)+360)%360/45)%8]}` : 'Richtung anhand der zugeordneten Punkte';
  return `${arm} · ${description} · ${labels.join(', ') || 'noch keine Punkte'}`;
}

export function initializeGateEditor({$, html, el, draft, selected, busy, setBusy, preview, accept, redraw, message, onModeChange}) {
  let selectedId = null, picking = false, adding = false;
  function current() { return draft()?.gates.find(g=>g.id===selectedId); }
  function enabled() { return $('gate-edit-mode').checked && (draft()?.geometryMode || 'editable') === 'editable'; }
  function render() {
    const site=draft(), editable=!!site && (site.geometryMode || 'editable')==='editable';
    $('gate-edit-mode').disabled=busy() || !editable;
    $('gate-editor').hidden=!enabled() || !site;
    if (!site) return;
    if (!site.gates.some(g=>g.id===selectedId)) selectedId=site.gates[0]?.id || null;
    const oldPartner=$('gate-merge-with').value, oldWay=$('gate-target-way').value;
    $('gate-select').replaceChildren(...site.gates.map(g=>html('option',{value:g.id,selected:g.id===selectedId},`${g.label} · OSM ${g.osmWayId}`)));
    const oldArm=$('gate-new-arm').value;
    $('gate-new-arm').replaceChildren(...Object.entries(site.logicalArms).map(([arm,labels])=>html('option',{value:arm,selected:arm===oldArm},armLabel(site,arm,labels))));
    for(const id of ['gate-add','gate-new-kind','gate-new-arm']) $(id).disabled=busy() || !editable;
    const gate=current();
    const partners=site.gates.filter(g=>g.id!==selectedId && g.kind===gate?.kind);
    $('gate-merge-with').replaceChildren(html('option',{value:''},'Nur verschieben'),...partners.map(g=>html('option',{value:g.id,selected:g.id===oldPartner},`Mit ${g.label} zusammenlegen`)));
    $('gate-target-way').replaceChildren(html('option',{value:''},'Automatisch: nächster erlaubter Weg'),...site.ways.map(w=>html('option',{value:String(w.id),selected:String(w.id)===oldWay},`OSM ${w.id} · ${w.tags.highway}${w.tags.name ? ' · '+w.tags.name : ''}`)));
    for(const id of ['gate-select','gate-merge-with','gate-target-way','gate-place','gate-delete']) $(id).disabled=busy() || !editable || !gate;
    $('gate-add').textContent=adding ? 'Neuen Punkt jetzt auf Karte anklicken (Escape: Abbruch)' : 'Punkt hinzuf\u00fcgen: auf Karte setzen';
    $('gate-place').textContent=picking && !adding ? 'Ziel jetzt auf der Karte anklicken …' : 'Ziel auf Karte wählen';
    const arm=Object.entries(site.logicalArms).find(([,labels])=>labels.includes(gate?.label));
    $('gate-editor-help').textContent=adding ? 'Ein Straßenarm ist eine Straße in einer Richtung ab der Kreuzung, einschließlich ihrer Radwege. Beispiel: Marsstraße nach Nordost. Entry führt in die Fläche, Exit aus ihr heraus. Auf den gewünschten Weg nahe der Grenze klicken.' : gate ? `${gate.label}: ${arm ? armLabel(site,...arm) : 'keine Straßenrichtung zugeordnet'}. Beim Verschieben folgt die Flächengrenze; andere Punkte bleiben an ihren OSM-Wegen. Beim Zusammenlegen entfällt der gewählte zweite Punkt.` : 'Kein Anschluss vorhanden.';
  }
  async function apply(operation) {
    if(busy()) return;
    setBusy(true);
    try {
      const result=await preview({expectedVersion:selected().editVersion,geometry:geometryOf(draft()),gateEdit:operation});
      const ids=new Set(draft().gates.map(g=>g.id));
      if(adding) selectedId=result.gates.find(g=>!ids.has(g.id))?.id || selectedId;
      accept(result);picking=false;adding=false;
      message('Entwurf geändert. Fläche und Anschlüsse gemeinsam prüfen, dann „Geometrie speichern“ wählen.');
    } catch(error) {message(error.message,true);}
    finally {setBusy(false);render();redraw();}
  }
  function move(location) {
    if(adding) return apply({action:'add',kind:$('gate-new-kind').value,arm:$('gate-new-arm').value,location,...($('gate-target-way').value ? {wayId:$('gate-target-way').value}:{})});
    const partner=$('gate-merge-with').value;
    return apply({action:partner ? 'merge':'move',gateId:selectedId,location,
      ...(partner ? {mergeIds:[partner]}:{}),...($('gate-target-way').value ? {wayId:$('gate-target-way').value}:{})});
  }
  function attach(map) {
    render();
    if(!enabled()) return;
    const targetWay=draft().ways.find(w=>String(w.id)===$('gate-target-way').value);
    if(targetWay) map.svg.append(el('polyline',{points:targetWay.coordinates.map(p=>map.project.to(p).join(',')).join(' '),
      fill:'none',stroke:'#e88b12','stroke-width':4,'stroke-opacity':'.8','pointer-events':'none'}));
    if(picking) {map.svg.setAttribute('tabindex','0');map.svg.focus({preventScroll:true});}
    map.svg.addEventListener('click',event=>{
      if(!picking || busy() || event.button!==0) return;
      event.stopImmediatePropagation();move(map.project.from(map.position(event)));
    },true);
    map.svg.addEventListener('keydown',event=>{
      if(event.key==='Escape' && picking) {picking=false;adding=false;render();redraw();}
    });
    for(const gate of draft().gates) {
      const [x,y]=map.project.to(gate.location), radius=map.width/95;
      const handle=el('circle',{cx:x,cy:y,r:radius,fill:gate.id===selectedId ? '#ffe194':'transparent',
        'fill-opacity':gate.id===selectedId ? '.8':'1',stroke:gate.id===selectedId ? '#a76e0d':'transparent','stroke-width':.7,
        'data-no-pan':'',tabindex:0,'aria-label':`${gate.label} auswählen oder ziehen`});
      handle.append(el('title',{},`${gate.label}: anklicken oder ziehen. Zielweg bei Bedarf in der Liste festlegen.`));
      let start=null,position=null;
      handle.addEventListener('pointerdown',event=>{
        if(busy() || picking || event.button!==0) return;
        event.stopPropagation();selectedId=gate.id;render();
        handle.setAttribute('fill','#ffe194');handle.setAttribute('stroke','#a76e0d');
        start=[event.clientX,event.clientY];position=gate.location;handle.setPointerCapture(event.pointerId);
      });
      handle.addEventListener('pointermove',event=>{
        if(!start) return;
        const xy=map.position(event);position=map.project.from(xy);handle.setAttribute('cx',xy[0]);handle.setAttribute('cy',xy[1]);
      });
      handle.addEventListener('pointerup',event=>{
        if(!start) return;
        const moved=Math.hypot(event.clientX-start[0],event.clientY-start[1])>3;
        start=null;
        if(moved) move(position);else {render();redraw();}
      });
      handle.addEventListener('pointercancel',()=>{start=null;redraw();});
      map.svg.append(handle);
    }
  }
  $('gate-edit-mode').addEventListener('change',()=>{picking=false;adding=false;onModeChange?.(enabled());render();redraw();});
  $('gate-select').addEventListener('change',()=>{selectedId=$('gate-select').value;picking=false;adding=false;$('gate-merge-with').value='';render();redraw();});
  $('gate-target-way').addEventListener('change',()=>{render();redraw();});
  $('gate-place').addEventListener('click',()=>{if(busy()) return;adding=false;picking=true;render();redraw();message('Ziel auf dem gewünschten OSM-Weg anklicken. Escape beendet die Zielauswahl.');});
  $('gate-add').addEventListener('click',()=>{if(busy()) return;adding=true;picking=true;render();redraw();message('Neuen Entry/Exit auf dem Zielweg an der Flächengrenze anklicken. Typ und Straßenarm oben auswählen. Escape bricht ab.');});
  $('gate-delete').addEventListener('click',()=>{if(current()) apply({action:'delete',gateId:selectedId});});
  return {render,attach,isPicking:()=>picking && enabled()};
}
