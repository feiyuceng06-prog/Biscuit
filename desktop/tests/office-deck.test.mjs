import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {
  newDeck,
  newSlide,
  generatedBody,
  applyBody,
  readDeck,
  composition,
} from '../electron/office/deck.mjs';
import { reviewExport } from '../electron/office/review.mjs';

test('single-slide regeneration preserves seven siblings, concurrent title and a newer body', () => {
  const deck = newDeck();
  deck.slides = Array.from({ length: 8 }, (_, i) => newSlide('第' + (i + 1) + '页'));
  const original = deck.slides[3];
  const latest = {
    ...deck,
    slides: deck.slides.map((s) => (s.id === original.id ? { ...s, title: '手动标题' } : s)),
  };
  const body = generatedBody(original, {
    items: [{ label: '风险', text: '晚到的配件' }],
    notes: '周报',
  });
  const updated = applyBody(latest, original, body);
  assert.equal(updated.slides[3].title, '手动标题');
  assert.equal(updated.slides[3].items[0].label, '风险');
  deck.slides.forEach((s, i) => {
    if (i !== 3) assert.equal(updated.slides[i], s);
  });
  assert.equal(applyBody(updated, original, body), updated);
  assert.deepEqual(readDeck(JSON.parse(JSON.stringify(updated))), updated);
});

test('opening a deck refuses duplicate IDs and non-embedded images', () => {
  const deck = newDeck();
  deck.slides[0].image = 'file:///private/figure.png';
  assert.throws(() => readDeck(deck));
  deck.slides[0].image = '';
  deck.slides.push(deck.slides[0]);
  assert.throws(() => readDeck(deck));
});

test('chart bodies require numbers and preserve the signs of real values', () => {
  const slide = newSlide('净变化', 'chart');
  assert.throws(() => generatedBody(slide, { items: [{ label: '北区' }] }));
  Object.assign(
    slide,
    generatedBody(slide, {
      items: [
        { label: '北区', value: -42 },
        { label: '南区', value: 0 },
      ],
    }),
  );
  assert.deepEqual(
    composition(slide, 1, 1)
      .find((o) => o.type === 'chart')
      .items.map((i) => i.value),
    [-42, 0],
  );
});

test('chart units survive reopening and only the annotated category is highlighted', () => {
  const deck = newDeck();
  const slide = newSlide('周五客流', 'chart');
  deck.slides = [slide];
  Object.assign(
    slide,
    generatedBody(slide, {
      unit: '人次',
      items: [
        { label: '首周', value: 26 },
        { label: '次周', value: 35, text: '多了 9 人次' },
      ],
    }),
  );
  const reopened = readDeck(JSON.parse(JSON.stringify(deck))).slides[0];
  for (const theme of ['paper', 'sand', 'midnight']) {
    const objects = composition(reopened, 1, 1, theme);
    const chart = objects.find((o) => o.type === 'chart');
    assert.notEqual(chart.colors[0], chart.colors[1]);
    assert.ok(objects.some((o) => o.value === '35 人次'));
    assert.ok(objects.some((o) => o.value === '多了 9 人次' && o.field === 'text-1'));
    const plain = composition(
      { ...reopened, items: reopened.items.map((i) => ({ ...i, text: '' })) },
      1,
      1,
      theme,
    );
    assert.ok(plain.find((o) => o.type === 'chart').w > chart.w);
  }
  slide.unit = {};
  assert.throws(() => readDeck(deck));
});

test('a review worker that exits without a valid report leaves an explicit fallback', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'biscuit-review-test-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const destination = path.join(dir, 'saved.pptx');
  const bytes = Buffer.from('saved export snapshot');
  await fs.writeFile(destination, bytes);
  const deck = newDeck();
  const incomplete = { schemaVersion: 1, deckId: deck.id, status: 'checked', pages: [], issues: [],
    pptxSha256: createHash('sha256').update(bytes).digest('hex'), critic: { status: 'not_requested' } };
  for (const script of [
    `require('node:fs').writeFileSync(require('node:path').join(process.argv.at(-1), 'report.json'),
      JSON.stringify(${JSON.stringify(incomplete)}))`,
    '',
    'require("node:fs").writeFileSync(require("node:path").join(process.argv.at(-1), "report.json"), "{}")',
  ]) {
    const result = await reviewExport(destination, bytes, deck, {
      command: process.execPath, args: ['-e', script, '--'],
    });
    assert.equal(result.status, 'preview_unavailable');
    const report = JSON.parse(await fs.readFile(result.report, 'utf8'));
    assert.equal(report.deckId, deck.id);
    assert.equal(report.pptxSha256, createHash('sha256').update(bytes).digest('hex'));
    assert.deepEqual(report.pages, []);
    assert.deepEqual(await fs.readFile(destination), bytes);
  }
});

test('a failed review worker preserves a valid preflight report for the saved bytes', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'biscuit-review-test-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const destination = path.join(dir, 'saved.pptx');
  const bytes = Buffer.from('saved export snapshot');
  await fs.writeFile(destination, bytes);
  const deck = newDeck();
  const checkpoint = {
    schemaVersion: 1, deckId: deck.id, status: 'needs_review', pptxSha256: createHash('sha256').update(bytes).digest('hex'),
    critic: { status: 'unavailable' }, pages: [{ slideId: deck.slides[0].id, png: 'slide-1.png' }], issues: [],
  };
  const script = `
    require('node:fs').writeFileSync(require('node:path').join(process.argv.at(-1), 'report.json'),
      JSON.stringify(${JSON.stringify(checkpoint)}));
    process.exit(124);
  `;
  const result = await reviewExport(destination, bytes, deck, {
    command: process.execPath, args: ['-e', script, '--'],
  });
  assert.equal(result.status, 'needs_review');
  assert.deepEqual(JSON.parse(await fs.readFile(result.report, 'utf8')), checkpoint);
});
