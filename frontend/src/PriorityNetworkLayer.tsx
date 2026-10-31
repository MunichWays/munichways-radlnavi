import React, { useEffect, useState } from 'react';
import * as L from 'leaflet';
import { Alert, Button, LinearProgress } from '@mui/material';
import { StreetFeature, streetRating } from './streetDetails';

// The bundled leaflet-rotate-map declarations re-export themselves instead of
// Leaflet's types. Keep the small runtime contract explicit here.
type MapLayer = { addTo: (map: NetworkMap) => unknown };
type NetworkMap = { removeLayer: (layer: MapLayer) => unknown };
const leaflet = L as unknown as {
  canvas: () => MapLayer;
  geoJSON: (data: unknown, options: { renderer: unknown; interactive: boolean;
    style: (feature: StreetFeature) => { color: string; weight: number; dashArray?: string } }) => MapLayer;
};

export default function PriorityNetworkLayer({ map, visible }: { map: NetworkMap | null; visible: boolean }) {
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!map || !visible) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 45000);
    let disposed = false;
    let layer: MapLayer | undefined;
    let renderer: MapLayer | undefined;
    setError(false);
    setLoading(true);
    async function load() {
      const manifestResponse = await fetch('/street-details/manifest.json', { cache: 'no-cache', signal: controller.signal });
      if (!manifestResponse.ok) throw new Error('Manifest nicht verfügbar');
      const manifest = await manifestResponse.json();
      if (!/^[a-f0-9]{64}$/.test(manifest.snapshot)) throw new Error('Ungültiger Datenstand');
      const response = await fetch(`/street-details/${manifest.snapshot}/priority-network-v1.json`, { signal: controller.signal });
      if (!response.ok) throw new Error('RadVorrang-Netz nicht verfügbar');
      const collection = await response.json();
      if (disposed) return;
      renderer = leaflet.canvas();
      layer = leaflet.geoJSON(collection, { renderer, interactive: false,
        style: feature => {
          const rating = streetRating(feature.properties);
          return { color: rating.color, weight: 1.5,
            dashArray: ['#F44336', '#000000'].includes(rating.color) ? '6 5' : undefined };
        } });
      layer.addTo(map!);
    }
    load().catch(() => { if (!disposed) setError(true); }).finally(() => {
      window.clearTimeout(timeout);
      if (!disposed) setLoading(false);
    });
    return () => {
      disposed = true;
      controller.abort();
      window.clearTimeout(timeout);
      if (layer) map.removeLayer(layer);
      if (renderer) map.removeLayer(renderer);
    };
  }, [map, visible, attempt]);
  if (!visible) return null;
  if (error) return <Alert severity="error" action={<Button color="inherit" onClick={() => setAttempt(value => value + 1)}>Erneut laden</Button>}>RadVorrang-Netz konnte nicht geladen werden.</Alert>;
  return loading ? <LinearProgress aria-label="RadVorrang-Netz wird geladen" /> : null;
}
