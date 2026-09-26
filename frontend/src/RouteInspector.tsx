import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Paper, Portal, TextField } from '@mui/material';
// The package ships without TypeScript declarations.
// @ts-ignore
import textInstructions from 'osrm-text-instructions';

const examples = [
  { name: 'Birketweg', start: '48.145395, 11.520751', end: '48.145413, 11.522572' },
  { name: 'Schrammerstraße', start: '48.139050, 11.576817', end: '48.138800, 11.577644' },
  { name: 'Waisenhausstraße', start: '48.161527, 11.529508', end: '48.162217, 11.529328' },
  { name: 'Lenbachplatz', start: '48.140563, 11.568148', end: '48.140709, 11.570143' },
];

export function parseCoordinates(value: string): number[] {
  const values = value.replaceAll('[', '').replaceAll(']', '').split(',').map(part => part.trim());
  const [lat, lon] = values.map(Number);
  if (values.length !== 2 || values.some(part => !part) || !Number.isFinite(lat) ||
      !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
    throw new Error('Koordinaten bitte als Breite, Länge eingeben, z. B. 48.145395, 11.520751.');
  }
  return [lon, lat];
}

export function listSteps(route: any) {
  let distance = 0;
  const legs = route?.legs || [{ steps: route?.steps || [] }];
  return legs.flatMap((leg: any, legIndex: number) => (leg.steps || []).map((step: any, stepIndex: number) => {
    const at = distance;
    distance += Number(step.distance) || 0;
    let instruction: string;
    try { instruction = textInstructions('v5').compile('de', step); }
    catch { instruction = 'Für dieses Manöver ist keine deutsche Übersetzung verfügbar.'; }
    return { step, at, instruction, legIndex, stepIndex };
  }));
}

type Props = {
  open: boolean;
  onClose: () => void;
  route: any;
  variant: string;
  onMap: (step: any) => void;
  startPosition?: { lat: string | number; lon: string | number } | null;
  endPosition?: { lat: string | number; lon: string | number } | null;
};

