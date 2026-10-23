import { preferEntrances } from './entrancePreference';

const building = {
  place_id: 1, category: 'building', type: 'apartments',
  display_name: '19, Schlossschmidstraße, München', lat: '48.145', lon: '11.52',
  address: { road: 'Schlossschmidstraße', house_number: '19', city: 'München', postcode: '80639' },
};
const entrance = {
  ...building, place_id: 2, category: 'entrance', type: 'yes', lat: '48.146', lon: '11.521',
};

test('Schlossschmidstraße 19 uses entrance coordinates even when the building ranks first', () => {
  const results = preferEntrances([building, entrance]);
  expect(results[0]).toMatchObject({ lat: entrance.lat, lon: entrance.lon,
    display_name: 'Schlossschmidstraße 19, 80639 München' });
  expect(results[1]).toMatchObject({ lat: entrance.lat, lon: entrance.lon });
  expect(building.lat).toBe('48.145');
});

test('buildings without a matching entrance retain their centroid', () => {
  const others = [
    { ...entrance, address: { ...entrance.address, house_number: '19a' } },
    { ...entrance, address: { ...entrance.address, road: 'Andere Straße' } },
    { ...entrance, address: { ...entrance.address, city: 'Freising' } },
    { ...entrance, address: { ...entrance.address, postcode: '80331' } },
    { ...entrance, category: 'place', type: 'house' },
  ];
  for (const other of others) {
    expect(preferEntrances([building, other])[0]).toMatchObject({ lat: building.lat, lon: building.lon });
  }
  expect(preferEntrances([building])[0]).toMatchObject({ lat: building.lat, lon: building.lon });
});

test('embedded entrance data requires the same house number and entrance=yes', () => {
  const node = { type: 'yes', lat: entrance.lat, lon: entrance.lon,
    extratags: { 'addr:housenumber': '19' } };
  expect(preferEntrances([{ ...building, entrances: [node] }])[0]).toMatchObject({ lat: node.lat, lon: node.lon });
  for (const entrances of [null, [], [{ ...node, extratags: {} }],
    [{ ...node, extratags: { 'addr:housenumber': '21' } }], [{ ...node, type: 'exit' }]]) {
    expect(preferEntrances([{ ...building, entrances }])[0]).toMatchObject({ lat: building.lat, lon: building.lon });
  }
});

test('entrance extratags are recognized and incomplete addresses remain unchanged', () => {
  expect(preferEntrances([building, { ...entrance, category: 'place', type: 'house',
    extratags: { entrance: 'yes' } }])[0].lat).toBe(entrance.lat);
  const coordinate = { display_name: '48.1, 11.5', lat: '48.1', lon: '11.5' };
  expect(preferEntrances([coordinate])).toEqual([coordinate]);
  expect(preferEntrances([])).toEqual([]);
});

test('the reported building with house numbers 19,21,23,25 selects the requested entrance', () => {
  const multiAddress = { ...building, address: { ...building.address, house_number: '19,21,23,25' },
    entrances: [
      { type: 'yes', lat: '48.1465283', lon: '11.5171865', extratags: { 'addr:housenumber': '21' } },
      { type: 'yes', lat: '48.1465810', lon: '11.5175767', extratags: { 'addr:housenumber': '19' } },
    ] };
  expect(preferEntrances([multiAddress], 'Schlossschmidstraße 19 München')[0]).toMatchObject({
    lat: '48.1465810', lon: '11.5175767', address: { house_number: '19' },
  });
  expect(preferEntrances([multiAddress], 'Schlossschmidstraße 25')[0]).toMatchObject({ lat: building.lat, lon: building.lon });
  expect(preferEntrances([multiAddress], 'Schlossschmidstraße')[0]).toMatchObject({ lat: building.lat, lon: building.lon });
});
