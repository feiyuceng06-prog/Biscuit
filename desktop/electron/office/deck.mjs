import { planDesign, restoreDesign, textUnits } from './director.mjs';
import { barPlot, chartDomain, eastAsian, hasChartValue, resolveSlideLayout, textHeight } from './planner.mjs';
import { distributePhotos, hasPhotos, maxDeckPictureData, maxPictureData, pictureDataSize, pictureObject, pictureRatio, validPhotos } from './photos.mjs';

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
export { hasChartValue };
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
  const { pendingPhotos, ...next } = draft;
  if (draft.photoInput?.title) slides[0].title = draft.photoInput.title;
  if (draft.photoInput?.copy && !['cover', 'image', 'conclusion'].includes(slides.at(-1).layout))
    throw Error('末页原文需要摄影展示或说明版式，请调整大纲后再试');
  const pictures = pendingPhotos?.length ? pendingPhotos
    : draft.photoInput ? draft.slides.flatMap(s => s.photos ?? []) : [];
  return { ...next, title: draft.photoInput?.title || clean(result.title, 120) || slides[0].title,
    slides: distributePhotos(slides, pictures, draft.brief) };
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
  if (deck.photoInput?.copy && current.id === deck.slides.at(-1).id
    && ['cover', 'image', 'conclusion'].includes(current.layout)) {
    body = { ...body, items: [{ ...body.items[0], label: '', text: deck.photoInput.copy }] };
  }
  // The generation contract requires an explicit finite number for every chart
  // row, including a zero whose category label was left empty.
  const replacement = deck.design?.version === 2 && current.layout === 'chart'
    ? { ...body, items: body.items.map(item => ({ ...item, valueKind: 'chart-data' })) } : body;
  return {
    ...deck,
    slides: deck.slides.map((s) =>
      s.id === current.id ? { ...s, ...replacement, revision: s.revision + 1, generated: true } : s,
    ),
  };
}
// Remember which values came from a chart when a v2 slide changes its editable layout.
export function preserveLayoutContent(slide, patch) {
  if (!patch.layout || patch.layout === slide.layout
    || ![slide.layout, patch.layout].includes('chart')) return patch;
  return {
    ...patch,
    items: (patch.items ?? slide.items).map((item) => ({
      ...item, valueKind: hasChartValue(slide, item) ? 'chart-data' : 'text',
    })),
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
      !string(s.image, maxPictureData) ||
      (s.image && !/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+=*$/.test(s.image)) ||
      (s.photos !== undefined && !validPhotos(s.photos))
    )
      fail();
    id(s.id);
    for (const row of s.items) {
      if (!row || !string(row.label, 60) || !string(row.text, 220) || !Number.isFinite(row.value)
        || ![undefined, 'text', 'chart-data'].includes(row.valueKind))
        fail();
      id(row.id);
    }
  }
  if (raw.photoInput !== undefined && (!raw.photoInput || !string(raw.photoInput.title, 120)
    || !string(raw.photoInput.copy, 220))) fail();
  if (raw.pendingPhotos !== undefined && !validPhotos(raw.pendingPhotos)) fail();
  if (pictureDataSize(raw.slides) + (raw.pendingPhotos ?? []).reduce((sum, p) => sum + p.data.length, 0)
    > maxDeckPictureData) fail();
  if (raw.design !== undefined) return { ...raw, design: restoreDesign(raw, raw.design) };
  if (hasPhotos(raw)) return { ...raw, design: planDesign(raw, {}, { visualPlanner: true }) };
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

export function exportPages(deck) {
  return deck.slides.map((slide, i) => composition(slide, i + 1, deck.slides.length, deck.theme, deck.design));
}

