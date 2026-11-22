// Run after baseline.py, using new PPTX bytes and the production after-save hook.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { powerPoint } from '../../desktop/electron/office/pptx.mjs';
import { reviewExport } from '../../desktop/electron/office/review.mjs';

const [baseline, out] = process.argv.slice(2);
await fs.mkdir(out, {recursive: true});
const measurements = [];
for (const row of JSON.parse(await fs.readFile(path.join(baseline, 'baseline.json')))) {
  const deck = JSON.parse(await fs.readFile(path.join(baseline, row.deck + '.json')));
  const destination = path.join(out, row.deck + '.pptx');
  const bytes = await powerPoint(deck);
  await fs.writeFile(destination, bytes);
  const result = await reviewExport(destination, bytes, deck, {command: process.env.PYTHON || 'python', args: ['-m','feiyu']});
  const report = JSON.parse(await fs.readFile(result.report));
  assert.deepEqual(report.pages.map(p => p.sha256), row.pngSha256, row.deck);
  measurements.push({deck: row.deck, identicalPages: report.pages.length, durationMs: report.durationMs,
    status: report.status, issues: report.issues.map(i => [i.slideId, i.kind])});
}
await fs.writeFile(path.join(out, 'comparison.json'), JSON.stringify(measurements, null, 2) + '\n');
