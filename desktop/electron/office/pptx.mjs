import pptxgen from 'pptxgenjs';
import { readDeck, composition } from './deck.mjs';

export async function powerPoint(raw) {
  const deck = readDeck(raw);
  const ppt = new pptxgen();
  ppt.layout = 'LAYOUT_WIDE';
  ppt.author = 'Biscuit';
  ppt.title = deck.title;
  for (const [index, slide] of deck.slides.entries()) {
    const page = ppt.addSlide();
    for (const o of composition(slide, index + 1, deck.slides.length, deck.theme)) {
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
          fontFace: 'Microsoft YaHei',
          align: o.align || 'left',
          fontSize: o.size,
          bold: o.bold,
          color: o.color,
          margin: 0,
          valign: 'top',
          breakLine: false,
          fit: 'shrink',
          paraSpaceAfter: 0,
        });
      if (o.type === 'chart')
        page.addChart(
          ppt.ChartType.bar,
          [{ name: '数值', labels: o.items.map((r) => r.label), values: o.items.map((r) => r.value) }],
          {
            ...box,
            barDir: 'col',
            showLegend: false,
            showTitle: false,
            showValue: true,
            catAxisLabelFontSize: 13,
            catAxisLabelColor: o.ink,
            valAxisHidden: true,
            valGridLine: { style: 'none' },
            catAxisLineShow: true,
            catAxisLineColor: o.rule,
            catAxisLabelPos: 'low',
            dataLabelPosition: 'outEnd',
            dataLabelFormatCode: 'General',
            dataLabelColor: o.ink,
            chartColors: [o.accent],
            showCatName: false,
            showBorder: false,
          },
        );
      if (o.type === 'image') {
        // Keep the whole image visible in its reserved rectangle.
        page.addImage({ data: o.data, ...box });
      }
    }
    if (slide.notes) page.addNotes(slide.notes);
  }
  return ppt.write({ outputType: 'nodebuffer' });
}
