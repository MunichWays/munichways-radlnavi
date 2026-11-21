import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Paper, Portal } from '@mui/material';
// The package ships without TypeScript declarations.
// @ts-ignore
import textInstructions from 'osrm-text-instructions';
import { appGuidancePreview } from './appGuidancePreview';

type WayType = 'cycleway' | 'road';

function intersectionWayType(intersection: any): WayType | null {
  const classes = intersection?.classes;
  if (!Array.isArray(classes)) return null;
  const cycleway = classes.includes('cycleway');
  const road = classes.includes('road');
  if (cycleway === road) return null;
  return cycleway ? 'cycleway' : 'road';
}

export function listSteps(route: any) {
  let distance = 0;
  const legs = route?.legs || [{ steps: route?.steps || [] }];
  return legs.flatMap((leg: any, legIndex: number) => {
    let previousWayType: WayType | null = null;
    return (leg.steps || []).map((step: any, stepIndex: number) => {
    const at = distance;
    distance += Number(step.distance) || 0;
    let baseInstruction: string;
    try { baseInstruction = textInstructions('v5').compile('de', step); }
    catch { baseInstruction = 'Für dieses Manöver ist keine deutsche Übersetzung verfügbar.'; }
    const intersections = step.intersections;
    const outgoing = Array.isArray(intersections) && intersections.length
      ? intersectionWayType(intersections[0]) : null;
    const detectedWayType: WayType | null = step.mode === 'cycling' &&
      step.maneuver?.type !== 'depart' && step.maneuver?.type !== 'arrive' &&
      previousWayType && outgoing && previousWayType !== outgoing ? outgoing : null;
    previousWayType = step.mode === 'cycling' && Array.isArray(intersections) && intersections.length
      ? intersectionWayType(intersections[intersections.length - 1]) : null;
    return { step, at, baseInstruction, detectedWayType,
      instruction: baseInstruction, legIndex, stepIndex };
    });
  });
}

type Props = {
  open: boolean;
  onClose: () => void;
  route: any;
  variant: string;
  onMap: (step: any) => void;
};

