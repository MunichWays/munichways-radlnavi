import { safeStreetUrl, streetDetailGroup, streetLinks, streetName, streetRating, streetSearchRadius, streetText } from './streetDetails';
import { StreetSearchIndex } from './streetDetailsSearch';

test('normalizes missing text without losing zero and falls back to MunichWays name', () => {
  expect(streetText(' - ')).toBeUndefined();
  expect(streetText(null)).toBeUndefined();
  expect(streetText(0)).toBe('0');
  expect(streetName({ osm_name: ' ', munichways_name: 'Name' })).toBe('Name');
  expect(streetName({})).toBe('Streckenabschnitt');
});
test.each([['3', 'Hervorragend'], ['2', 'Gemütlich'], ['1', 'Durchschnittlich'], ['0', 'Keine Aussage'],
  ['-1', 'Stressig'], ['-2', 'Sehr stressig'], ['-3', 'Unter allen Umständen vermeiden']])('OSM class %s overrides exported rating', (value, label) => {
  expect(streetRating({ osm_class_bicycle: value, color: 'red' }).label).toBe(label);
});
test('unknown/missing classes use known exported colors or an explicit unrated label', () => {
  expect(streetRating({ color: 'green' }).label).toBe('Grün');
  expect(streetRating({ osm_class_bicycle: 'invalid', color: 'unknown' }).label).toBe('Nicht bewertet');
});
test('extracts text and deduplicated safe links from HTML without accepting executable or relative URLs', () => {
  const links = streetLinks('<p><a href="https://example.org/a" onclick="bad()"><b>Mehr</b></a></p>' +
    '<a href="javascript:alert(1)">Bad</a><a href="data:text/html,x">Bad</a><a href="/relative">Bad</a>' +
    '<a href="https://example.org/a">Duplicate</a><a href="https://example.org/b">Zwei</a>');
  expect(links).toEqual([{ title: 'Mehr', url: 'https://example.org/a' }, { title: 'Zwei', url: 'https://example.org/b' }]);
  expect(streetLinks('https://www.mapillary.com/app/?pKey=1, https://example.org')).toHaveLength(2);
  expect(safeStreetUrl('https://user:secret@example.org')).toBeUndefined();
  expect(safeStreetUrl('//example.org')).toBeUndefined();
  expect(safeStreetUrl('javascript:https://example.org')).toBeUndefined();
});
test('uses numeric OSM IDs for group paths, rejecting traversal', () => {
  expect(streetDetailGroup('osm_123')).toBe('23');
  expect(streetDetailGroup('osm_1')).toBe('01');
  expect(() => streetDetailGroup('osm_../x')).toThrow();
});

const line = (id: number, lat = 48.1) => ({ type: 'Feature', id: `osm_${id}`, properties: { munichways_id: 'shared' },
  geometry: { type: 'LineString', coordinates: [[11.5, lat], [11.502, lat]] } });
const collection = (features: any[]) => ({ type: 'FeatureCollection', features });

test('finds the middle of a line, selects parallel ways separately and applies the meter radius', () => {
  const index = new StreetSearchIndex(collection([line(1), line(2, 48.1001), line(3, 48.101)]), 3);
  const results = index.search(48.1, 11.501, 20);
  expect(results.map(c => c.id)).toEqual(['osm_1', 'osm_2']);
  expect(results[0].distance).toBeLessThan(0.01);
  expect(index.search(48.1, 11.501, 5).map(c => c.id)).toEqual(['osm_1']);
  expect(index.search(11.501, 48.1, 20)).toEqual([]);
  expect(index.search(48.3, 11.5, 20)).toEqual([]);
});
test('bbox overlap alone is not a hit and degenerate segments do not break distance calculation', () => {
  const diagonal = { ...line(1), geometry: { type: 'LineString', coordinates: [[11.5, 48.1], [11.502, 48.102]] } };
  const pointLine = { ...line(2), geometry: { type: 'LineString', coordinates: [[11.501, 48.1], [11.501, 48.1]] } };
  const index = new StreetSearchIndex(collection([diagonal, pointLine]), 2);
  expect(index.search(48.1, 11.501, 5).map(c => c.id)).toEqual(['osm_2']);
});
test('rejects malformed collections, duplicate IDs and disconnected geometry formats', () => {
  expect(() => new StreetSearchIndex(collection([line(1)]), 2)).toThrow();
  expect(() => new StreetSearchIndex(collection([line(1), line(1)]), 2)).toThrow();
  expect(() => new StreetSearchIndex(collection([{ ...line(1), geometry: { type: 'MultiLineString', coordinates: [] } }]), 1)).toThrow();
});
test('search tolerance shrinks with zoom and never exceeds twenty meters', () => {
  expect(streetSearchRadius(48.1, 14)).toBe(20);
  expect(streetSearchRadius(48.1, 19)).toBeLessThan(2);
});
