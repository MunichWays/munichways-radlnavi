import test from 'node:test';
import assert from 'node:assert/strict';
import {projection, visibleTiles, moveVertex, spreadLabels} from '../junction_review/web/app.js';

test('projection round trips and keeps north upwards with equal metric scale', () => {
  for (const origin of [[11.6, 48.1], [-73.98, 40.7], [151.2, -33.8]]) {
    const map = projection(origin), point = [origin[0] + .001, origin[1] + .002];
    const xy = map.to(point), back = map.from(xy);
    assert.ok(xy[0] > 0 && xy[1] < 0);
    assert.ok(Math.abs(back[0] - point[0]) < 1e-10 && Math.abs(back[1] - point[1]) < 1e-10);
  }
});

test('moving the first polygon vertex also moves the closing vertex, without editing source', () => {
  const polygon = [[0, 0], [1, 0], [1, 1], [0, 0]];
  const moved = moveVertex(polygon, 0, [.2, .2]);
  assert.deepEqual(moved[0], moved.at(-1));
  assert.deepEqual(polygon[0], [0, 0]);
});

test('OSM tiles align exactly with Web Mercator at city and junction scales', () => {
  for (const origin of [[11.6, 48.1], [151.2, -33.8]]) {
    for (const box of [[-100, -70, 200, 140], [-5000, -3000, 10000, 6000]]) {
      const map = projection(origin), tiles = visibleTiles(box, origin, 1000);
      assert.ok(tiles.length > 0 && tiles.length < 60);
      for (const tile of tiles) {
        const [z, x, y] = tile.key.split('/').map(Number), n = 2 ** z;
        const corner = [x / n * 360 - 180, Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI];
        const xy = map.to(corner);
        assert.ok(Math.abs(xy[0] - tile.x) < 1e-6 && Math.abs(xy[1] - tile.y) < 1e-6);
        assert.ok(tile.url.startsWith('https://tile.openstreetmap.org/'));
        assert.ok(tile.x < box[0] + box[2] && tile.x + tile.size > box[0]);
        assert.ok(tile.y < box[1] + box[3] && tile.y + tile.size > box[1]);
      }
    }
  }
});

test('crowded shared-gate labels retain identity, order and readable spacing', () => {
  const labels = spreadLabels([{id: 'a', y: 30}, {id: 'b', y: 30}, {id: 'c', y: 32}], 10, 0, 50);
  assert.deepEqual(labels.map(x => x.id), ['a', 'b', 'c']);
  assert.ok(labels[1].labelY - labels[0].labelY >= 10);
  assert.ok(labels[2].labelY - labels[1].labelY >= 10);
  assert.ok(labels.at(-1).labelY <= 50);
});
