import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { newDeck, newSlide, blankItem, composition, readDeck } from '../electron/office/deck.mjs';
import { planDesign } from '../electron/office/director.mjs';
import { powerPoint } from '../electron/office/pptx.mjs';
import { reviewManifest } from '../electron/office/review.mjs';

// Read Office packages using the ZIP dependency of the native exporter.
const require = createRequire(import.meta.url);
const Zip = createRequire(require.resolve('pptxgenjs'))('jszip');
const styles = ['editorial', 'minimal', 'corporate', 'technology'];
const image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+XuiQAAAAASUVORK5CYII=';
const uploaded = {
  id: 'pptx-' + 'ab'.repeat(32),
  name: 'Reference.pptx',
  slideCount: 8,
  textDensity: 'dense',
  hasCharts: true,
  hasImages: true,
  titleAlignment: 'center',
  palette: 'dark',
};

function sample() {
  const deck = { ...newDeck(), title: '季度复盘', brief: '董事会汇报', theme: 'midnight' };
  deck.slides = [
    ['cover', 'Quarterly review', 1],
    ['image', '客户实例', 3],
    ['comparison', '计划与实际', 2],
    ['chart', '净变化', 3],
    ['timeline', '后续日程', 4],
    ['conclusion', '下一步', 3],
  ].map(([layout, title, count], page) => ({
    ...newSlide(title, layout),
    notes: '演讲者备注 ' + page + '\nSecond line & <reference>',
    image: ['cover', 'image'].includes(layout) ? image : '',
    ...(layout === 'chart' && { unit: '万元' }),
    items: Array.from({ length: count }, (_, i) => ({
      ...blankItem(), label: '项目 ' + (page + 1) + ' / ' + (i + 1),
      text: '原文 ' + (page + 1) + '.' + (i + 1) + '：<事实> & 金额\nRetain this sentence.',
      value: [-42, 0, 18.25, 5][i],
    })),
  }));
  return deck;
}

function objectsFor(deck, page, design) {
  return composition(deck.slides[page], page + 1, deck.slides.length, deck.theme, design);
}

test('the director responds deterministically to audience, setting, deck cues and explicit direction', () => {
  const deck = { ...newDeck(), title: 'Overview' };
  const automatic = planDesign(deck);
  assert.equal(automatic.direction, 'minimal');
  assert.equal(planDesign(deck, { audience: 'engineering team' }).direction, 'technology');
  assert.equal(planDesign(deck, { audience: '学生' }).direction, 'editorial');
  assert.equal(planDesign(sample()).direction, 'corporate');
  assert.deepEqual(planDesign(structuredClone(deck)), automatic);
  assert.deepEqual(JSON.parse(JSON.stringify(automatic)), automatic);
  const stage = planDesign(deck, { direction: 'technology', audience: '领导', setting: '大屏投影' });
  assert.equal(stage.direction, 'technology');
  assert.ok(stage.tokens.typography.body > planDesign(deck, { direction: 'technology' }).tokens.typography.body);
  assert.notEqual(stage.tokens.palette.bg, planDesign(deck, { direction: 'technology', setting: 'printed handouts' }).tokens.palette.bg);
});

test('rhythm follows slide semantics and curated ranking responds to content and capacity', () => {
  const deck = sample();
  const corporate = planDesign(deck, { direction: 'corporate' });
  assert.equal(corporate.rhythm[0].role, 'opening');
  assert.equal(corporate.rhythm[1].emphasis, 'image');
  assert.deepEqual(corporate.rhythm.slice(2).map(({ role }) => role), ['contrast', 'evidence', 'mechanism', 'conclusion']);
  const chartPlan = corporate.rhythm[3];
  assert.equal(chartPlan.referenceId, 'corporate-evidence');
  const investor = planDesign({ ...deck, title: 'Investor pitch', brief: '' }, { direction: 'corporate' });
  assert.equal(investor.rhythm[3].referenceId, 'corporate-investment');

  const longChart = structuredClone(deck.slides[3]);
  longChart.items.forEach((item) => { item.text = '长'.repeat(220); });
  const dense = planDesign({ ...deck, title: 'Investor pitch', brief: '', slides: [longChart] },
    { direction: 'corporate' });
  assert.equal(dense.rhythm[0].density, 'dense');
  assert.equal(dense.rhythm[0].referenceId, 'corporate-evidence');
  for (const page of corporate.rhythm) {
    const reference = corporate.references.find(({ id }) => id === page.referenceId);
    assert.equal(reference.direction, 'corporate');
    assert.ok(reference.layouts.includes(page.layout));
    assert.ok(reference.owner && reference.rights && reference.allowedLessons.length && reference.prohibitedReuse.length);
  }
});

