import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { applyBody, blankItem, composition, generatedBody, newDeck, newSlide, readDeck } from '../electron/office/deck.mjs';
import { planDesign } from '../electron/office/director.mjs';
import { photoCounts, pictureObject } from '../electron/office/photos.mjs';
import { powerPoint } from '../electron/office/pptx.mjs';
import { reviewManifest } from '../electron/office/review.mjs';

const zip = createRequire(createRequire(import.meta.url).resolve('pptxgenjs'))('jszip');
const source = readFileSync(new URL('../renderer/office/reading-room.jpg', import.meta.url));
const data = 'data:image/jpeg;base64,' + source.toString('base64');
const series = count => Array.from({ length: count }, (_, i) => ({
  id: 'photo-' + (i + 1), data, name: 'Print ' + (i + 1), caption: 'Plate ' + (i + 1), fit: 'cover',
}));
const row = (label, text, value = 0) => ({ ...blankItem(), label, text, value });
const page = (layout, title, items, photos = []) => ({ ...newSlide(title, layout), items, photos });
const deck = (...slides) => ({
  ...newDeck(), title: 'Where the Water Turns', brief: 'Use five photographs on the cover.',
  slides, design: { version: 2, preferences: { direction: 'photography' } },
});
const cover = (title = 'Where the Water Turns') =>
  page('cover', title, [row('Study in five prints', 'A study of the winter shoreline')], series(5));
const objects = (document, i = 0) =>
  composition(document.slides[i], i + 1, document.slides.length, document.theme, document.design);
const pictures = (document, i) => objects(document, i).filter(o => o.type === 'image');

test('the five-photo cover has centered editable type, equal gaps and independently bound photos', () => {
  const document = readDeck(deck(cover()));
  const [plan] = document.design.slidePlans;
  assert.equal(plan.variant, 'photo-cover');
  assert.equal(plan.focalPoint, 'photo-2');
  assert.deepEqual(plan.assetStrategy.photoCount, { requested: 5, actual: 5 });
  assert.deepEqual(plan.assetStrategy.photos.map(o => o.photoId), document.slides[0].photos.map(p => p.id));

  const actual = pictures(document);
  assert.deepEqual(actual.map(({ x, y, w, h }) => [x, y, w, h]), [
    [94, 221.5, 86, 157], [187, 193, 168, 214], [362, 163, 236, 274],
    [605, 193, 168, 214], [780, 221.5, 86, 157],
  ]);
  assert.equal(objects(document)[0].color, 'F7F3F2');
  const title = objects(document).find(o => o.field === 'title');
  assert.deepEqual([title.fontFace, title.italic, title.align], ['Liberation Serif', true, 'center']);
  assert.ok(objects(document).some(o => o.value === 'A study of the winter shoreline' && o.field === 'text-0'));
  const captions = objects(document).filter(o => o.field?.startsWith('caption-'));
  assert.deepEqual(captions.map(o => o.value), series(5).map(p => p.caption));
  assert.ok(captions.every(o => o.y > 437 && o.size <= 11));
});

test('the work and essay pages use distinct structures, and long titles get additional space', () => {
  const longTitle = 'Walking the winter shoreline from tidal pools to the last light beyond the rocks';
  const work = page('image', 'After the tide', [row('', '')], series(1));
  const essay = page('conclusion', 'On returning', [row('In the field', 'I waited at the same point on successive evenings.')]);
  const document = readDeck(deck(cover(), work, essay, cover(longTitle)));
  assert.deepEqual(document.design.slidePlans.map(plan => plan.variant), ['photo-cover', 'photo-work', 'photo-essay', 'photo-cover']);
  const headline = i => objects(document, i).find(o => o.field === 'title');
  const artwork = pictures(document, 1)[0];
  assert.ok(artwork.y + artwork.h < headline(1).y);
  assert.ok(headline(2).x + headline(2).w < objects(document, 2).find(o => o.field === 'text-0').x);
  assert.equal(headline(3).value, longTitle);
  assert.ok(headline(3).h > headline(0).h);
  assert.ok(headline(3).size < headline(0).size);
  assert.ok(headline(3).y + headline(3).h < pictures(document, 3)[2].y);
  assert.equal(document.design.slidePlans[3].contentEditProposal, undefined);
});

