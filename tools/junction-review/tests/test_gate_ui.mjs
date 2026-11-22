import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {geometryOf,initializeGateEditor,armLabel} from '../junction_review/web/gate-ui.js';

test('street directions name the road and compass direction even for an empty arm',()=>{
  const site={armDescriptions:{'Arm-1':{names:['Marsstraße'],bearing:37}}};
  assert.equal(armLabel(site,'Arm-1',['Exit-1','Entry-5']),
    'Arm-1 · Marsstraße nach Nordost · Exit-1, Entry-5');
  assert.match(armLabel(site,'Arm-1',[]),/Marsstraße nach Nordost.*noch keine Punkte/);
  assert.match(armLabel({},'Arm-2',['Exit-2']),/zugeordneten Punkte.*Exit-2/);
});

class Node {
  constructor(tag='div',attrs={},text='') {this.tag=tag;this.children=[];this.listeners={};this.attributes={};this.textContent=text;Object.assign(this,attrs);}
  get value() {return this.tag==='select' ? (this.children.find(n=>n.selected)||this.children[0])?.value||'' : this._value||'';}
  set value(value) {if(this.tag==='select') this.children.forEach(n=>n.selected=n.value===value);else this._value=value;}
  replaceChildren(...nodes) {this.children=nodes;}
  append(...nodes) {this.children.push(...nodes);}
  addEventListener(name,callback) {this.listeners[name]=callback;}
  setAttribute(k,v) {this.attributes[k]=v;}
  async emit(name,event={}) {await this.listeners[name]?.({button:0,stopImmediatePropagation(){},...event});await new Promise(resolve=>setImmediate(resolve));}
  focus() {}
}

test('gate merge uses the full draft and a later delete preserves that staged merge',async()=>{
  const original=JSON.parse(readFileSync(new URL('./fixtures/gate-edit-p3.json',import.meta.url)));
  const base={...original,editVersion:0,geometryFingerprint:'original'};
  let draft=structuredClone(base),busy=false;
  const elements=new Map(),$=id=>{
    if(!elements.has(id)) elements.set(id,new Node(['gate-select','gate-merge-with','gate-target-way','gate-new-arm','gate-new-kind'].includes(id)?'select':'div'));
    return elements.get(id);
  };
  $('gate-edit-mode').checked=true;
  const calls=[],map={svg:new Node(),width:100,project:{to:p=>p,from:p=>p},position:e=>e.location};
  const editor=initializeGateEditor({$,html:(...args)=>new Node(...args),el:(...args)=>new Node(...args),
    draft:()=>draft,selected:()=>base,busy:()=>busy,setBusy:b=>busy=b,
    preview:async payload=>{
      calls.push(payload);
      const result={...draft,...structuredClone(payload.geometry),geometryFingerprint:'changed'};
      const remove=payload.gateEdit.action==='merge' ? payload.gateEdit.mergeIds : [payload.gateEdit.gateId];
      result.gates=result.gates.filter(g=>!remove.includes(g.id));
      return result;
    },accept:result=>draft=result,redraw(){},message(){}});
  editor.render();
  $('gate-select').value='entry-2';await $('gate-select').emit('change');
  $('gate-merge-with').value='entry-3';$('gate-target-way').value='421302932';
  await $('gate-place').emit('click');editor.attach(map);
  await map.svg.emit('click',{location:[11.6465695,48.1087776]});
  assert.equal(calls[0].gateEdit.action,'merge');
  assert.deepEqual(calls[0].gateEdit.mergeIds,['entry-3']);
  assert.equal(calls[0].gateEdit.wayId,'421302932');
  assert.equal(calls[0].geometry.gates.length,original.gates.length);
  assert.equal(draft.gates.some(g=>g.id==='entry-3'),false);
  await $('gate-delete').emit('click');
  assert.equal(calls[1].geometry.gates.some(g=>g.id==='entry-3'),false);
  assert.equal(original.gates.some(g=>g.id==='entry-3'),true);
  const copy=geometryOf(draft);copy.logicalArms['Arm-1'].pop();
  assert.notDeepEqual(copy.logicalArms,draft.logicalArms);
});


test('adding an exit passes type, arm and explicit road and retains staged geometry',async()=>{
  const base={...JSON.parse(readFileSync(new URL('./fixtures/gate-edit-p5.json',import.meta.url))),editVersion:0};
  let draft=structuredClone(base),busy=false;
  const elements=new Map(),$=id=>{
    if(!elements.has(id)) elements.set(id,new Node(['gate-select','gate-merge-with','gate-target-way','gate-new-arm','gate-new-kind'].includes(id)?'select':'div'));
    return elements.get(id);
  };
  $('gate-edit-mode').checked=true;
  $('gate-new-kind').append(new Node('option',{value:'entry'}),new Node('option',{value:'exit'}));
  const calls=[],map={svg:new Node(),width:100,project:{to:p=>p,from:p=>p},position:e=>e.location};
  const editor=initializeGateEditor({$,html:(...args)=>new Node(...args),el:(...args)=>new Node(...args),
    draft:()=>draft,selected:()=>base,busy:()=>busy,setBusy:b=>busy=b,
    preview:async payload=>{
      calls.push(payload);
      const result={...draft,...structuredClone(payload.geometry)};
      result.gates.push({id:'manual-exit-4',label:'Exit-4',kind:'exit',osmWayId:3302001,location:payload.gateEdit.location});
      result.logicalArms['Arm-3'].push('Exit-4');return result;
    },accept:r=>draft=r,redraw:()=>{},message:()=>{}});
  editor.render();$('gate-new-kind').value='exit';$('gate-new-arm').value='Arm-3';$('gate-target-way').value='3302001';
  await $('gate-add').emit('click');editor.attach(map);
  await map.svg.emit('click',{location:[11.64685,48.0962087]});
  assert.deepEqual(calls[0].gateEdit,{action:'add',kind:'exit',arm:'Arm-3',wayId:'3302001',location:[11.64685,48.0962087]});
  assert.deepEqual(calls[0].geometry,geometryOf(base));
  assert.equal($('gate-select').value,'manual-exit-4');
  assert.equal(editor.isPicking(),false);
});
