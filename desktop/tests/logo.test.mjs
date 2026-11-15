import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ui = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../ui');
const shape = (svg) => {
  const found = svg.match(/viewBox="([^"]+)"[\s\S]*?<g transform="([^"]+)">\s*<path\b([^>]*?)\sd="([^"]+)"/);
  assert.ok(found, 'no single <g><path> in:\n' + svg.slice(0, 200));
  return { viewBox: found[1], transform: found[2], attrs: found[3], d: found[4] };
};

test('the dog traced at startup is the same path as logo.svg', async () => {
  const logo = shape(await fs.readFile(path.join(ui, 'logo.svg'), 'utf8'));
  const html = await fs.readFile(path.join(ui, 'index.html'), 'utf8');
  const template = html.match(/<template id="dog">([\s\S]*?)<\/template>/);
  assert.ok(template, 'index.html has no <template id="dog">');
  const dog = shape(template[1]);
  assert.deepEqual([dog.viewBox, dog.transform, dog.d], [logo.viewBox, logo.transform, logo.d]);
  // The trace animates stroke-dashoffset from 1 to 0, which only spans the whole outline at pathLength 1.
  assert.match(dog.attrs, /pathLength="1"/);
});
