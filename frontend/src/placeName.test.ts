import { compactPlaceName, withCompactPlaceName } from './placeName';

test('street addresses omit repeated districts and administrative levels', () => {
  expect(compactPlaceName({ name: 'Marienplatz', display_name: 'Full hierarchy',
    address: { pedestrian: 'Marienplatz', neighbourhood: 'Angerviertel',
      quarter: 'Bezirksteil Angerviertel', suburb: 'Altstadt-Lehel',
      city: 'München', postcode: '80331', state: 'Bayern', country: 'Deutschland' }
  })).toBe('Marienplatz, 80331 München');
  expect(compactPlaceName({ name: 'Wotanstraße', address: {
    road: 'Wotanstraße', house_number: '7', city: 'München', postcode: '80639',
    neighbourhood: 'Nymphenburg', suburb: 'Neuhausen-Nymphenburg'
  } })).toBe('Wotanstraße 7, 80639 München');
});

test('POIs retain name, house number and city to distinguish branches', () => {
  const place = { name: 'Café', display_name: 'Long name', lat: '48.1', lon: '11.5',
    address: { road: 'Hauptstraße', house_number: '12a', city: 'Freising', postcode: '85354' }
  };
  expect(withCompactPlaceName(place)).toEqual({ ...place,
    display_name: 'Café, Hauptstraße 12a, 85354 Freising' });
  expect(place.display_name).toBe('Long name');
});

test('missing structured address preserves custom and coordinate names', () => {
  expect(compactPlaceName({ display_name: '48.1, 11.5' })).toBe('48.1, 11.5');
  expect(compactPlaceName({ display_name: 'Mein Treffpunkt, am Park' })).toBe('Mein Treffpunkt, am Park');
  expect(compactPlaceName({ display_name: 'Treffpunkt', address: {} })).toBe('Treffpunkt');
  expect(compactPlaceName({ name: 'Park', address: { village: 'Eching' } })).toBe('Park, Eching');
});

test('an unnamed house does not repeat its house number as a POI name', () => {
  expect(compactPlaceName({ display_name: '7, Wotanstraße, Nymphenburg, München, Bayern, Deutschland',
    address: { road: 'Wotanstraße', house_number: '7', city: 'München', postcode: '80639' }
  })).toBe('Wotanstraße 7, 80639 München');
});
