import { galleryFrames } from './photos.mjs';

// Content types and layout geometry are shared by ranking, Canvas and PPTX.
export function textUnits(value) {
  return Array.from(value).reduce((total, char) => total + (char.charCodeAt(0) < 128 ? 0.6 : 1.05), 0);
}

export const eastAsian = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u;

export function textHeight(value, size, width, lineHeight, reserveEm = 0) {
  return value.split('\n').reduce((lines, row) =>
    lines + Math.max(1, Math.ceil((textUnits(row) * size) / Math.max(1, width - size * reserveEm))), 0)
    * size * lineHeight;
}

export function hasChartValue(slide, item) {
  return item.valueKind === 'chart-data' || (item.valueKind === undefined && slide.layout === 'chart'
    && Boolean(item.label.trim() || item.value !== 0));
}

function period(label) {
  const input = label.trim();
  const relative = /^(week|day|month|quarter|year)\s+(\d{1,3})$|^第\s*(\d{1,3})\s*(周|天|日|个月|月|季度|年)$/i.exec(input);
  if (relative) return ['relative-' + (relative[1]?.toLowerCase() ?? relative[4]), Number(relative[2] ?? relative[3])];
  let match = /^(\d{4})(?:年)?$/.exec(input);
  if (match && +match[1] >= 1000) return ['year', +match[1]];
  match = /^(\d{4})[- ]?Q([1-4])$|^(\d{4})年?第?([1-4])季度$/i.exec(input);
  if (match) return ['quarter', 4 * Number(match[1] ?? match[3]) + Number(match[2] ?? match[4])];
  match = /^(\d{4})[-年](\d{1,2})(?:月)?(?:[-月](\d{1,2})日?)?$/.exec(input);
  if (!match) match = /^(\d{4})年(\d{1,2})月(\d{1,2})日$/.exec(input);
  if (!match || +match[1] < 1000 || +match[2] < 1 || +match[2] > 12) return null;
  if (!match[3]) return ['month', 12 * +match[1] + +match[2]];
  const day = new Date(Date.UTC(+match[1], +match[2] - 1, +match[3]));
  return day.getUTCMonth() === +match[2] - 1 ? ['day', day.getTime() / 86400000] : null;
}

function timeIntervals(items) {
  const dates = items.map(({ label }) => period(label));
  if (!dates.length || !dates.every((date) => date && date[0] === dates[0][0]))
    return { dated: false, regular: false };
  const steps = dates.slice(1).map((date, i) => date[1] - dates[i][1]);
  return { dated: true, regular: steps.length > 0 && steps[0] > 0 && steps.every((step) => step === steps[0]) };
}

function slideContent(slide) {
  const data = [];
  const entries = [];
  const annotations = [];
  slide.items.forEach((item, index) => {
    if (hasChartValue(slide, item)) {
      data.push(index);
      if (item.text.trim()) annotations.push(index);
    } else if (item.label.trim() || item.text.trim()) {
      entries.push(index);
    }
  });
  return { data, entries, annotations, indices: slide.items.map((_, index) => index) };
}

export function chartDomain(items) {
  const values = items.map(({ value }) => value);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const bound = (value) => Math.min(Number.MAX_VALUE, Math.max(-Number.MAX_VALUE, value));
  const edge = Math.max(-min, max) || 1;
  return { min: bound(min - edge * 0.14), max: bound(max + edge * 0.14) };
}

export function barPlot(chart, valueSize) {
  const values = chart.items.map(({ value }) => value);
  const numberWidth = Math.max(...values.map((value) => textUnits(String(value)))) * valueSize + 12;
  const inset = Math.min(chart.w * 0.18, Math.max(25, numberWidth));
  const labelWidth = chart.w * 0.34;
  const left = labelWidth + (Math.min(...values) < 0 ? inset : 12);
  const right = chart.w - (Math.max(...values) >= 0 ? inset : 12);
  return { left, right, top: 3, bottom: chart.h - 3, labelWidth };
}

const typeFloor = { title: 25, label: 15, body: 15, caption: 12, value: 14 };
const mediaReason = '使用现有配图，保留完整画面。';

