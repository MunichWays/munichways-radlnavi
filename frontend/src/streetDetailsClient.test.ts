import { StreetDetailsClient } from './streetDetailsClient';
import { createStreetDetailsWorker } from './createStreetDetailsWorker';
import { StreetManifest } from './streetDetails';
jest.mock('./createStreetDetailsWorker', () => ({ createStreetDetailsWorker: jest.fn() }));

const manifest: StreetManifest = { schemaVersion: 1, snapshot: 'a'.repeat(64), retrievedAt: '2026-10-31T10:00:00Z',
  sourceUrl: 'https://example.org', sourceCreatedAt: '2026-10-26', featureCount: 1, bbox: [11, 48, 12, 49] };
const response = (data: unknown, ok = true, contentType = 'application/json') => ({ ok,
  headers: new Headers({ 'content-type': contentType }), json: async () => data } as Response);
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; jest.clearAllMocks(); });

test('reuses one worker, ignores aborted replies, and can create a fresh worker after failure', async () => {
  const worker: any = { postMessage: jest.fn(), terminate: jest.fn() };
  (createStreetDetailsWorker as jest.Mock).mockReturnValue(worker);
  const client = new StreetDetailsClient();
  const first = new AbortController();
  const firstResult = client.search(48.1, 11.5, 16, first.signal).catch(error => error.name);
  const secondResult = client.search(48.1, 11.6, 16, new AbortController().signal, 'priority');
  expect(worker.postMessage).toHaveBeenNthCalledWith(1, expect.objectContaining({ mode: 'all' }));
  expect(worker.postMessage).toHaveBeenNthCalledWith(2, expect.objectContaining({ mode: 'priority' }));
  first.abort();
  worker.onmessage({ data: { id: 1, result: { manifest, candidates: ['old'] } } });
  worker.onmessage({ data: { id: 2, result: { manifest, candidates: [] } } });
  expect(await firstResult).toBe('AbortError');
  expect((await secondResult).candidates).toEqual([]);
  expect(createStreetDetailsWorker).toHaveBeenCalledTimes(1);
  const failed = client.search(48, 11, 16, new AbortController().signal);
  worker.onerror();
  await expect(failed).rejects.toThrow('gestartet');
  const next = client.search(48, 11, 16, new AbortController().signal).catch(error => error.name);
  expect(createStreetDetailsWorker).toHaveBeenCalledTimes(2);
  client.dispose();
  expect(await next).toBe('AbortError');
});
test('caches detail groups by snapshot and verifies the selected way ID', async () => {
  global.fetch = jest.fn().mockResolvedValue(response({ osm_123: { osm_id: '123', osm_name: 'Weg' } }));
  const client = new StreetDetailsClient();
  const signal = new AbortController().signal;
  expect((await client.details(manifest, 'osm_123', signal)).osm_name).toBe('Weg');
  await client.details(manifest, 'osm_123', signal);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  await client.details({ ...manifest, snapshot: 'b'.repeat(64) }, 'osm_123', signal);
  expect(global.fetch).toHaveBeenCalledTimes(2);
  await expect(client.details(manifest, 'osm_223', signal)).rejects.toThrow('gültige Details');
  client.dispose();
});
test('rejects SPA HTML, HTTP errors and mismatched detail IDs, allowing retry', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce(response({}, true, 'text/html'))
    .mockResolvedValueOnce(response({}, false)).mockResolvedValueOnce(response({ osm_123: { osm_id: '999' } }));
  const client = new StreetDetailsClient();
  const signal = new AbortController().signal;
  await expect(client.details(manifest, 'osm_123', signal)).rejects.toThrow('nicht verfügbar');
  await expect(client.details(manifest, 'osm_123', signal)).rejects.toThrow('nicht verfügbar');
  await expect(client.details(manifest, 'osm_123', signal)).rejects.toThrow('gültige Details');
  (global.fetch as jest.Mock).mockResolvedValueOnce(response({ osm_123: { osm_id: '123', osm_name: 'Nach Wiederholen' } }));
  expect((await client.details(manifest, 'osm_123', signal)).osm_name).toBe('Nach Wiederholen');
  client.dispose();
});
