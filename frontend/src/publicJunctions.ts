export type Coordinate = [number, number];
export type ReviewStatus = 'confirmed' | 'open' | 'deferred' | 'excluded';
export interface PublicGate { label: string; kind: 'entry' | 'exit'; location: Coordinate; forward: Coordinate; shared?: boolean; }
export interface PublicJunction {
  id: string; number: number; name: string; city?: string; district?: {id: string; name: string} | null; origin: Coordinate; polygon: Coordinate[]; gates: PublicGate[];
  status: ReviewStatus; geometryRevision: number; note: string; deferredUntil?: string | null;
  technical: string; deploymentStatus: string; deployment: string; backendVersion?: string;
  branchMovements: number; liveMovements: number;
  movements: {entryLabel: string; exitLabel: string; kind: string; enabled: boolean; reason?: string}[];
  rechecks: {entry?: string; exit?: string; date?: string; reason?: string}[];
}
export interface PublicJunctionData { schemaVersion: number; readOnly: boolean; projectName: string; publishedAt: string; sites: PublicJunction[]; }
export const reviewLabels: Record<ReviewStatus, string> = {
  confirmed: 'Bestätigt', open: 'Offen', deferred: 'Zurückgestellt', excluded: 'Ausgeschlossen',
};
export const reviewColors: Record<ReviewStatus, string> = {
  confirmed: '#21825c', open: '#a75a00', deferred: '#896400', excluded: '#77717e',
};
/** Public display status: derived from the human decision plus technical and live evidence. */
export type ViewStatus = ReviewStatus | 'checked' | 'live';
export const viewLabels: Record<ViewStatus, string> = {
  live: 'Live', checked: 'Technisch geprüft', confirmed: 'Bestätigt', open: 'Offen', deferred: 'Zurückgestellt', excluded: 'Ausgeschlossen',
};
export const viewColors: Record<ViewStatus, string> = {
  ...reviewColors, checked: '#1d5f8c', live: '#b0127a',
};
export function viewStatus(site: Pick<PublicJunction, 'status' | 'technical' | 'deploymentStatus'>): ViewStatus {
  if (site.status !== 'confirmed') return site.status;
  if (site.deploymentStatus === 'live') return 'live';
  return site.technical && site.technical !== 'not-run' ? 'checked' : 'confirmed';
}
export function parsePublicJunctions(value: any): PublicJunctionData {
  if (![1, 2].includes(value?.schemaVersion) || value.readOnly !== true || !Array.isArray(value.sites)
    || typeof value.projectName !== 'string' || !Number.isFinite(Date.parse(value.publishedAt))
    || value.sites.some((s: any) => !Number.isInteger(s.number) || !reviewLabels[s.status as ReviewStatus]
      || !Array.isArray(s.origin) || s.origin.length !== 2 || !s.origin.every(Number.isFinite)
      || !Array.isArray(s.gates) || !Array.isArray(s.polygon))) {
    throw new Error('Der veröffentlichte Kartenstand ist ungültig. Bitte später erneut laden.');
  }
  return value;
}
export function filterPublicJunctions(sites: PublicJunction[], query: string, status: string): PublicJunction[] {
  const text = query.trim().toLocaleLowerCase('de');
  const number = /^k?\d+$/.test(text) ? Number(text.replace(/^k/, '')) : null;
  return sites.filter(s => (status === 'all' || viewStatus(s) === status)
    && (number !== null ? s.number === number : s.name.toLocaleLowerCase('de').includes(text)))
    .sort((a,b) => a.number - b.number);
}
export interface JunctionGroup { city: string; districts: {id: string; title: string; sites: PublicJunction[]}[]; count: number; }
const NO_DISTRICT = 'Ohne Stadtbezirk';
/** City, then district (BA01 … BA25, unassigned last); sites keep their number order. */
export function groupPublicJunctions(sites: PublicJunction[]): JunctionGroup[] {
  const cities = new Map<string, Map<string, {id: string; title: string; sites: PublicJunction[]}>>();
  for (const site of sites) {
    const city = site.city || 'München';
    const id = site.district?.id || NO_DISTRICT;
    const title = site.district ? `${site.district.id} · ${site.district.name}` : NO_DISTRICT;
    if (!cities.has(city)) cities.set(city, new Map());
    const districts = cities.get(city)!;
    if (!districts.has(id)) districts.set(id, {id, title, sites: []});
    districts.get(id)!.sites.push(site);
  }
  const order = (id: string) => id === NO_DISTRICT ? 'ZZ' : id;
  return [...cities.entries()]
    .sort(([a], [b]) => (a === 'München' ? -1 : b === 'München' ? 1 : a.localeCompare(b, 'de')))
    .map(([city, districts]) => {
      const list = [...districts.values()].sort((a, b) => order(a.id).localeCompare(order(b.id), 'de'));
      return {city, districts: list, count: list.reduce((n, d) => n + d.sites.length, 0)};
    });
}
