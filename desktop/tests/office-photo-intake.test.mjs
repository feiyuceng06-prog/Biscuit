import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { applyBody, newDeck, outlineDeck, readDeck } from '../electron/office/deck.mjs';
import { distributePhotos, photoCredits } from '../electron/office/photos.mjs';
import { powerPoint } from '../electron/office/pptx.mjs';

const zip = createRequire(createRequire(import.meta.url).resolve('pptxgenjs'))('jszip');
const data = 'data:image/jpeg;base64,' + readFileSync(new URL('../renderer/office/reading-room.jpg', import.meta.url)).toString('base64');
const photos = ['one', 'two', 'three', 'four'].map(id => ({ id, name: id + '.jpg', data, fit: 'contain' }));
const outline = { slides: ['cover', 'image', 'conclusion'].map(layout => ({ title: layout, layout })) };

test('intake round-trips photos, binds author text and allocates explicit counts first', async () => {
  const draft = { ...newDeck(), brief: '封面 0 张照片；说明页 1 张照片', pendingPhotos: photos,
    source: 'three.jpg | credit A\nfour | credit B https://example.com/4', photoInput: { title: '我的标题', copy: '保留的正文。' } };
  const deck = outlineDeck(readDeck(draft), outline, 3);
  assert.equal(deck.pendingPhotos, undefined);
  assert.deepEqual(deck.slides.map(s => s.photos?.map(p => p.id) ?? []), [[], ['one','two','three'], ['four']]);
  assert.equal(deck.slides[0].title, draft.photoInput.title);
  const last = deck.slides[2];
  const written = applyBody(deck, last, { items: [{ ...last.items[0], text: '替代' }], notes: 'agent notes' });
  assert.equal(written.slides[2].items[0].text, draft.photoInput.copy);
  assert.deepEqual(photoCredits(deck.source, last.photos), ['four | credit B https://example.com/4']);
  const native = await zip.loadAsync(await powerPoint(written));
  const notes = await native.file('ppt/notesSlides/notesSlide3.xml').async('string');
  assert.match(notes, /agent notes/);
  assert.match(notes, /four \| credit B https:\/\/example.com\/4/);
  assert.doesNotMatch(notes, /credit A/);
  assert.deepEqual(outlineDeck(written, outline, 3).slides[2].photos, last.photos);
});

test('open pages share assets in order, impossible counts preserve the input for retry', () => {
  const pages = outline.slides;
  assert.deepEqual(distributePhotos(pages, photos, '').map(s => s.photos.length), [2, 1, 1]);
  assert.throws(() => distributePhotos(pages, photos, '封面 5 张照片'), /总数/);
  assert.throws(() => distributePhotos(pages.slice(0, 1), photos, '作品页 1 张照片'), /缺少/);
  assert.deepEqual(photos.map(p => p.id), ['one','two','three','four']);
  assert.throws(() => readDeck({ ...newDeck(), pendingPhotos: [{ data: '' }] }), /无效/);
});

test('paired catalogue titles follow picture order and measured orientations on the comparison page', async () => {
  const { catalogueComparison } = await import('../electron/office/photos.mjs');
  const { composition, generatedBody } = await import('../electron/office/deck.mjs');
  const sample = name => 'data:image/jpeg;base64,' + readFileSync(
    new URL('../../evals/presentation/photo-pilot/media/' + name + '.jpg', import.meta.url)).toString('base64');
  const pendingPhotos = [
    { id: 'vertical', name: 'portrait.jpg', data: sample('260348') },
    { id: 'horizontal', name: 'landscape.jpg', data: sample('260089') },
  ];
  const draft = { ...newDeck(), photoInput: { title: '', copy: '' }, pendingPhotos, brief: '比较画幅',
    source: 'landscape | B | Cedars | 1857 | https://example.com/b\nportrait | A | Sitters | 1870s | https://example.com/a' };
  const deck = outlineDeck(draft, { slides: [{ title: '比较', layout: 'comparison' }] }, 1);
  assert.equal(distributePhotos(outline.slides.concat({ layout: 'comparison' }), pendingPhotos, '比较页两张照片').at(-1).photos.length, 2);
  const slide = deck.slides[0];
  const body = catalogueComparison(deck, slide);
  assert.deepEqual(body.items.map(({ label, text }) => [label, text]), [['竖幅', 'Sitters'], ['横幅', 'Cedars']]);
  assert.equal(catalogueComparison({ ...deck, source: 'Free prose without catalogue rows' }, slide), undefined);
  const generated = readDeck(applyBody(deck, slide, generatedBody(slide, body)));
  assert.equal(generated.design.slidePlans[0].variant, 'photo-comparison');
  const objects = composition(generated.slides[0], 1, 1, generated.theme, generated.design);
  for (const [i, picture] of objects.filter(o => o.type === 'image').entries()) {
    const text = objects.find(o => o.field === 'text-' + i);
    assert.ok(text.y > picture.y + picture.h);
    assert.ok(picture.x + picture.w / 2 >= text.x && picture.x + picture.w / 2 <= text.x + text.w);
  }
});