export default function RouteInspector({ open, onClose, route, variant, onMap }: Props) {
  const [error, setError] = useState('');
  const snapshot = useMemo(() => route ? {
    source: 'Aktuelle Kartenroute', variant, captured_at_utc: new Date().toISOString(),
    response: route.response || { route },
  } : null, [route, variant]);
  const panel = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const [position, setPosition] = useState({ x: window.innerWidth > 960 ? 380 : 8, y: 16 });
  const [minimized, setMinimized] = useState(false);
  const moveTo = useCallback((x: number, y: number) => {
    const bounds = panel.current?.getBoundingClientRect();
    setPosition({
      x: Math.max(8, Math.min(x, window.innerWidth - (bounds?.width || 300) - 8)),
      y: Math.max(8, Math.min(y, window.innerHeight - (bounds?.height || 100) - 8)),
    });
  }, []);
  useEffect(() => {
    const fit = () => setPosition(previous => ({
      x: Math.max(8, Math.min(previous.x, window.innerWidth - 308)),
      y: Math.max(8, Math.min(previous.y, window.innerHeight - 188)),
    }));
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  const speechRun = useRef(0);
  const [speaking, setSpeaking] = useState<number | null>(null);
  const canSpeak = typeof window.speechSynthesis !== 'undefined';
  const stopSpeech = useCallback(() => {
    speechRun.current++;
    window.speechSynthesis?.cancel();
  }, []);
  const stop = () => {
    stopSpeech();
    setSpeaking(null);
  };
  useEffect(() => {
    stopSpeech();
    setSpeaking(null);
    setError('');
    return stopSpeech;
  }, [open, route, stopSpeech]);
  useEffect(() => {
    if (open) setMinimized(false);
  }, [open]);

  const selectedRoute = route?.response?.routes?.[0] || route;
  const rawRows = listSteps(selectedRoute);
  const preview = appGuidancePreview(selectedRoute, rawRows);
  const rows = preview.rows;

  function speak(index: number, all: boolean, app = false) {
    stop();
    const run = speechRun.current;
    const next = (i: number) => {
      while (i < rows.length && (app ? !rows[i].appSpeech : !!rows[i].previewKey)) i++;
      if (run !== speechRun.current || i >= rows.length) { setSpeaking(null); return; }
      setSpeaking(i);
      const utterance = new SpeechSynthesisUtterance(app ? rows[i].appSpeech! : rows[i].instruction);
      utterance.lang = 'de-DE';
      utterance.onend = () => {
        if (run !== speechRun.current) return;
        if (all) next(i + 1); else setSpeaking(null);
      };
      utterance.onerror = () => {
        if (run === speechRun.current) { setSpeaking(null); setError('Vorlesen wurde unterbrochen oder ist nicht verfügbar.'); }
      };
      window.speechSynthesis.speak(utterance);
    };
    next(index);
  }

  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'radlnavi-routenpruefung.json';
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (!open) return null;
  return <Portal><Paper ref={panel} role="dialog" aria-modal="false" aria-labelledby="route-inspector-title"
    elevation={10} style={{ position: 'fixed', zIndex: 1300, left: position.x, top: position.y,
      width: 560, height: minimized ? 'auto' : 620, minWidth: 'min(300px, calc(100vw - 16px))',
      minHeight: minimized ? undefined : 180, maxWidth: `calc(100vw - ${position.x + 8}px)`,
      maxHeight: `calc(100dvh - ${position.y + 8}px)`, resize: minimized ? 'none' : 'both',
      overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
    <div style={{ display: 'flex', alignItems: 'center', background: '#e3f5ff', padding: 8, flexShrink: 0 }}>
      <div id="route-inspector-title" tabIndex={0} aria-label="Prüffenster verschieben, auch mit Pfeiltasten"
        style={{ cursor: 'move', touchAction: 'none', userSelect: 'none', flex: 1, fontWeight: 'bold' }}
        onPointerDown={event => {
          if (event.button !== 0) return;
          drag.current = { x: event.clientX, y: event.clientY, left: position.x, top: position.y };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={event => {
          if (drag.current) moveTo(drag.current.left + event.clientX - drag.current.x,
            drag.current.top + event.clientY - drag.current.y);
        }}
        onPointerUp={() => { drag.current = null; }}
        onPointerCancel={() => { drag.current = null; }}
        onLostPointerCapture={() => { drag.current = null; }}
        onKeyDown={event => {
          const delta: Record<string, number[]> = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] };
          if (delta[event.key]) {
            event.preventDefault();
            moveTo(position.x + delta[event.key][0], position.y + delta[event.key][1]);
          }
        }}>Hinweise einer Route prüfen</div>
      <Button onClick={() => setMinimized(value => !value)}>{minimized ? 'Öffnen' : 'Verkleinern'}</Button>
      <Button onClick={onClose}>Schließen</Button>
    </div>
    <div hidden={minimized} style={{ overflow: 'auto', flex: 1, padding: minimized ? 0 : 16 }}>
      <p>Am Titel verschieben, an der unteren rechten Ecke die Größe ändern. Die Karte bleibt bedienbar.</p>
      <p>RadlNavi: bisherige deutsche Manövertexte. App: Textvorschau für die geplante Fahrt,
        mit geprüften Kreuzungsansagen bei 120/40 m und unterdrückten Einzelhinweisen.
        Normale Manöver sind angenähert; GPS, Startansagen, Versatzfilter, Fahrtverlauf und tatsächlicher
        Sprechzeitpunkt werden nicht vollständig simuliert. Sonderhinweise zeigen mögliche Anfahrtsvarianten.</p>
      <p>Variante: {variant === 'direct' ? 'Direkt' : variant === 'discovery' ? 'Entdeckertour' : 'Standard'}</p>
      {error && <p role="alert">{error}</p>}
      <details><summary>Abfrage und Zeitpunkt</summary>
        <p>Quelle: aktuelle Kartenroute; automatische Aktualisierung nach jeder Neuberechnung.</p>
        {snapshot && <p>In die Prüfansicht übernommen: {snapshot.captured_at_utc}</p>}
      </details>
      <p><a href="/kreuzungspruefung/"
        target="_blank" rel="noopener noreferrer">Kreuzungsprüfung</a></p>
      {!snapshot && <p>Bitte zuerst eine Route auf der Karte berechnen.</p>}
      {snapshot && <>
        <p>{Math.round(selectedRoute.distance)} m · {rows.length} Manöver · {snapshot.source}</p>
        <p>{preview.junctionCount} große Kreuzungen in den geprüften Routendaten.
          {!preview.junctionCount && ' Keine passende aktive Kreuzungsbeziehung geliefert; normale Hinweise bleiben.'}</p>
        {preview.invalidMetadata && <p role="alert">Kreuzungsmetadaten unvollständig oder ungültig: keine Makro-Vorschau.</p>}
        <Button onClick={download}>Rohantwort herunterladen</Button>
        <Button disabled={!canSpeak || !rows.length} onClick={() => speak(0, true)}>RadlNavi: Alle Hinweise vorlesen</Button>
        <Button disabled={!canSpeak || !rows.some(row => row.appSpeech)} onClick={() => speak(0, true, true)}>App: Alle Hinweise vorlesen</Button>
        <Button disabled={speaking === null} onClick={stop}>Vorlesen stoppen</Button>
        {!canSpeak && <p>Dieser Browser unterstützt das Vorlesen nicht.</p>}
        {!rows.length && <p>Diese Antwort enthält keine Manöver.</p>}
        <ol style={{ paddingLeft: 28 }}>
          {rows.map((row: any, index: number) => <li key={row.previewKey || `${row.legIndex}-${row.stepIndex}`}
            style={{ padding: 12, marginBottom: 8, border: '1px solid #ccc', borderRadius: 6,
              background: speaking === index ? '#e3f5ff' : undefined }}>
            <strong>RadlNavi: {row.instruction}</strong>
            <p><strong>{row.appDisplay ? 'App-Anzeige:' : 'App:'}</strong>{' '}
              {row.appDisplay || row.appInstruction}
              {row.context && <> · {row.context}</>}
              {row.appDisplay && row.stepIndex === -1 && <> · Ansage: {row.appInstruction}</>}
            </p>
            <p>Bei {Math.round(row.at)} m ab Start · Abschnitt {row.legIndex + 1} · danach {Math.round(row.step.distance)} m</p>
            <p>Straße: {row.step.name || 'ohne Namen'} · Manöver: <code>{row.step.maneuver?.type} / {row.step.maneuver?.modifier || '—'}</code></p>
            <Button disabled={!canSpeak || !!row.previewKey} onClick={() => speak(index, false)}>Hinweis {index + 1} vorlesen</Button>
            <Button disabled={!canSpeak || !row.appSpeech} onClick={() => speak(index, false, true)}>App vorlesen</Button>
            <Button disabled={!row.step.maneuver?.location} onClick={() => {
              stop(); onMap(row.step);
            }}>Hinweis {index + 1} auf Karte</Button>
            <details><summary>Unveränderte Manöverdaten</summary>
              <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(row.step, null, 2)}</pre>
            </details>
          </li>)}
        </ol>
      </>}
    </div>
  </Paper></Portal>;
}
