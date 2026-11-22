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
