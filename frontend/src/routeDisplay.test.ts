import { routeDisplaySections, withoutPushing } from './routeDisplay';

const a: [number, number] = [11, 48];
const b: [number, number] = [11.001, 48];
const c: [number, number] = [11.002, 48];
const d: [number, number] = [11.003, 48];
const step = (points: number[][], mode: string) => ({ mode,
  geometry: { type: 'LineString', coordinates: points }, maneuver: { type: 'depart' } });
const route = (steps: any[], points = [a, b, c, d]) => ({
  geometry: { type: 'LineString', coordinates: points }, steps });

test('keeps initial and final pushing sections with the cycling route between them', () => {
  const sections = routeDisplaySections(route([
    step([a, b], 'pushing bike'), step([b, c], 'cycling'), step([c, d], 'pushing bike'),
  ]));
  expect(sections).toEqual([
    { pushing: true, coordinates: [a, b] },
    { pushing: false, coordinates: [b, c] },
    { pushing: true, coordinates: [c, d] },
  ]);
  expect(withoutPushing([a, b, c, d], sections)).toEqual([[b, c]]);
});

test('an entirely pushed journey remains visible without a solid line beneath it', () => {
  const sections = routeDisplaySections(route([step([a, b, c, d], 'pushing bike')]));
  expect(sections).toEqual([{ pushing: true, coordinates: [a, b, c, d] }]);
  expect(withoutPushing([a, b, c, d], sections)).toEqual([]);
});

test('preserves ordinary cycling routes and their rating paths', () => {
  const sections = routeDisplaySections(route([step([a, b, c, d], 'cycling')]));
  expect(sections).toEqual([{ pushing: false, coordinates: [a, b, c, d] }]);
  expect(withoutPushing([a, b, c, d], sections)).toEqual([[a, b, c, d]]);
});

test('matches ordered geometry across duplicate points and leg boundaries', () => {
  const result = routeDisplaySections({ geometry: { type: 'LineString', coordinates: [a, a, b, c] },
    legs: [{ steps: [step([a, a, b], 'pushing bike')] }, { steps: [step([b, c], 'cycling')] }] });
  expect(result).toEqual([{ pushing: true, coordinates: [a, b] }, { pushing: false, coordinates: [b, c] }]);
});

test('incomplete optional step geometry preserves the complete route', () => {
  expect(routeDisplaySections(route([step([b, c], 'pushing bike')]))).toEqual([
    { pushing: false, coordinates: [a, b, c, d] },
  ]);
});

test('clips partial rating edges on a walking way without suppressing the next cycling edge', () => {
  const sections = [{ pushing: true, coordinates: [a, b] }, { pushing: false, coordinates: [b, c] }];
  expect(withoutPushing([[11.0001, 48], b, c], sections)).toEqual([[b, c]]);
});
