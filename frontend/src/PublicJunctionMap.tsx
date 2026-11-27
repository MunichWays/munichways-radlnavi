import React, {ComponentProps, useEffect, useRef, useState} from 'react';
import * as leaflet from 'leaflet';
import type * as Leaflet from '../node_modules/@types/leaflet';
import DistrictLayer from './DistrictLayer';
import {Coordinate, PublicJunction, viewColors, viewLabels, viewStatus} from './publicJunctions';

// The installed rotation wrapper recursively re-exports its own declarations.
// Use the matching upstream declarations for this ordinary Leaflet map.
const L = leaflet as unknown as typeof Leaflet;
const latLng = (p: Coordinate): Leaflet.LatLngTuple => [p[1], p[0]];
function text(value: string) { const span=document.createElement('span'); span.textContent=value; return span; }

type DistrictMap = ComponentProps<typeof DistrictLayer>['map'];

export default function PublicJunctionMap({sites, selected, onSelect, position, showDistricts=true}: {
  sites: PublicJunction[]; selected: PublicJunction | null; onSelect: (site: PublicJunction) => void;
  position: {point: Coordinate; accuracy: number} | null; showDistricts?: boolean;
}) {
  const container=useRef<HTMLDivElement>(null), map=useRef<Leaflet.Map | null>(null);
  const [districtMap,setDistrictMap]=useState<DistrictMap>(null);
  const markers=useRef<Leaflet.LayerGroup>(), details=useRef<Leaflet.LayerGroup>(), location=useRef<Leaflet.LayerGroup>();
  const select=useRef(onSelect); select.current=onSelect;
  useEffect(()=>{
    const current=L.map(container.current!, {zoomControl:true}).setView([48.14,11.57],12);
    map.current=current;
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom:19, updateWhenIdle:true,
    }).addTo(current);
    markers.current=L.layerGroup().addTo(current); details.current=L.layerGroup().addTo(current); location.current=L.layerGroup().addTo(current);
    const observer=new ResizeObserver(()=>current.invalidateSize()); observer.observe(container.current!);
    setDistrictMap(current as unknown as DistrictMap);
    return ()=>{observer.disconnect(); setDistrictMap(null); current.remove(); map.current=null;};
  },[]);
  useEffect(()=>{
    markers.current?.clearLayers();
    sites.forEach(s=>{
      const color=viewColors[viewStatus(s)];
      L.circleMarker(latLng(s.origin),{radius:7,weight:2,color,fillColor:color,fillOpacity:.85})
        .bindTooltip(text(`K${s.number} · ${s.name} · ${viewLabels[viewStatus(s)]}`))
        .on('click',()=>select.current(s)).addTo(markers.current!);
    });
  },[sites]);
  useEffect(()=>{
    details.current?.clearLayers();
    if(!map.current) return;
    if(!selected) {
      if(sites.length) map.current.fitBounds(L.latLngBounds(sites.map(s=>latLng(s.origin))),{padding:[25,25],maxZoom:14});
      return;
    }
    const layer=details.current!;
    if(selected.polygon.length) L.polygon(selected.polygon.map(latLng),{color:'#7139a4',weight:3,fillOpacity:.12}).addTo(layer);
    const groups=new Map<string,{point:Coordinate; labels:string[]; kind:string}>();
    selected.gates.forEach(g=>{
      const key=g.location.map(n=>n.toFixed(7)).join(',');
      const group=groups.get(key) || {point:g.location,labels:[],kind:g.kind}; group.labels.push(g.label); groups.set(key,group);
      const scale=Math.cos(g.location[1]*Math.PI/180);
      const offset=(forward:number,side=0):Coordinate=>[
        g.location[0]+(g.forward[0]*forward-g.forward[1]*side)/(111320*scale),
        g.location[1]+(g.forward[1]*forward+g.forward[0]*side)/111320];
      const color=g.kind==='entry' ? '#13764e' : '#185fbe';
      L.polyline([offset(-3),offset(3),offset(1.5,1),offset(3),offset(1.5,-1)].map(latLng),{color,weight:2}).addTo(layer);
    });
    groups.forEach(g=>{
      L.circleMarker(latLng(g.point),{radius:4,color:g.kind==='entry' ? '#13764e' : '#185fbe',fillOpacity:1})
        .bindTooltip(text(g.labels.join(' / ')),{permanent:true,direction:g.point[0]<selected.origin[0]?'left':'right',className:'junction-gate-label'})
        .addTo(layer);
    });
    if(selected.polygon.length) map.current.fitBounds(L.latLngBounds(selected.polygon.map(latLng)),{padding:[70,55],maxZoom:19});
    else map.current.setView(latLng(selected.origin),18);
  },[selected,sites]);
  useEffect(()=>{
    location.current?.clearLayers();
    if(!position || !map.current) return;
    L.circle(latLng(position.point),{radius:position.accuracy,color:'#1673e7',weight:1,fillOpacity:.08}).addTo(location.current!);
    L.circleMarker(latLng(position.point),{radius:7,color:'white',weight:2,fillColor:'#1673e7',fillOpacity:1})
      .bindTooltip(text('Mein Standort')).addTo(location.current!);
    map.current.setView(latLng(position.point),17);
  },[position]);
  return <div className="junction-map-wrap">
    <div ref={container} className="junction-map" aria-label="Karte der Kreuzungen" />
    <div className="junction-map-status"><DistrictLayer map={districtMap} visible={showDistricts}/></div>
  </div>;
}
