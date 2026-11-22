// Rebuild each pair from identical fixtures using the production export and review paths.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { newDeck, newSlide } from '../../desktop/electron/office/deck.mjs';
import { powerPoint } from '../../desktop/electron/office/pptx.mjs';
import { reviewExport, reviewManifest } from '../../desktop/electron/office/review.mjs';

const [out, version, caseId, direction] = process.argv.slice(2);
const plannerCase = ['phase2', 'phase3'].includes(version);
assert.ok(out && (plannerCase || ['before', 'after'].includes(version)),
  'Usage: node director-compare.mjs OUTPUT before|after|phase2|phase3 [case] [direction]');
const fixtures = JSON.parse(await fs.readFile(new URL(plannerCase ? './planner-cases.json' : './director-cases.json', import.meta.url)));
const cases = fixtures.filter(c => !caseId || c.id === caseId);
assert.ok(cases.length, 'Unknown case');
if (direction) assert.ok(version === 'after' && ['editorial', 'minimal', 'corporate', 'technology'].includes(direction));
const photo = 'data:image/jpeg;base64,' + await fs.readFile(new URL('../../desktop/renderer/office/reading-room.jpg', import.meta.url), 'base64');
const backend = { command: process.env.PYTHON || 'python', args: ['-m', 'feiyu'] };
await Promise.all(cases.map(async ({id, title, brief, audience, setting, slides}) => {
  const dir = path.resolve(out, id, direction || version);
  await fs.mkdir(dir, {recursive: true});
  const deck = {...newDeck(), id, title, brief, source: '虚构演示案例，用于设计对照。', slides:
    slides.map(([layout, headline, items, detail], n) => ({
      ...newSlide(headline, layout), id: id + '-' + (n + 1), generated: true,
      image: detail === 'photo' ? photo : '', unit: layout === 'chart' ? detail : '',
      notes: '设计对照样例。' + headline + '。材料来自固定输入 ' + id + '。',
      items: items.map(([label, text, value = 0], i) => ({id: id + '-' + n + '-' + i, label, text, value})),
    }))};
  if (plannerCase || version === 'after') {
    const { planDesign } = await import('../../desktop/electron/office/director.mjs');
    const frozen = structuredClone(deck);
    deck.design = planDesign(deck, {direction: direction || 'auto', audience, setting}, {visualPlanner: version === 'phase3'});
    if (plannerCase) assert.equal(deck.design.version, version === 'phase3' ? 2 : 1);
    assert.deepEqual(deck.slides, frozen.slides);
    await fs.writeFile(path.join(dir, 'design.json'), JSON.stringify(deck.design, null, 2) + '\n');
  }
  await fs.writeFile(path.join(dir, 'manifest.json'), JSON.stringify(reviewManifest(deck), null, 2) + '\n');
  if (process.env.MANIFEST_ONLY === '1') return;
  const bytes = await powerPoint(deck);
  const dest = path.join(dir, 'deck.pptx');
  await fs.writeFile(dest, bytes);
  const result = await reviewExport(dest, bytes, deck, backend);
  const report = JSON.parse(await fs.readFile(result.report));
  assert.equal(report.pages.length, slides.length, result.status);
  await fs.rename(path.dirname(result.report), path.join(dir, 'review'));
  console.log(id, version, result.status, result.critic);
}));
