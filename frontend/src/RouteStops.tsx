import React, { useEffect, useState } from 'react';
import { Autocomplete, Button, TextField } from '@mui/material';
import { coordinateSuggestion } from './coordinateSuggestion';
import { withCompactPlaceName } from './placeName';
import { MAX_STOPS } from './routeTransfer';

function Stop({ value, onChange, index }: any) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<any[]>(value ? [value] : []);
  useEffect(() => {
    const controller = new AbortController();
    const coordinate = coordinateSuggestion(query);
    setOptions(coordinate ? [coordinate] : value ? [value] : []);
    const timer = setTimeout(async () => {
      if (!query.trim() || coordinate) return;
      try {
        const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&q=${encodeURIComponent(query)}&limit=5&viewbox=11.1,48.5,12,47.8`, { signal: controller.signal });
        if (!response.ok) return;
        const data = await response.json();
        if (!controller.signal.aborted && Array.isArray(data)) setOptions(data.map(withCompactPlaceName));
      } catch (_) { /* Keep coordinate input available after lookup errors. */ }
    }, 700);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, value]);
  const choices = value && !options.some(p => p.lat === value.lat && p.lon === value.lon) ? [value, ...options] : options;
  return <Autocomplete size="small" value={value} options={choices} filterOptions={x => x}
    getOptionLabel={(p: any) => p.display_name || ''} isOptionEqualToValue={(a, b) => a.lat === b.lat && a.lon === b.lon}
    onChange={(_, p) => onChange(p)} onInputChange={(_, text, reason) => { if (reason === 'input') setQuery(text); }}
    noOptionsText="Adresse oder Breitengrad, Längengrad eingeben"
    renderInput={params => <TextField {...params} label={`Zwischenziel ${index + 1}`} />} />;
}

export default function RouteStops({ stops, onChange }: { stops: any[]; onChange: (stops: any[]) => void }) {
  const move = (i: number, delta: number) => {
    const next = [...stops]; [next[i], next[i + delta]] = [next[i + delta], next[i]]; onChange(next);
  };
  return <div className="route-stops">
    {stops.map((stop, i) => <div key={i}>
      <Stop value={stop} index={i} onChange={(value: any) => onChange(stops.map((p, j) => j === i ? value : p))} />
      <div className="stop-actions">
        <Button size="small" sx={{ px: 0, minWidth: 0 }} onClick={() => onChange(stops.filter((_, j) => j !== i))}>Entfernen</Button>
        <span>
          <Button size="small" sx={{ minWidth: 32 }} aria-label={`Zwischenziel ${i + 1} nach oben`} disabled={!i} onClick={() => move(i, -1)}>↑</Button>
          <Button size="small" sx={{ minWidth: 32 }} aria-label={`Zwischenziel ${i + 1} nach unten`} disabled={i === stops.length - 1} onClick={() => move(i, 1)}>↓</Button>
        </span>
      </div>
    </div>)}
    <Button size="small" sx={{ alignSelf: 'flex-start', px: 0 }} disabled={stops.length >= MAX_STOPS} onClick={() => onChange([...stops, null])}>Zwischenziel hinzufügen</Button>
  </div>;
}
