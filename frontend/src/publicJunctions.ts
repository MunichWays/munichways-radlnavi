export type Coordinate = [number, number];
export type ReviewStatus = 'confirmed' | 'open' | 'deferred' | 'excluded';
export interface PublicGate { label: string; kind: 'entry' | 'exit'; location: Coordinate; forward: Coordinate; shared?: boolean; }
export interface PublicJunction {
  id: string; number: number; name: string; origin: Coordinate; polygon: Coordinate[]; gates: PublicGate[];
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
export function parsePublicJunctions(value: any): PublicJunctionData {
  if (value?.schemaVersion !== 1 || value.readOnly !== true || !Array.isArray(value.sites)
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
  return sites.filter(s => (status === 'all' || s.status === status)
    && (number !== null ? s.number === number : s.name.toLocaleLowerCase('de').includes(text)))
    .sort((a,b) => a.number - b.number);
}
