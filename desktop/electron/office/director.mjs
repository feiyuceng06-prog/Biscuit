import { directions } from './directions.mjs';
import { selectReference } from './references.mjs';
import { planSlides, textUnits } from './planner.mjs';
import { hasPhotos, photoCounts, photographyIntent } from './photos.mjs';

export { textUnits };

const densityRank = { sparse: 0, balanced: 1, dense: 2 };
const topicPatterns = {
  technology: /\b(?:technolog\w*|engineer\w*|developer\w*|architecture|infrastructure|api|systems?|devops|software|platform|latency)\b|技术|工程师|架构|平台|系统|研发|开发者/i,
  report: /\b(?:corporate|business|board|executive\w*|leadership|management|quarterly|finance|status|report\w*|operations|kpi)\b|企业|领导|管理层|董事|汇报|季度|财务|复盘|经营|周报/i,
  investor: /\b(?:investor\w*|fundrais\w*|venture|pitch|valuation)\b|投资|融资|路演/i,
  story: /\b(?:stor(?:y|ies|ytelling)|editorial|narrative|museum|exhibition|culture|creative|case stud(?:y|ies))\b|故事|叙事|编辑|展览|文化|策展|案例/i,
  teaching: /\b(?:students?|teach\w*|lesson\w*|educat\w*|training|classroom|lecture|workshop)\b|学生|教学|课程|培训|课堂|讲座/i,
  launch: /\b(?:launch\w*|product|keynote|customers?|clients?|showcase|introduc\w*|portfolio)\b|发布|新品|产品|客户|介绍|作品集/i,
};
const stagePattern = /\b(?:stage|project\w*|large[ -]screen|auditorium|keynote)\b|大屏|投影|现场演讲|会场/i;
const preReadPattern = /会前(?:预读|阅读)|书面简报|\bpre[- ]?read\b|\breading memo\b/i;
const printPattern = /\b(?:print\w*|handout\w*)\b|打印|印刷/i;
const topicWeights = {
  technology: { technology: 5 },
  report: { corporate: 5 },
  investor: { corporate: 4 },
  story: { editorial: 5 },
  teaching: { editorial: 3, minimal: 1 },
  launch: { minimal: 3 },
};

const record = (value) => value !== null && typeof value === 'object'
  && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
