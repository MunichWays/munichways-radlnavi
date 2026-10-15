import { TextEncoder, TextDecoder } from 'util';
import { gpxFilename, createTransfer, readTransferGpx, transferGpx, trackGpx, validateTransfer } from './routeTransfer';
import { readFileSync } from 'fs';
import { normalizeRouteResponse } from './routingRequests';
import fixture from './fixtures/route-transfer.json';
Object.assign(globalThis, { TextEncoder, TextDecoder });

test('real Komoot discovery tour retains all eight named waypoints and the exact track on export', () => {
  const source = readFileSync('src/fixtures/komoot-discovery.gpx', 'utf8');
  const transfer = readTransferGpx(source);
  expect(transfer.version).toBe(0);
  expect(transfer.plan).toHaveLength(10);
  expect(transfer.plan[1]).toEqual({ name: 'Amsterdamer Straße (Geheimtipp)', coordinates: [11.602076, 48.169055] });
  expect(transfer.plan[2].name).toBe('Schwabinger See');
  expect(transfer.plan[8].name).toBe('Nymphenburger Kanal');
  const restored = readTransferGpx(trackGpx(transfer.name, transfer.response.routes[0].geometry.coordinates, transfer.plan));
  expect(restored).toEqual(transfer);
});

test('standard waypoints reject invalid coordinates and excess stops; missing names have a fallback', () => {
  const prefix = '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">';
  const track = '<trk><trkseg><trkpt lat="48" lon="11"/><trkpt lat="49" lon="12"/></trkseg></trk></gpx>';
  const stop = '<wpt lat="48.5" lon="11.5"><name>A &amp; B</name></wpt>';
  const transfer = readTransferGpx(prefix + stop + track);
  expect(readTransferGpx(trackGpx(transfer.name, transfer.response.routes[0].geometry.coordinates, transfer.plan)).plan[1].name).toBe('A & B');
  expect(() => readTransferGpx(prefix + stop.replace('48.5', 'NaN') + track)).toThrow();
  expect(() => readTransferGpx(prefix + stop.repeat(21) + track)).toThrow(/maximal 20/);
  expect(readTransferGpx(prefix + '<wpt lat="48.5" lon="11.5"/>' + track).plan[1].name).toBe('Zwischenziel 1');
  expect(readTransferGpx(prefix + track).plan).toHaveLength(2);
});

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
