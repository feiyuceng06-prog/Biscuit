export const maxPhotos = 12;
export const maxPictureData = 3_000_000;
export const maxDeckPictureData = 12_000_000;
export const maxPhotoCaption = 160;

export function pictureDataSize(slides) {
  return slides.reduce((size, slide) => size + slide.image.length
    + (slide.photos ?? []).reduce((sum, photo) => sum + photo.data.length, 0), 0);
}

export function pictureRatio(data, checkType = false) {
  const comma = data.indexOf(',') + 1;
  try {
    function header(length) {
      const bytes = atob(data.slice(comma, comma + length));
      return new DataView(Uint8Array.from(bytes, char => char.charCodeAt(0)).buffer);
    }
    let view = header(32);
    if (view.getUint32(0) === 0x89504e47 && view.getUint32(4) === 0x0d0a1a0a
      && view.getUint32(12) === 0x49484452 && (!checkType || data.startsWith('data:image/png;'))) {
      const width = view.getUint32(16), height = view.getUint32(20);
      return width && height ? width / height : undefined;
    }
    if (view.getUint16(0) === 0xffd8 && (!checkType || data.startsWith('data:image/jpeg;'))) {
      view = header(4096);
      let pos = 2;
      while (pos + 9 < (data.length - comma) * 0.75) {
        if (pos + 9 >= view.byteLength)
          view = header(Math.max(Math.ceil((pos + 12) / 3) * 4, Math.ceil(view.byteLength / 3) * 8));
        if (view.getUint8(pos++) !== 0xff) break;
        const marker = view.getUint8(pos);
        if (marker === 0xff) continue;
        pos++;
        const length = view.getUint16(pos);
        if (length < 2 || marker === 0xda || marker === 0xd9) break;
        if (length >= 8 && marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
          const width = view.getUint16(pos + 5), height = view.getUint16(pos + 3);
          return width && height ? width / height : undefined;
        }
        pos += length;
      }
    }
  } catch { /* A missing or incomplete header cannot supply an aspect ratio. */ }
}

export function validPhotos(photos) {
  if (!Array.isArray(photos) || photos.length > maxPhotos) return false;
  const ids = new Set();
  return photos.every(photo => {
    if (!photo || typeof photo.id !== 'string' || !photo.id || photo.id.length > 80 || ids.has(photo.id)
      || (photo.name !== undefined && (typeof photo.name !== 'string' || photo.name.length > 255))
      || (photo.caption !== undefined && (typeof photo.caption !== 'string' || photo.caption.length > maxPhotoCaption))
      || ![undefined, 'contain', 'cover'].includes(photo.fit)
      || (photo.focus !== undefined && (!photo.focus
        || ![photo.focus.x, photo.focus.y].every(n => Number.isFinite(n) && n >= 0 && n <= 1)))
      || typeof photo.data !== 'string' || photo.data.length > maxPictureData
      || !/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/.test(photo.data)
      || (photo.data.length - photo.data.indexOf(',') - 1) % 4 === 1
      || !pictureRatio(photo.data, true)) return false;
    ids.add(photo.id);
    return true;
  });
}

export const hasPhotos = deck => deck.slides.some(slide => slide.photos?.length);
const photoRoles = {
  cover: /封面|\b(?:cover|title slide)\b/i,
  image: /作品页|图像页|\b(?:gallery|image|work|portfolio) (?:slide|page)s?\b/i,
  conclusion: /说明页|\b(?:essay|explanation|notes?) (?:slide|page)s?\b/i,
};
export const photographyIntent = value =>
  /摄影(?:作)?品集|摄影集|摄影作品|影集|\b(?:photo(?:graphy|graphic)?[- ](?:book|essay|portfolio|collection|album)|photobook|photography showcase)\b/i.test(value)
  || (photoRoles.cover.test(value) && (photoCounts(value).cover ?? 0) >= 2);

const englishCounts = 'zero one two three four five six seven eight nine ten eleven twelve'.split(' ');
const chineseCounts = '零 一 二 三 四 五 六 七 八 九 十 十一 十二'.split(' ');
const photoNoun = 'photos?|photographs?|pictures?|images?';
const englishCount = new RegExp(
  `\\b(\\d+|${englishCounts.join('|')})[ -]+(?:(?:individual|independent|separate|portrait|landscape|black-and-white) )*(?:${photoNoun})\\b`, 'gi');
const chineseCount = /(\d+|[一二两三四五六七八九]?十[一二三四五六七八九]?|[零一二两三四五六七八九])\s*(?:张|幅)\s*(?:(?:独立|黑白|竖版|横版|人像|风景)\s*)*(?:摄影(?:作品)?|照片|图片|图像|相片|图)/g;