function candidateSet(slide, content, rhythm, tokens) {
  const { layout, title, items } = slide;
  const image = slide.image || slide.photos?.length;
  const { data, indices } = content;
  const meta = (family, variant, score, reason, extra) => ({ layout: family, variant, score, reason, ...extra });
  const album = tokens.graphics.photoAlbum;
  if (!data.length && (album || slide.photos?.length)) {
    if (layout === 'comparison' && slide.photos?.length === 2 && !slide.image && items.length === 2)
      return [meta('comparison', 'photo-comparison', 67, '把每幅照片与同序的对照文字放进同一栏。')];
    if (layout === 'cover')
      return [meta('cover', 'photo-cover', 68, '按素材顺序布置居中的照片组，标题、副标题和图注各有独立空间。')];
    if (layout === 'image' && image) return [
      meta('image', 'photo-work', 67, '先展示作品，再阅读标题和说明。'),
      meta('image', 'photo-work-side', 56, '在作品旁为长标题和说明分配独立空间。'),
    ];
    if (layout === 'conclusion' || (layout === 'image' && !image))
      return [meta('statement', 'photo-essay', 67, '用标题与独立说明栏组织阅读顺序。')];
  }
  const presentation = rhythm.role === 'opening' || rhythm.role === 'transition' || rhythm.role === 'conclusion';
  const compact = rhythm.density !== 'dense';
  const left = tokens.titleAlignment !== 'center';
  const statement = [
    meta('statement', 'statement-led', 46 + (presentation ? 8 : 0) + (compact ? 7 : 0),
      '放大主张，用独立区域承接正文。'),
    meta('statement', 'statement-rows', 40 + (compact ? 0 : 13),
      '用宽行保留小标题和较长正文。'),
  ];
  if (indices.length === 1 && !image && !data.length && items[0].text.trim()) {
    const hasTakeaway = /核心问题|核心观点|关键发现|关键结论|核心主张|^takeaway$|^key finding$/i.test(items[0].label.trim());
    statement.push(meta('statement', hasTakeaway ? 'statement-takeaway' : 'statement-wide', 65,
      hasTakeaway ? '正文明确标出核心问题或发现，直接放大该句，标题作为引导。' : '单一主张使用全宽标题，下方单独承接说明。'));
  }
  if (layout === 'cover') return [
    ...(image ? [meta('cover', 'cover-image', 55, '开场标题与配图并列。')] : []),
    meta('cover', 'cover-title', 56, '以全宽标题建立开场焦点。', { feasible: !image }),
    meta('cover', 'cover-brief', 47, '把开场说明分行，给正文和配图留足空间。'),
  ];
  if (layout === 'chart' && data.length) {
    const time = timeIntervals(data.map((i) => items[i]));
    const longLabels = data.some((i) => {
      const label = items[i].label;
      return textUnits(label) > (eastAsian.test(label) ? 8.5 : 16) || label.includes('\n');
    });
    const signed = data.some(i => items[i].value < 0) && data.some(i => items[i].value > 0);
    const ranking = /\b(?:ranking|rank|top|bottom)\b|排名|排行|最多|最少|最高|最低/i.test(title);
    const chart = (variant, score, reason, feasible = true) =>
      meta('chart', variant, score, reason, { feasible, chartEncoding: variant.split('-')[0] });
    const encodings = [
      chart('line-focus', 66, '使用等间隔、按时间递增的观测值绘制折线。', time.regular),
      chart('bars-focus', longLabels || ranking || signed ? 63 : 46, signed
        ? '以共同零点向两侧展示正负变化，保留零值标签。' : '水平条形给类别标签与排名留出空间。'),
      chart('columns-focus', longLabels ? 41 : 59, time.dated
        ? '以独立柱表示各时间点，避免暗示连续或等间隔的变化。'
        : '以共同零基线对照离散类别的原始数值。'),
    ];
    return [
      ...encodings,
      ...encodings.map((c) => ({ ...c, variant: c.variant.replace('focus', 'details'), score: c.score - 5,
        reason: c.reason + (content.entries.length || content.annotations.length
          ? ' 单独排列类别说明和其他内容。' : ' 将图表集中在略窄的内容区。') })),
    ];
  }
  if (layout === 'image' && image) return [
    meta('image', 'image-hero', 55 + (rhythm.emphasis === 'image' ? 5 : 0), mediaReason + ' 将视线集中在图片上。'),
    meta('image', 'image-split', 57, mediaReason + ' 为说明保留更宽的文字区。'),
    meta('image', 'image-caption', 46, mediaReason + ' 将长说明移至全宽区域。'),
  ];
  if (layout === 'comparison' && indices.length >= 2) return [
    meta('comparison', 'comparison-pair', 57 + (left ? 0 : 2), '为对照项分配同等宽度和文字层级。',
      { feasible: indices.length === 2 }),
    meta('comparison', 'comparison-rows', 53 + (compact ? 0 : 8), '用相同的行结构并列多个对照项，保留事实和上下文。'),
  ];
  if (layout === 'timeline') {
    const { dated, regular } = timeIntervals(items);
    return dated ? [
      meta('sequence', 'timeline-track', 56, '按原始顺序展示等间隔时间点。', { feasible: regular }),
      meta('sequence', 'timeline-milestones', 53, '按原文排列有日期的里程碑，间距只用于分隔条目。'),
    ] : [
      meta('sequence', 'process-flow', compact ? 57 : 47, '沿正向阅读顺序展示步骤。'),
      meta('sequence', 'process-stack', 54, '纵向安排步骤，为说明保留宽度。'),
    ];
  }
  return statement;
}

