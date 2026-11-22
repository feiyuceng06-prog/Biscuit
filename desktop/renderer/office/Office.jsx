import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, BriefcaseBusiness, FileText, FolderOpen, Plus, Upload, X, CircleAlert, Info, LoaderCircle } from 'lucide-react';
import { Canvas } from './Canvas.jsx';
import { createPortal } from 'react-dom';
import {
  newDeck,
  newSlide,
  outlineDeck,
  generatedBody,
  applyBody,
  preserveLayoutContent,
  readDeck,
} from '../../electron/office/deck.mjs';
import { requestPage } from './model.mjs';
import { draft } from './drafts.mjs';
import { libraryExample } from './library-example.mjs';
import readingRoom from './reading-room.jpg';
import { planDesign } from '../../electron/office/director.mjs';
import { catalogueComparison, hasPhotos, maxDeckPictureData, maxPhotos, photoCredits, photographyIntent, pictureDataSize } from '../../electron/office/photos.mjs';
import { DesignBrief } from './DesignBrief.jsx';
import { loadPhoto } from './Inspector.jsx';
import { Studio } from './Studio.jsx';

import './office.css';

const sample = libraryExample(readingRoom);
const mediaText = (value, limit) => value?.replace(/[\u0000-\u001f]/g, ' ').slice(0, limit);

