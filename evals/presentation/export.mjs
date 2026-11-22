// Freeze the model boundary; use the same exporter as presentation_save.
import fs from 'node:fs/promises';
import path from 'node:path';
import { powerPoint } from '../../desktop/electron/office/pptx.mjs';
import { libraryExample } from '../../desktop/renderer/office/library-example.mjs';
import { newDeck, newSlide } from '../../desktop/electron/office/deck.mjs';

const out = process.argv[2];
await fs.mkdir(out, {recursive: true});
const briefs = JSON.parse(await fs.readFile(new URL('./briefs.json', import.meta.url)));
const photo = 'data:image/jpeg;base64,' + await fs.readFile(new URL('../../desktop/renderer/office/reading-room.jpg', import.meta.url), 'base64');
for (const [id, brief, layout, theme, title, items, unit] of briefs) {
  const deck = layout === 'library' ? libraryExample(photo) : {
    ...newDeck(), theme, title, brief, source: '虚构测试材料：' + JSON.stringify(items),
    slides: [{ ...newSlide(title, layout), unit, generated: true,
      image: id === 'brand' ? photo : id === 'exception' ? 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGPcHGvEwMDAxMDAwMDAAAAPwwFGQrk+RwAAAABJRU5ErkJggg==' : '',
      items: items.map(([label, text, value = 0]) => ({label, text, value})) }],
  };
  deck.id = id;
  deck.slides.forEach((s, n) => {
    s.id = id + '-' + (n + 1);
    s.items.forEach((item, i) => { item.id = s.id + '-' + (i + 1); });
  });
  const start = performance.now();
  const bytes = await powerPoint(deck);
  const ms = Math.round(performance.now() - start);
  await fs.writeFile(path.join(out, id + '.pptx'), bytes);
  await fs.writeFile(path.join(out, id + '.json'), JSON.stringify(deck));
  console.log(id, deck.slides.length, ms);
}