function countsIn(text) {
  const normalized = text.normalize('NFKC').toLowerCase();
  return [
    ...Array.from(normalized.matchAll(englishCount), ([, value]) =>
      /^\d+$/.test(value) ? Number(value) : englishCounts.indexOf(value)),
    ...Array.from(normalized.matchAll(chineseCount), ([, value]) =>
      /^\d+$/.test(value) ? Number(value) : chineseCounts.indexOf(value === '两' ? '二' : value)),
  ];
}

// The requested count is a brief constraint. The imported assets determine the actual layout.
export function photoCounts(brief) {
  const counts = {};
  for (const clause of brief.split(/[。；;\n]|\.\s+/)) {
    const mentions = Object.entries(photoRoles).flatMap(([role, pattern]) => {
      const match = pattern.exec(clause);
      return match ? [{ role, index: match.index, end: match.index + match[0].length }] : [];
    }).sort((a, b) => a.index - b.index);
    const add = (role, values) => (counts[role] ??= []).push(...values);
    if (mentions.length < 2) {
      add(mentions[0]?.role ?? 'general', countsIn(clause));
      continue;
    }
    const leadingCount = countsIn(clause.slice(0, mentions[0].index)).length > 0;
    mentions.forEach(({ role, index, end }, i) => {
      const segment = leadingCount ? clause.slice(mentions[i - 1]?.end ?? 0, index)
        : clause.slice(end, mentions[i + 1]?.index ?? clause.length);
      add(role, countsIn(segment));
    });
  }
  const result = {};
  for (const role of Object.keys(photoRoles)) {
    const distinct = new Set(counts[role]?.length ? counts[role] : role === 'cover' ? counts.general : []);
    const [count] = distinct;
    if (distinct.size === 1 && count >= 0 && count <= maxPhotos) result[role] = count;
  }
  return result;
}

export function pictureObject(region, data, fit = 'contain', focus = { x: 0.5, y: 0.5 }) {
  const { x, y, w, h } = region;
  const ratio = pictureRatio(data) ?? 1077 / 810;
  if (fit === 'contain') {
    const width = Math.min(w, h * ratio);
    const height = width / ratio;
    return { type: 'image', x: x + (w - width) / 2, y: y + (h - height) / 2, w: width, h: height, data };
  }
  const width = Math.min(1, w / (h * ratio));
  const height = Math.min(1, h * ratio / w);
  const offset = (value, span) => Math.max(0, Math.min(1 - span, value - span / 2));
  return { type: 'image', x, y, w, h, data, crop: {
    x: offset(focus.x, width), y: offset(focus.y, height), w: width, h: height,
  } };
}

export function galleryFrames(photos, { x, y, w, h }, strip = false) {
  const count = photos.length;
  if (!count) return [];
  const captions = photos.some(photo => photo.caption?.trim());
  const captionGap = captions ? 6 : 0;
  const gap = strip ? 7 : 12;
  if (strip && count <= 7) {
    const captionHeight = captions ? 34 : 0;
    const usable = h - captionGap - captionHeight;
    const sizes = photos.map((_, i) => {
      if (count === 1) return [440, 274];
      if (count === 2) return [286, 250];
      const distance = Math.abs(i - (count - 1) / 2);
      if (distance === 0) return [236, 274];
      if (distance <= 1) return [168, 214];
      return [86, 157];
    });
    const sum = sizes.reduce((total, [width]) => total + width, 0);
    const scaleX = Math.min(1, (w - gap * (count - 1)) / sum);
    const scaleY = Math.min(1, usable / 274);
    let left = x + (w - sum * scaleX - gap * (count - 1)) / 2;
    const center = y + usable / 2;
    return sizes.map(([width, height]) => {
      const frame = { x: left, y: center - height * scaleY / 2, w: width * scaleX, h: height * scaleY,
        captionY: center + 137 * scaleY + captionGap, captionHeight };
      left += frame.w + gap;
      return frame;
    });
  }

  const columns = count <= 3 ? count : count <= 6 ? Math.ceil(count / 2) : count <= 9 ? 3 : 4;
  const rows = Math.ceil(count / columns);
  const width = (w - gap * (columns - 1)) / columns;
  const step = (h + gap) / rows;
  const captionHeight = captions ? Math.min(34, (step - gap - captionGap) * 0.45) : 0;
  const height = step - gap - captionGap - captionHeight;
  return photos.map((_, i) => {
    const row = Math.floor(i / columns);
    const inRow = Math.min(columns, count - row * columns);
    const top = y + row * step;
    return { x: x + (columns - inRow) * (width + gap) / 2 + (i % columns) * (width + gap),
      y: top, w: width, h: height, captionY: top + height + captionGap, captionHeight };
  });
}
