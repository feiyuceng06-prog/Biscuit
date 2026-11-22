import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import {
  newDeck, newSlide, blankItem, composition, readDeck, preserveLayoutContent, generatedBody, applyBody,
} from '../electron/office/deck.mjs';
import { planDesign } from '../electron/office/director.mjs';
import { powerPoint } from '../electron/office/pptx.mjs';
import { reviewManifest } from '../electron/office/review.mjs';

const zip = createRequire(createRequire(import.meta.url).resolve('pptxgenjs'))('jszip');
const photo = 'data:image/jpeg;base64,' + readFileSync(
  new URL('../renderer/office/reading-room.jpg', import.meta.url), 'base64',
);
const row = (label, text = '', value = 0) => ({ ...blankItem(), label, text, value });
const slide = (layout, title, items, extra = {}) => ({ ...newSlide(title, layout), items, ...extra });
const deckFor = (...slides) => ({ ...newDeck(), slides });
const plan = (deck, preferences = { direction: 'corporate' }) =>
  planDesign(deck, preferences, { visualPlanner: true });
const objects = (deck, design, i = 0) =>
  composition(deck.slides[i], i + 1, deck.slides.length, deck.theme, design);
const chart = (title, categories, values) => slide(
  'chart', title, categories.map((label, i) => row(label, '', values[i])), { unit: '分钟' },
);

test('the visual planner picks six editable families, ranks candidates and varies adjacent pages', () => {
  const deck = deckFor(
    slide('cover', 'A reading product', [row('Launch', 'Back to the original passage.')], { image: photo }),
    slide('conclusion', 'Only one outcome matters', [row('Observation', 'A reader can resume the same passage.')]),
    slide('image', 'An evening at the library', [row('Scene', 'The reading room stays open.')], { image: photo }),
    slide('comparison', 'Two ways to resume', [row('By date', 'Search the calendar.'), row('By book', 'Search the shelf.')]),
    slide('timeline', 'How a bookmark is stored', [
      row('Capture', 'Save the page.'), row('Store', 'Write the record.'), row('Resume', 'Open the original passage.'),
    ]),
    chart('Average wait', ['Groups A', 'Groups B', 'Groups C'], [5, 10, 0]),
    ...Array.from({ length: 3 }, () => slide('conclusion', 'Outcome', [row('Read', 'Keep the original section.')])),
  );
  const original = structuredClone(deck);
  const design = plan(deck);
  assert.equal(design.version, 2);
  assert.deepEqual(plan(structuredClone(deck)), design);
  assert.deepEqual(deck, original);
  assert.deepEqual(design.slidePlans.slice(0, 6).map(({ layout }) => layout),
    ['cover', 'statement', 'image', 'comparison', 'sequence', 'chart']);
  assert.equal(design.slidePlans[4].variant, 'process-flow');
  assert.notEqual(design.slidePlans[6].variant, design.slidePlans[7].variant);
  assert.notEqual(objects(deck, design, 6).find(o => o.field === 'title').w,
    objects(deck, design, 7).find(o => o.field === 'title').w);
  for (const [i, page] of design.slidePlans.entries()) {
    const ids = new Set([deck.slides[i].id, ...deck.slides[i].items.map(({ id }) => id)]);
    assert.equal(page.slideId, deck.slides[i].id);
    assert.equal(page.keyMessage, deck.slides[i].title);
    assert.ok(page.focalPoint && page.selectionReason && page.density);
    assert.ok(page.referenceIds.every((id) => design.references.some((ref) => ref.id === id)));
    assert.ok(page.contentBindings.every(({ nodeId, slotId, emphasis }) => ids.has(nodeId) && slotId && emphasis));
    assert.ok(page.candidates.every(({ score, reasons }) => Number.isFinite(score) && reasons.length > 0));
    assert.ok(page.candidates.length >= 1 && page.candidates.length <= 4);
    assert.equal(page.candidates[0].variant, page.variant);
    assert.equal(page.candidates[0].feasible, true);
  }
  const hero = objects(deck, design, 2).find(o => o.type === 'image');
  assert.equal(hero.data, photo);
  assert.equal(design.slidePlans[2].assetStrategy.image.fit, 'contain');
});

