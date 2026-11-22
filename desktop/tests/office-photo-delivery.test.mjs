import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { blankItem, newDeck, newSlide } from '../electron/office/deck.mjs';
import { deliverPhotography } from '../electron/office/photo-delivery.mjs';
import { powerPoint } from '../electron/office/pptx.mjs';

const zip = createRequire(createRequire(import.meta.url).resolve('pptxgenjs'))('jszip');
const root = fileURLToPath(new URL('../..', import.meta.url));
const backend = { command: process.env.PYTHON || 'python3',
  args: ['-c', 'import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("feiyu", run_name="__main__")', root] };
const available = (command, args) => spawnSync(command, args, { cwd: root, windowsHide: true }).status === 0;
const renderer = !available('soffice', ['--version']) || !available('pdftotext', ['-v'])
  || !available('pdftoppm', ['-v']) || !available('pdffonts', ['-v'])
  || !available(backend.command, ['-c', 'import feiyu, PIL'])
  ? 'requires LibreOffice, Poppler and the Python backend' : false;
const image = 'data:image/jpeg;base64,' + await fs.readFile(new URL('../renderer/office/reading-room.jpg', import.meta.url), 'base64');
const photos = count => Array.from({ length: count }, (_, i) => ({
  id: 'print-' + i, data: image, name: 'Print ' + i, caption: '晨光下的书页与回声',
  fit: i ? 'contain' : 'cover', focus: { x: 0.85, y: 0.18 },
}));
const row = (label, text, value = 0) => ({ ...blankItem(), label, text, value });
const slide = (layout, title, items, pictures = []) => ({
  ...newSlide(title, layout), items, photos: pictures, notes: '馆藏来源和拍摄者附注。',
});
const deck = (...slides) => ({
  ...newDeck(), slides, design: { version: 2, preferences: { direction: 'photography' } },
});
const json = async file => JSON.parse(await fs.readFile(file, 'utf8'));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const spread = '潮水　海岸　礁石　船只　'.repeat(10);
const wide = 'ＴＨＥ　ＣＯＡＳＴＬＩＮＥ　'.repeat(6);
const allText = xml => [...xml.matchAll(/<a:t>(.*?)<\/a:t>/gs)].map(match => match[1]);
const picturesIn = xml => xml.match(/<p:pic>.*?<\/p:pic>/gs);

async function target(t) {
  const archive = process.env.BISCUIT_PHOTO_TEST_OUTPUT;
  const dir = await fs.mkdtemp(path.join(archive || os.tmpdir(), 'biscuit-photo-delivery-'));
  if (!archive) t.after(() => fs.rm(dir, { recursive: true, force: true }));
  return path.join(dir, '作品.pptx');
}

test('actual Chinese text is re-rendered after one local fix and one photographic layout fallback',
  { skip: renderer, timeout: 60000 }, async t => {
    const work = slide('image', spread, [row('来源', spread.repeat(2).slice(0, 220))], photos(3));
    const essay = slide('conclusion', wide, [row('来源', wide.repeat(2).slice(0, 220))]);
    const chart = slide('chart', 'Exhibition attendance', [row('Spring', '', 0), row('Autumn', '', 18)]);
    chart.unit = 'visitors';
    const input = deck(work, essay, chart);
    const snapshot = structuredClone(input);
    const destination = await target(t);
    const prior = await powerPoint(deck(slide('cover', '之前的文稿', [row('原始标题', '')], photos(1))));
    await fs.writeFile(destination, prior);
    const result = await deliverPhotography(destination, input, { backend });
    assert.deepEqual(await fs.readFile(result.previousPptx), prior);
    const report = await json(result.report);
    assert.equal(result.destination, destination, result.failureReason);
    assert.equal(result.repairAttempts, 2);
    assert.equal(result.failureReason, null);
    assert.equal(report.unresolvedIssues.length, 0);
    assert.deepEqual(report.rounds.map(({ stage, accepted }) => [stage, accepted]),
      [['initial', true], ['local', true], ['fallback', true]]);
    assert.equal(report.initialPptx, result.initialPptx);
    assert.equal(report.finalPptx, result.finalPptx);
    assert.deepEqual(input, snapshot);
    for (const round of report.rounds) {
      assert.ok(round.durationMs > 0);
      const review = await json(round.report);
      assert.equal(sha256(await fs.readFile(round.pptx)), review.pptxSha256);
      assert.equal(review.pages.length, input.slides.length);
      for (const page of review.pages)
        assert.equal(sha256(await fs.readFile(path.join(path.dirname(round.report), page.png))), page.sha256);
    }
    const initial = await json(result.initialReport);
    assert.ok(initial.issues.some(issue => issue.kind === 'clipping' && issue.slideId === work.id
      && issue.elementIds.includes('title')));
    assert.ok(initial.issues.some(issue => issue.kind === 'clipping' && issue.slideId === essay.id
      && issue.elementIds.includes('text-0')));
    const local = await json(report.rounds[1].report);
    assert.ok(local.issues.some(issue => issue.slideId === work.id && issue.elementIds.includes('title')));
    assert.ok(local.issues.every(issue => issue.slideId !== essay.id));
    assert.ok(report.pages.every(page => page.png.startsWith('fallback/review/')));
    assert.equal(sha256(await fs.readFile(path.join(path.dirname(result.report), report.pdf))), report.pdfSha256);

    const published = await fs.readFile(result.destination);
    assert.deepEqual(published, await fs.readFile(result.finalPptx));
    const before = await zip.loadAsync(await fs.readFile(result.initialPptx));
    const after = await zip.loadAsync(published);
    for (const i of [1, 2, 3]) {
      const file = 'ppt/slides/slide' + i + '.xml';
      const first = await before.file(file).async('string');
      const final = await after.file(file).async('string');
      assert.deepEqual(allText(first), allText(final));
      assert.deepEqual(picturesIn(first), picturesIn(final));
      const notes = 'ppt/notesSlides/notesSlide' + i + '.xml';
      assert.equal(await before.file(notes).async('string'), await after.file(notes).async('string'));
    }
    const [firstChart] = before.file(/^ppt\/charts\/chart\d+\.xml$/);
    const [finalChart] = after.file(/^ppt\/charts\/chart\d+\.xml$/);
    assert.equal(await firstChart.async('string'), await finalChart.async('string'));
    const [workbook] = after.file(/^ppt\/embeddings\/.*\.xlsx$/);
    const embedded = await zip.loadAsync(await workbook.async('nodebuffer'));
    const worksheet = await embedded.file('xl/worksheets/sheet1.xml').async('string');
    assert.match(worksheet, /<c r="B2"[^>]*><v>0<\/v><\/c>/);
    const media = Object.keys(before.files).filter(file => /^ppt\/media\/.+\.jpeg$/.test(file));
    assert.ok(media.length > 0);
    for (const file of media)
      assert.deepEqual(await before.file(file).async('nodebuffer'), await after.file(file).async('nodebuffer'));
  });

