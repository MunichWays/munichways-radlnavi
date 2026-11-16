import { readFile, appendFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { prepareSnapshot } from './build_street_details.mjs';

export async function hasStreetDetailsUpdate({ fetchImpl = fetch,
  manifestUrl = 'https://radlnavi.munichways.de/street-details/manifest.json' } = {}) {
  const config = JSON.parse(await readFile(new URL('./street-details-source.json', import.meta.url), 'utf8'));
  async function download(url) {
    const response = await fetchImpl(url, { cache: 'no-store', signal: AbortSignal.timeout(120000) });
    if (!response.ok) throw new Error(`V20 update check failed: HTTP ${response.status} (${url})`);
    return response;
  }
  const source = await download(config.url);
  const raw = Buffer.from(await source.arrayBuffer());
  // Use the build's validation and processor version, not Last-Modified alone.
  const { manifest } = prepareSnapshot(raw, config);
  const deployed = await (await download(manifestUrl)).json();
  if (deployed?.schemaVersion !== 1 || !/^[a-f0-9]{64}$/.test(deployed.snapshot)) {
    throw new Error('Invalid deployed V20 manifest');
  }
  return manifest.snapshot !== deployed.snapshot;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const changed = await hasStreetDetailsUpdate();
  console.log(`V20 changed: ${changed}`);
  if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT, `changed=${changed}\n`);
}
