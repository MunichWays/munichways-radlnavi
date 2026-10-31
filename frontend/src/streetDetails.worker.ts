import { StreetSearchIndex } from './streetDetailsSearch';
import { StreetManifest, streetSearchRadius } from './streetDetails';

export function validateStreetManifest(value: unknown): StreetManifest {
  const m = value as StreetManifest;
  if (!m || m.schemaVersion !== 1 || !/^[a-f0-9]{64}$/.test(m.snapshot) ||
      !Number.isInteger(m.featureCount) || m.featureCount < 1 || !Number.isFinite(Date.parse(m.retrievedAt)) ||
      !Array.isArray(m.bbox) || m.bbox.length !== 4 || !m.bbox.every(Number.isFinite) ||
      m.bbox[0] > m.bbox[2] || m.bbox[1] > m.bbox[3]) throw new Error('Ungültiger V20-Datenstand.');
  return m;
}

async function readJson(url: string, revalidate = false) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(url, { signal: controller.signal, cache: revalidate ? 'no-cache' : 'default' });
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
      throw new Error('V20-Streckendaten sind derzeit nicht verfügbar.');
    }
    return await response.json();
  } finally { clearTimeout(timeout); }
}

let initialized: Promise<{ manifest: StreetManifest; index: StreetSearchIndex }> | undefined;
function initialize() {
  if (!initialized) {
    initialized = (async () => {
      const manifest = validateStreetManifest(await readJson('/street-details/manifest.json', true));
      const geometry = await readJson(`/street-details/${manifest.snapshot}/geometry.json`);
      return { manifest, index: new StreetSearchIndex(geometry, manifest.featureCount) };
    })().catch(error => { initialized = undefined; throw error; });
  }
  return initialized;
}

// The worker owns both JSON parsing and the index. Only nearby candidates cross back to React.
globalThis.onmessage = async (event: MessageEvent<{ id: number; lat: number; lng: number; zoom: number }>) => {
  const { id, lat, lng, zoom } = event.data;
  try {
    if (!Number.isFinite(zoom) || zoom < 14 || zoom > 24) throw new Error('Für Streckendetails bitte hineinzoomen.');
    const { manifest, index } = await initialize();
    const candidates = index.search(lat, lng, streetSearchRadius(lat, zoom));
    globalThis.postMessage({ id, result: { manifest, candidates } });
  } catch (error) {
    globalThis.postMessage({ id, error: error instanceof Error && error.name !== 'AbortError'
      ? error.message : 'Die Streckensuche hat zu lange gedauert. Bitte erneut versuchen.' });
  }
};
