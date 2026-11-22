import React from 'react';
import { composition } from '../../electron/office/deck.mjs';

function Chart({ o }) {
  const values = o.items.map((r) => r.value);
  const scale = Math.max(...values.map(Math.abs), 1);
  const high = Math.max(0, ...values) / scale,
    low = Math.min(0, ...values) / scale;
  const span = high - low || 1,
    height = o.h - 78;
  const baseline = 35 + (height * high) / span,
    step = (o.w - 40) / values.length;
  return (
    <g transform={'translate(' + o.x + ' ' + o.y + ')'}>
      <path d={'M10 ' + baseline + 'h' + (o.w - 20)} stroke="#9BAFAA" />
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
              fill="#007E75"
            />
            <text
              x={x}
              y={r.value >= 0 ? top - 8 : top + 18}
              textAnchor="middle"
              fontSize="17"
              fill="#172F37"
            >
              {r.value}
            </text>
            <foreignObject x={x - step * 0.5} y={o.h - 28} width={step} height="30">
              <div className="office-chart-label">{r.label}</div>
            </foreignObject>
          </g>
        );
      })}
    </g>
  );
}
export function Canvas({ slide, index, total, onEdit }) {
  return (
    <svg
      className="office-slide"
      viewBox="0 0 960 540"
      role="img"
      aria-label={slide.title || '无标题幻灯片'}
    >
      {composition(slide, index + 1, total).map((o, i) => {
        const box = { x: o.x, y: o.y, width: o.w, height: o.h };
        if (o.type === 'rect') return <rect key={i} {...box} fill={'#' + o.color} />;
        if (o.type === 'image')
          return <image key={i} {...box} href={o.data} preserveAspectRatio="none" />;
        if (o.type === 'chart') return <Chart key={i} o={o} />;
        return (
          <foreignObject
            key={i}
            {...box}
            onDoubleClick={onEdit && o.field ? () => onEdit(o.field) : undefined}
          >
            <div
              className="office-slide-text"
              style={{
                fontSize: o.size,
                color: '#' + o.color,
                fontWeight: o.bold ? 700 : 400,
              }}
            >
              {o.value}
            </div>
          </foreignObject>
        );
      })}
    </svg>
  );
}
