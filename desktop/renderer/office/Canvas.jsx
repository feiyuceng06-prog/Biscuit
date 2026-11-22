import React, { useState } from 'react';
import { composition } from '../../electron/office/deck.mjs';
import { maxPhotoCaption } from '../../electron/office/photos.mjs';

function Chart({ o }) {
  if (o.encoding) return <PlannedChart o={o} />;
  return <LegacyChart o={o} />;
}

function PlannedChart({ o }) {
  const horizontal = o.encoding === 'bars';
  const line = o.encoding === 'line';
  const labelWidth = horizontal ? o.plot.labelWidth : (o.w - 28) / o.items.length;
  const plotLeft = horizontal ? o.plot.left : 14;
  const plotRight = horizontal ? o.plot.right : o.w - 14;
  const plotTop = horizontal ? o.plot.top : 24;
  const plotBottom = horizontal ? o.plot.bottom : o.h - 48;
  const step = horizontal ? (plotBottom - plotTop) / o.items.length : (plotRight - plotLeft) / o.items.length;
  // Normalize first so the range stays finite even for large mixed-sign values.
  const scale = Math.max(-o.domain.min, o.domain.max);
  const low = o.domain.min / scale;
  const high = o.domain.max / scale;
  const fraction = (value) => (value / scale - low) / (high - low);
  const coordinate = horizontal
    ? (value) => plotLeft + (plotRight - plotLeft) * fraction(value)
    : (value) => plotBottom - (plotBottom - plotTop) * fraction(value);
  const zero = coordinate(0);
  const points = o.items.map(({ value }, i) => ({
    x: horizontal ? coordinate(value) : plotLeft + step * (i + 0.5),
    y: horizontal ? plotTop + step * (i + 0.5) : coordinate(value),
  }));
  return (
    <g fontFamily={o.fontFamily} transform={'translate(' + o.x + ' ' + o.y + ')'} data-encoding={o.encoding}>
      <line
        x1={horizontal ? zero : plotLeft}
        x2={horizontal ? zero : plotRight}
        y1={horizontal ? plotTop : zero}
        y2={horizontal ? plotBottom : zero}
        stroke={'#' + o.rule}
        strokeWidth={o.axisWidth}
      />
      {line && <polyline points={points.map(({ x, y }) => x + ',' + y).join(' ')}
        fill="none" stroke={'#' + o.colors[0]} strokeWidth={2.5} />}
      {o.items.map((item, i) => {
        const { x, y } = points[i];
        const bar = horizontal
          ? { x: Math.min(x, zero), y: y - step * 0.29, width: Math.abs(x - zero), height: step * 0.58 }
          : { x: x - step * 0.29, y: Math.min(y, zero), width: step * 0.58, height: Math.abs(y - zero) };
        const positive = item.value >= 0;
        return (
          <g key={item.id}>
            {line
              ? <circle cx={x} cy={y} r={3} fill={'#' + o.colors[i]} />
              : <rect {...bar} fill={'#' + o.colors[i]} />}
            <text
              x={horizontal ? x + (positive ? 7 : -7) : x}
              y={horizontal ? y : y + (line || positive ? -8 : o.valueSize + 4)}
              textAnchor={horizontal ? positive ? 'start' : 'end' : 'middle'}
              dominantBaseline={horizontal ? 'central' : undefined}
              fontSize={o.valueSize}
              fontFamily={o.valueFontFace}
              fill={'#' + o.ink}
            >
              {item.value}
            </text>
            {!o.wrappedCategories && <foreignObject x={horizontal ? 0 : x - labelWidth / 2}
              y={horizontal ? y - step / 2 : plotBottom + 8} width={labelWidth}
              height={horizontal ? step : 40}>
              <div className="office-chart-label" style={{
                display: 'flex', alignItems: horizontal ? 'center' : 'flex-start',
                justifyContent: horizontal ? 'flex-start' : 'center',
                height: '100%', textAlign: horizontal ? 'left' : 'center',
                color: '#' + o.ink, fontSize: o.categorySize,
              }}>
                {item.label}
              </div>
            </foreignObject>}
          </g>
        );
      })}
    </g>
  );
}