test('the planner tracks scoped requests without inventing missing photos', () => {
  assert.deepEqual(photoCounts('封面中央 ５ 张独立照片；作品页用两幅黑白摄影；说明页放 0 张照片。'),
    { cover: 5, image: 2, conclusion: 0 });
  assert.deepEqual(photoCounts('Cover: five portrait photographs, work page: two images.'), { cover: 5, image: 2 });
  assert.deepEqual(photoCounts('Use one photo on the cover and seven photos on the gallery slide.'), { cover: 1, image: 7 });
  assert.deepEqual(photoCounts('A five-photo cover'), { cover: 5 });
  assert.deepEqual(photoCounts('A five-page presentation with 5 cm borders.'), {});
  assert.deepEqual(photoCounts('Use two or three photos. Use 13 photos on the cover.'), {});
  assert.equal(planDesign({ ...newDeck(), brief: 'Make a six-photo cover.' }, {}, { visualPlanner: true }).direction, 'photography');
  const draft = deck(cover());
  draft.brief = 'Make a six-photo cover.';
  draft.slides[0].photos = series(3);
  const document = readDeck(draft);
  assert.deepEqual(document.design.slidePlans[0].assetStrategy.photoCount, { requested: 6, actual: 3 });
  assert.equal(pictures(document).length, 3);
});

test('covers place every supported photo count in order without overlapping frames', () => {
  for (let count = 1; count <= 12; count++) {
    const slide = { ...cover(), photos: series(count) };
    const document = deck(slide);
    document.design = planDesign(document, document.design.preferences, { visualPlanner: true });
    const frames = pictures(document);
    assert.deepEqual(frames.map(o => o.photoId), slide.photos.map(p => p.id));
    for (const [i, frame] of frames.entries()) {
      const { x, y, w, h } = frame;
      assert.ok(x >= 94 && x + w <= 866.001 && y >= 162 && y + h <= 478.001 && w > 0 && h > 0);
      assert.ok(frames.slice(i + 1).every(other => x + w <= other.x || y + h <= other.y));
    }
  }
});

test('both fit modes preserve source proportions and crop offsets follow bounded focal points', () => {
  const frame = { x: 12, y: 15, w: 80, h: 160 };
  const contained = pictureObject(frame, data);
  assert.equal(contained.w / contained.h, 1077 / 810);
  assert.equal(contained.crop, undefined);
  assert.equal(contained.y + contained.h / 2, frame.y + frame.h / 2);
  const left = pictureObject(frame, data, 'cover', { x: 0, y: 1 });
  const right = pictureObject(frame, data, 'cover', { x: 1, y: 0 });
  assert.equal(left.crop.x, 0);
  assert.equal(right.crop.x + right.crop.w, 1);
  assert.equal(right.crop.y, 0);
  assert.ok(Math.abs((right.crop.w * 1077) / (right.crop.h * 810) - frame.w / frame.h) < 1e-12);
  const lower = pictureObject({ ...frame, w: 320, h: 40 }, data, 'cover', { x: 0.5, y: 1 });
  assert.equal(lower.crop.w, 1);
  assert.equal(lower.crop.y + lower.crop.h, 1);
});

test('opening validates photo data and keeps legacy slides, notes, order and editable chart values', () => {
  const chart = page('chart', 'Change in attendance', [row('Afternoon', 'From the register', -3), row('Morning', '', 0)], series(12));
  chart.image = data;
  chart.unit = 'visits';
  chart.notes = 'Source: daily register.';
  const incoming = deck(chart, cover());
  incoming.slides[1].photos.reverse();
  const reopened = readDeck(JSON.parse(JSON.stringify(incoming)));
  assert.deepEqual(pictures(reopened, 1).map(o => o.photoId), incoming.slides[1].photos.map(p => p.id));
  assert.equal(pictures(reopened, 0).length, 13);
  const chartObjects = objects(reopened);
  assert.deepEqual(chartObjects.find(o => o.type === 'chart').items.map(o => o.value), [-3, 0]);
  assert.ok(chartObjects.some(o => o.value === chart.unit));
  assert.ok(chartObjects.some(o => o.value === 'From the register'));
  assert.equal(reopened.slides[0].notes, chart.notes);
  assert.ok(chartObjects.every(o => o.w > 0 && o.h > 0 && o.x >= 0 && o.y >= 0 && o.x + o.w <= 960 && o.y + o.h <= 540));
  const result = generatedBody(chart, { items: [{ label: 'Morning', value: 2 }], photos: [{ data: 'invented' }] });
  assert.deepEqual(applyBody(reopened, chart, result).slides[0].photos, chart.photos);

  const legacy = newDeck();
  legacy.brief = 'A photography portfolio with five pictures on the cover.';
  legacy.slides[0].image = data;
  assert.equal(readDeck(legacy), legacy);
  assert.equal(planDesign(legacy).version, 1);
  assert.equal(planDesign(legacy, {}, { visualPlanner: true }).direction, 'photography');
  const { design, ...unplanned } = incoming;
  assert.equal(readDeck(unplanned).design.version, 2);
  assert.equal(readDeck({ ...unplanned, design: { version: 1, preferences: { direction: 'editorial' } } }).design.direction, 'editorial');
  for (const photos of [
    null, series(13), [{ ...series(1)[0], data: 'file:///private/photo.jpg' }],
    [{ ...series(1)[0], data: 'data:image/png;base64,AABBCCDD' }],
    [{ ...series(1)[0], data: data.replace('jpeg', 'png') }],
    [{ ...series(1)[0], focus: { x: -0.5, y: 1 } }],
    [{ ...series(1)[0], fit: 'stretch' }],
    [series(1)[0], series(1)[0]],
  ]) assert.throws(() => readDeck(deck({ ...cover(), photos })), /格式无效/);
  const base64 = data.slice(data.indexOf(',') + 1).replace(/=+$/, '');
  const large = 'data:image/jpeg;base64,' + base64.padEnd(2_499_996, 'A');
  const largePhotos = series(5).map(p => ({ ...p, data: large }));
  assert.throws(() => readDeck(deck({ ...cover(), photos: largePhotos })), /超出限制/);
});

