import { compactPlaceName } from './placeName';
export const GPX_NAMESPACE = 'https://www.munichways.de/gpx/1';
export const MAX_STOPS = 20;
export const MAX_TRANSFER_BYTES = 4 * 1024 * 1024;
export type PlanPoint = { name: string; coordinates: number[] };
export type RouteTransfer = {
  version: 1; name: string; createdAt: string; provider: 'radlnavi';
  variant: 'standard' | 'direct'; plan: PlanPoint[]; response: any;
};
const point = (p: any) => Array.isArray(p) && p.length === 2 &&
  p.every(Number.isFinite) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90;

export function validateTransfer(value: any): RouteTransfer {
  const route = value?.response?.routes?.[0];
  if (value?.version !== 1 || value.provider !== 'radlnavi' ||
      !['standard', 'direct'].includes(value.variant) ||
      typeof value.name !== 'string' || !value.name.trim() || value.name.length > 200 ||
      typeof value.createdAt !== 'string' || !Number.isFinite(Date.parse(value.createdAt)) ||
      !Array.isArray(value.plan) || value.plan.length < 2 || value.plan.length > MAX_STOPS + 2 ||
      !value.plan.every((p: any) => typeof p.name === 'string' && p.name.length <= 500 && point(p.coordinates)) ||
      value.response?.code !== 'Ok' || value.response.routes.length !== 1 ||
      route?.geometry?.type !== 'LineString' || !Array.isArray(route.geometry.coordinates) ||
      route.geometry.coordinates.length < 2 || route.geometry.coordinates.length > 100000 ||
      !route.geometry.coordinates.every(point) ||
      !Number.isFinite(route.distance) || route.distance < 0 ||
      !Number.isFinite(route.duration) || route.duration < 0 ||
      !Array.isArray(route.legs) || route.legs.length !== value.plan.length - 1 ||
      !route.legs.every((leg: any) => Array.isArray(leg.steps) && leg.steps.length >= 2 &&
        leg.steps[0]?.maneuver?.type === 'depart' && leg.steps[leg.steps.length - 1]?.maneuver?.type === 'arrive' &&
        leg.steps.every((step: any) => point(step.maneuver?.location) &&
          typeof step.maneuver.type === 'string' && typeof step.mode === 'string' &&
          Number.isFinite(step.distance) && step.distance >= 0 &&
          Number.isFinite(step.duration) && step.duration >= 0 &&
          step.geometry?.type === 'LineString' && Array.isArray(step.geometry.coordinates) &&
          step.geometry.coordinates.length > 0 && step.geometry.coordinates.every(point)))) {
    throw new Error('Die Datei enthält keine gültige MunichWays-Route mit Navigationsdaten.');
  }
  if (new TextEncoder().encode(JSON.stringify(value)).length > MAX_TRANSFER_BYTES) {
    throw new Error('Die Route ist zu groß (maximal 4 MB).');
  }
  const joined = route.legs.flatMap((leg: any) => leg.steps.filter((step: any) => step.maneuver.type !== 'arrive').flatMap((step: any) => step.geometry.coordinates));
  const distinct = (coords: number[][]) => coords.filter((p, i) => !i || p[0] !== coords[i - 1][0] || p[1] !== coords[i - 1][1]);
  if (JSON.stringify(distinct(joined)) !== JSON.stringify(distinct(route.geometry.coordinates))) {
    throw new Error('Strecke und Navigationsschritte passen nicht zusammen.');
  }
  return value;
}

export function createTransfer(route: any, plan: any[], variant: 'standard' | 'direct', name: string): RouteTransfer {
  // Capture only the selected route. Do not share another calculated alternative.
  return validateTransfer({ version: 1, provider: 'radlnavi', variant, name: name.trim(),
    createdAt: new Date().toISOString(),
    plan: plan.map(p => ({ name: compactPlaceName(p), coordinates: [Number(p.lon), Number(p.lat)] })),
    response: { code: 'Ok', routes: [route.response.routes[0]], waypoints: route.response.waypoints },
  });
}

const xml = (value: string) => value.replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]!));

export function transferGpx(transfer: RouteTransfer): string {
  validateTransfer(transfer);
  const coords = transfer.response.routes[0].geometry.coordinates;
  const result = `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<gpx version="1.1" creator="MunichWays RadlNavi" xmlns="http://www.topografix.com/GPX/1/1" xmlns:mw="${GPX_NAMESPACE}">` +
    `<metadata><name>${xml(transfer.name)}</name></metadata>` +
    `<trk><name>${xml(transfer.name)}</name><trkseg>` +
    coords.map((p: number[]) => `<trkpt lat="${p[1]}" lon="${p[0]}"/>`).join('') +
    `</trkseg></trk><extensions><mw:route>${xml(JSON.stringify(transfer))}</mw:route></extensions></gpx>`;
  if (new TextEncoder().encode(result).length > MAX_TRANSFER_BYTES) throw new Error('GPX-Datei ist zu groß (maximal 4 MB).');
  return result;
}

