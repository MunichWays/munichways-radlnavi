import test from 'node:test';
import assert from 'node:assert/strict';
import {initializeAreas} from '../junction_review/web/area-ui.js';

// Exercise actual UI event handlers without network or a browser dependency.
class Node {
  constructor(tag='div', attrs={}, text='') {
    this.tag=tag; this.children=[]; this.listeners={}; this.attributes={}; this.textContent=text;
    this.dataset={}; this.classList={toggle(){}}; this.hidden=false; this.disabled=false;
    Object.assign(this,attrs);
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children=nodes; }
  setAttribute(k,v) { this.attributes[k]=v; }
  getScreenCTM() { return {a:100000}; }
  focus() {}
  scrollIntoView() {}
  querySelectorAll(tag) { return this.children.flatMap(n=>[...(n.tag===tag?[n]:[]),...(n.querySelectorAll?.(tag)||[])]); }
  addEventListener(name,callback) { this.listeners[name]=callback; }
  async emit(name,event={}) { return this.listeners[name]?.({button:0,detail:1,preventDefault(){},...event}); }
}

async function harness(overrides={}) {
  const elements=new Map(), $=id=>{
    if (!elements.has(id)) elements.set(id,new Node());
    return elements.get(id);
  };
  for (const id of ['pick-area','draw-area','finish-area','undo-area','prepare-area','clear-area','cancel-area-task','open-project']) $(id).tag='button';
  $('area-panel').querySelectorAll=()=>[...elements.values()].filter(n=>n.tag==='button');
  let busy=false, map, accepted=null;
  const calls=[], api=async(path,options)=>{
    calls.push([path,options]);
    if (overrides[path]) return overrides[path](options);
    if (path==='/api/projects') return [];
    if (path==='/api/jobs/current') return null;
    throw new Error('Unexpected API: '+path);
  };
  const make=(tag,attrs,text)=>new Node(tag,attrs,text);
  initializeAreas({$,api,createMap:()=>{
    map={svg:new Node('svg'),project:{to:p=>p,from:p=>p},position:event=>event.position};return map;
  },line(){},el:make,html:make,project:()=>({sites:[{origin:[11,48]}]}),acceptProject:d=>{accepted=d;},
  setBusy:b=>{busy=b;},isBusy:()=>busy,message:text=>{$('message').textContent=text;}});
  await new Promise(resolve=>setImmediate(resolve));
  return {$,calls,get busy(){return busy;},get map(){return map;},get accepted(){return accepted;}};
}

test('OSM failure replaces searching text, hides spinner and permits a second attempt',async()=>{
  let attempts=0;
  const h=await harness({'/api/areas/search':async()=>{
    attempts++;if(attempts===1) throw new Error('OSM vorübergehend nicht verfügbar. Bitte erneut versuchen.');return [];
  }});
  h.$('area-name').value='Olcheing';
  await h.$('area-search').emit('submit');
  assert.match(h.$('area-status').textContent,/erneut versuchen/);
  assert.equal(h.$('area-spinner').hidden,true);
  assert.equal(h.busy,false);
  await h.$('area-search').emit('submit');
  assert.equal(h.$('area-results').hidden,false);
  assert.match(h.$('area-results').children[0].textContent,/Kein Gebiet/);
});

test('rename targets the selected saved project without opening or replacing the current project',async()=>{
  const h=await harness({
    '/api/projects':async()=>[{id:'other',name:'Six cases',count:6,active:false}],
    '/api/projects/rename':async()=>({workspaceId:'other',project:{name:'East Munich'},sites:[]})
  });
  h.$('project-select').value='other';
  await h.$('rename-project').emit('click');
  assert.equal(h.$('project-rename-form').hidden,false);
  assert.equal(h.$('project-rename-name').value,'Six cases');
  h.$('project-rename-name').value='East Munich';
  await h.$('project-rename-form').emit('submit');
  assert.deepEqual(h.calls.find(([path])=>path==='/api/projects/rename')[1].body,
    {id:'other',name:'East Munich',expectedName:'Six cases'});
  assert.equal(h.accepted,null);
  assert.equal(h.$('project-rename-form').hidden,true);
  assert.match(h.$('message').textContent,/East Munich/);
});

test('results have prominent names; boundary is fetched only when a result is chosen',async()=>{
  const item={id:1,name:'Dachau',description:'Dachau',level:'8',bounds:{minlon:11,maxlon:11.1,minlat:48,maxlat:48.1}};
  const h=await harness({'/api/areas/search':async()=>[item],'/api/areas/boundary':async()=>({...item,outlines:[[[11,48],[11.1,48.1]]]})});
  h.$('area-name').value='dachau';
  await h.$('area-search').emit('submit');
  assert.equal(h.calls.some(([p])=>p==='/api/areas/boundary'),false);
  const card=h.$('area-results').children.find(n=>n.tag==='button');
  assert.equal(card.children[0].textContent,'Dachau');
  await card.emit('click');
  assert.equal(h.calls.filter(([p])=>p==='/api/areas/boundary').length,1);
  assert.equal(h.$('prepare-area').disabled,false);
  assert.match(h.$('area-status').textContent,/Dachau/);
});

test('four-corner drawing closes by clicking its first point, without duplicate vertices',async()=>{
  const h=await harness();
  await h.$('draw-area').emit('click');
  for(const p of [[11,48],[11.001,48],[11.001,48.001],[11,48.001],[11,48]]) await h.map.svg.emit('click',{position:p});
  assert.equal(h.$('prepare-area').disabled,false);
  assert.equal(h.$('finish-area').hidden,true);
  assert.match(h.$('area-status').textContent,/4 Eckpunkten/);
});

test('double-click finishes after first click adds a vertex; the second click is not added',async()=>{
  const h=await harness();await h.$('draw-area').emit('click');
  for(const p of [[11,48],[11.001,48],[11.001,48.001]]) await h.map.svg.emit('click',{position:p});
  await h.map.svg.emit('click',{position:[11.001,48.001],detail:2});
  await h.map.svg.emit('dblclick');
  assert.equal(h.$('prepare-area').disabled,false);
  assert.match(h.$('area-status').textContent,/3 Eckpunkten/);
});

test('search shows a spinner while waiting and cancellation clears busy state',async()=>{
  const h=await harness({'/api/areas/search':({signal})=>new Promise((resolve,reject)=>{
    signal.addEventListener('abort',()=>reject(new DOMException('Abgebrochen','AbortError')));
  })});
  h.$('area-name').value='Dachau';
  const pending=h.$('area-search').emit('submit');
  assert.equal(h.$('area-spinner').hidden,false);
  assert.equal(h.busy,true);
  await h.$('cancel-area-task').emit('click'); await pending;
  assert.equal(h.$('area-spinner').hidden,true);
  assert.equal(h.busy,false);
  assert.match(h.$('area-status').textContent,/Abgebrochen/);
});

test('an invalid crossing polygon remains editable and undo allows correction',async()=>{
  const h=await harness(); await h.$('draw-area').emit('click');
  for(const p of [[11,48],[11.001,48.001],[11,48.001],[11.001,48]]) await h.map.svg.emit('click',{position:p});
  await h.$('finish-area').emit('click');
  assert.equal(h.$('prepare-area').disabled,true);
  assert.match(h.$('area-status').textContent,/kreuzen/);
  await h.$('undo-area').emit('click'); await h.$('finish-area').emit('click');
  assert.equal(h.$('prepare-area').disabled,false);
  assert.match(h.$('area-status').textContent,/3 Eckpunkten/);
});
