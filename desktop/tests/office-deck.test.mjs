import test from 'node:test';
import assert from 'node:assert/strict';
import {
  newDeck,
  newSlide,
  generatedBody,
  applyBody,
  readDeck,
  composition,
} from '../electron/office/deck.mjs';

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