// Imported and generated outlines often store a process or a contrast in a
// generic conclusion page. Treat that source key as a hint, keep its editable
// content intact, and measure the inferred alternatives alongside the originals.
function candidatesForContent(slide, content, rhythm, tokens) {
  const original = candidateSet(slide, content, rhythm, tokens);
  if (original[0].variant.startsWith('photo-')) return original;
  if (slide.layout !== 'conclusion' && !(slide.layout === 'image' && !slide.image && !slide.photos?.length)) return original;
  const count = content.indices.length;
  const { title } = slide;
  let inferred;
  if (content.data.length >= 2) inferred = 'chart';
  else if (slide.image || slide.photos?.length) inferred = 'image';
  else if (count > 1 && (timeIntervals(slide.items).dated
      || /流程|工序|处理步骤|工作步骤|流水线|\b(?:workflow|pipeline|procedure|steps)\b/i.test(title))) inferred = 'timeline';
  else if (count === 2 && /对比|两种|两类|差异|\b(?:compare|comparison|versus|vs)\b/i.test(title)) inferred = 'comparison';
  if (!inferred) {
    if (tokens.readingCopy && !content.data.length && count && slide.items.some(item => item.text.trim()))
      return [...original, { layout: 'statement', variant: 'statement-reading', score: 77,
        reason: '会前阅读使用连续的文字层级，保留原文并按段落分配空间。' }];
    return original;
  }
  const alternatives = candidateSet({ ...slide, layout: inferred }, content, rhythm, tokens);
  return [...alternatives, ...original];
}

const preferredFloor = (region) => region.role === 'title'
  ? Math.max(typeFloor.title, Math.floor(region.size * 0.62))
  : Math.min(region.size, Math.max(typeFloor[region.role], region.size - 5));

// Relative chart label allowance follows the chart's category allocation.
function measure(resolved, tokens) {
  let fitPenalty = 0;
  const overflow = [];
  for (const box of resolved.text) {
    if (!box.value.trim()) continue;
    const reserve = eastAsian.test(box.value) ? 1 : 0;
    const floor = preferredFloor(box);
    const ratio = textHeight(box.value, floor, box.w, tokens.typography.lineHeight + 0.09, reserve) / box.h;
    if (ratio > 1) overflow.push({ nodeId: box.nodeId, slotId: box.slotId });
    fitPenalty += Math.max(0, ratio - 0.72);
  }
  const graph = resolved.chart;
  if (graph) {
    const bars = graph.encoding === 'bars';
    const labelWidth = bars ? graph.w * 0.34 : (graph.w - 52) / graph.items.length;
    for (const item of graph.items) {
      const labelSpace = bars ? graph.h / graph.items.length - 7 : 45;
      const labelRatio = item.label ? textHeight(item.label, 12, labelWidth, 1.15) / labelSpace : 0;
      if (labelRatio > 1) overflow.push({ nodeId: item.id, slotId: 'chart-category' });
      fitPenalty += Math.max(0, labelRatio - 0.72);
    }
    const ratio = (bars ? 112 : 143) / graph.h;
    if (ratio > 1) overflow.push(...graph.items.map(({ id }) => ({ nodeId: id, slotId: 'chart-value' })));
    fitPenalty += Math.max(0, ratio - 0.72);
  }
  return { overflow, fitPenalty };
}

function reasons(candidate, overflow, repeated) {
  return [
    candidate.reason,
    ...(candidate.feasible === false ? ['当前内容不满足这个版式的结构条件。'] : []),
    ...(overflow ? ['部分内容超出演示字号下的空间。'] : []),
    ...(repeated ? ['相邻页已使用相同版式。'] : []),
  ];
}

