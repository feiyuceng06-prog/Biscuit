// The canvas and PowerPoint share a 960 × 540 point coordinate system.
export const layouts = Object.freeze({
  cover: '封面',
  conclusion: '结论',
  image: '图文',
  comparison: '对比',
  chart: '数据图表',
  timeline: '时间线',
});
export const maxItems = (layout) => ({ cover: 1, comparison: 2, image: 3 })[layout] ?? 4;
export const uid = () => globalThis.crypto.randomUUID();
const clean = (str, max) => (typeof str === 'string' ? str.trim().slice(0, max) : '');
export const blankItem = () => ({ id: uid(), label: '', text: '', value: 0 });
export function newSlide(title = '新的一页', layout = 'conclusion') {
  return {
    id: uid(),
    title,
    layout,
    items: [blankItem()],
    notes: '',
    image: '',
    revision: 0,
    generated: false,
  };
}
export function newDeck() {
  return {
    version: 1,
    id: uid(),
    title: '未命名演示文稿',
    source: '',
    brief: '',
    slides: [newSlide('演示文稿标题', 'cover')],
  };
}
export function outlineDeck(draft, result, count) {
  if (!Array.isArray(result?.slides) || result.slides.length !== count)
    throw Error('大纲页数与要求不符');
  const slides = result.slides.map((row) => {
    if (!Object.hasOwn(layouts, row?.layout) || !clean(row.title, 120)) throw Error('大纲格式不完整');
    return newSlide(clean(row.title, 120), row.layout);
  });
  return { ...draft, title: clean(result.title, 120) || slides[0].title, slides };
}
export function generatedBody(slide, result) {
  if (!Array.isArray(result?.items) || !result.items.length) throw Error('模型没有返回页面正文');
  const items = result.items.slice(0, maxItems(slide.layout)).map((row) => {
    if (!row || (!clean(row.label, 60) && !clean(row.text, 220))) throw Error('模型返回了空白内容');
    if (slide.layout === 'chart' && !Number.isFinite(row.value)) throw Error('图表缺少有效数值');
    return {
      id: uid(),
      label: clean(row.label, 60),
      text: clean(row.text, 220),
      value: Number.isFinite(row.value) ? row.value : 0,
    };
  });
  return { items, notes: clean(result.notes, 1200) };
}
// Only replace the requested body. Title changes can coexist with a pending request.
export function applyBody(deck, original, body) {
  const current = deck.slides.find((s) => s.id === original.id);
  if (!current || current.revision !== original.revision || current.layout !== original.layout)
    return deck;
  return {
    ...deck,
    slides: deck.slides.map((s) =>
      s.id === current.id ? { ...s, ...body, revision: s.revision + 1, generated: true } : s,
    ),
  };
}
export function readDeck(raw) {
  const fail = () => {
    throw Error('演示文稿文件格式无效或超出限制');
  };
  const string = (s, n) => typeof s === 'string' && s.length <= n;
  const ids = new Set();
  const id = (s) => {
    if (!string(s, 80) || !s || ids.has(s)) fail();
    ids.add(s);
  };
  if (
    raw?.version !== 1 ||
    !string(raw.title, 120) ||
    !string(raw.source, 30000) ||
    !string(raw.brief, 1500) ||
    !Array.isArray(raw.slides) ||
    !raw.slides.length ||
    raw.slides.length > 20
  )
    fail();
  id(raw.id);
  let imageBytes = 0;
  for (const s of raw.slides) {
    if (
      !s ||
      typeof s.layout !== 'string' ||
      !Object.hasOwn(layouts, s.layout) ||
      !string(s.title, 120) ||
      !string(s.notes, 1200) ||
      !Number.isSafeInteger(s.revision) ||
      s.revision < 0 ||
      typeof s.generated !== 'boolean' ||
      !Array.isArray(s.items) ||
      s.items.length < 1 ||
      s.items.length > 4 ||
      !string(s.image, 3_000_000) ||
      (s.image && !/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+=*$/.test(s.image))
    )
      fail();
    id(s.id);
    imageBytes += s.image.length;
    for (const row of s.items) {
      if (!row || !string(row.label, 60) || !string(row.text, 220) || !Number.isFinite(row.value))
        fail();
      id(row.id);
    }
  }
  if (imageBytes > 12_000_000) fail();
  return raw;
}