export function Office({ workspace }) {
  const [deck, setDeck] = useState(null),
    current = useRef(null),
    history = useRef([]);
  const [ready, setReady] = useState(false),
    [stage, setStage] = useState('home');
  const [selected, setSelected] = useState(''),
    [count, setCount] = useState(8),
    [change, setChange] = useState('');
  const [busy, setBusy] = useState(''),
    [workingPage, setWorkingPage] = useState(null),
    [message, setMessage] = useState(''),
    [error, setError] = useState('');
  const autoDesign = useRef(false);
  const dialog = useRef(null),
    fileInput = useRef(null),
    reportInput = useRef(null),
    job = useRef(null);
  const index = Math.max(0, deck?.slides.findIndex((s) => s.id === selected) ?? 0);
  const slide = deck?.slides[index];

  useEffect(() => {
    let live = true;
    setReady(false);
    const flag = window.feiyuDesktop.core.invoke('presentation_design_enabled').catch(() => false);
    const saved = (workspace ? draft(workspace) : Promise.resolve(null)).catch(() => {
      if (live) setError('无法读取本地草稿，可打开已保存的源文件');
      return null;
    });
    Promise.all([flag, saved]).then(([enabled, value]) => {
      if (!live) return;
      autoDesign.current = enabled === true;
      if (value) {
        current.current = readDeck(value);
        setDeck(current.current);
      }
    }).catch(() => {
      if (live) setError('无法读取本地草稿，可打开已保存的源文件');
    }).finally(() => {
      if (live) setReady(true);
    });
    return () => {
      live = false;
      job.current?.abort();
    };
  }, [workspace]);

  function commit(next, record = true) {
    const previous = current.current;
    if (next === previous) return;
    if (next.design && next.design === previous?.design) {
      next = { ...next, design: planDesign(next, next.design.preferences, { visualPlanner: next.design.version === 2 }) };
    } else if (!next.design && (hasPhotos(next) || (next.brief !== previous?.brief && photographyIntent(next.brief)))) {
      next = { ...next, design: planDesign(next, {}, { visualPlanner: true }) };
    }
    if (record && previous) history.current = [...history.current.slice(-29), previous];
    current.current = next;
    setDeck(next);
    if (workspace)
      draft(workspace, next).catch(() => setError('本地草稿保存失败，请点击「保存源文件」'));
  }
  function undo() {
    const previous = history.current.pop();
    if (previous) {
      commit(previous, false);
      setMessage('已撤销');
    }
  }
  function select(id) {
    setSelected(id);
    setChange('');
  }
  function editSlide(id, patch) {
    const deck = current.current;
    const next = {
      ...deck,
      slides: deck.slides.map((s) =>
        s.id === id
          ? {
              ...s,
              ...(deck.design?.version === 2 ? preserveLayoutContent(s, patch) : patch),
              generated: s.generated || 'items' in patch || 'notes' in patch,
              revision: s.revision + (Object.keys(patch).some((k) => k !== 'title') ? 1 : 0),
            }
          : s,
      ),
    };
    if (
      ('image' in patch || 'photos' in patch) && pictureDataSize(next.slides, next.pendingPhotos) > maxDeckPictureData
    ) {
      setError('文稿图片总量已达上限，请移除图片后再导入');
      return;
    }
    commit(next);
  }
  function appendPhotos(deckId, slideId, photos) {
    const active = current.current;
    const page = active?.id === deckId && active.slides.find(s => s.id === slideId);
    if (!page) return;
    const ordered = [...(page.photos ?? []), ...photos];
    if (ordered.length > maxPhotos) {
      setError('每页最多可导入 ' + maxPhotos + ' 张照片');
      return;
    }
    setError('');
    editSlide(slideId, { photos: ordered });
  }
  function importPool(files) {
    if (!files.length) return;
    const snapshot = current.current;
    void run('正在读取待排版照片', async (signal) => {
      const pool = [...(snapshot.pendingPhotos ?? [])];
      if (pool.length + files.length > maxPhotos) throw Error('一次排版最多支持 12 张照片');
      for (const file of files) pool.push(await loadPhoto(file));
      signal.throwIfAborted();
      if (current.current !== snapshot) throw Error('材料已改变，请重新导入照片');
      if (pictureDataSize(snapshot.slides, pool) > maxDeckPictureData)
        throw Error('文稿图片总量已达上限');
      commit({ ...snapshot, pendingPhotos: pool, photoInput: snapshot.photoInput ?? { title: '', copy: '' } });
    });
  }
  function enter(next) {
    setStage(next);
    setError('');
    setMessage('');
  }
  function newPresentation(example = false) {
    if (
      current.current &&
      !window.confirm('新建将替换这份本地草稿。已保存的源文件可随时打开，继续新建吗？')
    )
      return;
    const next = example ? libraryExample(readingRoom) : newDeck();
    if (!example && autoDesign.current) next.design = planDesign(next, {}, { visualPlanner: true });
    history.current = [];
    commit(next, false);
    select(next.slides[0].id);
    enter(example ? 'edit' : 'source');
  }
  async function openFile(e) {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    try {
      if (file.size > 15_000_000) throw Error('源文件超过 15 MB');
      const next = readDeck(JSON.parse(await file.text()));
      if (current.current && !window.confirm('打开文件将替换本地草稿，继续吗？')) return;
      history.current = [];
      commit(next, false);
      select(next.slides[0].id);
      enter(next.pendingPhotos?.length ? 'source' : 'edit');
    } catch (e) {
      setError(e.message);
    }
  }
  async function report(file) {
    if (!file) return;
    try {
      if (!/\.(md|markdown|txt)$/i.test(file.name) || file.size > 125000)
        throw Error('请选择不超过 3 万字的 Markdown 或 TXT 文件');
      const text = await file.text();
      if (text.length > 30000) throw Error('参考材料最多支持 3 万字');
      commit({ ...current.current, source: text });
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }
  async function save(format) {
    try {
      setError('');
      const destination = await window.feiyuDesktop.core.invoke('presentation_save', {
        format,
        deck: current.current,
      });
      if (typeof destination === 'string') setMessage('已保存到 ' + destination);
      else if (destination?.initialReport) {
        const { status, repairAttempts, report } = destination;
        const label = status === 'draft' ? '导出仅保留为草稿' : status === 'export_failed' ? '导出失败'
          : status === 'checked' ? '基础检查通过' : '需复核';
        setMessage(label + (destination.destination ? ' · ' + destination.destination : '') +
          ' · 修复尝试 ' + repairAttempts + ' 次 · 报告 ' + report);
      } else if (destination) {
        const label = { checked: '基础检查通过', needs_review: '需复核', blocked: '发现阻断问题',
          preview_unavailable: '无法完成预览检查' }[destination.status];
        setMessage('已保存到 ' + destination.destination + ' · ' + label +
          (destination.critic === 'checked' ? ' · 已完成模型视觉审查' : ' · 模型视觉审查未完成') +
          (destination.report ? ' · 报告 ' + destination.report : ''));
      }
    } catch (e) {
      setError(e.message);
    }
  }
  async function run(label, work) {
    if (job.current) return;
    const controller = new AbortController();
    job.current = controller;
    setBusy(label);
    setError('');
    setMessage('');
    try {
      await work(controller.signal);
    } catch (e) {
      if (!controller.signal.aborted) setError(e.message);
    } finally {
      if (job.current === controller) {
        job.current = null;
        setBusy('');
        setWorkingPage(null);
      }
    }
  }
  function outline() {
    const original = current.current;
    if (
      (original.slides.length > 1 || original.slides.some((s) => s.generated || s.image || s.photos?.length)) &&
      !window.confirm('重新生成大纲会替换当前页面，可在完成后撤销。继续吗？')
    )
      return;
    void run('正在生成大纲', async (signal) => {
      const result = await requestPage(
        { action: 'outline', source: original.source, brief: original.brief, count,
          photoBrief: original.photoInput && JSON.stringify({ title: original.photoInput.title,
            finalCopy: original.photoInput.copy, files: (original.pendingPhotos ?? []).map(p => mediaText(p.name, 80)) }),
          direction: original.design?.preferences?.direction && original.design.preferences.direction !== 'auto'
            ? original.design.direction : original.photoInput ? 'photography' : original.design?.direction },
        signal,
      );
      signal.throwIfAborted();
      const next = outlineDeck(original, result, count);
      commit(next);
      select(next.slides[0].id);
      enter('edit');
      setMessage('大纲已生成，可以先调整标题和版式');
    });
  }
  function generate(all) {
    const original = current.current;
    const targets = all ? original.slides.filter((s) => !s.generated) : [slide];
    void run('正在生成正文', async (signal) => {
      let skipped = 0;
      for (const [i, target] of targets.entries()) {
        signal.throwIfAborted();
        const now = current.current;
        const active = now.slides.find((s) => s.id === target.id);
        if (!active || active.revision !== target.revision) {
          skipped++;
          continue;
        }
        setWorkingPage(active.id);
        setBusy(all ? '正在生成正文 ' + (i + 1) + ' / ' + targets.length : '正在重写本页正文');
        const requestedPhotos = now.design?.slidePlans?.find(plan => plan.slideId === active.id)
          ?.assetStrategy.photoCount?.requested;
        const media = active.photos?.length || requestedPhotos !== undefined
          ? JSON.stringify({
              requestedPhotos,
              sourceRows: photoCredits(now.source, active.photos).join('\n').slice(0, 1300),
              photos: (active.photos ?? []).map(({ name, caption }) => ({
                name: mediaText(name, 40), caption: mediaText(caption, 60),
              })),
            })
          : undefined;
        const catalogue = all && catalogueComparison(now, active);
        const response = catalogue || await requestPage(
          {
            action: 'slide',
            source: now.source,
            brief: now.brief,
            title: active.title,
            layout: active.layout,
            direction: now.design?.direction,
            outline: now.slides.map((s) => s.title).join('\n'),
            current: JSON.stringify({ items: active.items, unit: active.unit }),
            media,
            change: all ? '' : change,
          },
          signal,
        );
        signal.throwIfAborted();
        const latest = current.current;
        const next = applyBody(latest, active, generatedBody(active, response));
        if (next === latest) skipped++;
        else commit(next);
      }
      setMessage(
        skipped ? '已保留生成期间手动修改的页面' : all ? '逐页生成完成' : '本页正文已更新，可撤销',
      );
    });
  }
  function move(delta) {
    const rows = [...deck.slides];
    rows.splice(index + delta, 0, rows.splice(index, 1)[0]);
    commit({ ...deck, slides: rows });
  }
  function stop() {
    job.current?.abort();
    setMessage('已停止接收生成结果，已完成的页面已保留');
  }
  const pending = deck?.slides.filter((s) => !s.generated).length;
  return (
    <>
      <button
        className="nav"
        type="button"
        onClick={() => {
          enter('home');
          dialog.current.showModal();
        }}
      >
        <span className="nav__icon">
          <svg className="icon" viewBox="0 0 16 16" aria-hidden="true">
            <rect x="1.8" y="4.7" width="12.4" height="9" rx="1.5" />
            <path d="M5.3 4.5V3.3h5.4v1.2M2 8.5h12" />
          </svg>
        </span>
        <span className="nav__text">办公</span>
      </button>
      {createPortal(
        <dialog
          ref={dialog}
          className="office"
          data-stage={stage}
          aria-label="办公"
          onCancel={() => {
            if (job.current) stop();
          }}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (
              (e.ctrlKey || e.metaKey) &&
              e.key === 'z' &&
              !['INPUT', 'TEXTAREA'].includes(e.target.tagName) &&
              !busy
            ) {
              e.preventDefault();
              undo();
            }
          }}
        >
          {stage !== 'edit' && (
            <header className="office-bar">
              <div>
                <button onClick={() => enter('home')} disabled={!!busy || stage === 'home'}>
                  <BriefcaseBusiness size={18} aria-hidden="true" /> 办公
                </button>
                {stage !== 'home' && (
                  <>
                    <span aria-hidden="true">/</span>
                    <strong>演示文稿</strong>
                  </>
                )}
              </div>
              <div>
                <button
                  aria-label="关闭办公"
                  onClick={() => {
                    if (job.current) stop();
                    dialog.current.close();
                  }}
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </div>
            </header>
          )}
          <input hidden ref={fileInput} type="file" accept=".json" onChange={openFile} />
          {stage === 'home' && (
            <main className="office-home">
              <div className="office-library">
                <h1>演示文稿</h1>
                <p className="office-lead">从参考材料起草，在画布上编辑，再导出 PowerPoint。</p>
                <div className="office-actions">
                  <button className="office-primary" disabled={!ready} onClick={() => newPresentation()}>
                    <Plus size={17} />新建演示文稿
                  </button>
                  <button disabled={!ready} onClick={() => fileInput.current.click()}>
                    <FolderOpen size={17} />打开源文件
                  </button>
                </div>
                <section className="office-recent" aria-label="本工作区草稿">
                  <h2>本工作区草稿</h2>
                  {deck ? (
                    <button onClick={() => enter(deck.pendingPhotos?.length ? 'source' : 'edit')}>
                      <FileText size={18} /><strong>{deck.title}</strong><small>{deck.slides.length} 页</small><ArrowRight size={16} />
                    </button>
                  ) : <p>{ready ? '暂无草稿。新建后可在这里继续编辑。' : '正在读取草稿…'}</p>}
                </section>
              </div>
              <section className="office-sample">
                <h2>示例文稿</h2>
                <button className="office-sample-link" aria-label="打开示例文稿" disabled={!ready} onClick={() => newPresentation(true)}>
                  <Canvas slide={sample.slides[0]} index={0} total={sample.slides.length} theme={sample.theme} />
                  <span><strong>{sample.title}</strong><small>{sample.slides.length} 页</small><ArrowRight size={16} /></span>
                </button>
              </section>
            </main>
          )}
          {stage === 'source' && deck && (
            <main
              className="office-source"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (!busy) void report(e.dataTransfer.files[0]);
              }}
            >
              <h1>制作要求与材料</h1>
              <fieldset disabled={!!busy}>
                <label>
                  制作要求
                  <textarea
                    maxLength={1500}
                    placeholder="给管理层做一份项目汇报，重点讲风险与下一步决策"
                    value={deck.brief}
                    onChange={(e) => commit({ ...deck, brief: e.target.value })}
                  />
                </label>
                <label>
                  参考材料
                  <textarea
                    className="office-report"
                    maxLength={30000}
                    placeholder="粘贴项目报告，或将 Markdown、TXT 文件拖到这里"
                    value={deck.source}
                    onChange={(e) => commit({ ...deck, source: e.target.value })}
                  />
                </label>
                <div className="office-actions">
                  <button onClick={() => reportInput.current.click()}><Upload size={16} />导入材料</button>
                  <input
                    type="file"
                    hidden
                    ref={reportInput}
                    accept=".txt,.md,.markdown"
                    onChange={(e) => {
                      void report(e.target.files[0]);
                      e.target.value = '';
                    }}
                  />
                  <label>
                    页数
                    <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                      {Array.from({ length: 20 }, (_, i) => (
                        <option key={i}>{i + 1}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <details className="office-photo-intake">
                  <summary>摄影素材与指定原文</summary>
                  <label>待排版照片
                    <input type="file" multiple accept="image/png,image/jpeg" onChange={e => {
                      importPool(Array.from(e.target.files)); e.target.value = '';
                    }} />
                  </label>
                  {!!deck.pendingPhotos?.length && <p>待排版 {deck.pendingPhotos.length} 张
                    <button type="button" onClick={() => commit({ ...deck, pendingPhotos: [] })}>清空待排版照片</button></p>}
                  <small>要保留逐图出处，请在参考材料中每行填写「文件名 | 出处」。</small>
                  <label>首页标题（原样保留）<input maxLength={120} value={deck.photoInput?.title ?? ''}
                    onChange={e => commit({ ...deck, photoInput: { copy: '', ...deck.photoInput, title: e.target.value } })} /></label>
                  <label>末页正文（原样保留）<textarea maxLength={220} value={deck.photoInput?.copy ?? ''}
                    onChange={e => commit({ ...deck, photoInput: { title: '', ...deck.photoInput, copy: e.target.value } })} /></label>
                </details>
                <DesignBrief key={deck.id} deck={deck} commit={commit} onError={setError} disabled={!!busy} />
                <div className="office-actions office-submit">
                  <button
                    className="office-primary"
                    disabled={!deck.brief.trim() && !deck.source.trim() && !deck.photoInput?.title.trim()}
                    onClick={outline}
                  >
                    生成大纲
                  </button>
                  <button disabled={!!deck.pendingPhotos?.length} title={deck.pendingPhotos?.length ? '先生成大纲以分配待排版照片' : undefined} onClick={() => enter('edit')}>手动编辑</button>
                </div>
              </fieldset>
            </main>
          )}
          {stage === 'edit' && slide && (
            <Studio
              deck={deck}
              index={index}
              select={select}
              commit={commit}
              edit={(patch) => editSlide(slide.id, patch)}
              appendPhotos={(photos) => appendPhotos(deck.id, slide.id, photos)}
              onError={setError}
              move={move}
              workingPage={workingPage}
              busy={!!busy}
              canUndo={history.current.length > 0 && !busy}
              undo={undo}
              save={save}
              enter={enter}
              close={() => {
                if (job.current) stop();
                dialog.current.close();
              }}
              add={() => {
                const s = newSlide();
                commit({ ...deck, slides: [...deck.slides, s] });
                select(s.id);
              }}
              pending={pending}
              generate={generate}
              change={change}
              setChange={setChange}
            />
          )}
          {(error || busy || message) && (
            <footer className="office-status" role={error ? 'alert' : 'status'}>
              {error ? <CircleAlert size={17} /> : busy ? <LoaderCircle className="office-loading" size={17} /> : <Info size={17} />}
              <span>{error || busy || message}</span>
              {busy && <button onClick={stop}>停止生成</button>}
            </footer>
          )}
        </dialog>,
        document.body,
      )}
    </>
  );
}