export function planSlides(deck, rhythm, tokens, requestedPhotoCounts = {}) {
  const inputs = deck.slides.map((slide, index) => {
    const content = slideContent(slide);
    const candidates = candidatesForContent(slide, content, rhythm[index], tokens)
      .filter(candidate => candidate.feasible !== false)
      .sort((a, b) => b.score - a.score)
      .slice(0, 4);
    return { slide, content, rhythm: rhythm[index], candidates };
  });
  const plans = [];
  for (const [i, { slide, content, rhythm: pace, candidates }] of inputs.entries()) {
    const previous = plans.at(-1);
    const nextFamily = inputs[i + 1]?.candidates[0]?.layout;
    const ranked = candidates.map((candidate) => {
      const plan = { ...candidate, density: pace.density };
      const resolved = resolveSlideLayout(slide, tokens, plan, content);
      const { overflow, fitPenalty } = measure(resolved, tokens);
      const repeated = previous?.variant === plan.variant;
      const sameness = nextFamily === plan.layout && previous?.layout === plan.layout ? 2 : 0;
      const score = candidate.score - fitPenalty * 7 - (repeated ? 14 : 0) - sameness;
      return { ...plan, resolved, overflow, score: Math.round(score * 100) / 100,
        reasons: reasons(candidate, overflow.length > 0, repeated) };
    }).sort((a, b) => Number(a.feasible === false) - Number(b.feasible === false)
      || Number(Boolean(a.overflow.length)) - Number(Boolean(b.overflow.length))
      || b.score - a.score);
    const picked = ranked[0];
    const { layout, variant, resolved, overflow, chartEncoding } = picked;
    const lead = slide.items.find((item) => item.label.trim() || item.text.trim());
    const keyMessage = (variant === 'statement-takeaway' && slide.items[0].text.trim()) || slide.title.trim() || lead?.label.trim() || lead?.text.trim() || '';
    const photos = resolved.gallery ?? [];
    const photoFocus = variant === 'photo-cover' ? Math.floor((photos.length - 1) / 2) : 0;
    const requested = requestedPhotoCounts[slide.layout];
    const contentBindings = [
      ...resolved.text.filter(({ value }) => value.trim()).map(({ nodeId, slotId, emphasis }) =>
        ({ nodeId, slotId, emphasis })),
      ...resolved.chart?.items.flatMap(({ id }, index) => [
        { nodeId: id, slotId: 'chart-category', emphasis: 'secondary' },
        { nodeId: id, slotId: 'chart-value', emphasis: resolved.chart.focus < 0 || index === resolved.chart.focus ? 'primary' : 'secondary' },
      ]) ?? [],
      ...(resolved.picture ? [{ nodeId: slide.id, slotId: 'image', emphasis: layout === 'image' ? 'primary' : 'supporting' }] : []),
      ...photos.map(({ photo, slotId }, index) => ({
        nodeId: photo.id, slotId, emphasis: index === photoFocus && ['cover', 'image'].includes(layout)
          ? 'primary' : 'supporting',
      })),
      ...(slide.notes.trim() ? [{ nodeId: slide.id, slotId: 'speaker-notes', emphasis: 'supporting' }] : []),
    ];
    const focalPoint = variant === 'statement-takeaway' ? 'takeaway' : resolved.chart ? 'chart'
      : photos[photoFocus] && ['cover', 'image'].includes(layout) ? photos[photoFocus].slotId : layout === 'image' ? 'image'
      : contentBindings[0]?.slotId ?? 'headline';
    plans.push({
      slideId: slide.id, sourceLayout: slide.layout, layout, variant, keyMessage, focalPoint,
      density: overflow.length ? 'dense' : pace.density,
      contentBindings, referenceIds: [pace.referenceId],
      selectionReason: picked.reasons[0] + (previous?.layout === layout && previous.variant !== variant
        ? ' 与相邻同类页面采用不同的组织方式。' : ''),
      candidates: ranked.map(({ layout, variant, score, feasible, overflow, reasons }) => ({
        layout, variant, score, feasible: feasible !== false && !overflow.length, reasons,
      })),
      ...(chartEncoding && { chartEncoding }),
      assetStrategy: {
        image: slide.image ? { source: 'existing-slide-image', fit: 'contain', slotId: 'image' } : null,
        chart: chartEncoding ? { source: 'slide-items', editable: true, encoding: chartEncoding } : null,
        ...(slide.photos?.length > 0 && { photos: photos.filter(({ photo }) => !photo.legacy).map(({ photo, slotId }) => ({
          source: 'slide-photo', photoId: photo.id, slotId, fit: photo.fit ?? 'contain',
          focus: { x: photo.focus?.x ?? 0.5, y: photo.focus?.y ?? 0.5 },
        })) }),
        ...(requested !== undefined && { photoCount: { requested, actual: photos.length + Number(Boolean(resolved.picture)) } }),
      },
      ...(overflow.length && { contentEditProposal: {
        action: 'split-slide', summary: '建议将超出容量的内容移至后续页，保留原文、数值和备注。',
        nodeIds: [...new Set(overflow.map(({ nodeId }) => nodeId))],
        slots: overflow,
      } }),
    });
  }
  return plans;
}

