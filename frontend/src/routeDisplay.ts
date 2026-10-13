type Coordinate = [number, number];
export type RouteSection = { coordinates: Coordinate[]; pushing: boolean };

const samePoint = (a: Coordinate, b: Coordinate) => a[0] === b[0] && a[1] === b[1];
const pushingMode = (mode: string) => ['pushing bike', 'walking', 'pushing'].includes(mode);
const distinct = (points: Coordinate[]) => points.filter((p, i) => !i || !samePoint(p, points[i - 1]));

/** Match ordered step geometry, including initial/final and wholly pushed routes. */
export function routeDisplaySections(route: any): RouteSection[] {
  const coordinates = distinct(route?.geometry?.coordinates || []);
  if (coordinates.length < 2) return [];
  const fallback = [{ coordinates, pushing: false }];
  const steps = route.steps || route.legs?.flatMap((leg: any) => leg.steps || []) || [];
  const sections: RouteSection[] = [];
  let cursor = 0;
  for (const step of steps) {
    if (step.maneuver?.type === 'arrive') continue;
    if (step.geometry?.type !== 'LineString') return fallback;
    const points = distinct(step.geometry.coordinates);
    if (!points.length || !samePoint(points[0], coordinates[cursor])) return fallback;
    for (const point of points.slice(1)) {
      if (++cursor >= coordinates.length || !samePoint(point, coordinates[cursor])) return fallback;
    }
    if (points.length < 2) continue;
    const pushing = pushingMode(step.mode);
    const last = sections[sections.length - 1];
    if (last?.pushing === pushing) last.coordinates.push(...points.slice(1));
    else sections.push({ coordinates: points, pushing });
  }
  return cursor === coordinates.length - 1 ? sections : fallback;
}

/** Rating/highlight lines must not fill the gaps of a pushing section. */
export function withoutPushing(path: Coordinate[], sections: RouteSection[]): Coordinate[][] {
  const walkingEdges = sections.filter(section => section.pushing)
    .flatMap(section => section.coordinates.slice(1).map((b, i) => [section.coordinates[i], b]));
  if (!walkingEdges.length) return [path];
  const result: Coordinate[][] = [];
  let current: Coordinate[] = [];
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1], b = path[i];
    const x = (a[0] + b[0]) / 2, y = (a[1] + b[1]) / 2;
    const walking = walkingEdges.some(([p, q]) => {
      const scale = Math.cos(y * Math.PI / 180);
      const dx = (q[0] - p[0]) * scale, dy = q[1] - p[1];
      const px = (x - p[0]) * scale, py = y - p[1];
      const t = dx || dy ? Math.max(0, Math.min(1, (px * dx + py * dy) / (dx * dx + dy * dy))) : 0;
      return Math.hypot(px - t * dx, py - t * dy) < 0.000001;
    });
    if (walking) {
      if (current.length > 1) result.push(current);
      current = [];
    } else {
      if (!current.length) current.push(a);
      current.push(b);
    }
  }
  if (current.length > 1) result.push(current);
  return result;
}
