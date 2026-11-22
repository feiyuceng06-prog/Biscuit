import { eastAsian } from './planner.mjs';
import { reviewObjectId } from './review.mjs';

export const isTextOverflow = issue => issue.source === 'deterministic'
  && ['clipping', 'overflow'].includes(issue.kind);

const right = box => box.x + box.w;
const bottom = box => box.y + box.h;
const intersects = (a, b) => a.x < right(b) && right(a) > b.x && a.y < bottom(b) && bottom(a) > b.y;
const caption = object => object.field?.startsWith('caption-');
const floor = object => {
  if (object.field === 'title') return 20;
  if (object.field?.startsWith('text-')) return 14;
  if (object.field?.startsWith('label-')) return 11;
  return 10;
};

// Leave space for the widest Latin letters, CJK punctuation and font substitution.
const widthUnits = value => Array.from(value).reduce((sum, char) =>
  sum + (/^[MW@%]$/.test(char) ? 1 : char.codePointAt(0) < 128 ? 0.65 : 1.1), 0);
const estimatedHeight = object => object.value.split('\n').reduce((lines, line) =>
  lines + Math.max(1, Math.ceil(widthUnits(line) * object.size / Math.max(1, object.w - object.wrapPadding))), 0)
  * object.size * object.lineHeight + 5;

function typeset(object, size, frame = {}) {
  return { ...object, ...frame, size, lineHeight: 1.24, fit: 'none', wrapPadding: eastAsian.test(object.value) ? size * 2 : size };
}

function local(page, targets) {
  const next = [...page];
  for (const i of targets) {
    const object = next[i];
    const minimum = Math.min(object.size, floor(object));
    const size = Math.max(minimum, Math.floor(object.size * 0.85));
    const text = typeset(object, size);
    // An adjacent title, copy block, image or chart limits expansion on either axis.
    const free = candidate => !next.some((other, j) => i !== j
      && ['text', 'image', 'chart'].includes(other.type) && intersects(candidate, other));
    const left = Math.max(24, text.x - 14);
    const edge = Math.min(936, right(text) + 14);
    const wider = { ...text, x: left, w: edge - left };
    const box = wider.w > text.w && free(wider) ? wider : text;
    const taller = { ...box, h: Math.min(522 - box.y, box.h + 26) };
    const candidate = taller.h > box.h && free(taller) ? taller : box;
    if (estimatedHeight(candidate) <= candidate.h) next[i] = candidate;
  }
  return next;
}

// Nest all text in a reading band measured against the existing image/caption positions.
// The pictures, their native crop, the slide notes and all original text values stay intact.
function stack(objects, { x, y, w, h }, align) {
  for (const scale of [1, 0.88, 0.75, 0]) {
    const rows = objects.map(object =>
      typeset(object, Math.max(floor(object), Math.floor(Math.min(object.size, 36) * scale)), { x, w, align }));
    let top = y;
    const placed = rows.map(row => {
      const height = Math.ceil(estimatedHeight(row));
      const next = { ...row, y: top, h: height };
      top += height + 7;
      return next;
    });
    if (top - 7 <= y + h) return placed;
  }
}

function fallback(page, targets, variant, margin) {
  if (!['photo-cover', 'photo-work', 'photo-work-side', 'photo-essay'].includes(variant)
    || page.some(object => object.type === 'chart')) return page;
  const text = page.filter(object => object.type === 'text' && object.field && !caption(object));
  if (!text.length || !targets.some(i => text.includes(page[i]))) return page;
  const anchors = page.filter(object => object.type === 'image'
    || (object.type === 'text' && !text.includes(object)));
  const media = anchors.filter(object => object.type === 'image' || caption(object));
  const x = margin;
  const edge = 960 - margin;
  const band = (left, top, end) => ({ x: left, y: top, w: edge - left, h: end - top });
  const end = variant === 'photo-cover' ? 520 : 485;
  const title = text.find(object => object.field === 'title');
  const content = [title, ...text.filter(object => object !== title)].filter(Boolean);
  let placed;
  if (variant === 'photo-cover' && media.length) {
    const opening = content.filter(object => ['title', 'text-0'].includes(object.field));
    const credits = content.filter(object => !opening.includes(object));
    const header = stack(opening, band(x, 24, Math.min(...media.map(object => object.y)) - 8), 'center');
    const footer = stack(credits, band(x, Math.max(...media.map(bottom)) + 8, end), 'center');
    if (header && footer) placed = [...header, ...footer];
  } else if (variant === 'photo-work' && media.length) {
    placed = stack(content, band(x, Math.max(...media.map(bottom)) + 8, end), 'left');
  } else {
    const left = media.length ? Math.max(...media.map(right)) + 16 : x;
    placed = stack(content, band(left, 32, end), variant === 'photo-cover' ? 'center' : 'left');
  }
  if (!placed || placed.some(object => anchors.some(anchor => intersects(anchor, object)))) return page;
  const fields = new Map(placed.map(object => [object.field, object]));
  const background = page[0].color;
  return page.map(object => {
    if (object.type === 'text') return fields.get(object.field) ?? object;
    // Old row dividers would run through the text after reflow.
    if (object.type === 'rect' && object.h <= 2 && placed.some(field => intersects(field, object)))
      return { ...object, color: background };
    return object;
  });
}

export function repairPhotoPages(deck, pages, issues, stage) {
  const changes = [];
  const repaired = pages.map((page, index) => {
    const slideId = deck.slides[index].id;
    const ids = new Set(issues.filter(issue => isTextOverflow(issue) && issue.slideId === slideId)
      .flatMap(issue => issue.elementIds));
    const targets = page.flatMap((object, i) => object.type === 'text' && object.field
      && ids.has(reviewObjectId(object, i)) ? [i] : []);
    if (!targets.length) return page;
    const variant = deck.design.slidePlans[index].variant;
    const next = stage === 'local' ? local(page, targets)
      : fallback(page, targets, variant, deck.design.tokens.spacing.margin);
    const elementIds = next.flatMap((object, i) => object !== page[i] ? [reviewObjectId(object, i)] : []);
    if (elementIds.length) changes.push({ slideId, elementIds, layout: variant });
    return next;
  });
  return { pages: repaired, changes };
}
