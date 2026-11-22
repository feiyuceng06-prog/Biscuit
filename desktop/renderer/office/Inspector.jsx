import React, { useState } from 'react';
import { layouts, maxItems, blankItem, hasChartValue, uid } from '../../electron/office/deck.mjs';
import { maxPhotos, maxPhotoCaption, maxPictureData } from '../../electron/office/photos.mjs';

const imageTypes = ['image/png', 'image/jpeg'];

async function loadImage(file) {
  if (!imageTypes.includes(file.type) || file.size > 12_000_000)
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

export async function loadPhoto(file) {
  if (!imageTypes.includes(file.type) || file.size > 30_000_000)
    throw Error('请选择 30 MB 以内的 PNG 或 JPEG 照片');
  const image = await createImageBitmap(file, { imageOrientation: 'from-image' });
  try {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    let longestEdge = Math.min(1800, Math.max(image.width, image.height));
    while (true) {
      const scale = longestEdge / Math.max(image.width, image.height);
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      const data = canvas.toDataURL(file.type, 0.88);
      if (data === 'data:,') throw Error('无法处理照片，请选择尺寸更小的文件');
      if (data.length <= maxPictureData) return { id: uid(), name: file.name.slice(0, 255), data };
      longestEdge = Math.floor(longestEdge * 0.75);
    }
  } finally {
    image.close();
  }
}

function PhotoInspector({ photos, edit, appendPhotos, error }) {
  const [importing, setImporting] = useState(false);
  async function importFiles(event) {
    const files = Array.from(event.target.files);
    event.target.value = '';
    if (!files.length) return;
    if (photos.length + files.length > maxPhotos) {
      error('每页最多可导入 ' + maxPhotos + ' 张照片');
      return;
    }
    setImporting(true);
    try {
      const imported = [];
      for (const file of files) imported.push(await loadPhoto(file));
      appendPhotos(imported);
    } catch (e) {
      error(e.name === 'InvalidStateError' ? '无法读取照片，请选择有效的 PNG 或 JPEG' : e.message);
    } finally {
      setImporting(false);
    }
  }
  function update(index, patch) {
    edit({ photos: photos.map((photo, i) => i === index ? { ...photo, ...patch } : photo) });
  }
  function move(index, delta) {
    const ordered = [...photos];
    const [photo] = ordered.splice(index, 1);
    ordered.splice(index + delta, 0, photo);
    edit({ photos: ordered });
  }
  return (
    <fieldset className="office-photos">
      <legend>本页照片 <span>{photos.length} / {maxPhotos}</span></legend>
      <label>导入照片
        <input type="file" multiple accept={imageTypes.join(',')} onChange={importFiles}
          disabled={importing || photos.length >= maxPhotos} />
      </label>
      {importing && <small role="status">正在导入照片…</small>}
      {photos.map((photo, index) => {
        const name = photo.name || '照片 ' + (index + 1);
        const focus = photo.focus ?? { x: 0.5, y: 0.5 };
        return (
          <details className="office-photo" key={photo.id}>
            <summary><img src={photo.data} alt="" /><span>{name}</span></summary>
            <label>图注
              <input maxLength={maxPhotoCaption} value={photo.caption ?? ''}
                onChange={e => update(index, { caption: e.target.value })} />
            </label>
            <label>填充方式
              <select value={photo.fit ?? 'contain'} onChange={e => update(index, { fit: e.target.value })}>
                <option value="contain">显示完整照片</option>
                <option value="cover">裁切以填满相框</option>
              </select>
            </label>
            {photo.fit === 'cover' && Object.entries({ x: '水平焦点', y: '垂直焦点' }).map(([axis, label]) => (
              <label key={axis}>{label}
                <input type="range" min="0" max="100" step="1" value={Math.round(focus[axis] * 100)}
                  onChange={e => update(index, { focus: { ...focus, [axis]: e.target.valueAsNumber / 100 } })} />
              </label>
            ))}
            <div className="office-actions">
              <button type="button" aria-label={'前移 ' + name} disabled={!index} onClick={() => move(index, -1)}>前移</button>
              <button type="button" aria-label={'后移 ' + name} disabled={index === photos.length - 1} onClick={() => move(index, 1)}>后移</button>
              <button type="button" aria-label={'移除 ' + name} onClick={() => edit({ photos: photos.filter((_, i) => i !== index) })}>移除</button>
            </div>
          </details>
        );
      })}
    </fieldset>
  );
}

export function Inspector({ slide, edit, appendPhotos, error, planned = false }) {
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
      <PhotoInspector photos={slide.photos ?? []} edit={edit} appendPhotos={appendPhotos} error={error} />
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
