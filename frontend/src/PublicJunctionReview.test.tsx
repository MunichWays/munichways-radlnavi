import React from 'react';
import {fireEvent, render, screen} from '@testing-library/react';
import '@testing-library/jest-dom';
import PublicJunctionReview from './PublicJunctionReview';
import {filterPublicJunctions, groupPublicJunctions, parsePublicJunctions} from './publicJunctions';

jest.mock('./PublicJunctionMap',()=>()=> <div>Kartenansicht</div>);
const site = {id:'one',number:1,name:'Romanplatz',origin:[11.5,48.1],polygon:[],gates:[],status:'confirmed',geometryRevision:2,
  technical:'Technisch bestanden',deployment:'Noch nicht live',branchMovements:4,movements:[],rechecks:[],note:''};
const data = {schemaVersion:1,readOnly:true,projectName:'München',publishedAt:'2026-11-21T20:00:00Z',sites:[site,{...site,id:'two',number:2,name:'Marsstraße',status:'excluded'}]};
beforeEach(()=>{window.history.replaceState(null,'','/'); global.fetch=jest.fn().mockResolvedValue({ok:true,json:async()=>data});});
test('filters the published snapshot by number, street and status',()=>{
  const parsed=parsePublicJunctions(data);
  expect(filterPublicJunctions(parsed.sites,'K01','all').map(s=>s.number)).toEqual([1]);
  expect(filterPublicJunctions(parsed.sites,'MARS','all').map(s=>s.number)).toEqual([2]);
  expect(filterPublicJunctions(parsed.sites,'','confirmed')).toHaveLength(1);
  expect(()=>parsePublicJunctions({...data,readOnly:false})).toThrow();
});
test('loads details from a read-only snapshot and returns to the filtered list',async()=>{
  render(<PublicJunctionReview/>);
  fireEvent.click(await screen.findByRole('button',{name:/K1 · Bestätigt/}));
  expect(screen.getByRole('heading',{name:'K1 · Romanplatz'})).toBeInTheDocument();
  expect(screen.getByText('Noch nicht live')).toBeInTheDocument();
  expect(window.location.hash).toBe('#K1');
  fireEvent.click(screen.getByRole('button',{name:/Alle Kreuzungen/}));
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'Mars'}});
  expect(screen.queryByRole('button',{name:/K1 · Bestätigt/})).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:/K2 · Ausgeschlossen/})).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
});
test('handles unavailable published data',async()=>{
  (fetch as jest.Mock).mockResolvedValue({ok:false});
  render(<PublicJunctionReview/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Kartenstand konnte nicht geladen');
});
test('opens a shared junction link',async()=>{
  window.history.replaceState(null,'','#K2');
  render(<PublicJunctionReview/>);
  expect(await screen.findByRole('heading',{name:'K2 · Marsstraße'})).toBeInTheDocument();
});
test('groups the list by city and district, unassigned last',async()=>{
  const district=(id:string,name:string)=>({id,name});
  const grouped={...data,schemaVersion:2,sites:[
    {...site,number:3,id:'three',city:'München',district:district('BA04','Schwabing-West')},
    {...site,number:1,id:'one',city:'München',district:district('BA01','Altstadt-Lehel')},
    {...site,number:2,id:'two',city:'München',district:null,status:'excluded'},
    {...site,number:4,id:'four',city:'Augsburg',district:null}]};
  const groups=groupPublicJunctions(parsePublicJunctions(grouped).sites as any);
  expect(groups.map(g=>[g.city,g.count,g.districts.map(d=>d.title)])).toEqual([
    ['München',3,['BA01 · Altstadt-Lehel','BA04 · Schwabing-West','Ohne Stadtbezirk']],
    ['Augsburg',1,['Ohne Stadtbezirk']]]);
  (fetch as jest.Mock).mockResolvedValue({ok:true,json:async()=>grouped});
  const {container}=render(<PublicJunctionReview/>);
  expect(await screen.findByRole('region',{name:'München'})).toBeInTheDocument();
  expect(screen.getByText('BA04 · Schwabing-West')).toBeInTheDocument();
  expect(container.querySelectorAll('details[open]')).toHaveLength(0);
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'Roman'}});
  expect(container.querySelectorAll('details[open]').length).toBeGreaterThan(0);
  expect(screen.getByRole('checkbox',{name:'Stadtbezirke'})).toBeChecked();
});
