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
    (raw.theme !== undefined && (typeof raw.theme !== 'string' || !Object.hasOwn(themes, raw.theme))) ||
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

export const themes = {
  paper: {
    name: '白纸',
    bg: 'FFFFFF',
    ink: '202122',
    soft: '57595A',
    tint: 'F0F0ED',
    rule: 'D5D6D1',
    accent: '344EAE',
  },
  sand: {
    name: '陶土',
    bg: 'FBF6ED',
    ink: '362B26',
    soft: '655549',
    tint: 'F1E2D0',
    rule: 'D7BC9F',
    accent: 'A64930',
  },
  midnight: {
    name: '午夜',
    bg: '1C2028',
    ink: 'F4F2EB',
    soft: 'B5BBCA',
    tint: '2A303D',
    rule: '545D70',
    accent: 'AEBBF5',
  },
};
export function composition(slide, page, total, theme = 'paper') {
  const { bg, ink, soft, tint, rule, accent } = themes[theme] || themes.paper;
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
  rect(0, 0, 960, 540, bg);
  const ellipse = (x, y, w, h, color, outline = false) =>
    objects.push({ type: 'ellipse', x, y, w, h, color, outline });
  const title = (x, y, w, h, size) => text(x, y, w, h, slide.title, size, ink, true, 'title');
  const body = (row, i, x, y, w, h, size) => text(x, y, w, h, row.text, size, soft, false, 'text-' + i);
  const label = (row, i, x, y, w, h, size) => text(x, y, w, h, row.label, size, ink, true, 'label-' + i);
  if (slide.layout === 'cover' && theme === 'paper') {
    text(116, 110, 728, 48, items[0].label, 18, soft, false, 'label-0');
    title(70, 179, 820, 131, 61);
    body(items[0], 0, 108, 323, 744, 115, 24);
    for (const object of objects) if (object.type === 'text') object.align = 'center';
  } else if (slide.layout === 'cover') {
    rect(615, 0, 345, 540, tint);
    if(theme==='midnight') {
      ellipse(645,115,277,277,rule,true);
      ellipse(676,146,215,215,rule,true);
      ellipse(710,180,147,147,accent,true);
      ellipse(872,135,14,14,accent);
      ellipse(765,236,37,37,accent);
    } else {
      for (let i = 0; i < 10; i++)
        ellipse(640 + i * 13, 76 + i * 8, 282 - i * 13, 365 - i * 16, accent, true);
    }
    text(55, 66, 505, 60, items[0]?.label, 18, accent, true, 'label-0');
    title(52, 153, 523, 175, 58);
    body(items[0], 0, 55, 350, 515, 105, 24);
  } else if (slide.layout === 'conclusion') {
    title(52, 57, 355, 346, 46);
    const step = 382 / items.length;
    items.forEach((r, i) => {
      const y = 65 + i * step;
      rect(445, y, 457, 1, rule);
      label(r, i, 445, y + 10, 457, step * 0.35, 25);
      body(r, i, 445, y + step * 0.4 + 5, 457, step * 0.55 - 4, 21);
    });
  } else {
    title(52, 46, 855, 95, 43);
    if (slide.layout === 'chart') {
      objects.push({ type: 'chart', x: 59, y: 155, w: 840, h: 300, items, accent, ink, rule });
    } else if (slide.layout === 'comparison') {
      const step = 864 / items.length;
      items.forEach((r, i) => {
        const x = 49 + i * step;
        rect(x, 167, step - 14, 274, i ? tint : bg);
        rect(x, 167, step - 14, 3, i ? accent : ink);
        label(r, i, x + 18, 194, step - 53, 77, 32);
        body(r, i, x + 18, 285, step - 53, 137, 23);
      });
    } else if (slide.layout === 'timeline') {
      const step = 852 / items.length;
      rect(58, 221, Math.max(24, (items.length - 1) * step), 2, rule);
      items.forEach((r, i) => {
        const x = 54 + i * step;
        ellipse(x, 214, 16, 16, accent);
        label(r, i, x, 247, step - 15, 74, 25);
        body(r, i, x, 328, step - 15, 127, 20);
      });
    } else {
      const image = !!slide.image,
        width = image ? 400 : 840,
        step = 293 / items.length;
      items.forEach((r, i) => {
        const y = 155 + i * step;
        rect(54, y, width, 1, rule);
        label(r, i, 54, y + 7, width, step * 0.38, 24);
        body(r, i, 54, y + step * 0.4 + 4, width, step * 0.54, 20);
      });
      if (image) objects.push({ type: 'image', x: 496, y: 145, w: 401, h: 302, data: slide.image });
    }
  }
  rect(54, 480, 852, 1, rule);
  text(
    833,
    495,
    78,
    25,
    String(page).padStart(2, '0') + ' / ' + String(total).padStart(2, '0'),
    12,
    soft,
  );
  return objects;
}
