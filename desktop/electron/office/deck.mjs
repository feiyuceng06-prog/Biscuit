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
    if (!Object.hasOwn(layouts, row?.layout) || !clean(row.title, 120))
      throw Error('大纲格式不完整');
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
  const body = { items, notes: clean(result.notes, 1200) };
  if (slide.layout === 'chart' && typeof result.unit === 'string')
    body.unit = clean(result.unit, 24);
  return body;
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
    (raw.theme !== undefined &&
      (typeof raw.theme !== 'string' || !Object.hasOwn(themes, raw.theme))) ||
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
      (s.unit !== undefined && !string(s.unit, 24)) ||
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
    ink: '14181E',
    soft: '454D5A',
    tint: 'EAF0FA',
    rule: 'CFD6E0',
    accent: '2449AD',
    mutedBar: 'A8B7D4',
  },
  sand: {
    name: '陶土',
    bg: 'FBF6EB',
    ink: '302A23',
    soft: '60564B',
    tint: 'F2E4C9',
    rule: 'D3C3AA',
    accent: '9D422C',
    mutedBar: 'C9BBA5',
  },
  midnight: {
    name: '午夜',
    bg: '192221',
    ink: 'F0F3EA',
    soft: 'C4CFC3',
    tint: '2B3936',
    rule: '53645D',
    accent: 'D6ED87',
    mutedBar: '778B80',
  },
};