const ink = '172F37',
  teal = '007E75',
  grey = '476269',
  pale = 'E0EEE9',
  white = 'FFFFFF';
export function composition(slide, page, total) {
  const cover = slide.layout === 'cover';
  const objects = [];
  const rect = (x, y, w, h, color) => objects.push({ type: 'rect', x, y, w, h, color });
  function text(x, y, w, h, value, size, color = ink, bold = false, field = null) {
    if (!value) return;
    // Reserve room for wraps in both Chinese and Latin scripts, in the editor and export.
    const lines = (font) =>
      String(value)
        .split('\n')
        .reduce((n, line) => {
          const units = Array.from(line).reduce(
            (sum, c) => sum + (c.charCodeAt(0) < 128 ? 0.6 : 1.05),
            0,
          );
          return n + Math.max(1, Math.ceil((units * font) / w));
        }, 0);
    while (size > 8 && lines(size) * size * 1.35 > h) size--;
    objects.push({ type: 'text', x, y, w, h, value, size, color, bold, field });
  }
  const items = slide.items.slice(0, maxItems(slide.layout));
  rect(0, 0, 960, 540, cover ? ink : 'F9FBF8');
  rect(52, 46, 44, 5, cover ? '7ED6BC' : teal);
  text(
    52,
    cover ? 128 : 76,
    855,
    cover ? 150 : 95,
    slide.title,
    cover ? 55 : 40,
    cover ? white : ink,
    true,
    'title',
  );
  if (cover) {
    text(55, 296, 806, 46, items[0]?.label, 24, 'C2DFD8', true, 'label-0');
    text(55, 348, 806, 95, items[0]?.text, 23, 'C2DFD8', false, 'text-0');
  } else if (slide.layout === 'chart') {
    objects.push({ type: 'chart', x: 60, y: 178, w: 833, h: 283, items });
  } else if (slide.layout === 'comparison') {
    items.forEach((row, i) => {
      const x = 52 + i * 442;
      rect(x, 185, 414, 245, i ? pale : ink);
      text(x + 24, 210, 365, 65, row.label, 29, i ? ink : white, true, 'label-' + i);
      text(x + 24, 287, 365, 125, row.text, 22, i ? grey : 'D3EAE1', false, 'text-' + i);
    });
  } else if (slide.layout === 'timeline') {
    const step = 845 / items.length;
    rect(59, 232, Math.max(10, (items.length - 1) * step), 3, teal);
    items.forEach((row, i) => {
      const x = 55 + i * step;
      rect(x, 225, 16, 16, teal);
      text(x, 260, step - 16, 70, row.label, 24, ink, true, 'label-' + i);
      text(x, 336, step - 16, 110, row.text, 18, grey, false, 'text-' + i);
    });
  } else {
    const hasImage = slide.layout === 'image' && slide.image;
    const width = hasImage ? 445 : 846;
    const step = 286 / items.length;
    items.forEach((row, i) => {
      const y = 181 + i * step;
      rect(53, y + 4, 4, step - 15, teal);
      text(73, y, width - 20, step * 0.39, row.label, 25, ink, true, 'label-' + i);
      text(73, y + step * 0.4, width - 20, step * 0.56, row.text, 20, grey, false, 'text-' + i);
    });
    if (hasImage) {
      rect(548, 184, 359, 270, pale);
      objects.push({ type: 'image', x: 548, y: 184, w: 359, h: 270, data: slide.image });
    }
  }
  text(842, 492, 68, 26, String(page) + ' / ' + total, 13, cover ? 'BBD8CF' : grey);
  return objects;
}