test('uploaded references apply bounded style cues without accepting imported tokens or assets', () => {
  const deck = sample();
  const reference = { ...uploaded, color: 'FF0000', slideText: 'reference-only copy', image };
  const design = planDesign(deck, { direction: 'editorial', reference });
  const defaultDesign = planDesign(deck, { direction: 'editorial' });
  assert.deepEqual(design.preferences.reference, uploaded);
  assert.notEqual(design.tokens.palette.bg, defaultDesign.tokens.palette.bg);
  assert.equal(objectsFor(deck, 1, design).find(({ field }) => field === 'title').align, 'center');
  assert.ok(design.rhythm.every(({ density }) => density === 'dense'));
  assert.ok(!JSON.stringify(design).includes('reference-only copy'));
  const mixed = planDesign(deck, { direction: 'editorial', reference: { ...uploaded, palette: 'mixed', titleAlignment: 'mixed' } });
  assert.notEqual(objectsFor(deck, 0, mixed)[0].color, objectsFor(deck, 1, mixed)[0].color);
  assert.equal(objectsFor(deck, 0, mixed).find(({ field }) => field === 'title').align, 'center');
  assert.equal(objectsFor(deck, 1, mixed).find(({ field }) => field === 'title').align, 'left');

  const reordered = {
    ...deck,
    slides: deck.slides.slice(1).reverse(),
    design: { ...design, tokens: { palette: { bg: 'FF0000' }, fonts: { title: 'untrusted' } } },
  };
  const restored = readDeck(reordered);
  assert.deepEqual(restored.design, planDesign(reordered, design.preferences));
  assert.equal(restored.design.preferences.reference.id, uploaded.id);
  assert.deepEqual(restored.design.rhythm.map(({ slideId }) => slideId), reordered.slides.map(({ id }) => id));
  assert.equal(restored.slides, reordered.slides);
  assert.equal(readDeck(deck), deck);
  for (const preferences of [
    { direction: 'paper' }, { audience: 'x'.repeat(121) }, { setting: [] },
    { reference: { ...uploaded, id: 'ref-abc' } }, { reference: { ...uploaded, slideCount: 101 } },
    { reference: { ...uploaded, hasCharts: 'yes' } }, { reference: { ...uploaded, palette: 'user-color' } },
  ]) assert.throws(() => readDeck({ ...deck, design: { preferences } }), /设计设置无效/);
  assert.throws(() => readDeck({ ...deck, design: { version: 2 } }), /设计设置无效/);
});

test('styles apply visibly distinct geometry and reusable, readable tokens to every existing layout', () => {
  const deck = sample();
  const motifs = styles.map((direction) => {
    const design = planDesign(deck, { direction });
    const pages = deck.slides.map((_, i) => objectsFor(deck, i, design));
    assert.ok(pages.every((objects) => objects[0].color === design.tokens.palette.bg));
    const boxes = pages.flat();
    for (const { x, y, w, h } of boxes) {
      assert.ok([x, y, w, h].every(Number.isFinite) && x >= 0 && y >= 0 && w > 0 && h > 0);
      assert.ok(x + w <= 960.01 && y + h <= 540.01);
    }
    for (const [page, slide] of deck.slides.entries()) {
      const objects = pages[page];
      assert.equal(objects.find(({ field }) => field === 'title').value, slide.title);
      for (const [i, item] of slide.items.entries()) {
        assert.equal(objects.find(({ field }) => field === 'label-' + i).value, item.label);
        assert.equal(objects.find(({ field }) => field === 'text-' + i).value, item.text);
      }
      assert.equal(objects.find(({ field }) => field === 'title').lineHeight, design.tokens.typography.lineHeight);
    }
    const chart = pages[3].find(({ type }) => type === 'chart');
    assert.deepEqual(chart.items.map(({ value }) => value), [-42, 0, 18.25]);
    assert.equal(chart.fontFace, design.tokens.fonts.data.cjk);
    assert.equal(chart.valueFontFace, design.tokens.fonts.data.latin);
    return pages[0].filter(({ type }) => type === 'rect').map(({ x, y, w, h }) => [x, y, w, h].join(',')).join('|');
  });
  assert.equal(new Set(motifs).size, 4);
});