test('intervals govern line and timeline encodings while mixed, ordinal or long categories remain discrete', () => {
  const intervals = ['第1周', '第2周', '第3周'];
  const deck = deckFor(
    chart('Wait by week', intervals, [-3.125, 0, 0.0625]),
    chart('Wait by stage', ['第1步', '第2步', '第3步'], [3, 4, 0]),
    chart('Wait over irregular intervals', ['2025-01', '2025-02', '2025-04'], [2, 1, 0]),
    chart('Year labels out of order', ['2023', '2025', '2024'], [3, 4, 0]),
    chart('Score by library area', ['儿童阅览服务区域入口', '综合借还服务台入口', '三楼数字资源服务区域'], [-5, 0, 0.25]),
    slide('timeline', 'Regular dates', intervals.map((name) => row(name, '原文时间'))),
    slide('timeline', 'Milestones', ['2025-01', '2025-02', '2025-04'].map(name => row(name, '原文时间'))),
  );
  const design = plan(deck);
  assert.deepEqual(design.slidePlans.slice(0, 5).map(({ chartEncoding }) => chartEncoding),
    ['line', 'columns', 'columns', 'columns', 'bars']);
  assert.deepEqual(design.slidePlans.slice(5).map(({ variant }) => variant), ['timeline-track', 'timeline-milestones']);
  assert.ok(design.slidePlans[1].candidates.filter(c => c.variant.startsWith('line-')).every(c => !c.feasible));
  const graph = objects(deck, design).find(o => o.type === 'chart');
  assert.deepEqual(graph.items.map(({ value }) => value), [-3.125, 0, 0.0625]);
  assert.ok(graph.domain.min < -3.125 && graph.domain.max > 0.0625);
});

test('layout changes preserve typed series, text, pictures, units and notes without charting prose defaults', () => {
  const source = chart('Original counts', ['Close', 'Open'], [0, -3.125]);
  source.image = photo;
  source.notes = 'Keep the exact source and original unit.';
  source.items[1].text = 'Verified observation.';
  const comparison = { ...source, ...preserveLayoutContent(source, { layout: 'comparison' }) };
  const deck = deckFor(comparison);
  const design = plan(deck);
  const page = objects(deck, design);
  assert.equal(design.slidePlans[0].layout, 'comparison');
  assert.deepEqual(comparison.items.map(({ valueKind }) => valueKind), ['chart-data', 'chart-data']);
  for (const value of ['Close', 'Open', '0', '-3.125', source.items[1].text, source.unit])
    assert.ok(page.some((o) => o.value === value), value);
  assert.ok(page.some((o) => o.data === photo));
  assert.ok(design.slidePlans[0].contentBindings.some(b => b.slotId === 'speaker-notes'));
  assert.equal(readDeck({ ...deck, design }).slides[0].notes, source.notes);

  const prose = slide('comparison', 'Two plans', [row('A', 'First'), row('B', 'Second')]);
  const chartLayout = { ...prose, ...preserveLayoutContent(prose, { layout: 'chart' }) };
  const draft = deckFor(chartLayout);
  assert.equal(plan(draft).slidePlans[0].layout, 'statement');
  assert.equal(objects(draft, plan(draft)).some(o => o.type === 'chart'), false);
  chartLayout.items[1] = { ...chartLayout.items[1], value: 0, valueKind: 'chart-data' };
  const graph = objects(draft, plan(draft)).find(o => o.type === 'chart');
  assert.deepEqual(graph.items.map(({ label, value }) => [label, value]), [['B', 0]]);
});