test('real overflow with no safe layout retains a draft and an existing valid target',
  { skip: renderer, timeout: 60000 }, async t => {
    const destination = await target(t);
    const good = await powerPoint(deck(slide('cover', '开罗的尼罗河岸', [row('馆藏', '')], photos(1))));
    await fs.writeFile(destination, good);
    const title = '在漫长的冬季沿着寂静的海岸寻找逐渐消退的潮水，以及从雾中浮现出的山脊与村落'.repeat(2);
    const copy = '潮水退去之后，海岸露出柔软的纹理。我们沿着层层堆积的岩石缓慢前行，把镜头转向远方。日落之前，水上的微光从灰蓝变成深紫，远处的船只只留下安静的剪影。'.repeat(2);
    const label = '海岸　海岸　海岸　海岸　海岸　海岸　海岸　海岸';
    const gallery = photos(12).map(photo => ({ ...photo, caption: label.repeat(3).slice(0, 160) }));
    const input = deck(slide('image', title, gallery.slice(0, 4).map(() => row(label, copy)), gallery));
    const result = await deliverPhotography(destination, input, { backend });
    const report = await json(result.report);
    assert.equal(result.status, 'draft');
    assert.equal(result.requestedDestination, destination);
    assert.equal(result.destination, result.finalPptx);
    assert.equal(path.basename(result.destination), 'draft.pptx');
    assert.deepEqual(await fs.readFile(destination), good);
    assert.ok(result.repairAttempts <= 2);
    assert.ok(report.issues.some(issue => issue.source === 'deterministic' && issue.kind === 'overflow'));
    for (let i = 0; i < gallery.length; i++)
      assert.ok(report.issues.some(issue => issue.source === 'deterministic'
        && ['clipping', 'overflow'].includes(issue.kind) && issue.elementIds.includes('caption-' + i)),
        'Unresolved dense caption ' + i + ' must be reported');
    assert.ok(report.unresolvedIssues.length);
    assert.match(result.failureReason, /Unresolved deterministic findings/);
    assert.equal(sha256(await fs.readFile(result.finalPptx)), report.pptxSha256);
  });

test('unavailable preflight leaves an explicit draft without publishing the initial PPTX', async t => {
  const destination = await target(t);
  const input = deck(slide('cover', '开罗的尼罗河岸', [row('馆藏', '')], photos(1)));
  const result = await deliverPhotography(destination, input, { backendError: 'Review worker unavailable' });
  assert.equal(result.status, 'draft');
  assert.equal(result.reviewStatus, 'preview_unavailable');
  assert.equal(result.failureReason, 'Review worker unavailable');
  assert.equal(result.repairAttempts, 0);
  await assert.rejects(fs.access(destination), { code: 'ENOENT' });
  assert.deepEqual(await fs.readFile(result.initialPptx), await fs.readFile(result.finalPptx));
});
