import { validateStreetManifest } from './streetDetails.worker';
import { streetSourceLabel } from './streetDetails';

const manifest = { schemaVersion: 1 as const, snapshot: 'a'.repeat(64),
  sourceUrl: 'https://example.org/V20.geojson', sourceCreatedAt: '2026-11-01',
  retrievedAt: '2026-11-02T07:00:00Z', featureCount: 1, bbox: [11, 48, 12, 49] };

test('existing source dates remain readable; missing HTTP metadata is shown honestly', () => {
  expect(streetSourceLabel(validateStreetManifest(manifest))).toContain('01.11.2026');
  const unknown = validateStreetManifest({ ...manifest, sourceCreatedAt: null });
  expect(streetSourceLabel(unknown)).toBe('Datenstand unbekannt, Quelle V20.geojson.');
  for (const sourceCreatedAt of ['invalid', '2026-02-31', undefined]) {
    expect(() => validateStreetManifest({...manifest, sourceCreatedAt})).toThrow();
  }
});
