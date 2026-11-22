import pptxgen from 'pptxgenjs';
import { photoCredits } from './photos.mjs';
import { readDeck, exportPages } from './deck.mjs';

// PptxGenJS interprets numeric values of 100 or more as EMUs.
const imageCoord = (inches) => inches >= 100 ? Math.round(inches * 914400) : inches;
const pictureName = (value) => value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');

export async function powerPoint(raw, pages) {
  const deck = readDeck(raw);
  const ppt = new pptxgen();
  ppt.layout = 'LAYOUT_WIDE';
  ppt.author = 'Biscuit';
  ppt.title = deck.title;
  for (const [index, objects] of (pages ?? exportPages(deck)).entries()) {
    const page = ppt.addSlide();
    for (const o of objects) {
      const box = { x: o.x / 72, y: o.y / 72, w: o.w / 72, h: o.h / 72 };
      if (o.type === 'rect')
        page.addShape(ppt.ShapeType.rect, {
          ...box,
          line: { transparency: 100 },
          fill: { color: o.color },
        });
      if (o.type === 'ellipse')
        page.addShape(ppt.ShapeType.ellipse, {
          ...box,
          line: o.outline ? { color: o.color, width: 1.25 } : { transparency: 100 },
          fill: o.outline ? { color: o.color, transparency: 100 } : { color: o.color },
        });
      if (o.type === 'text')
        page.addText(o.value, {
          ...box,
          fontFace: o.fontFace ?? (o.serif ? 'Noto Serif CJK SC' : 'Microsoft YaHei'),
          ...(o.lineHeight && { lineSpacing: o.size * o.lineHeight }),
          lang: 'zh-CN',
          align: o.align || 'left',
          fontSize: o.size,
          bold: o.bold,
          italic: o.italic,
          color: o.color,
          // Office and LibreOffice can hang CJK punctuation past the wrap boundary.
          // PptxGenJS writes the first two array entries as the left and right insets.
          margin: o.wrapPadding
            ? o.align === 'center'
              ? [o.wrapPadding / 2, o.wrapPadding / 2, 0, 0]
              : [0, o.wrapPadding, 0, 0]
            : 0,
          valign: 'top',
          breakLine: false,
          fit: o.fit ?? 'shrink',
          paraSpaceAfter: 0,
        });
      if (o.type === 'chart')
        page.addChart(
          o.encoding === 'line' ? ppt.ChartType.line : ppt.ChartType.bar,
          // PptxGenJS 4 writes a falsy numeric zero as an empty worksheet cell.
          // Its XML writer emits the literal '0' as a number in both the workbook and chart cache.
          [{ name: '数值', labels: o.items.map((r) => r.label), values: o.items.map((r) => r.value === 0 ? '0' : r.value) }],
          {
            ...box,
            barDir: o.encoding === 'bars' ? 'bar' : 'col',
            ...(o.encoding === 'bars' && { catAxisOrientation: 'maxMin', catAxisCrossesAt: 'max' }),
            ...(o.wrappedCategories && { layout: {
              x: o.plot.left / o.w, y: o.plot.top / o.h,
              w: (o.plot.right - o.plot.left) / o.w, h: (o.plot.bottom - o.plot.top) / o.h,
            } }),
            ...(o.encoding === 'line' && { lineSize: 2.5, lineDataSymbol: 'circle', lineDataSymbolSize: 6 }),
            ...(o.domain && {
              valAxisMinVal: o.domain.min,
              valAxisMaxVal: o.domain.max,
              barGapWidthPct: 70,
            }),
            showLegend: false,
            showTitle: false,
            showValue: true,
            catAxisLabelFontSize: o.categorySize ?? 13,
            ...(o.fontFace && {
              catAxisLabelFontFace: o.fontFace,
              catAxisLabelFontBold: o.categoryBold,
              catAxisLineSize: o.axisWidth,
              catAxisLabelFrequency: 1,
              dataLabelFontFace: o.valueFontFace,
              dataLabelFontBold: o.valueBold,
            }),
            catAxisLabelColor: o.ink,
            valAxisHidden: true,
            valGridLine: { style: 'none' },
            catAxisLineShow: true,
            catAxisLineColor: o.rule,
            catAxisLabelPos: o.wrappedCategories ? 'none' : 'low',
            dataLabelPosition: o.encoding === 'line' ? 't' : 'outEnd',
            dataLabelFormatCode: 'General',
            dataLabelColor: o.ink,
            chartColors: o.colors,
            dataLabelFontSize: o.valueSize ?? 15,
            showCatName: false,
            showBorder: false,
          },
        );
      if (o.type === 'image') {
        const options = { data: o.data, ...box,
          ...(o.photoId && { objectName: pictureName(o.name || o.photoId), altText: pictureName(o.alt) }) };
        if (o.crop) {
          // Set the source size and native crop independently so PowerPoint retains the full media.
          const width = box.w / o.crop.w;
          const height = box.h / o.crop.h;
          options.w = imageCoord(width);
          options.h = imageCoord(height);
          options.sizing = { type: 'crop', w: box.w, h: box.h,
            x: imageCoord(o.crop.x * width), y: imageCoord(o.crop.y * height) };
        }
        page.addImage(options);
      }
    }
    const slide = deck.slides[index];
    const credits = photoCredits(deck.source, slide.photos).filter(line => !slide.notes.includes(line));
    const notes = [slide.notes, ...credits].filter(Boolean).join('\n');
    if (notes) page.addNotes(notes);
  }
  return ppt.write({ outputType: 'nodebuffer' });
}