function xmlText(xml) {
  return [...xml.matchAll(/<a:t(?: [^>]*)?>([^<]*)<\/a:t>/g)].map(([, value]) => value
    .replaceAll('\r\n', '\n').replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&amp;', '&')).join('\n');
}

test('native PPTX packages preserve source content, notes and editable chart data in all directions', async () => {
  const source = sample();
  for (const direction of styles) {
    const design = planDesign(source, { direction });
    const stale = { ...design, rhythm: [], tokens: {} };
    const deck = { ...source, design: stale };
    const manifest = reviewManifest(deck);
    assert.equal(manifest.design.direction, direction);
    assert.equal(manifest.design.rhythm.length, source.slides.length);
    const pptx = await Zip.loadAsync(await powerPoint(deck));
    const read = (name) => pptx.file(name).async('string');
    for (const [index, slide] of source.slides.entries()) {
      const slideXml = await read('ppt/slides/slide' + (index + 1) + '.xml');
      const notesXml = await read('ppt/notesSlides/notesSlide' + (index + 1) + '.xml');
      const title = manifest.slides[index].objects.find(({ field }) => field === 'title');
      assert.ok(slideXml.includes('typeface="' + title.fontFace + '"'));
      assert.ok(slideXml.includes('val="' + design.tokens.palette.bg + '"'));
      assert.ok(xmlText(slideXml).includes(slide.title));
      assert.ok(xmlText(notesXml).includes(slide.notes));
      for (const { label, text } of slide.items) {
        assert.ok(xmlText(slideXml).includes(label));
        assert.ok(xmlText(slideXml).includes(text));
      }
    }
    const [chartFile] = pptx.file(/^ppt\/charts\/chart\d+\.xml$/);
    const [workbookFile] = pptx.file(/^ppt\/embeddings\/.*\.xlsx$/);
    const chart = await chartFile.async('string');
    const workbook = await Zip.loadAsync(await workbookFile.async('nodebuffer'));
    const cells = await workbook.file('xl/worksheets/sheet1.xml').async('string');
    const native = manifest.slides[3].objects.find(({ type }) => type === 'chart');
    assert.ok(chart.includes('typeface="' + native.fontFace + '"'));
    assert.ok(chart.includes('typeface="' + native.valueFontFace + '"'));
    assert.ok(chart.includes('sz="' + native.categorySize * 100 + '"'));
    assert.ok(chart.includes('sz="' + native.valueSize * 100 + '"'));
    assert.ok(chart.includes('<c:showVal val="1"'));
    assert.ok(chart.includes('val="' + native.colors[0] + '"'));
    for (const { label, value } of source.slides[3].items) {
      assert.ok(chart.includes('<c:v>' + label + '</c:v>'));
      assert.ok(chart.includes('<c:v>' + value + '</c:v>'));
      assert.ok(cells.includes('<v>' + value + '</v>'));
    }
  }
  assert.deepEqual(Object.keys(source).filter((key) => key === 'design'), []);
});

test('brand accents remain deck-local and keep readable text colors', () => {
  const source = sample();
  const normal = planDesign(source, { direction: 'corporate' });
  const branded = planDesign(source, { direction: 'corporate', brandAccent: '#ffFfee' });
  assert.deepEqual(branded.tokens.palette, normal.tokens.palette);
  const first = objectsFor(source, 0, branded);
  assert.ok(first.some(o => o.type === 'rect' && o.color === 'FFFFEE'));
  assert.ok(first.every(o => o.type !== 'text' || o.color !== 'FFFFEE'));
  assert.ok(objectsFor(source, 0, normal).every(o => o.color !== 'FFFFEE'));
  assert.throws(() => planDesign(source, { brandAccent: 'red' }));
});

test('designed pictures retain intrinsic proportions and comparisons avoid full-height card fills', () => {
  const deck = sample();
  for (const direction of styles) {
    const design = planDesign(deck, { direction });
    const picture = objectsFor(deck, 0, design).find(o => o.type === 'image');
    assert.equal(picture.w, picture.h); // the fixture is a 1 × 1 PNG
    const comparison = objectsFor(deck, 2, design);
    assert.ok(!comparison.some(o => o.type === 'rect' && o.color === design.tokens.palette.tint && o.h > 200));
  }
});

test('muted data bars have at least 3:1 contrast with their backgrounds in all directions', () => {
  function luminance(hex) {
    const channels = hex.match(/../g).map(byte => Number.parseInt(byte, 16) / 255);
    return channels.reduce((sum, v, i) => sum + [0.2126, 0.7152, 0.0722][i] *
      (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4), 0);
  }
  for (const direction of styles) for (const palette of ['light', 'dark']) {
    const {bg, mutedBar} = planDesign(sample(), { direction, reference: { ...uploaded, palette } }).tokens.palette;
    const [low, high] = [luminance(bg), luminance(mutedBar)].sort((a, b) => a - b);
    assert.ok((high + 0.05) / (low + 0.05) >= 3, direction + ' ' + palette);
  }
});
