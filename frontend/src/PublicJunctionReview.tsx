import React, {useEffect, useMemo, useState} from 'react';
import PublicJunctionMap from './PublicJunctionMap';
import {Coordinate, PublicJunction, PublicJunctionData, ReviewStatus, filterPublicJunctions, groupPublicJunctions, parsePublicJunctions, reviewLabels} from './publicJunctions';
import './PublicJunctionReview.css';

const DISTRICT_KEY='kreuzungspruefung.stadtbezirke';
function storedDistricts() { try { return window.localStorage.getItem(DISTRICT_KEY)!=='off'; } catch { return true; } }

export default function PublicJunctionReview() {
  const [showDistricts,setShowDistricts]=useState(storedDistricts);
  function toggleDistricts(value:boolean) {
    setShowDistricts(value); try { window.localStorage.setItem(DISTRICT_KEY,value?'on':'off'); } catch { /* optional */ }
  }
  const [data,setData]=useState<PublicJunctionData | null>(null), [error,setError]=useState('');
  const [query,setQuery]=useState(''), [status,setStatus]=useState('all'), [selectedNumber,setSelectedNumber]=useState<number | null>(null);
  const [position,setPosition]=useState<{point:Coordinate;accuracy:number} | null>(null), [locating,setLocating]=useState(false), [locationError,setLocationError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    fetch('/kreuzungspruefung/data.json',{signal:controller.signal,cache:'no-cache'})
      .then(r=>{if(!r.ok) throw new Error('Der Kartenstand konnte nicht geladen werden. Bitte erneut laden.'); return r.json();})
      .then(parsePublicJunctions).then(setData).catch(e=>{if(e.name!=='AbortError') setError(e.message);});
    return ()=>controller.abort();
  },[]);
  useEffect(()=>{
    const update=()=>{const match=/^#K(\d+)$/i.exec(window.location.hash); setSelectedNumber(match ? Number(match[1]) : null);};
    update(); window.addEventListener('hashchange',update); return ()=>window.removeEventListener('hashchange',update);
  },[]);
  const sites=useMemo(()=>filterPublicJunctions(data?.sites || [],query,status),[data,query,status]);
  const groups=useMemo(()=>groupPublicJunctions(sites),[sites]);
  const filtered=!!query.trim() || status!=='all';
  const selected=data?.sites.find(s=>s.number===selectedNumber) || null;
  function select(site:PublicJunction) {setSelectedNumber(site.number); window.history.replaceState(null,'',`#K${site.number}`);}
  function clear() {setSelectedNumber(null); window.history.replaceState(null,'',window.location.pathname);}
  function locate() {
    setLocationError('');
    if(!navigator.geolocation) {setLocationError('Dieser Browser unterstützt die Standortanzeige nicht.');return;}
    setLocating(true);
    navigator.geolocation.getCurrentPosition(p=>{
      setPosition({point:[p.coords.longitude,p.coords.latitude],accuracy:p.coords.accuracy});setLocating(false);
    },()=>{setLocationError('Standort nicht verfügbar. Bitte Standortzugriff im Browser erlauben.');setLocating(false);},
    {enableHighAccuracy:true,timeout:12000,maximumAge:10000});
  }
  return <div className="junction-review">
    <header className="junction-header"><div><a href="/">← RadlNavi</a><h1>Kreuzungsprüfung</h1><p>{data?.projectName || 'Kartenstand wird geladen …'}</p></div>
      <div className="junction-published">Nur-Lese-Ansicht{data && <><br/>Stand: {new Date(data.publishedAt).toLocaleString('de-DE')}<br/>{data.sites.length} Kreuzungen</>}</div></header>
    {error && <p role="alert">{error}</p>}
    <div className="junction-controls"><label>Suche<input type="search" value={query} placeholder="K67 oder Straßenname" onChange={e=>{setQuery(e.target.value);clear();}}/></label>
      <label>Status<select value={status} onChange={e=>{setStatus(e.target.value);clear();}}><option value="all">Alle</option>{Object.entries(reviewLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
      <button type="button" onClick={locate} disabled={locating}>{locating?'Standort wird gesucht …':'Mein Standort'}</button>
      <label className="junction-toggle"><input type="checkbox" checked={showDistricts} onChange={e=>toggleDistricts(e.target.checked)}/>Stadtbezirke</label></div>
    {locationError && <p role="alert">{locationError}</p>}
    {position && <p className="junction-location">Standort bei letzter Abfrage · Genauigkeit ca. {Math.round(position.accuracy)} m</p>}
    {data && <main className="junction-layout"><section className="junction-pane" aria-label="Kreuzungen und Details">
      {selected ? <><button type="button" onClick={clear}>← Alle Kreuzungen</button><h2>K{selected.number} · {selected.name}</h2>
        <p className={`junction-status ${selected.status}`}>{reviewLabels[selected.status]} · Geometrie v{selected.geometryRevision}</p>
        <p>{selected.technical}</p><p>{selected.deployment}</p>
        {!!selected.branchMovements && <p>{selected.branchMovements} Fahrbeziehungen im Backend-Code aktiviert.</p>}
        {selected.deferredUntil && <p>Wiedervorlage: {selected.deferredUntil}</p>}
        {selected.note && <p className="junction-note">{selected.note}</p>}
        {!selected.polygon.length && <p>Für diesen Fall ist keine Fläche hinterlegt.</p>}
        <p className="junction-legend">Grün: Entry · Blau: Exit · Violett: Kreuzungsfläche · Pfeile: Fahrtrichtung</p>
        {!!selected.movements.length && <details><summary>Fahrbeziehungen ({selected.movements.length})</summary><ul className="junction-movements">{selected.movements.map((m,i)=><li key={i}><strong>{m.entryLabel} → {m.exitLabel}</strong>: {m.kind==='left'?'links':m.kind==='straight'?'geradeaus':m.kind==='right'?'rechts':m.kind}
          {m.kind==='right' || m.kind==='standard' ? ' · normale Ansagen' : m.enabled ? ' · technisch bestanden' : ' · normale Ansagen (ausgeschlossen)'}
          {!m.enabled && m.reason && <p>{m.reason}</p>}</li>)}</ul></details>}
        {!!selected.rechecks.length && <details><summary>Wiedervorlagen</summary><ul>{selected.rechecks.map((r,i)=><li key={i}>{r.entry} → {r.exit} · {r.date} · {r.reason}</li>)}</ul></details>}
        <p className="junction-readonly">Öffentlicher Kartenstand. Bearbeitung erfolgt in der lokalen Kreuzungsapp.</p>
      </> : <><h2>{sites.length} Kreuzungen</h2><p>Auf der Karte oder in der Liste auswählen.</p><p className="junction-legend">● Grün: bestätigt · Orange: offen · Ocker: zurückgestellt · Grau: ausgeschlossen</p>
        <nav aria-label="Kreuzungsliste">{groups.map(g=><section className="junction-city" key={g.city} aria-label={g.city}>
          <h3>{g.city} <small>{g.count}</small></h3>
          {g.districts.map(d=><details className="junction-district" key={`${d.id}-${filtered}`} open={filtered}>
            <summary><span>{d.title}</span><small>{d.sites.length}{d.sites.some(x=>x.status==='confirmed') ? ` · ${d.sites.filter(x=>x.status==='confirmed').length} bestätigt` : ''}</small></summary>
            {d.sites.map(s=><button className="junction-list-item" type="button" key={s.id} onClick={()=>select(s)}><strong>K{s.number} · {reviewLabels[s.status as ReviewStatus]}</strong><span>{s.name}</span></button>)}
          </details>)}
        </section>)}</nav>
        {!sites.length && <p>Keine Kreuzung gefunden.</p>}</>}
    </section><PublicJunctionMap sites={sites} selected={selected} onSelect={select} position={position} showDistricts={showDistricts}/></main>}
  </div>;
}
