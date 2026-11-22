import React from 'react';
import { layouts, maxItems, blankItem, hasChartValue } from '../../electron/office/deck.mjs';

async function loadImage(file) {
  if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 12_000_000)
    throw Error('请选择 12 MB 以内的 PNG 或 JPEG');
  const image = await createImageBitmap(file);
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 1077;
    canvas.height = 810;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#E0EEE9';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const k = Math.min(canvas.width / image.width, canvas.height / image.height);
    const w = image.width * k,
      h = image.height * k;
    ctx.drawImage(image, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
    return canvas.toDataURL('image/jpeg', 0.87);
  } finally {
    image.close();
  }
}
export function Inspector({ slide, edit, error, planned = false }) {
  const updateItem = (id, patch) =>
    edit({ items: slide.items.map((item) => (item.id === id ? { ...item, ...patch } : item)) });
  const imageInput = async (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    try {
      edit({ image: await loadImage(file) });
    } catch (e) {
      error(e.message);
    }
  };
  const limit = maxItems(slide.layout);
  const supportsImage = planned || slide.layout === 'image' || slide.layout === 'cover';
  const isDataRow = row => slide.layout === 'chart' || (planned && hasChartValue(slide, row));
  const visibleItems = planned ? slide.items : slide.items.slice(0, limit);
  return (
    <aside className="office-inspector">
      <h3>编辑本页</h3>
      <label>
        页面标题
        <input
          id="office-field-title"
          maxLength={120}
          value={slide.title}
          onChange={(e) => edit({ title: e.target.value })}
        />
      </label>
      <label>
        版式
        <select value={slide.layout} onChange={(e) => edit({ layout: e.target.value })}>
          {Object.entries(layouts).map(([key, name]) => (
            <option key={key} value={key}>
              {name}
            </option>
          ))}
        </select>
      </label>
      {supportsImage && (
        <label>
          配图
          <input type="file" accept="image/png,image/jpeg" onChange={imageInput} />
        </label>
      )}
      {supportsImage && slide.image && (
        <button onClick={() => edit({ image: '' })}>移除配图</button>
      )}
      {(slide.layout === 'chart' || (planned && slide.items.some(row => hasChartValue(slide, row)))) && (
        <label>
          图表单位
          <input maxLength={24} value={slide.unit || ''} onChange={(e) => edit({ unit: e.target.value })} />
        </label>
      )}
      {visibleItems.map((row, i) => (
        <fieldset key={row.id}>
          <legend>
            {isDataRow(row) ? '数据' : '内容'} {i + 1}
          </legend>
          <label>
            小标题
            <input
              id={'office-field-label-' + i}
              maxLength={60}
              value={row.label}
              onChange={(e) => updateItem(row.id, { label: e.target.value })}
            />
          </label>
          {isDataRow(row) ? (
            <label>
              数值
              <input
                type="number"
                step="any"
                defaultValue={planned && !hasChartValue(slide, row) ? '' : row.value}
                key={String(row.value) + (row.valueKind || '')}
                onBlur={(e) => {
                  if (e.target.value !== '' && Number.isFinite(e.target.valueAsNumber))
                    updateItem(row.id, { value: e.target.valueAsNumber, ...(planned && { valueKind: 'chart-data' }) });
                  else if (planned && e.target.value === '' && hasChartValue(slide, row))
                    updateItem(row.id, { value: 0, valueKind: 'text' });
                }}
              />
            </label>
          ) : (
            <label>
              正文
              <textarea
                id={'office-field-text-' + i}
                maxLength={220}
                value={row.text}
                onChange={(e) => updateItem(row.id, { text: e.target.value })}
              />
            </label>
          )}
          {isDataRow(row) && (
            <label>
              {planned ? '数据说明' : '图旁解读（显示第一条非空解读）'}
              <textarea maxLength={220} value={row.text} onChange={(e) => updateItem(row.id, { text: e.target.value })} />
            </label>
          )}
          {slide.items.length > 1 && (
            <button onClick={() => edit({ items: slide.items.filter((item) => item.id !== row.id) })}>
              移除这一项
            </button>
          )}
        </fieldset>
      ))}
      {slide.items.length < limit && (
        <button onClick={() => edit({ items: [...slide.items, { ...blankItem(), ...(planned && { valueKind: 'text' }) }] })}>添加内容项</button>
      )}
      <label>
        演讲备注
        <textarea
          maxLength={1200}
          value={slide.notes}
          onChange={(e) => edit({ notes: e.target.value })}
        />
      </label>
    </aside>
  );
}