const invalid = () => { throw Error('演示文稿设计设置无效或超出限制'); };
const choice = (value, allowed) => allowed.includes(value) ? value : invalid();
function preferenceText(value, max) {
  if (typeof value !== 'string' || value.length > max) invalid();
  return value.trim();
}
function readPreferences(input) {
  if (!record(input)) invalid();
  const { direction = 'auto', audience = '', setting = '', reference } = input;
  const preferences = {
    direction: choice(direction, ['auto', ...Object.keys(directions)]),
    audience: preferenceText(audience, 120),
    setting: preferenceText(setting, 120),
  };
  if (input.brandAccent !== undefined && input.brandAccent !== '') {
    if (typeof input.brandAccent !== 'string' || !/^#?[0-9a-f]{6}$/i.test(input.brandAccent)) invalid();
    preferences.brandAccent = input.brandAccent.replace('#', '').toUpperCase();
  }
  if (input.background) preferences.background = choice(input.background, ['light', 'dark']);
  if (input.brandFont) {
    const font = preferenceText(input.brandFont, 64);
    if (!/^[\p{L}\p{N}][\p{L}\p{M}\p{N} ._-]*$/u.test(font)) invalid();
    preferences.brandFont = font;
  }
  if (reference !== undefined) {
    if (!record(reference)) invalid();
    const { id, name, slideCount, textDensity, hasCharts, hasImages, titleAlignment, palette } = reference;
    if (typeof id !== 'string' || !/^pptx-[a-f0-9]{64}$/.test(id)
      || !Number.isSafeInteger(slideCount) || slideCount < 1 || slideCount > 100
      || typeof hasCharts !== 'boolean' || typeof hasImages !== 'boolean') invalid();
    preferences.reference = {
      id, name: preferenceText(name, 255), slideCount,
      textDensity: choice(textDensity, Object.keys(densityRank)),
      hasCharts, hasImages,
      titleAlignment: choice(titleAlignment, ['left', 'center', 'mixed']),
      palette: choice(palette, ['light', 'dark', 'mixed']),
    };
  }
  return preferences;
}

function slideDensity(slide) {
  const units = textUnits(slide.title) + slide.items.reduce(
    (total, item) => total + textUnits(item.label) + textUnits(item.text), 0,
  );
  if (units > 190 || (units > 115 && slide.items.length >= 3)) return 'dense';
  return units < 60 ? 'sparse' : 'balanced';
}

function topicTags(text) {
  return Object.entries(topicPatterns).filter(([, pattern]) => pattern.test(text)).map(([topic]) => topic);
}

function chooseDirection(deck, preferences, densities, visualPlanner) {
  if (preferences.direction !== 'auto') return [preferences.direction, '采用指定的设计方向。'];
  if (hasPhotos(deck) || (visualPlanner && photographyIntent(`${deck.title} ${deck.brief}`)))
    return ['photography', '摄影素材或制作要求适合按摄影集组织。'];

  const scores = { minimal: 2, corporate: 0, editorial: 0, technology: 0 };
  const addTopics = (text, weight) => {
    for (const topic of topicTags(text)) {
      for (const [direction, points] of Object.entries(topicWeights[topic]))
        scores[direction] += weight * points;
    }
  };
  addTopics(preferences.audience, 2);
  addTopics(preferences.setting, 1.5);
  addTopics(`${deck.title} ${deck.brief}`, 1);
  addTopics(deck.slides.map((slide) => slide.title).join(' '), 0.5);

  const share = (test) => deck.slides.filter(test).length / deck.slides.length;
  const charts = share(({ layout }) => layout === 'chart');
  const images = share(({ image }) => Boolean(image));
  scores.corporate += 5 * share(({ layout }) => ['chart', 'comparison', 'timeline'].includes(layout));
  scores.editorial += 6 * images;
  scores.corporate += 4 * densities.filter((density) => density === 'dense').length / deck.slides.length;
  if (stagePattern.test(preferences.setting)) scores.minimal += 2;
  const { reference } = preferences;
  if (reference) {
    if (reference.palette === 'dark') scores.technology += 3;
    if (reference.titleAlignment === 'center' || reference.textDensity === 'sparse') scores.minimal += 3;
    if (reference.textDensity === 'dense') scores.corporate += 3;
    if (reference.hasCharts) scores.corporate += 3 * charts;
    if (reference.hasImages) scores.editorial += 3 * images;
  }

  const direction = Object.keys(scores).reduce((best, key) => scores[key] > scores[best] ? key : best);
  const explanation = {
    minimal: '受众、场景或内容支持以简明排版突出主要信息。',
    corporate: '汇报语境或证据密度适合用稳定的层级组织信息。',
    editorial: '叙事、教学或配图内容适合用有节奏的标题与留白串联。',
    technology: '技术语境或参考的明暗特征适合采用高对比线框。',
  };
  return [direction, explanation[direction]];
}

function slideRole(slide, index, total) {
  const roleForLayout = { cover: 'opening', chart: 'evidence', comparison: 'contrast', timeline: 'mechanism' };
  if (Object.hasOwn(roleForLayout, slide.layout)) return roleForLayout[slide.layout];
  if (/\b(?:transition|agenda|next up)\b|议程|过渡|章节/i.test(slide.title)) return 'transition';
  if (slide.layout === 'conclusion' && (index === total - 1
    || /\b(?:summary|conclusions?|takeaways?|next steps)\b|总结|结论|下一步/i.test(slide.title))) return 'conclusion';
  if (index <= 1 || /\b(?:context|background|overview)\b|背景|概览/i.test(slide.title)) return 'context';
  return slide.layout === 'image' && (slide.image || slide.photos?.length) ? 'evidence' : 'thesis';
}

function designTokens(direction, preferences, brief) {
  const style = directions[direction];
  const { reference, setting } = preferences;
  const stage = stagePattern.test(setting);
  const paletteMode = preferences.background ?? reference?.palette ?? (style.preferDark && !printPattern.test(setting) ? 'dark' : 'light');
  return {
    palette: { ...(paletteMode === 'dark' ? (style.dark ?? directions.editorial.dark) : style.light) },
    ...(paletteMode === 'mixed' && style.dark && { openingPalette: { ...style.dark } }),
    fonts: Object.fromEntries(Object.entries(style.fonts).map(([role, font]) => [
      role, preferences.brandFont
        ? { latin: preferences.brandFont, cjk: preferences.brandFont, fallback: [font.latin, font.cjk, ...font.fallback] }
        : { ...font, fallback: [...font.fallback] },
    ])),
    typography: {
      ...style.typography,
      title: style.typography.title + (stage ? 3 : 0),
      body: style.typography.body + (stage ? 2 : 0),
    },
    spacing: { ...style.spacing },
    graphics: {
      ...style.graphics,
      ...(preferences.brandAccent && { brandAccent: preferences.brandAccent }),
      imageShare: style.graphics.imageShare + (reference?.hasImages ? 0.04 : 0),
    },
    titleAlignment: reference?.titleAlignment ?? style.alignment,
    ...(!reference && preReadPattern.test(setting || brief) && { readingCopy: true }),
    density: reference?.textDensity ?? 'balanced',
  };
}

export function planDesign(deck, preferences = {}, { visualPlanner = false } = {}) {
  preferences = readPreferences(preferences);
  const densities = deck.slides.map(slideDensity);
  const [direction, reason] = chooseDirection(deck, preferences, densities, visualPlanner);
  const tokens = designTokens(direction, preferences, deck.brief);
  const photoPlanning = direction === 'photography' || hasPhotos(deck);
  const counts = photoPlanning ? photoCounts(deck.brief) : {};
  visualPlanner ||= photoPlanning;
  const selected = new Map();
  const deckTopics = topicTags(`${deck.title} ${deck.brief} ${preferences.audience} ${preferences.setting}`);
  const rhythm = deck.slides.map((slide, index) => {
    const role = slideRole(slide, index, deck.slides.length);
    const emphasis = slide.layout === 'chart' ? 'data'
      : slide.photos?.length || (slide.image && ['cover', 'image'].includes(slide.layout)) ? 'image' : 'text';
    // Keep enough capacity for the source content even when the reference was sparse.
    const density = preferences.reference && densityRank[tokens.density] > densityRank[densities[index]]
      ? tokens.density : densities[index];
    const reference = selectReference({
      layout: slide.layout, direction, density,
      topics: [...deckTopics, ...topicTags(slide.title)],
    });
    selected.set(reference.id, reference);
    return {
      slideId: slide.id, layout: slide.layout, role, emphasis, density,
      referenceId: reference.id, rationale: reference.allowedLessons[0],
    };
  });

  const reference = preferences.reference;
  const thesis = directions[direction].thesis;
  const referenceReason = reference ? '参考文稿提供明暗、标题对齐和密度偏好，页面布局仍以当前内容为准。' : '';
  return {
    version: visualPlanner === true ? 2 : 1,
    ...(visualPlanner === true && { slidePlans: planSlides(deck, rhythm, tokens, counts) }),
    direction,
    rationale: reason + thesis + referenceReason,
    rhythm,
    tokens,
    preferences,
    visualThesis: thesis,
    imageryPolicy: photoPlanning ? 'existing-slide-images-and-photos' : 'existing-slide-images',
    constraints: { aspectRatio: '16:9', preserveContent: true, nativeCharts: true },
    negativeRules: ['no-reference-content-or-assets', 'no-meaning-by-color-alone'],
    references: [...selected.values()].map((entry) => ({
      ...entry,
      layouts: [...entry.layouts], topics: [...entry.topics],
      allowedLessons: [...entry.allowedLessons], prohibitedReuse: [...entry.prohibitedReuse],
    })),
  };
}

export function restoreDesign(deck, design) {
  if (!record(design) || ![undefined, 1, 2].includes(design.version)
    || (design.version === 2 && !record(design.preferences))) invalid();
  // Preferences are the only persisted input. Rebuild all derived data for the current
  // slide order/content, even if a saved plan claims to be current.
  const { preferences = {} } = design;
  return planDesign(deck, preferences, { visualPlanner: design.version === 2 });
}
