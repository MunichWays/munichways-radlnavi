// Optional end-to-end QA against the local production bundle and real prepared V20 data.
// Install Playwright in the ignored cache; see frontend/README.md.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { chromium } = await import('../.cache/browser/node_modules/playwright/index.mjs');
const build = path.join(root, 'build');
const manifest = JSON.parse(await readFile(path.join(build, 'street-details/manifest.json'), 'utf8'));
const geometry = JSON.parse(await readFile(path.join(build, 'street-details', manifest.snapshot, 'geometry.json'), 'utf8'));
const center = [11.584225, 48.134991];
const project = ([lon, lat], zoom = 14) => {
  const sin = Math.sin(lat * Math.PI / 180), scale = 256 * 2 ** zoom;
  return [(lon + 180) / 360 * scale, (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * scale];
};
// A real segment midpoint near the initial map center avoids relying on test-only app hooks.
const segments = geometry.features.flatMap(f => f.geometry.coordinates.slice(1).map((b, i) => {
  const a = f.geometry.coordinates[i];
  const midpoint = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  return { feature: f, midpoint, score: Math.hypot((midpoint[0] - center[0]) * 0.67, midpoint[1] - center[1]) };
})).sort((a, b) => a.score - b.score);
const target = segments[0];
const requests = [];
const types = { '.js': 'application/javascript', '.json': 'application/json', '.css': 'text/css',
  '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png' };
const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname.startsWith('/street-details/')) requests.push(url.pathname);
  if (url.pathname.endsWith('.pbf')) { res.writeHead(200); res.end(); return; }
  const relative = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname).slice(1);
  const filename = path.resolve(build, relative);
  if (!filename.startsWith(build + path.sep)) { res.writeHead(403); res.end(); return; }
  try {
    const body = await readFile(filename);
    res.writeHead(200, { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream' }); res.end(body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ headless: true, channel: process.env.STREET_TEST_BROWSER_CHANNEL || 'msedge' });
try {
  for (const mobile of [false, true]) {
    const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 900 },
      isMobile: mobile, hasTouch: mobile });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://**/*', async route => {
      if (process.env.STREET_TEST_MAPILLARY === '1' &&
          (new URL(route.request().url()).hostname.endsWith('mapillary.com') ||
           route.request().frame().url().startsWith('https://www.mapillary.com/'))) await route.continue();
      else if (route.request().url().includes('/leaflet.css')) await route.fulfill({
        body: await readFile(path.join(root, 'node_modules/leaflet/leaflet.css')), contentType: 'text/css' });
      else await route.abort();
    });
    await page.goto(base);
    if (mobile) await page.getByRole('button', { name: 'Menü ausblenden' }).click();
    const map = page.locator('.leaflet-container');
    await map.waitFor({ state: 'visible' });
    // Wait for the application's initial invalidateSize(300 ms) and layout to settle.
    await page.waitForTimeout(500);
    const box = await map.boundingBox();
    const c = project(center), t = project(target.midpoint);
    let x = box.x + box.width / 2 + t[0] - c[0], y = box.y + box.height / 2 + t[1] - c[1];
    // Calibrate the pixel origin via the map's visible click diagnostic: the
    // responsive planner changes Leaflet's initial center during invalidateSize.
    const clicked = page.waitForEvent('console', { predicate: message => message.text().startsWith('clicked on point') });
    await page.mouse.click(x, y, { button: 'right' });
    const actualClick = await (await clicked).args()[1].jsonValue();
    const actual = project([actualClick.lng, actualClick.lat]);
    x += t[0] - actual[0]; y += t[1] - actual[1];
    await map.dispatchEvent('click');
    const cdp = mobile ? await context.newCDPSession(page) : null;
    const openMenu = async () => {
      if (mobile) {
        // Exercise the fork's actual touch-hold handler, including its synthetic contextmenu.
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y }] });
        await page.getByRole('button', { name: 'Details anzeigen', exact: true }).waitFor({ timeout: 15000 });
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      } else await page.mouse.click(x, y, { button: 'right' });
      await page.getByRole('button', { name: 'Details anzeigen', exact: true }).waitFor({ timeout: 15000 }).catch(async error => {
        console.log(JSON.stringify({ mobile, box, x, y, target: target.feature.id, point: target.midpoint, requests, errors,
          text: await page.locator('body').innerText() }, null, 2));
        await page.screenshot({ path: path.join(root, '.cache/street-details-failure.png') });
        throw error;
      });
    };
    await openMenu();
    const menu = page.locator('#menu');
    const menuBox = await menu.boundingBox();
    await page.screenshot({ path: path.join(root, `.cache/street-menu-${mobile ? 'mobile' : 'desktop'}.png`) });
    assert(menuBox.x >= 0 && menuBox.x + menuBox.width <= (mobile ? 390 : 1280), JSON.stringify({ menuBox,
      viewport: await page.evaluate(() => ({ inner: innerWidth, client: document.documentElement.clientWidth, visual: visualViewport?.width })) }));
    assert(await page.getByRole('button', { name: 'Route von hier', exact: true }).isEnabled());
    await page.getByRole('button', { name: 'Details anzeigen', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.waitFor();
    assert.equal(await dialog.getAttribute('aria-modal'), 'false');
    assert.equal(await dialog.locator('#street-details-title').innerText(), 'Streckendetails');
    const choice = dialog.getByRole('button', { name: new RegExp(`OSM ${target.feature.id.slice(4)}$`) });
    if (await choice.count()) await choice.click();
    await dialog.locator('.street-detail-name').waitFor();
    const preview = dialog.locator('iframe[title="Mapillary-Straßenansicht"]');
    assert.equal(await preview.count(), 1, 'Selected real V20 way has a Mapillary preview');
    if (process.env.STREET_TEST_MAPILLARY === '1') {
      await page.frameLocator('iframe[title="Mapillary-Straßenansicht"]').locator('canvas').waitFor({ timeout: 45000 });
    }
    assert.match(await dialog.locator('.street-snapshot').innerText(), /^Datenstand 26\.10\.2026, Quelle IST_RadlVorrangNetz_Oberbayern_V20\.geojson\.$/);
    const header = dialog.locator('#street-details-title');
    const beforeMove = await dialog.boundingBox();
    await header.focus();
    await page.keyboard.press('ArrowDown');
    const afterMove = await dialog.boundingBox();
    assert(afterMove.y > beforeMove.y, 'Window must move with keyboard');
    await dialog.getByRole('button', { name: 'Verkleinern', exact: true }).click();
    assert.equal(await dialog.locator('.street-detail-name').isVisible(), false);
    await dialog.getByRole('button', { name: 'Öffnen', exact: true }).click();
    await dialog.locator('.street-detail-name').waitFor();
    // Closing the map menu/panning must leave this independent window intact.
    await map.dispatchEvent('click');
    assert(await dialog.isVisible());
    if (!mobile) {
      const boxBeforeDrag = await dialog.boundingBox();
      const titleBox = await header.boundingBox();
      await page.mouse.move(titleBox.x + 20, titleBox.y + 10);
      await page.mouse.down(); await page.mouse.move(titleBox.x + 50, titleBox.y + 30, { steps: 5 }); await page.mouse.up();
      assert((await dialog.boundingBox()).x > boxBeforeDrag.x, 'Window must be draggable');
      const beforeResize = await dialog.boundingBox();
      await page.mouse.move(beforeResize.x + beforeResize.width - 3, beforeResize.y + beforeResize.height - 3);
      await page.mouse.down();
      await page.mouse.move(beforeResize.x + beforeResize.width - 63, beforeResize.y + beforeResize.height - 43, { steps: 5 });
      await page.mouse.up();
      assert((await dialog.boundingBox()).width < beforeResize.width - 20, 'Window must resize using its corner');
    }
    if (mobile) {
      const rect = await dialog.boundingBox();
      assert(rect.x >= 0 && rect.x + rect.width <= 390 && rect.y + rect.height <= 845,
        `Mobile dialog must fit visible viewport: ${JSON.stringify(rect)}`);
    }
    assert(await page.locator('path[stroke="#8E24AA"]').count() > 0, 'Selected V20 geometry must be highlighted');
    await page.screenshot({ path: path.join(root, `.cache/street-details-${mobile ? 'mobile' : 'desktop'}.png`) });
    await dialog.getByRole('button', { name: 'Schließen', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    assert.equal(await page.locator('path[stroke="#8E24AA"]').count(), 0);
    assert(await map.evaluate(e => e === document.activeElement), 'Focus returns to the map when the original menu has closed');
    await map.dispatchEvent('click');
    const before = requests.filter(p => p.endsWith('/geometry.json')).length;
    await openMenu();
    assert.equal(requests.filter(p => p.endsWith('/geometry.json')).length, before, 'Search index must be reused');
    assert.deepEqual(errors, [], 'No uncaught browser errors');
    console.log(`${mobile ? 'Mobile touch-hold' : 'Desktop right-click'}: real worker, candidate choice, detail loading, highlight, focus and cached index OK (${target.feature.id}).`);
    await context.close();
  }
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