test('crop geometry and typography export natively and the preflight manifest carries no embedded data', async () => {
  const first = cover();
  first.photos[0].focus = { x: 1, y: 0 };
  first.photos[4].fit = 'contain';
  const document = readDeck(deck(first));
  const archive = await zip.loadAsync(await powerPoint(document));
  const xml = await archive.file('ppt/slides/slide1.xml').async('string');
  const native = Array.from(xml.matchAll(/<p:pic>(.*?)<\/p:pic>/gs), ([, picture]) => picture);
  const manifest = reviewManifest(document);
  const rendered = manifest.slides[0].objects.filter(o => o.type === 'image');
  assert.equal(native.length, 5);
  assert.equal(rendered.length, native.length);
  assert.match(xml, /<a:rPr\b[^>]*\bi="1"[^>]*>.*?<a:latin typeface="Liberation Serif".*?<a:t>Where the Water Turns<\/a:t>/s);
  for (const [i, picture] of native.entries()) {
    const item = rendered[i];
    assert.equal(item.id, 'photo:' + first.photos[i].id);
    assert.ok(!('data' in item));
    assert.match(picture, new RegExp('name="Print ' + (i + 1) + '"'));
    assert.match(picture, new RegExp('descr="Plate ' + (i + 1) + '"'));
    const [, x, y, w, h] = /<a:off x="(\d+)" y="(\d+)"\/>\s*<a:ext cx="(\d+)" cy="(\d+)"\/>/.exec(picture);
    for (const [key, value] of Object.entries({ x, y, w, h })) assert.ok(Math.abs(+value / 12700 - item[key]) < 0.001);
    const crop = /<a:srcRect l="(-?\d+)" r="(-?\d+)" t="(-?\d+)" b="(-?\d+)"\/>/.exec(picture);
    if (item.crop) {
      const { x, y, w, h } = item.crop;
      const expected = [x, 1 - x - w, y, 1 - y - h].map(value => Math.round(value * 100000));
      assert.deepEqual(crop.slice(1).map(Number), expected);
    } else {
      assert.equal(crop, null);
    }
  }
  const media = Object.keys(archive.files).filter(name => /^ppt\/media\/.+\.jpeg$/.test(name));
  assert.ok(media.length >= 1);
  for (const name of media) assert.deepEqual(await archive.file(name).async('nodebuffer'), source);
});

test('the cover credit follows the tallest image and a photo essay groups its title with its copy', () => {
  const first = cover();
  first.photos = first.photos.map(photo => ({ ...photo, caption: '' }));
  const last = page('conclusion', 'A low horizon', [row('The sky', 'The ships occupy a narrow band.')], series(1));
  const document = readDeck(deck(first, last));
  const coverObjects = objects(document, 0);
  const tallestEdge = Math.max(...pictures(document, 0).map(photo => photo.y + photo.h));
  const credit = coverObjects.find(object => object.field === 'label-0');
  assert.ok(credit.y >= tallestEdge && credit.y - tallestEdge <= 18);
  for (const field of ['title', 'text-0', 'label-0']) {
    const run = coverObjects.find(object => object.field === field);
    assert.equal(run.italic, true);
    assert.equal(run.fontFace, 'Liberation Serif');
  }
  const essay = objects(document, 1);
  const heading = essay.find(object => object.field === 'title');
  const body = essay.find(object => object.field === 'text-0');
  const photo = pictures(document, 1)[0];
  assert.ok(photo.x + photo.w < heading.x);
  assert.ok(body.x >= heading.x && body.y >= heading.y + heading.h);
});
