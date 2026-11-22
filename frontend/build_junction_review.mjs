// Publish only the human review pages and images, not frozen OSM/route records.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(frontend, '../docs/large-junction-analysis');
const target = path.join(frontend, 'public/docs/large-junction-analysis');
if (fs.existsSync(source)) {
  function copy(directory, destination) {
    fs.mkdirSync(destination, { recursive: true });
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const from = path.join(directory, entry.name);
      const to = path.join(destination, entry.name);
      if (entry.isDirectory()) copy(from, to);
      else if (/\.(html|svg|png)$/.test(entry.name)) fs.copyFileSync(from, to);
    }
  }
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    if (entry.isDirectory() && (entry.name === 'kreuzungspruefung' ||
        /^review-batch-.*-images$/.test(entry.name))) {
      copy(path.join(source, entry.name), path.join(target, entry.name));
    }
  }
  // Public priority overview; no frozen routing or OSM extracts are published.
  for (const name of ['outgoing-lanes-munich.html', 'outgoing-lanes-munich-inventory.json']) {
    const from = path.join(source, name);
    if (fs.existsSync(from)) fs.copyFileSync(from, path.join(target, name));
  }
  // The first review gallery links its public release notes.
  fs.copyFileSync(path.join(source, 'review-batch-01-release.md'),
    path.join(target, 'review-batch-01-release.md'));
} else if (!fs.existsSync(path.join(target, 'kreuzungspruefung/index.html'))) {
  throw new Error('Junction review pages must be staged before the frontend Docker build.');
}
console.log('Junction review pages available under /docs/large-junction-analysis/.');
const publicMap = path.join(frontend, 'public/kreuzungspruefung/data.json');
const publicSnapshot = path.join(source, 'public-junction-review.json');
if (fs.existsSync(publicSnapshot)) {
  fs.mkdirSync(path.dirname(publicMap), {recursive: true});
  fs.copyFileSync(publicSnapshot, publicMap);
} else if (!fs.existsSync(publicMap)) {
  throw new Error('Public junction map snapshot must be staged before the Docker build.');
}