function LegacyChart({ o }) {
  const values = o.items.map((r) => r.value);
  const scale = Math.max(...values.map(Math.abs), 1);
  const high = Math.max(0, ...values) / scale,
    low = Math.min(0, ...values) / scale;
  const span = high - low || 1,
    height = o.h - 78;
  const baseline = 35 + (height * high) / span,
    step = (o.w - 40) / values.length;
  return (
    <g fontFamily={o.fontFamily} transform={'translate(' + o.x + ' ' + o.y + ')'}>
      <path d={'M10 ' + baseline + 'h' + (o.w - 20)} stroke={'#' + o.rule} strokeWidth={o.axisWidth} />
      {o.items.map((r, i) => {
        const x = 20 + step * (i + 0.5),
          top = baseline - (height * (r.value / scale)) / span;
        return (
          <g key={r.id}>
            <rect
              x={x - step * 0.28}
              y={Math.min(top, baseline)}
              width={step * 0.56}
              height={Math.max(1, Math.abs(top - baseline))}
              fill={'#' + o.colors[i]}
            />
            <text
              x={x}
              y={r.value >= 0 ? top - 8 : top + 18}
              textAnchor="middle"
              fontSize={o.valueSize ?? 17} fontWeight={o.valueBold ? 700 : undefined} fontFamily={o.valueFontFace}
              fill={'#' + o.ink}
            >
              {r.value}
            </text>
            <foreignObject x={x - step * 0.5} y={o.h - 28} width={step} height="30">
              <div className="office-chart-label" style={{ color: '#' + o.ink, fontSize: o.categorySize, fontWeight: o.categoryBold ? 700 : undefined }}>
                {r.label}
              </div>
            </foreignObject>
          </g>
        );
      })}
    </g>
  );
}
export function Canvas({ slide, index, total, theme, design, onEdit }) {
  const [active, setActive] = useState(null);
  const photoLayout = design?.slidePlans?.find(plan => plan.slideId === slide.id)?.variant.startsWith('photo-');
  const preview = onEdit
    ? {
        ...slide,
        title: slide.title || '点击添加标题',
        items: photoLayout ? slide.items : slide.items.map((r) => ({
          ...r,
          label: r.label || (design?.version === 2 && slide.layout === 'chart' ? '' : '添加小标题'),
          text: r.text || (slide.layout === 'chart' ? '' : '点击添加正文'),
        })),
        ...(active?.startsWith('caption-') && {
          photos: slide.photos?.map((photo, i) =>
            active === 'caption-' + i && !photo.caption?.trim() ? { ...photo, caption: '点击添加图注' } : photo),
        }),
      }
    : slide;
  return (
    <svg
      className="office-slide"
      viewBox="0 0 960 540"
      role={onEdit?'group':'img'}
      aria-label={slide.title || '无标题幻灯片'}
    >
      {composition(preview, index + 1, total, theme, design).map((o, i) => {
        const box = { x: o.x, y: o.y, width: o.w, height: o.h };
        if (o.type === 'rect') return <rect key={i} {...box} fill={'#' + o.color} />;
        if (o.type === 'ellipse')
          return (
            <ellipse
              key={i}
              cx={o.x + o.w / 2}
              cy={o.y + o.h / 2}
              rx={o.w / 2}
              ry={o.h / 2}
              fill={o.outline ? 'none' : '#' + o.color}
              stroke={o.outline ? '#' + o.color : 'none'}
              strokeWidth="1.25"
            />
          );
        if (o.type === 'image') {
          if (!o.crop) return <image key={i} {...box} href={o.data} preserveAspectRatio="none" data-photo-id={o.photoId} />;
          const { x, y, w, h } = o.crop;
          return <svg key={i} {...box} viewBox={`${x} ${y} ${w} ${h}`} overflow="hidden"
            preserveAspectRatio="none" data-photo-id={o.photoId}>
            <image x={0} y={0} width={1} height={1} href={o.data} preserveAspectRatio="none" />
          </svg>;
        }
        if (o.type === 'chart') return <Chart key={i} o={o} />;
        const [field, row] = o.field?.split('-') || [];
        const value = field === 'caption' ? slide.photos[row]?.caption ?? ''
          : row === undefined ? slide[field] : slide.items[row]?.[field];
        const style = {
          ...(o.wrapPadding && {
            paddingLeft: o.align === 'center' ? o.wrapPadding / 2 : 0,
            paddingRight: o.align === 'center' ? o.wrapPadding / 2 : o.wrapPadding,
            boxSizing: 'border-box',
          }),
          lineHeight: o.lineHeight, fontFamily: o.fontFamily || (o.serif ? '"Noto Serif CJK SC", "Songti SC", SimSun, serif' : undefined),
          textAlign: o.align, fontSize: o.size, color: '#' + o.color, fontWeight: o.bold ? 700 : 400,
          fontStyle: o.italic ? 'italic' : undefined,
        };
        return (
          <foreignObject key={o.field || i} {...box}>
            {onEdit && o.field && active === o.field ? (
              <textarea
                className="studio-inline"
                style={style}
                aria-label="画布文字"
                autoFocus
                maxLength={field === 'caption' ? maxPhotoCaption : field === 'unit' ? 24 : field === 'title' ? 120 : field === 'label' ? 60 : 220}
                value={value}
                onFocus={(e) => e.target.select()}
                onChange={(e) => onEdit(field, row, e.target.value)}
                onBlur={() => setActive(null)}
                onKeyDown={(e) => {
                  if (
                    !e.nativeEvent.isComposing &&
                    (e.key === 'Escape' || (e.key === 'Enter' && !e.shiftKey))
                  ) {
                    e.preventDefault();
                    e.stopPropagation();
                    setActive(null);
                  }
                }}
              />
            ) : (
              <div
                className="office-slide-text"
                data-editable={onEdit && o.field ? true : undefined}
                role={onEdit && o.field ? 'button' : undefined}
                tabIndex={onEdit && o.field ? 0 : undefined}
                onKeyDown={onEdit && o.field ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setActive(o.field);
                  }
                } : undefined}
                onClick={onEdit && o.field ? () => setActive(o.field) : undefined}
                style={{ ...style, opacity: onEdit && o.field && !value?.trim() ? 0.5 : 1 }}
              >
                {o.value}
              </div>
            )}
          </foreignObject>
        );
      })}
    </svg>
  );
}