export function composition(slide, page, total, theme = 'paper', design) {
  if (design?.version === 2) {
    const plan = design.slidePlans?.find((p) => p.slideId === slide.id && p.sourceLayout === slide.layout);
    if (plan) return plannedComposition(slide, page, total, design.tokens, plan);
  }
  // Layout selector previews can ask for a different layout before it is committed.
  if (slide.photos?.length || design?.direction === 'photography') {
    const preview = planDesign({ title: '', brief: '', slides: [slide] }, design?.preferences, { visualPlanner: true });
    return plannedComposition(slide, page, total, preview.tokens, preview.slidePlans[0]);
  }
  if (design) return designedComposition(slide, page, total, design);

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
    size = fitText(value, size, w, h, 1.35);
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

function fitText(value, size, w, h, lineHeight, reserveEm = 0) {
  const widths = String(value).split('\n').map(textUnits);
  while (
    size > 8 &&
    widths.reduce((n, units) => n + Math.max(1, Math.ceil((units * size) / (w - size * reserveEm))), 0)
      * size * lineHeight >
      h
  ) size--;
  return size;
}

function fontFor(font, value) {
  const faces = eastAsian.test(value) ? [font.cjk, font.latin] : [font.latin, font.cjk];
  const family = [...faces, ...font.fallback].map((face) => face.includes(' ') ? '"' + face + '"' : face);
  return { fontFace: faces[0], fontFamily: family.join(', ') };
}

function designedComposition(slide, page, total, design) {
  const { tokens } = design;
  const { fonts, typography: type, spacing, graphics: graphic } = tokens;
  const { items, image, layout, unit } = slide;
  const rhythm = design.rhythm.find((entry) => entry.slideId === slide.id && entry.layout === layout);
  const cover = layout === 'cover';
  const { bg, ink, soft, tint, rule, accent, mutedBar } =
    (cover && tokens.openingPalette) || tokens.palette;
  const alignment = tokens.titleAlignment === 'mixed'
    ? (cover ? 'center' : 'left') : tokens.titleAlignment;
  const density = rhythm?.density ?? tokens.density;
  const dense = density === 'dense';
  const margin = spacing.margin + (density === 'sparse' ? 8 : dense ? -3 : 0);
  const gap = spacing.gap + (density === 'sparse' ? 6 : dense ? -7 : tokens.density === 'sparse' ? 4 : 0);
  const gutter = spacing.gutter + (dense ? -5 : 0);
  const right = 960 - margin;
  const width = right - margin;
  const bottom = spacing.footer - 23;
  const objects = [];
  const rect = (x, y, w, h, color) => objects.push({ type: 'rect', x, y, w, h, color });
  const ruleAt = (x, y, w, color = rule) => rect(x, y, w, graphic.rule, color);
  function picture(x, y, w, h) {
    const intrinsic = pictureRatio(image);
    const ratio = Number.isFinite(intrinsic) && intrinsic > 0 ? intrinsic : 1077 / 810;
    const width = Math.min(w, h * ratio);
    const height = width / ratio;
    objects.push({ type: 'image', x: x + (w - width) / 2, y: y + (h - height) / 2,
      w: width, h: height, data: image });
  }

  function text(x, y, w, h, value, size, color, field, { font = 'body', bold = false, align = 'left' } = {}) {
    if (!value) return;
    const cjk = eastAsian.test(value);
    size = fitText(value, size, w, h, type.lineHeight + 0.09, cjk ? 1 : 0);
    objects.push({
      type: 'text', x, y, w, h, value, field, color, bold, align,
      size, ...(cjk && { wrapPadding: size }),
      lineHeight: type.lineHeight, ...fontFor(fonts[font], value),
    });
  }
  const title = (x, y, w, h, size = type.title) =>
    text(x, y, w, h, slide.title, size, ink, 'title', { font: 'title', bold: type.boldTitle, align: alignment });
  const label = (i, x, y, w, h, size = type.label, align = 'left') =>
    text(x, y, w, h, items[i].label, size, accent, 'label-' + i, { bold: true, align });
  const body = (i, x, y, w, h, align = 'left') =>
    text(x, y, w, h, items[i].text, type.body, soft, 'text-' + i, { align });

  function marker(x, y, side) {
    if (graphic.marker === 'circle')
      objects.push({ type: 'ellipse', x, y, w: side, h: side, color: accent });
    else rect(x, y, side, side, accent);
  }
  function headingMark(x, y, w) {
    const markColor = graphic.brandAccent ?? accent;
    switch (graphic.motif) {
      case 'rule': ruleAt(x, y, w, graphic.brandAccent ?? rule); break;
      case 'dash': ruleAt(x + (alignment === 'center' ? (w - 42) / 2 : 0), y, 42, markColor); break;
      case 'rail': rect(x, y, 54, 4, markColor); break;
      case 'corner':
        ruleAt(x, y, 22, markColor);
        rect(x, y, graphic.rule, 9, markColor);
        ruleAt(x + w - 12, y, 12, rule);
        break;
    }
  }
  function entry(i, x, y, w, h, align = 'left') {
    const { label: heading, text: copy } = items[i];
    const lines = Math.max(1, Math.ceil(textUnits(heading) * type.label / w));
    const labelHeight = copy ? Math.min(h * 0.48, Math.max(23, lines * type.label * 1.35)) : h;
    label(i, x, y, w, labelHeight, type.label, align);
    const offset = heading ? labelHeight + Math.min(5, h * 0.08) : 0;
    body(i, x, y + offset, w, h - offset, align);
  }
  function rows(indices, x, y, w, h, skipLabel = -1) {
    const step = h / indices.length;
    indices.forEach((i, index) => {
      const top = y + index * step;
      const pad = Math.min(graphic.panelFill ? spacing.inset : 8, step * 0.15);
      if (graphic.panelFill) rect(x, top + 2, w, step - 6, tint);
      ruleAt(x, top, w, graphic.panelFill ? rule : accent);
      const left = x + (graphic.panelFill ? spacing.inset : 0);
      const span = x + w - left - (graphic.panelFill ? spacing.inset : 0);
      if (i === skipLabel) {
        body(i, left, top + pad, span, step - pad * 2);
      } else if (indices.length >= 3 && w >= 470 && items[i].label && items[i].text) {
        const labelWidth = span * 0.29;
        label(i, left, top + pad, labelWidth, step - pad * 2);
        body(i, left + labelWidth + gutter, top + pad, span - labelWidth - gutter, step - pad * 2);
      } else entry(i, left, top + pad, span, step - pad * 2);
    });
  }
  function columns(x, y, w, h) {
    if (layout === 'comparison' && graphic.motif === 'rail') {
      const row = h / items.length;
      items.forEach((item, i) => {
        const top = y + i * row;
        const split = item.text && item.label ? w * 0.34 : item.label ? w : 0;
        ruleAt(x, top, w);
        label(i, x, top + spacing.inset, split, row - spacing.inset * 2, type.label + 2);
        const offset = split ? split + gutter : 0;
        body(i, x + offset, top + spacing.inset, Math.max(1, w - offset), row - spacing.inset * 2);
      });
      return;
    }
    const filled = graphic.panelFill && layout !== 'comparison';
    const cell = (w + gutter) / items.length - gutter;
    items.forEach((_, i) => {
      const left = x + i * (cell + gutter);
      const inset = filled ? spacing.inset : 0;
      if (filled) rect(left, y, cell, h, tint);
      ruleAt(left, y, cell, accent);
      entry(i, left + inset, y + spacing.inset, cell - 2 * inset, h - spacing.inset * 2);
    });
  }

  rect(0, 0, 960, 540, bg);
  const indices = items.map((_, i) => i);
  if (cover) {
    const titleY = image ? 135 : 128;
    const detailsY = image ? 285 : 315;
    if (graphic.cover === 'tint') rect(0, 0, 960, 300, tint);
    if (graphic.cover === 'rail') rect(0, 0, 13, 540, graphic.brandAccent ?? accent);
    if (graphic.cover === 'frame') {
      ruleAt(margin - 17, 27, width + 34);
      ruleAt(margin - 17, 487, width + 34);
      rect(margin - 17, 27, graphic.rule, 461, rule);
      rect(right + 16, 27, graphic.rule, 461, rule);
    }
    let x = margin;
    let w = width;
    if (image) {
      const imageWidth = (width - gutter) * (graphic.imageShare - (dense ? 0.08 : 0));
      const imageLeft = graphic.imageSide === 'left';
      x = imageLeft ? margin + imageWidth + gutter : margin;
      w = width - imageWidth - gutter;
      picture(imageLeft ? margin : right - imageWidth, 86, imageWidth, 373);
    }
    headingMark(x, 71, w);
    label(0, x, 88, w, 44, type.caption + 4, alignment);
    title(x, titleY, w, detailsY - titleY - 17, type.cover);
    if (items.length === 1) {
      ruleAt(x, detailsY - 5, w);
      body(0, x, detailsY + 15, w, bottom - detailsY - 15, alignment);
    } else {
      rows(indices, x, detailsY, w, bottom - detailsY, 0);
    }
  } else {
    const sideTitle = layout === 'conclusion' && alignment === 'left' && !dense
      && textUnits(slide.title) < 60 && (graphic.motif === 'rail' || graphic.motif === 'corner');
    const titleHeight = textUnits(slide.title) > 73 ? 127 : 99;
    const start = spacing.top + titleHeight + gap;
    if (sideTitle) {
      const side = Math.floor(width * 0.36);
      headingMark(margin, spacing.top, side);
      title(margin, spacing.top + 27, side, 290, type.title + 5);
      rows(indices, margin + side + gutter, spacing.top, width - side - gutter, bottom - spacing.top);
    } else {
      headingMark(margin, spacing.top - 12, width);
      title(margin, spacing.top, width, titleHeight + 2, type.title + (rhythm?.role === 'conclusion' ? 3 : 0));
      if (layout === 'chart') {
        const annotations = indices.filter((i) => items[i].text.trim());
        const longest = Math.max(...items.map(({ label }) => textUnits(label)));
        const stacked = annotations.length > 1 || (annotations.length === 1 && longest > 24);
        const panelWidth = annotations.length && !stacked ? Math.floor(width * 0.32) : 0;
        const chartWidth = panelWidth ? width - panelWidth - gutter : width;
        const chartLeft = graphic.chartSide === 'left' || !panelWidth;
        const chartX = chartLeft ? margin : right - chartWidth;
        const chartY = start + (unit ? 25 : 0);
        const panelTop = stacked ? bottom - Math.min(143, Math.floor((bottom - chartY) * 0.48)) : start;
        const chartBottom = stacked ? panelTop - 12 : bottom;
        const categorySize = Math.max(10, Math.min(type.category,
          Math.floor((chartWidth - 40) / items.length / Math.max(1, longest * 0.49))));
        text(chartX, start - 1, chartWidth, 24, unit, type.caption, soft, 'unit');
        objects.push({
          type: 'chart', x: chartX, y: chartY, w: chartWidth, h: chartBottom - chartY,
          items, ink, rule, categorySize, valueSize: type.value,
          categoryBold: graphic.motif === 'rail', valueBold: graphic.motif === 'corner',
          axisWidth: graphic.rule,
          ...fontFor(fonts.data, items.map((item) => item.label).join(' ')),
          valueFontFace: fonts.data.latin,
          colors: items.map((_, i) => (!annotations.length || annotations.includes(i) ? accent : mutedBar)),
        });
        if (stacked) {
          const cell = (width + gutter) / annotations.length - gutter;
          annotations.forEach((i, index) => {
            const x = margin + index * (cell + gutter);
            ruleAt(x, panelTop, cell);
            entry(i, x, panelTop + 8, cell, bottom - panelTop - 8);
          });
        } else if (panelWidth) {
          const i = annotations[0];
          const panelX = chartLeft ? right - panelWidth : margin;
          if (graphic.panelFill) rect(panelX, panelTop, panelWidth, bottom - panelTop, tint);
          ruleAt(panelX, panelTop, panelWidth, accent);
          const x = panelX + spacing.inset;
          const w = panelWidth - 2 * spacing.inset;
          label(i, x, panelTop + 15, w, 62);
          text(x, panelTop + 84, w, 70, [String(items[i].value), unit].filter(Boolean).join(' '),
            Math.min(type.display, type.title - 4), accent, null, { font: 'data', bold: true });
          body(i, x, panelTop + 164, w, bottom - panelTop - 164);
        }
      } else if (layout === 'image' && image) {
        const imageWidth = (width - gutter) * (graphic.imageShare - (dense ? 0.08 : 0));
        const imageLeft = graphic.imageSide === 'left';
        picture(imageLeft ? margin : right - imageWidth, start, imageWidth, bottom - start);
        rows(indices, imageLeft ? margin + imageWidth + gutter : margin, start,
          width - imageWidth - gutter, bottom - start);
      } else if (layout === 'timeline') {
        const side = graphic.marker === 'circle' ? 10 : 11;
        if (dense || graphic.motif === 'rule') {
          const step = (bottom - start) / items.length;
          const x = margin + side + spacing.inset;
          if (items.length > 1) rect(margin + side / 2, start + 12, graphic.rule, (items.length - 1) * step, rule);
          items.forEach((_, i) => {
            const y = start + i * step;
            const labelWidth = (right - x) * 0.25;
            marker(margin, y + 8, side);
            label(i, x, y + 4, labelWidth, step - 10);
            body(i, x + labelWidth + gutter, y + 4, right - x - labelWidth - gutter, step - 10);
          });
        } else {
          const cell = (width + gutter) / items.length - gutter;
          ruleAt(margin, start + side / 2, (cell + gutter) * (items.length - 1) + side);
          items.forEach((_, i) => {
            const x = margin + i * (cell + gutter);
            marker(x, start, side);
            entry(i, x, start + gap, cell, bottom - start - gap);
          });
        }
      } else if (layout === 'conclusion' || (layout === 'image' && dense)) {
        rows(indices, margin, start, width, bottom - start);
      } else {
        columns(margin, start, width, bottom - start);
      }
    }
  }
  const folio = String(page).padStart(2, '0') + ' / ' + String(total).padStart(2, '0');
  text(right - 104, spacing.footer, 104, 21, folio, type.caption, soft, null, { font: 'data', align: 'right' });
  return objects;
}


function plannedComposition(slide, page, total, tokens, plan) {
  const { text, marks, picture, gallery, chart, palette } = resolveSlideLayout(slide, tokens, plan);
  const { typography: type, fonts, spacing, graphics } = tokens;
  const { ink, soft, accent, mutedBar, rule } = palette;
  const markColors = { ...palette,
    'brand-rule': graphics.brandAccent ?? rule, 'brand-accent': graphics.brandAccent ?? accent };
  const objects = [];
  const leading = type.lineHeight + 0.09;
  function plannedSize(value, size, { w, h }, cjk) {
    while (size > 8 && textHeight(value, size, w, leading, cjk ? 1 : 0) > h) size--;
    return size;
  }
  function addText(region, value, size, color, field, font, bold = false, align = 'left', italic = false) {
    const { x, y, w, h } = region;
    const cjk = eastAsian.test(value);
    size = plannedSize(value, size, region, cjk);
    objects.push({ type: 'text', x, y, w, h, value, field, size, color, bold, align, ...(italic && { italic }),
      ...(cjk && { wrapPadding: size }), lineHeight: type.lineHeight, ...fontFor(font, value) });
  }

  for (const { type: kind, color, ...region } of marks) {
    if (kind === 'text-arrow') addText(region, '›', 17, markColors[color], null, fonts.body, true);
    else objects.push({ type: kind, color: markColors[color], ...region });
  }
  if (picture) objects.push(pictureObject(picture, slide.image));
  for (const { photo, slotId, ...region } of gallery ?? []) {
    objects.push({ ...pictureObject(region, photo.data, photo.fit, photo.focus),
      ...(photo.legacy ? {} : { photoId: photo.id, name: photo.name, alt: photo.caption || photo.name || 'Photo' }),
      slotId });
  }
  for (const region of text) {
    const { value, size, field, role, align } = region;
    const color = role === 'title' ? ink : ['label', 'value'].includes(role) ? accent : soft;
    const coverCredit = plan.variant === 'photo-cover' && ['subtitle', 'opening-credit'].includes(region.slotId);
    const font = role === 'title' || coverCredit ? fonts.title : role === 'value' ? fonts.data : fonts.body;
    const bold = role === 'title' ? type.boldTitle : ['label', 'value'].includes(role);
    addText(region, value, size, color, field, font, bold, align, (role === 'title' || coverCredit) && type.italicTitle);
  }
  if (chart?.items.length) {
    const { items, focus, encoding } = chart;
    const highlight = focus >= 0 && items.filter((item) => item.text.trim()).length === 1 && encoding !== 'line';
    const longest = Math.max(1, ...items.map((item) => textUnits(item.label)));
    const bars = encoding === 'bars';
    const labelWidth = bars ? chart.w * 0.34 : (chart.w - 52) / items.length;
    const categorySize = Math.max(11, Math.min(type.category, Math.floor(labelWidth / longest)));
    // Keep very long categories in a dedicated column instead of letting the chart
    // engine shrink the plot to make room for a single unwrapped label.
    const wrappedCategories = bars && (longest * categorySize > chart.w * 0.4 || items.some(({ label }) => label.includes('\n')));
    const plot = bars ? barPlot(chart, type.value) : undefined;
    objects.push({ type: 'chart', ...chart, domain: chartDomain(items), ink, rule, categorySize,
      ...(plot && { plot, wrappedCategories }),
      valueSize: type.value, axisWidth: graphics.rule,
      ...fontFor(fonts.data, items.map((item) => item.label).join(' ')), valueFontFace: fonts.data.latin,
      colors: items.map((_, i) => highlight && i !== focus ? mutedBar : accent),
    });
    if (wrappedCategories) {
      const step = (plot.bottom - plot.top) / items.length;
      items.forEach(({ label }, i) => {
        if (!label) return;
        const maxHeight = step - 4;
        const cjk = eastAsian.test(label);
        const size = plannedSize(label, categorySize, { w: plot.labelWidth, h: maxHeight }, cjk);
        const estimatedHeight = Math.min(maxHeight,
          textHeight(label, size, plot.labelWidth, leading, cjk ? 1 : 0));
        const y = chart.y + plot.top + step * (i + 0.5) - estimatedHeight / 2;
        addText({ x: chart.x, y, w: plot.labelWidth, h: estimatedHeight + 1 },
          label, size, ink, null, fonts.data);
      });
    }
  }
  if (plan.variant !== 'photo-cover')
    addText({ x: 856 - spacing.margin, y: spacing.footer, w: 104, h: 21 },
      String(page).padStart(2, '0') + ' / ' + String(total).padStart(2, '0'),
      type.caption, soft, null, fonts.data, false, 'right');
  return objects;
}