test('over-capacity text remains present and injected rendering choices are rederived on load', () => {
  const crowded = slide('comparison', 'Keep every source passage', Array.from({ length: 4 }, (_, i) =>
    row('Source ' + i, ('多\n').repeat(100) + '事实' + i)), { notes: 'The source includes line breaks.' });
  const source = deckFor(crowded, chart('Terms', ['Group A', 'Group B'], [1, 0]));
  const design = plan(source, { direction: 'technology', brandAccent: '#aabbcc' });
  const [dense] = design.slidePlans;
  assert.equal(dense.variant, 'comparison-rows');
  assert.equal(dense.density, 'dense');
  assert.equal(dense.candidates[0].feasible, false);
  assert.deepEqual(dense.contentEditProposal.nodeIds, crowded.items.map(({ id }) => id));
  for (const item of crowded.items) assert.ok(objects(source, design).some(o => o.value === item.text));
  assert.ok(objects(source, design).every(o => o.x >= 0 && o.y >= 0 && o.w > 0 && o.h > 0
    && o.x + o.w <= 960.01 && o.y + o.h <= 540.01));

  const reordered = { ...source, slides: [...source.slides].reverse() };
  reordered.design = { ...design, slidePlans: [{ layout: 'evil', slotId: 'injected' }], tokens: { palette: null } };
  const reopened = readDeck(JSON.parse(JSON.stringify(reordered)));
  assert.deepEqual(reopened.design, plan(reordered, design.preferences));
  assert.deepEqual(reviewManifest(reordered).design.slidePlans, reopened.design.slidePlans);
  assert.throws(() => readDeck({ ...source, design: { version: 2 } }), /设计设置无效/);
  assert.throws(() => readDeck({ ...source, design: { version: 2, preferences: { brandAccent: 'untrusted' } } }),
    /设计设置无效/);
  const v1 = planDesign(source);
  const legacy = readDeck({ ...source, design: { ...v1, slidePlans: design.slidePlans } });
  assert.deepEqual(legacy.design, v1);
  assert.deepEqual(objects(source, v1), objects(legacy, legacy.design));
  assert.equal(readDeck(source), source);
});

test('PPTX has editable line, bar and column charts with original numbers, categories, units and notes', async () => {
  const source = deckFor(
    chart('Monthly change', ['2025-01', '2025-02', '2025-03'], [-2.125, 0, 1.0625]),
    chart('Long category ranking', ['甲'.repeat(60), '乙'.repeat(60), '丙'.repeat(60)], [-13, 0, 6.125]),
    chart('Single categories', ['A', 'B', 'C'], [2, 0, 0.125]),
  );
  source.slides.forEach((page) => { page.notes = 'Keep the precise native series.'; });
  const deck = { ...source, design: plan(source) };
  const pptx = await zip.loadAsync(await powerPoint(deck));
  const charts = pptx.file(/^ppt\/charts\/chart\d+\.xml$/);
  const workbooks = pptx.file(/^ppt\/embeddings\/.*\.xlsx$/);
  assert.equal(charts.length, 3);
  assert.equal(workbooks.length, 3);
  const encodings = [/<c:lineChart>/, /<c:barDir val="bar"\/>/, /<c:barDir val="col"\/>/];
  for (const [i, page] of source.slides.entries()) {
    const graph = await charts[i].async('string');
    const data = await zip.loadAsync(await workbooks[i].async('nodebuffer'));
    const workbook = await data.file('xl/worksheets/sheet1.xml').async('string');
    const slideXml = await pptx.file('ppt/slides/slide' + (i + 1) + '.xml').async('string');
    const notes = await pptx.file('ppt/notesSlides/notesSlide' + (i + 1) + '.xml').async('string');
    assert.match(graph, encodings[i]);
    assert.ok(slideXml.includes(page.unit) && notes.includes(page.notes));
    for (const [row, item] of page.items.entries()) {
      assert.ok(graph.includes('<c:v>' + item.label + '</c:v>'));
      assert.ok(graph.includes('<c:v>' + item.value + '</c:v>'));
      assert.ok(workbook.includes('<c r="B' + (row + 2) + '"><v>' + item.value + '</v></c>'),
        'Expected the editable value in worksheet row ' + (row + 2));
    }
  }
  const wrapped = objects(deck, deck.design, 1);
  assert.equal(wrapped.find(o => o.type === 'chart').wrappedCategories, true);
  assert.ok(wrapped.some(o => o.type === 'text' && o.value === source.slides[1].items[0].label));
});

test('the model-provided zero stays typed when its category is blank and its annotation is present', () => {
  const source = deckFor(chart('Change', ['A', 'B'], [2, 1]));
  source.design = plan(source);
  const body = generatedBody(source.slides[0], { items: [
    { label: '', text: 'Blank category was recorded in the source.', value: 0 },
    { label: 'B', text: '', value: -2 },
  ] });
  const changed = applyBody(source, source.slides[0], body);
  assert.deepEqual(changed.slides[0].items.map(row => row.valueKind), ['chart-data', 'chart-data']);
  const rendered = objects(changed, plan(changed)).find(o => o.type === 'chart');
  assert.deepEqual(rendered.items.map(item => item.value), [0, -2]);
});