export default function RouteInspector({ open, onClose, route, variant, onMap, startPosition, endPosition }: Props) {
  const [start, setStart] = useState(examples[0].start);
  const [end, setEnd] = useState(examples[0].end);
  const [snapshot, setSnapshot] = useState<any>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
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
    if (!open) {
      request.current?.abort();
      stopSpeech();
      setSpeaking(null);
      setLoading(false);
    }
    return () => {
      request.current?.abort();
      stopSpeech();
    };
  }, [open, stopSpeech]);

  const selectedRoute = snapshot?.response.routes?.[0] || snapshot?.response.route;
  const rows = listSteps(selectedRoute);

  const calculate = useCallback(async (from: string, to: string) => {
    request.current?.abort();
    stopSpeech();
    setSpeaking(null);
    setError('');
    setSnapshot(null);
    const controller = new AbortController();
    request.current = controller;
    try {
      const coordinates = [parseCoordinates(from), parseCoordinates(to)].map(p => p.join(',')).join(';');
      const query = new URLSearchParams({ steps: 'true', geometries: 'geojson', overview: 'full',
        annotations: 'nodes,distance', alternatives: 'false', continue_straight: 'default', variant });
      const url = `${process.env.REACT_APP_BACKEND_URL || ''}/route/v1/bike/${coordinates}?${query}`;
      setLoading(true);
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error(`Die Route konnte nicht geladen werden (HTTP ${response.status}).`);
      const payload = await response.json();
      if (payload.code !== 'Ok' || !payload.routes?.[0]?.legs?.length) {
        throw new Error('RadlNavi hat keine Route mit Manövern geliefert.');
      }
      if (!controller.signal.aborted) setSnapshot({ url, variant,
        retrieved_at_utc: new Date().toISOString(), source: 'OSRM-kompatible RadlNavi-API', response: payload });
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Abruf fehlgeschlagen.');
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [variant, stopSpeech]);

  const sourceStart = startPosition ? `${startPosition.lat}, ${startPosition.lon}` : '';
  const sourceEnd = endPosition ? `${endPosition.lat}, ${endPosition.lon}` : '';
  useEffect(() => {
    if (!open) return;
    setMinimized(false);
    if (sourceStart || sourceEnd) {
      setStart(sourceStart);
      setEnd(sourceEnd);
    }
    if (sourceStart && sourceEnd) void calculate(sourceStart, sourceEnd);
    else if (sourceStart || sourceEnd) {
      request.current?.abort();
      stopSpeech();
      setSpeaking(null);
      setLoading(false);
      setSnapshot(null);
      setError('Bitte Start und Ziel ergänzen.');
    }
  }, [open, sourceStart, sourceEnd, calculate, stopSpeech]);

  function speak(index: number, all: boolean) {
    stop();
    const run = speechRun.current;
    const next = (i: number) => {
      if (run !== speechRun.current || i >= rows.length) { setSpeaking(null); return; }
      setSpeaking(i);
      const utterance = new SpeechSynthesisUtterance(rows[i].instruction);
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
      <p>Alle von RadlNavi gelieferten Manöver, einschließlich Start und Ziel. Die deutschen Texte
        werden im Browser erzeugt. Das Vorlesen ist eine Textvorschau; Ansagen, Filter und Zeitpunkt
        der Flutter-App werden hier nicht simuliert.</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {examples.map(example => <Button key={example.name} onClick={() => {
          setStart(example.start); setEnd(example.end);
        }}>{example.name}</Button>)}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, margin: '16px 0' }}>
        <TextField label="Start: Breite, Länge" value={start} onChange={e => setStart(e.target.value)} />
        <TextField label="Ziel: Breite, Länge" value={end} onChange={e => setEnd(e.target.value)} />
        <Button variant="contained" onClick={() => calculate(start, end)} disabled={loading}>Route prüfen</Button>
        <Button disabled={!route || loading} onClick={() => {
          stop(); setError(''); setSnapshot({ source: 'Aktuelle Kartenroute aus RadlNavi /route', variant,
            captured_at_utc: new Date().toISOString(), response: { route } });
        }}>Aktuelle Kartenroute übernehmen</Button>
      </div>
      <p>Variante: {variant === 'direct' ? 'Direkt' : 'Standard'}</p>
      {loading && <p role="status">Route wird geladen …</p>}
      {error && <p role="alert">{error}</p>}
      {snapshot && <>
        <p>{Math.round(selectedRoute.distance)} m · {rows.length} Manöver · {snapshot.source}</p>
        {snapshot.url && <details><summary>Abfrage und Zeitpunkt</summary>
          <p>{snapshot.retrieved_at_utc}</p><code style={{ overflowWrap: 'anywhere' }}>{snapshot.url}</code>
        </details>}
        <Button onClick={download}>Rohantwort herunterladen</Button>
        <Button disabled={!canSpeak || !rows.length} onClick={() => speak(0, true)}>Alle Hinweise vorlesen</Button>
        <Button disabled={speaking === null} onClick={stop}>Vorlesen stoppen</Button>
        {!canSpeak && <p>Dieser Browser unterstützt das Vorlesen nicht.</p>}
        {!rows.length && <p>Diese Antwort enthält keine Manöver.</p>}
        <ol style={{ paddingLeft: 28 }}>
          {rows.map((row: any, index: number) => <li key={`${row.legIndex}-${row.stepIndex}`}
            style={{ padding: 12, marginBottom: 8, border: '1px solid #ccc', borderRadius: 6,
              background: speaking === index ? '#e3f5ff' : undefined }}>
            <strong>{row.instruction}</strong>
            <p>Bei {Math.round(row.at)} m ab Start · Abschnitt {row.legIndex + 1} · danach {Math.round(row.step.distance)} m</p>
            <p>Straße: {row.step.name || 'ohne Namen'} · Manöver: <code>{row.step.maneuver?.type} / {row.step.maneuver?.modifier || '—'}</code></p>
            <Button disabled={!canSpeak} onClick={() => speak(index, false)}>Hinweis {index + 1} vorlesen</Button>
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