export function composition(slide, page, total, theme = 'paper') {
  const { bg, ink, soft, tint, rule, accent, mutedBar } = themes[theme] || themes.paper;
  const editorial = theme === 'sand',
    dark = theme === 'midnight';
  const objects = [];
  const rect = (x, y, w, h, color) => objects.push({ type: 'rect', x, y, w, h, color });
  function text(
    x,
    y,
    w,
    h,
    value,
    size,
    color,
    field,
    { bold = false, serif = false, align = 'left' } = {},
  ) {
    if (!value) return;
    const widths = String(value)
      .split('\n')
      .map((line) =>
        Array.from(line).reduce((sum, c) => sum + (c.charCodeAt(0) < 128 ? 0.6 : 1.05), 0),
      );
    while (
      size > 8 &&
      widths.reduce((n, units) => n + Math.max(1, Math.ceil((units * size) / w)), 0) * size * 1.35 >
        h
    )
      size--;
    objects.push({ type: 'text', x, y, w, h, value, size, color, field, bold, serif, align });
  }
  const items = slide.items.slice(0, maxItems(slide.layout));
  const title = (x, y, w, h, size, color = ink, align = 'left') =>
    text(x, y, w, h, slide.title, size, color, 'title', {
      bold: !editorial,
      serif: editorial,
      align,
    });
  const label = (i, x, y, w, h, size, color = ink, align = 'left') =>
    text(x, y, w, h, items[i].label, size, color, 'label-' + i, { bold: true, align });
  const body = (i, x, y, w, h, size, color = soft, align = 'left') =>
    text(x, y, w, h, items[i].text, size, color, 'text-' + i, { align });
  function rows(x, y, w, h) {
    const step = h / items.length;
    items.forEach((_, i) => {
      const top = y + i * step;
      rect(x, top, w, 1, rule);
      label(i, x, top + 10, w, step * 0.37, 24);
      body(i, x, top + 11 + step * 0.37, w, step * 0.58 - 12, 20);
    });
  }
  const illustration = (x, y, w, h) =>
    objects.push({ type: 'image', x, y, w, h, data: slide.image });
  const folio = String(page).padStart(2, '0') + ' / ' + String(total).padStart(2, '0');
  rect(0, 0, 960, 540, bg);
  if (slide.layout === 'cover') {
    if (slide.image) {
      if (dark) {
        illustration(240, 0, 720, 540);
        rect(0, 0, 451, 540, bg);
        label(0, 47, 56, 354, 55, 17, soft);
        title(44, 144, 362, 200, 62, accent);
        body(0, 47, 375, 354, 103, 23);
      } else if (editorial) {
        illustration(49, 76, 443, 333);
        label(0, 50, 424, 442, 49, 15, accent);
        title(520, 108, 395, 199, 63);
        rect(523, 330, 379, 1, rule);
        body(0, 523, 351, 379, 114, 22);
      } else {
        illustration(415, 66, 544, 409);
        label(0, 47, 64, 336, 58, 17, accent);
        title(44, 155, 350, 180, 58);
        body(0, 47, 368, 335, 100, 22);
      }
    } else if (editorial) {
      rect(0, 0, 960, 373, tint);
      label(0, 57, 53, 820, 56, 17, accent);
      title(52, 131, 845, 207, 67);
      rect(57, 371, 846, 1, accent);
      body(0, 57, 401, 785, 91, 24);
    } else if (dark) {
      label(0, 90, 92, 780, 49, 17, soft, 'center');
      title(57, 166, 846, 157, 74, accent, 'center');
      body(0, 108, 354, 744, 104, 22, soft, 'center');
    } else {
      label(0, 55, 53, 844, 54, 17, accent);
      title(50, 147, 858, 210, 75);
      rect(0, 392, 960, 148, accent);
      body(0, 56, 420, 770, 92, 24, 'FFFFFF');
    }
  } else if (slide.layout === 'chart') {
    title(51, 38, 856, 105, 42);
    const focus = items.findIndex((item) => item.text.trim());
    const chart = {
      type: 'chart',
      x: 53,
      y: 178,
      w: focus < 0 ? 851 : 513,
      h: 285,
      items,
      ink,
      rule,
      colors: items.map((_, i) => (focus < 0 || i === focus ? accent : mutedBar)),
    };
    if (editorial && focus >= 0) chart.x = 399;
    objects.push(chart);
    if (slide.unit) text(chart.x + 10, 149, chart.w - 20, 26, slide.unit, 15, soft, 'unit');
    if (focus >= 0) {
      const x = editorial ? 53 : 610;
      rect(x, 166, 299, 2, accent);
      label(focus, x, 187, 297, 51, 19);
      text(
        x - 2,
        246,
        301,
        93,
        [String(items[focus].value), slide.unit].filter(Boolean).join(' '),
        63,
        accent,
        null,
        { serif: editorial, bold: !editorial },
      );
      body(focus, x, 350, 298, 116, 21);
    }
  } else if (slide.layout === 'conclusion' && !editorial) {
    if (dark) rect(0, 0, 422, 540, tint);
    title(49, 73, 343, 356, 52, dark ? accent : ink);
    rows(457, 68, 448, 397);
  } else if (slide.layout === 'timeline' && editorial) {
    title(50, 63, 342, 346, 49);
    const step = 396 / items.length;
    items.forEach((_, i) => {
      const y = 65 + i * step;
      rect(422, y, 483, 1, rule);
      label(i, 422, y + 11, 123, step - 16, 20, accent);
      body(i, 555, y + 10, 350, step - 16, 22);
    });
  } else {
    title(51, 39, 855, 106, 44);
    if (slide.layout === 'comparison') {
      const step = 854 / items.length;
      items.forEach((_, i) => {
        const x = 53 + i * step;
        if (dark || (!editorial && i === 1)) rect(x, 168, step - 12, 288, tint);
        rect(x, 166, step - 12, 2, editorial ? accent : rule);
        label(i, x + 16, 197, step - 54, 92, 37, editorial ? accent : ink);
        body(i, x + 16, 308, step - 54, 129, 24);
      });
    } else if (slide.layout === 'timeline') {
      const step = 852 / items.length;
      rect(54, 218, step * (items.length - 1) + 12, 2, rule);
      items.forEach((_, i) => {
        const x = 53 + i * step;
        rect(x, 213, 11, 11, accent);
        label(i, x, 248, step - 17, 73, 25);
        body(i, x, 333, step - 17, 126, 21);
      });
    } else if (slide.layout === 'image' && slide.image) {
      const imageLeft = editorial || dark;
      illustration(imageLeft ? 52 : 507, 157, 400, 301);
      rows(imageLeft ? 498 : 53, 161, 408, 298);
    } else {
      // Parallel columns keep the evidence under its own heading, including a text-only image page.
      const step = 854 / items.length;
      items.forEach((_, i) => {
        const x = 53 + i * step;
        rect(x, 168, step - 15, 1, rule);
        label(i, x, 193, step - 19, 101, 33, accent);
        body(i, x, 308, step - 19, 143, 23);
      });
    }
  }
  const footColor =
    slide.layout === 'cover' && !slide.image && !dark && !editorial ? 'FFFFFF' : soft;
  text(
    dark && slide.layout === 'cover' && slide.image ? 303 : 808,
    504,
    99,
    23,
    folio,
    12,
    footColor,
    null,
    { align: 'right' },
  );
  return objects;
}
