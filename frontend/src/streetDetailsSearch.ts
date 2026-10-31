import { StreetCandidate, StreetCoordinate, StreetFeature } from './streetDetails';

const CELL = 0.002;
const METERS_PER_DEGREE = Math.PI * 6371000 / 180;
type Entry = { feature: StreetFeature; bbox: number[] };

function lineDistance(coordinates: StreetCoordinate[], lat: number, lon: number): number {
  const scaleX = METERS_PER_DEGREE * Math.cos(lat * Math.PI / 180);
  let nearest = Infinity;
  for (let i = 1; i < coordinates.length; i++) {
    const ax = (coordinates[i - 1][0] - lon) * scaleX;
    const ay = (coordinates[i - 1][1] - lat) * METERS_PER_DEGREE;
    const bx = (coordinates[i][0] - lon) * scaleX;
    const by = (coordinates[i][1] - lat) * METERS_PER_DEGREE;
    const dx = bx - ax, dy = by - ay;
    const t = dx === 0 && dy === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)));
    nearest = Math.min(nearest, Math.hypot(ax + t * dx, ay + t * dy));
  }
  return nearest;
}

/** Uniform geographic grid. Long lines use a bounded overflow list. No rendering geometry is simplified. */
export class StreetSearchIndex {
  private cells = new Map<string, Entry[]>();
  private large: Entry[] = [];
  constructor(collection: unknown, expectedCount: number) {
    const data = collection as { type?: string; features?: StreetFeature[] };
    if (data?.type !== 'FeatureCollection' || !Array.isArray(data.features) || data.features.length !== expectedCount) {
      throw new Error('Ungültige V20-Suchgeometrien.');
    }
    const ids = new Set<string>();
    for (const feature of data.features) {
      const coordinates = feature.geometry?.coordinates;
      if (!/^osm_\d+$/.test(feature.id) || ids.has(feature.id) || feature.geometry?.type !== 'LineString' ||
          !Array.isArray(coordinates) || coordinates.length < 2 || !feature.properties) {
        throw new Error('Ungültige V20-Strecke.');
      }
      ids.add(feature.id);
      const bbox = [180, 90, -180, -90];
      for (const c of coordinates) {
        if (!Array.isArray(c) || !Number.isFinite(c[0]) || !Number.isFinite(c[1]) || Math.abs(c[0]) > 180 || Math.abs(c[1]) > 90) {
          throw new Error('Ungültige V20-Koordinaten.');
        }
        bbox[0] = Math.min(bbox[0], c[0]); bbox[1] = Math.min(bbox[1], c[1]);
        bbox[2] = Math.max(bbox[2], c[0]); bbox[3] = Math.max(bbox[3], c[1]);
      }
      const entry = { feature, bbox };
      const [minX, minY, maxX, maxY] = bbox.map(n => Math.floor(n / CELL));
      if ((maxX - minX + 1) * (maxY - minY + 1) > 256) { this.large.push(entry); continue; }
      for (let x = minX; x <= maxX; x++) for (let y = minY; y <= maxY; y++) {
        const key = `${x},${y}`;
        const bucket = this.cells.get(key) || [];
        bucket.push(entry); this.cells.set(key, bucket);
      }
    }
  }

  search(lat: number, lon: number, radius: number): StreetCandidate[] {
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 85 || Math.abs(lon) > 180 ||
        !Number.isFinite(radius) || radius <= 0 || radius > 20) throw new Error('Ungültiger Suchpunkt.');
    const dy = radius / METERS_PER_DEGREE;
    const dx = dy / Math.cos(lat * Math.PI / 180);
    const entries = new Set(this.large);
    for (let x = Math.floor((lon - dx) / CELL); x <= Math.floor((lon + dx) / CELL); x++) {
      for (let y = Math.floor((lat - dy) / CELL); y <= Math.floor((lat + dy) / CELL); y++) {
        this.cells.get(`${x},${y}`)?.forEach(entry => entries.add(entry));
      }
    }
    const candidates: StreetCandidate[] = [];
    entries.forEach(({ feature, bbox }) => {
      if (bbox[0] > lon + dx || bbox[2] < lon - dx || bbox[1] > lat + dy || bbox[3] < lat - dy) return;
      const distance = lineDistance(feature.geometry.coordinates, lat, lon);
      if (distance <= radius) candidates.push({ ...feature, distance });
    });
    return candidates.sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id));
  }
}