export function readTransferGpx(source: string): any {
  if (new TextEncoder().encode(source).length > MAX_TRANSFER_BYTES || /<!DOCTYPE|<!ENTITY/i.test(source)) {
    throw new Error('GPX-Datei ist zu groß oder enthält nicht unterstützte XML-Deklarationen.');
  }
  const doc = new DOMParser().parseFromString(source, 'application/xml');
  if (doc.querySelector('parsererror')) throw new Error('Die GPX-Datei ist beschädigt.');
  if (doc.documentElement.localName !== 'gpx' || doc.documentElement.namespaceURI !== 'http://www.topografix.com/GPX/1/1' || doc.documentElement.getAttribute('version') !== '1.1') throw new Error('Bitte eine GPX-1.1-Datei auswählen.');
  if (doc.getElementsByTagNameNS('http://www.topografix.com/GPX/1/1', 'trk').length !== 1 || doc.getElementsByTagNameNS('http://www.topografix.com/GPX/1/1', 'trkseg').length !== 1) throw new Error('Bitte eine Datei mit einem durchgehenden Track auswählen.');
  const extension = doc.getElementsByTagNameNS(GPX_NAMESPACE, 'route');
  const track = Array.from(doc.getElementsByTagNameNS('http://www.topografix.com/GPX/1/1', 'trkpt'))
    .map(p => [p.hasAttribute('lon') ? Number(p.getAttribute('lon')) : NaN, p.hasAttribute('lat') ? Number(p.getAttribute('lat')) : NaN]);
  if (track.length < 2 || track.length > 100000 || !track.every(point)) throw new Error('Die GPX-Datei enthält keine gültige Strecke.');
  if (!extension.length) {
    // Standard GPX waypoints (including Komoot highlights), in file order.
    const stops = Array.from(doc.documentElement.children)
      .filter(p => p.localName === 'wpt' && p.namespaceURI === 'http://www.topografix.com/GPX/1/1')
      .map((p, i) => ({
        name: Array.from(p.children).find(c => c.localName === 'name' && c.namespaceURI === p.namespaceURI)?.textContent?.trim() || `Zwischenziel ${i + 1}`,
        coordinates: [p.hasAttribute('lon') ? Number(p.getAttribute('lon')) : NaN, p.hasAttribute('lat') ? Number(p.getAttribute('lat')) : NaN],
      }));
    if (stops.length > MAX_STOPS || !stops.every(p => point(p.coordinates) && p.name.length <= 500)) {
      throw new Error('GPX-Wegpunkte ungültig oder zu viele Zwischenziele (maximal 20).');
    }
    const gpxChild = (parent: Element | undefined, name: string) => parent && Array.from(parent.children)
      .find(e => e.localName === name && e.namespaceURI === doc.documentElement.namespaceURI);
    const title = gpxChild(gpxChild(doc.documentElement, 'metadata'), 'name')?.textContent?.trim() ||
      gpxChild(gpxChild(doc.documentElement, 'trk'), 'name')?.textContent?.trim() || 'GPX-Track';
    let distance = 0;
    const radians = (d: number) => d * Math.PI / 180;
    for (let i = 1; i < track.length; i++) {
      const [a, b] = [track[i - 1], track[i]];
      const h = Math.sin(radians(b[1] - a[1]) / 2) ** 2 + Math.cos(radians(a[1])) * Math.cos(radians(b[1])) * Math.sin(radians(b[0] - a[0]) / 2) ** 2;
      distance += 6371000 * 2 * Math.asin(Math.sqrt(Math.min(1, h)));
    }
    return { version: 0, name: title, plan: [{ name: 'Start', coordinates: track[0] }, ...stops, { name: 'Ziel', coordinates: track[track.length - 1] }],
      response: { code: 'Ok', routes: [{ geometry: { type: 'LineString', coordinates: track }, distance, duration: 0, legs: [], steps: [] }] } };
  }
  if (extension.length !== 1) throw new Error('Mehrdeutige MunichWays-Routendaten.');
  const transfer = validateTransfer(JSON.parse(extension[0].textContent || ''));
  if (JSON.stringify(track) !== JSON.stringify(transfer.response.routes[0].geometry.coordinates)) {
    throw new Error('GPX-Strecke und Navigationsdaten passen nicht zusammen.');
  }
  return transfer;
}

export function trackGpx(name: string, coordinates: number[][], plan: PlanPoint[] = []) {
  const stops = plan.slice(1, -1).map(p => `<wpt lat="${p.coordinates[1]}" lon="${p.coordinates[0]}"><name>${xml(p.name)}</name></wpt>`).join('');
  const result = `<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="MunichWays" xmlns="http://www.topografix.com/GPX/1/1">${stops}<trk><name>${xml(name)}</name><trkseg>${coordinates.map(p => `<trkpt lat="${p[1]}" lon="${p[0]}"/>`).join('')}</trkseg></trk></gpx>`;
  if (new TextEncoder().encode(result).length > MAX_TRANSFER_BYTES) throw new Error('GPX-Datei ist zu groß (maximal 4 MB).');
  return result;
}

// Preserve readable route names while avoiding path separators and reserved filenames.
export function gpxFilename(name: string): string {
  const clean = name.trim().replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/g, '').replace(/\.gpx$/i, '').replace(/[. ]+$/g, '');
  const safe = !clean || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(clean) ? 'MunichWays-Route' : clean;
  return `${safe}.gpx`;
}