export function resolveSlideLayout(slide, tokens, plan, content = slideContent(slide)) {
  const { layout, variant, chartEncoding } = plan;
  const { typography: type, spacing, graphics, palette } = tokens;
  const { items } = slide;
  const photoLayout = variant.startsWith('photo-');
  const photos = (slide.photos ?? []).map((photo, index) => ({ ...photo, index }));
  if (slide.image && (photos.length || photoLayout)) photos.push({ id: slide.id, data: slide.image, legacy: true });
  const image = slide.image || photos.length;
  const { data, entries, annotations, indices } = content;
  const left = spacing.margin;
  const width = 960 - 2 * left;
  const right = left + width;
  const top = spacing.top;
  const bottom = spacing.footer - 22;
  const gap = spacing.gutter;
  const alignment = tokens.titleAlignment === 'mixed'
    ? (layout === 'cover' ? 'center' : 'left') : tokens.titleAlignment;
  const text = [];
  const marks = [];
  let picture;
  let gallery;
  let chart;
  const box = (x, y, w, h) => ({ x, y, w, h });
  const rect = (x, y, w, h, color) => marks.push({ type: 'rect', ...box(x, y, w, h), color });
  const rule = (x, y, w, color = 'rule') => rect(x, y, w, graphics.rule, color);
  const point = (x, y, size) =>
    marks.push({ type: graphics.marker === 'circle' ? 'ellipse' : 'rect', ...box(x, y, size, size), color: 'accent' });
  function field(region, value, slotId, field, role, options = {}) {
    if (!value) return;
    text.push({ ...region, value, slotId, field, role, size: type[role], nodeId: slide.id,
      emphasis: 'secondary', ...options });
  }
  const title = (x, y, w, h, size = type.title) =>
    field(box(x, y, w, h), slide.title, 'headline', 'title', 'title', { size, emphasis: 'primary', align: alignment });
  const rowField = (i, region, name, role, slotId) =>
    field(region, items[i][name], slotId, name + '-' + i, role, { nodeId: items[i].id });
  function value(i, region, slot) {
    field(region, String(items[i].value), slot + '-value', null, 'value', { nodeId: items[i].id });
  }
  function entry(i, x, y, w, h, slot, horizontal = false) {
    const { label, text: copy } = items[i];
    const withValue = layout !== 'chart' && data.includes(i);
    const valueWidth = withValue ? Math.min(w * 0.40, 180) : 0;
    const available = valueWidth ? w - valueWidth - 10 : w;
    if (horizontal && label && copy) {
      const labelWidth = Math.floor(available * 0.32);
      rowField(i, box(x, y, labelWidth, h), 'label', 'label', slot + '-label');
      rowField(i, box(x + labelWidth + 15, y, available - labelWidth - 15, h), 'text', 'body', slot + '-body');
    } else {
      const labelHeight = label && copy
        ? Math.min(h * 0.54, Math.max(22, textHeight(label, type.label, available, type.lineHeight + 0.09, 1))) : label ? h : 0;
      rowField(i, box(x, y, available, labelHeight), 'label', 'label', slot + '-label');
      if (copy) {
        const offset = label ? labelHeight + 4 : 0;
        rowField(i, box(x, y + offset, available, h - offset), 'text', 'body', slot + '-body');
      }
    }
    if (withValue) value(i, box(x + w - valueWidth, y, valueWidth, h), slot);
  }
  function rows(list, x, y, w, h, slot = 'row') {
    const step = h / list.length;
    list.forEach((item, n) => {
      const yy = y + n * step;
      rule(x, yy, w);
      entry(item, x, yy + 7, w, step - 12, slot + '-' + n, w >= 410);
    });
  }
  function reserveImage(region, share, side = graphics.imageSide) {
    if (!image) return region;
    const imageWidth = (region.w - gap) * share;
    const onLeft = side === 'left';
    setPictures(box(onLeft ? region.x : region.x + region.w - imageWidth, region.y, imageWidth, region.h));
    return box(onLeft ? region.x + imageWidth + gap : region.x, region.y, region.w - imageWidth - gap, region.h);
  }
  function setPictures(region, strip = false) {
    if (!photos.length) {
      if (slide.image) picture = region;
      return;
    }
    gallery = galleryFrames(photos, region, strip).map(({ captionY, captionHeight, ...frame }, i) => {
      const photo = photos[i];
      const slotId = photo.legacy ? 'image' : 'photo-' + photo.index;
      field(box(frame.x, captionY, frame.w, captionHeight), photo.caption?.trim() ? photo.caption : '',
        slotId + '-caption', 'caption-' + photo.index, 'caption',
        { size: Math.min(11, type.caption), nodeId: photo.id, align: 'center' });
      return { ...frame, photo, slotId };
    });
  }
  function headingMark(x, y, w) {
    if (graphics.motif === 'rule') rule(x, y, w, 'brand-rule');
    else if (graphics.motif === 'dash') rule(x + (alignment === 'center' ? (w - 42) / 2 : 0), y, 42, 'brand-accent');
    else if (graphics.motif === 'rail') rect(x, y, 55, 4, 'brand-accent');
    else {
      rule(x, y, 22, 'brand-accent');
      rect(x, y, graphics.rule, 9, 'brand-accent');
    }
  }

  const cover = layout === 'cover';
  rect(0, 0, 960, 540, 'bg');
  if (cover && graphics.cover === 'tint') rect(0, 0, 960, 285, 'tint');
  if (cover && graphics.cover === 'rail') rect(0, 0, 13, 540, 'brand-accent');
  if (cover && graphics.cover === 'frame') {
    rule(left - 16, 25, width + 32);
    rule(left - 16, 488, width + 32);
    rect(left - 16, 25, graphics.rule, 464, 'rule');
    rect(right + 15, 25, graphics.rule, 464, 'rule');
  }

  const titleWidth = variant === 'statement-led' && alignment === 'left' && !image ? Math.floor(width * 0.41) : width;
  const header = Math.max(56, Math.min(133, textHeight(slide.title, type.title, titleWidth, type.lineHeight + 0.09, 1)));
  const start = top + header + spacing.gap;
  const units = slide.unit ?? '';
  const unitHeight = units ? 24 : 0;
  if (photoLayout) {
    function heading(region, size, align) {
      const reserve = eastAsian.test(slide.title) ? 1 : 0;
      while (size > typeFloor.title
        && textHeight(slide.title, size, region.w, type.lineHeight + 0.09, reserve) > region.h) size--;
      field(region, slide.title, 'headline', 'title', 'title', { size, emphasis: 'primary', align });
    }
    const written = indices.filter(i => items[i].label.trim() || items[i].text.trim());
    const fullWidth = box(left, 0, width, 0);
    const showUnit = (region) => field(region, units, 'chart-unit', 'unit', 'caption');
    if (variant === 'photo-cover') {
      const first = items[0];
      const extra = written.filter(i => i !== 0);
      const headingY = image ? 38 : 166;
      const headingH = Math.min(98, Math.max(65, textHeight(slide.title, type.cover, width, type.lineHeight + 0.09, 1)));
      heading({ ...fullWidth, y: headingY, h: headingH }, type.cover, 'center');
      const subtitleY = headingY + headingH + 4;
      const subtitleH = first.text ? Math.min(53, Math.max(28,
        textHeight(first.text, type.body, width, type.lineHeight + 0.09, 1))) : 0;
      field({ ...fullWidth, y: subtitleY, h: subtitleH }, first.text, 'subtitle', 'text-0', 'body',
        { nodeId: first.id, align: 'center', size: Math.min(15, type.body) });
      if (image) {
        const mediaY = Math.max(162, subtitleY + subtitleH + 6);
        const mediaBottom = extra.length ? 389 : 438;
        const captionAllowance = photos.some(photo => photo.caption?.trim()) ? 40 : 0;
        const mediaHeight = mediaBottom - mediaY + captionAllowance;
        setPictures(box(94, mediaY, 772, mediaHeight), true);
      }
      const lastPhotoEdge = gallery?.reduce((edge, photo) => Math.max(edge, photo.y + photo.h), 0) ?? 0;
      const hasCaptions = photos.some(photo => photo.caption?.trim());
      const creditY = image ? Math.min(extra.length ? 432 : 482, lastPhotoEdge + (hasCaptions ? 48 : 10)) : subtitleY + subtitleH + 24;
      field({ ...fullWidth, y: creditY, h: 18 }, first.label, 'opening-credit', 'label-0', 'caption',
        { nodeId: first.id, align: 'center' });
      showUnit(box(left, 501, Math.min(180, width), unitHeight));
      if (extra.length) {
        const rowsY = creditY + (first.label ? 19 : 1);
        const cell = (width - (extra.length - 1) * gap) / extra.length;
        extra.forEach((i, n) => entry(i, left + n * (cell + gap), rowsY, cell, spacing.footer - rowsY, 'opening-extra-' + i));
      }
    } else if (variant === 'photo-comparison') {
      heading(box(left, top, width, header), type.title, 'left');
      const mediaY = top + header + gap;
      const labelY = bottom - 86;
      setPictures(box(left, mediaY, width, labelY - mediaY - 10));
      gallery.forEach((frame, i) => entry(i, frame.x, labelY, frame.w, bottom - labelY - unitHeight, 'pair-' + i));
      showUnit(box(left, bottom - unitHeight, width, unitHeight));
    } else if (variant === 'photo-work') {
      const footerY = written.length ? 373 : 412;
      setPictures(box(left, top, width, footerY - top - 20));
      const headlineWidth = written.length ? Math.floor(width * 0.49) : width;
      heading(box(left, footerY, headlineWidth, bottom - footerY), type.title, 'left');
      showUnit(box(left, spacing.footer, Math.min(180, width), unitHeight));
      if (written.length) rows(written, left + headlineWidth + gap, footerY + 1, width - headlineWidth - gap, bottom - footerY, 'work-details');
    } else {
      const side = variant === 'photo-work-side' || (variant === 'photo-essay' && image);
      const leftW = Math.floor(width * (side ? 0.53 : 0.43));
      const contentX = left + leftW + gap;
      const contentW = right - contentX;
      const titleX = side ? contentX : left;
      const titleW = side ? contentW : leftW;
      const headingH = Math.max(76, Math.min(174,
        textHeight(slide.title, type.title, titleW, type.lineHeight + 0.09, 1)));
      const detailsY = side ? top + headingH + 24 : top + 24;
      heading(box(titleX, top, titleW, headingH), type.title, 'left');
      if (image) {
        const mediaY = side ? top : top + headingH + 22;
        setPictures(box(left, mediaY, leftW, bottom - mediaY));
      }
      showUnit(box(contentX, detailsY, contentW, unitHeight));
      if (written.length) rows(written, contentX, detailsY + unitHeight, contentW, bottom - detailsY - unitHeight, 'essay-details');
    }
  } else if (cover) {
    const brief = variant === 'cover-brief';
    const region = reserveImage(box(left, brief ? 56 : 80, width, bottom - (brief ? 56 : 80)),
      brief ? 0.33 : graphics.imageShare);
    const detailY = brief ? 231 : indices.length > 1 ? 302 : 323;
    const titleY = brief ? 78 : 124;
    headingMark(region.x, titleY - 18, region.w);
    title(region.x, titleY, region.w, detailY - titleY - 13, brief ? type.title + 5 : type.cover);
    field(box(region.x, detailY, region.w, unitHeight), units, 'chart-unit', 'unit', 'caption');
    rows(indices, region.x, detailY + unitHeight, region.w, bottom - detailY - unitHeight, 'opening-detail');
  } else if (variant === 'statement-reading') {
    title(left, top, width, header);
    field(box(left, start, width, unitHeight), units, 'chart-unit', 'unit', 'caption');
    const readWidth = Math.floor(width * 0.88);
    const x = alignment === 'center' ? left + (width - readWidth) / 2 : left;
    let y = start + unitHeight;
    const heights = indices.map(i => {
      const { label, text: body } = items[i];
      const lines = (copy, size) => copy ? textHeight(copy, size, readWidth, type.lineHeight + 0.09, 1) : 0;
      return Math.max(1, lines(label, type.label) + lines(body, type.body) + 8);
    });
    const blockGap = Math.min(spacing.gap, 20);
    const scale = Math.min(1, (bottom - y - blockGap * (indices.length - 1)) / heights.reduce((a, b) => a + b, 0));
    indices.forEach((i, n) => {
      const h = heights[n] * scale;
      entry(i, x, y, readWidth, h, 'reading-' + n);
      y += h + blockGap;
    });
  } else if (variant === 'statement-takeaway' || variant === 'statement-wide') {
    const takeaway = variant === 'statement-takeaway';
    const labelY = takeaway ? top + 110 : bottom - 138;
    headingMark(left, top, width);
    field(box(left, top + 22, width, takeaway ? 74 : labelY - top - 34), slide.title,
      'headline', 'title', 'title', { size: takeaway ? type.label + 3 : type.title + 5,
        emphasis: takeaway ? 'secondary' : 'primary', align: alignment });
    rule(left, labelY - 8, width);
    field(box(left, bottom - 21, width, unitHeight), units, 'chart-unit', 'unit', 'caption');
    rowField(0, box(left, labelY + 4, width, 42), 'label', 'label', 'statement-caption');
    field(box(left, labelY + 50, width, bottom - labelY - 50 - unitHeight), items[0].text,
      takeaway ? 'takeaway' : 'statement-support', 'text-0', takeaway ? 'title' : 'body',
      { size: takeaway ? type.title - 3 : type.body + 3, nodeId: items[0].id,
        emphasis: takeaway ? 'primary' : 'secondary' });
  } else if (variant === 'statement-led' && alignment === 'left' && !image) {
    headingMark(left, top, titleWidth);
    title(left, top + 30, titleWidth, bottom - top - 30, type.title + 8);
    const contentX = left + titleWidth + gap;
    field(box(contentX, top, right - contentX, unitHeight), units, 'chart-unit', 'unit', 'caption');
    rows(indices, contentX, top + unitHeight, right - contentX, bottom - top - unitHeight, 'statement-support');
  } else {
    headingMark(left, top - 12, width);
    title(left, top, width, header + 2, variant === 'statement-led' ? type.title + 7 : type.title);
    field(box(left, start, width, unitHeight), units, 'chart-unit', 'unit', 'caption');
    const y = start + unitHeight;
    const h = bottom - y;
    if (layout === 'chart') {
      const details = variant.endsWith('-details');
      const supporting = [...new Set([...entries, ...annotations])].sort((a, b) => a - b);
      const region = reserveImage(box(left, y, width, h), details ? 0.28 : 0.34, 'right');
      const side = supporting.length && (details || supporting.length === 1);
      const stack = supporting.length && !side;
      const panelW = side ? Math.floor((region.w - gap) * (details ? 0.42 : 0.32)) : 0;
      const panelH = stack ? Math.min(124, Math.floor(h * 0.35)) : 0;
      const chartW = panelW ? region.w - gap - panelW : region.w;
      const chartLeft = !side || graphics.chartSide === 'left';
      const chartX = chartLeft ? region.x : region.x + panelW + gap;
      const inset = details && !supporting.length ? Math.min(52, chartW * 0.09) : 0;
      chart = {
        ...box(chartX + inset, y, chartW - 2 * inset, panelH ? h - panelH - 10 : h), encoding: chartEncoding,
        items: data.map((i) => items[i]), focus: data.indexOf(annotations[0]),
      };
      if (side && supporting.length === 1 && annotations.includes(supporting[0])) {
        const index = supporting[0];
        const x = chartLeft ? chartX + chartW + gap : region.x;
        const item = items[index];
        rule(x, y, panelW, 'accent');
        rowField(index, box(x, y + 10, panelW, 48), 'label', 'label', 'chart-focus-category');
        field(box(x, y + 63, panelW, 78), [String(item.value), units].filter(Boolean).join(' '),
          'chart-focus-value', null, 'value', { size: Math.min(type.display, type.title - 4),
            nodeId: item.id, emphasis: 'primary' });
        rowField(index, box(x, y + 146, panelW, Math.max(20, h - 146)), 'text', 'body', 'chart-focus-note');
      } else if (side) {
        rows(supporting, chartLeft ? chartX + chartW + gap : region.x, y, panelW, h, 'chart-support');
      }
      if (stack) {
        const cell = (region.w + gap) / supporting.length - gap;
        supporting.forEach((index, i) => {
          const x = region.x + i * (cell + gap);
          rule(x, bottom - panelH, cell);
          entry(index, x, bottom - panelH + 8, cell, panelH - 8, 'chart-support-' + i);
        });
      }
    } else if (variant === 'image-caption') {
      const imageH = Math.floor(h * 0.47);
      setPictures(box(left, y, width, imageH));
      rows(indices, left, y + imageH + 8, width, h - imageH - 8, 'image-caption');
    } else {
      const share = variant === 'image-hero' ? Math.min(0.64, graphics.imageShare + 0.13)
        : variant === 'image-split' ? graphics.imageShare - 0.05 : 0.29;
      const region = reserveImage(box(left, y, width, h), share);
      if (variant === 'comparison-pair' || ['process-flow', 'timeline-track'].includes(variant)) {
        const cell = (region.w + gap) / indices.length - gap;
        const comparison = layout === 'comparison';
        const timeline = variant === 'timeline-track';
        // Size a paired comparison to the two actual text blocks. A full-height
        // divider makes two short fault descriptions look like empty panels.
        let rowY = y;
        let rowH = h;
        if (comparison && !data.length) {
          const required = items.map(item => 46 + textHeight(item.label, type.label, cell, type.lineHeight, 1)
            + textHeight(item.text, type.body, cell, type.lineHeight, 1));
          rowH = Math.min(h, Math.max(106, ...required));
          rowY += Math.max(0, h - rowH) * 0.36;
        }
        if (comparison) rect(region.x + cell + gap / 2, rowY, graphics.rule, rowH, 'rule');
        if (timeline) rule(region.x + cell / 2, y + 5, (cell + gap) * (indices.length - 1));
        indices.forEach((i) => {
          const x = region.x + i * (cell + gap);
          if (comparison) rule(x, rowY, cell, 'accent');
          else point(timeline ? x + cell / 2 - 5 : x, y, 11);
          if (!comparison && !timeline && i < indices.length - 1) {
            rule(x + 19, y + 5, cell + gap - 32);
            marks.push({ type: 'text-arrow', ...box(x + cell + gap - 20, y - 5, 16, 22), color: 'accent' });
          }
          entry(i, x, rowY + 27, cell, rowH - 27, layout + '-' + i);
        });
      } else if (layout === 'sequence') {
        const step = h / indices.length;
        const span = (indices.length - 1) * step;
        if (span > 0) rect(region.x + 5, y + 13, graphics.rule, span, 'rule');
        indices.forEach((i) => {
          const yy = y + i * step;
          point(region.x, yy + 8, 11);
          entry(i, region.x + 29, yy + 3, region.w - 29, step - 9, 'sequence-' + i, true);
        });
      } else if (variant === 'statement-led') {
        const inset = Math.min(78, region.w * 0.15);
        rows(indices, region.x + inset, y, region.w - inset * 2, h, 'statement-support');
      } else {
        rows(indices, region.x, y, region.w, h, layout);
      }
    }
  }
  return { text, marks, picture, gallery, chart, palette: (cover && tokens.openingPalette) || palette };
}
