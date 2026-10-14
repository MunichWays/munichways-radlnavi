import { TextEncoder, TextDecoder } from 'util';
import { gpxFilename, createTransfer, readTransferGpx, transferGpx, validateTransfer } from './routeTransfer';
import { normalizeRouteResponse } from './routingRequests';
import fixture from './fixtures/route-transfer.json';
Object.assign(globalThis, { TextEncoder, TextDecoder });

test('all legs and exact names survive web GPX roundtrip using the shared app fixture', () => {
  const route = normalizeRouteResponse(fixture.response);
  expect(route.steps).toHaveLength(4);
  expect(route.steps.filter((s: any) => s.maneuver.type === 'arrive')).toHaveLength(1);
  expect(route.analysis_legs).toHaveLength(3);
  expect(route.analysis_legs[1].start).toEqual([11.55, 48.16]);
  const transfer = createTransfer(route, fixture.plan.map(p => ({ display_name: p.name, lon: p.coordinates[0], lat: p.coordinates[1] })), 'standard', fixture.name);
  const restored = readTransferGpx(transferGpx(transfer));
  expect(restored).toEqual(transfer);
  expect(restored.response.routes[0].geometry.coordinates).toEqual(fixture.response.routes[0].geometry.coordinates);
});
test('mixed or unsupported navigation snapshots and external entities are rejected', () => {
  expect(() => validateTransfer({ ...fixture, version: 2 })).toThrow();
  expect(() => readTransferGpx('<!DOCTYPE gpx>' + transferGpx(fixture as any))).toThrow();
  const xml = transferGpx(fixture as any).replace('lat="48.15"', 'lat="49.15"');
  expect(() => readTransferGpx(xml)).toThrow(/passen nicht/);
});

test('export filenames preserve route names and neutralize paths', () => {
  expect(gpxFilename('GreenCity-über-Hackerbrücke')).toBe('GreenCity-über-Hackerbrücke.gpx');
  expect(gpxFilename('Tour.gpx')).toBe('Tour.gpx');
  expect(gpxFilename('../Tour: A/B?')).toBe('.._Tour_ A_B_.gpx');
  expect(gpxFilename('NUL')).toBe('MunichWays-Route.gpx');
});

test('saved GPX names omit districts while all coordinates and routing stay exact', () => {
  const plan = fixture.plan.map(p => ({ display_name: p.name, name: p.name,
    lon: p.coordinates[0], lat: p.coordinates[1], address: {
      road: 'Wotanstraße', house_number: '7', city: 'München', postcode: '80639',
      quarter: 'Bezirksteil Nymphenburg', suburb: 'Neuhausen-Nymphenburg'
    } }));
  const transfer = createTransfer(normalizeRouteResponse(fixture.response), plan, 'standard', fixture.name);
  const restored = readTransferGpx(transferGpx(transfer));
  expect(restored.plan[0].name).toBe(`${fixture.plan[0].name}, Wotanstraße 7, 80639 München`);
  expect(restored.plan.map((p: { coordinates: number[] }) => p.coordinates)).toEqual(fixture.plan.map(p => p.coordinates));
  expect(restored.response).toEqual(transfer.response);
  expect(plan[0].display_name).toBe(fixture.plan[0].name);
});
