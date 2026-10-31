import React, { useEffect, useRef, useState } from 'react';
import * as L from 'leaflet';
import { Alert, Button, LinearProgress } from '@mui/material';
import { streetLinks } from './streetDetails';

// leaflet-rotate-map's declarations re-export themselves. Describe the small
// Leaflet API used here, as in PriorityNetworkLayer, without changing that package.
type LayerContainer = { addLayer: (layer: MapLayer) => unknown };
type MapLayer = { addTo: (target: LayerContainer) => unknown };
type DistrictMap = LayerContainer & {
  removeLayer: (layer: MapLayer) => unknown; hasLayer: (layer: MapLayer) => boolean;
  getZoom: () => number; on: (event: string, handler: () => void) => unknown;
  off: (event: string, handler: () => void) => unknown;
  getPane: (name: string) => HTMLElement | undefined; createPane: (name: string) => HTMLElement;
};
type Marker = MapLayer & {
  bindTooltip: (content: HTMLElement, options: object) => Marker;
  bindPopup: (content: HTMLElement, options: object) => Marker;
  closePopup: () => unknown; getElement: () => HTMLElement | undefined;
  on: (event: string, handler: () => void) => Marker;
};
type District = {
  type: 'Feature'; id: string;
  properties: { name: string; bezirk_nummer: string; bezirk_region?: string; description?: string;
    links?: string; label_coordinate: [number, number] };
  geometry: { type: 'MultiPolygon'; coordinates: number[][][][] };
};
const leaflet = L as unknown as {
  svg: (options: object) => MapLayer;
  geoJSON: (data: unknown, options: object) => MapLayer;
  layerGroup: () => MapLayer & LayerContainer;
  divIcon: (options: object) => unknown;
  marker: (coordinate: [number, number], options: object) => Marker;
};

function textElement(tag: string, text: string) {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

function districtPopup(feature: District) {
  const p = feature.properties;
  const content = document.createElement('div');
  content.className = 'district-popup';
  content.append(textElement('h3', `${p.bezirk_nummer} · ${p.name.replace(/^\d+\s+/, '')}`));
  if (p.bezirk_region) content.append(textElement('p', `Region: ${p.bezirk_region.replace(/^LHM-/, '')}`));
  if (p.description) content.append(textElement('p', p.description));
  for (const link of streetLinks(p.links)) {
    const anchor = textElement('a', link.title) as HTMLAnchorElement;
    anchor.href = link.url; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
    content.append(anchor);
  }
  return content;
}

export default function DistrictLayer({ map, visible, streetSelection }: {
  map: DistrictMap | null; visible: boolean; streetSelection?: object | null;
}) {
  const markers = useRef<Marker[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (streetSelection) markers.current.forEach(marker => marker.closePopup());
  }, [streetSelection]);
  useEffect(() => {
    if (!map || !visible) return;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    let disposed = false;
    let boundaries: MapLayer | undefined;
    let renderer: MapLayer | undefined;
    const labels = leaflet.layerGroup();
    const fitLabels = () => {
      if (map.getZoom() >= 12) { if (!map.hasLayer(labels)) labels.addTo(map); }
      else if (map.hasLayer(labels)) map.removeLayer(labels);
    };
    setError(false); setLoading(true);
    async function load() {
      const response = await fetch('/data/stadtbezirke.geojson', { signal: controller.signal });
      if (!response.ok) throw new Error('Stadtbezirke nicht verfügbar');
      const collection = await response.json();
      if (collection?.type !== 'FeatureCollection' || collection.features?.length !== 25) throw new Error('Ungültige Bezirksdaten');
      if (disposed) return;
      const pane = map!.getPane('district-boundaries') || map!.createPane('district-boundaries');
      pane.style.zIndex = '350'; pane.style.pointerEvents = 'none';
      renderer = leaflet.svg({ pane: 'district-boundaries' });
      boundaries = leaflet.geoJSON(collection, { renderer, pane: 'district-boundaries', interactive: false,
        style: { color: '#656D7A', weight: 1.5, opacity: 0.8, dashArray: '5 5', fill: false } });
      boundaries.addTo(map!);
      markers.current = collection.features.map((feature: District) => {
        const p = feature.properties;
        const [lng, lat] = p.label_coordinate;
        const title = `${p.bezirk_nummer} · ${p.name.replace(/^\d+\s+/, '')}`;
        const marker = leaflet.marker([lat, lng], { icon: leaflet.divIcon({ className: 'district-label',
          html: textElement('span', p.bezirk_nummer), iconSize: [38, 24], iconAnchor: [19, 12] }),
          title, keyboard: true, autoPanOnFocus: false, bubblingMouseEvents: true })
          .bindTooltip(textElement('span', title), { direction: 'top', offset: [0, -12] })
          .bindPopup(districtPopup(feature), { autoPan: false, maxWidth: 280 });
        marker.on('add', () => marker.getElement()?.setAttribute('aria-label', `Stadtbezirk ${title}`));
        marker.addTo(labels);
        return marker;
      });
      fitLabels();
      map!.on('zoomend', fitLabels);
    }
    load().catch(() => { if (!disposed) setError(true); }).finally(() => {
      window.clearTimeout(timeout);
      if (!disposed) setLoading(false);
    });
    return () => {
      disposed = true; controller.abort(); window.clearTimeout(timeout);
      map.off('zoomend', fitLabels);
      markers.current.forEach(marker => marker.closePopup()); markers.current = [];
      map.removeLayer(labels);
      if (boundaries) map.removeLayer(boundaries);
      if (renderer) map.removeLayer(renderer);
    };
  }, [map, visible, attempt]);
  if (!visible) return null;
  if (error) return <Alert severity="error" action={<Button color="inherit" onClick={() => setAttempt(v => v + 1)}>Erneut laden</Button>}>Stadtbezirke konnten nicht geladen werden.</Alert>;
  return loading ? <LinearProgress aria-label="Stadtbezirke werden geladen" /> : null;
}
