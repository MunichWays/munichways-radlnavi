import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Paper, Portal } from '@mui/material';

export default function FloatingMapWindow({ open, title, onClose, children }: {
  open: boolean; title: string; onClose: () => void; children: React.ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const header = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const [position, setPosition] = useState({ x: document.documentElement.clientWidth > 960 ? 380 : 8, y: 16 });
  const [minimized, setMinimized] = useState(false);
  const moveTo = useCallback((x: number, y: number) => {
    const bounds = panel.current?.getBoundingClientRect();
    setPosition({
      x: Math.max(8, Math.min(x, document.documentElement.clientWidth - (bounds?.width || 300) - 8)),
      y: Math.max(8, Math.min(y, document.documentElement.clientHeight - (bounds?.height || 100) - 8)),
    });
  }, []);
  useEffect(() => {
    if (!open) return;
    setMinimized(false);
    const previous = document.activeElement as HTMLElement | null;
    // Portal refs are attached by the time the scheduled focus runs.
    const timer = window.setTimeout(() => header.current?.focus(), 0);
    return () => {
      clearTimeout(timer);
      drag.current = null;
      if (previous?.isConnected && previous.getClientRects().length) previous.focus();
      else (document.querySelector('.leaflet-container') as HTMLElement | null)?.focus();
    };
  }, [open]);
  useEffect(() => {
    const fit = () => setPosition(p => ({
      x: Math.max(8, Math.min(p.x, document.documentElement.clientWidth - 308)),
      y: Math.max(8, Math.min(p.y, document.documentElement.clientHeight - 108)),
    }));
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  if (!open) return null;
  return <Portal><Paper ref={panel} role="dialog" aria-modal="false" aria-labelledby="street-details-title"
    className="street-details-dialog" elevation={10}
    onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}
    style={{ position: 'fixed', zIndex: 1300, left: position.x, top: position.y,
      width: 560, height: minimized ? 'auto' : 620, minWidth: 'min(300px, calc(100vw - 16px))',
      minHeight: minimized ? undefined : 180, maxWidth: `calc(100vw - ${position.x + 8}px)`,
      maxHeight: `calc(100dvh - ${position.y + 8}px)`, resize: minimized ? 'none' : 'both',
      overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
    <div className="street-window-header">
      <div ref={header} id="street-details-title" tabIndex={0}
        aria-label={`${title} verschieben, auch mit Pfeiltasten`} className="street-window-title"
        onPointerDown={event => {
          if (event.button !== 0) return;
          drag.current = { x: event.clientX, y: event.clientY, left: position.x, top: position.y };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={event => {
          if (drag.current) moveTo(drag.current.left + event.clientX - drag.current.x,
            drag.current.top + event.clientY - drag.current.y);
        }}
        onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}
        onLostPointerCapture={() => { drag.current = null; }}
        onKeyDown={event => {
          const delta: Record<string, number[]> = { ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20] };
          if (delta[event.key]) { event.preventDefault(); moveTo(position.x + delta[event.key][0], position.y + delta[event.key][1]); }
        }}>{title}</div>
      <Button size="small" onClick={() => setMinimized(v => !v)}>{minimized ? 'Öffnen' : 'Verkleinern'}</Button>
      <Button size="small" onClick={onClose}>Schließen</Button>
    </div>
    <div hidden={minimized} className="street-window-content">{children}</div>
  </Paper></Portal>;
}
