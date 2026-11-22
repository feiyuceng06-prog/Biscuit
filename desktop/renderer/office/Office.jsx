import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  newDeck,
  newSlide,
  outlineDeck,
  generatedBody,
  applyBody,
  readDeck,
  layouts,
} from '../../electron/office/deck.mjs';
import { requestPage } from './model.mjs';
import { draft } from './drafts.mjs';
import { Canvas } from './Canvas.jsx';
import { Inspector } from './Inspector.jsx';
import './office.css';

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
    [message, setMessage] = useState(''),
    [error, setError] = useState('');
  const dialog = useRef(null),
    fileInput = useRef(null),
    reportInput = useRef(null),
    job = useRef(null);
  const index = Math.max(0, deck?.slides.findIndex((s) => s.id === selected) ?? 0);
  const slide = deck?.slides[index];

  useEffect(() => {
    let live = true;
    if (workspace)
      draft(workspace)
        .then((value) => {
          if (live && value) {
            current.current = readDeck(value);
            setDeck(current.current);
          }
        })
        .catch(() => {
          if (live) setError('无法读取本地草稿，可打开已保存的源文件');
        })
        .finally(() => {
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
              ...patch,
              generated: s.generated || 'items' in patch || 'notes' in patch,
              revision: s.revision + (Object.keys(patch).some((k) => k !== 'title') ? 1 : 0),
            }
          : s,
      ),
    };
    if (
      'image' in patch &&
      next.slides.reduce((size, page) => size + page.image.length, 0) > 12_000_000
    ) {
      setError('配图总量已达上限，请先移除一张配图');
      return;
    }
    commit(next);
  }
  function enter(next) {
    setStage(next);
    setError('');
    setMessage('');
  }
  function newPresentation() {
    if (
      current.current &&
      !window.confirm('新建将替换这份本地草稿。已保存的源文件可随时打开，继续新建吗？')
    )
      return;
    const next = newDeck();
    history.current = [];
    commit(next, false);
    select(next.slides[0].id);
    enter('source');
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
      enter('edit');
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
      if (destination) setMessage('已保存到 ' + destination);
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
      }
    }
  }
  function outline() {
    const original = current.current;
    if (
      (original.slides.length > 1 || original.slides.some((s) => s.generated)) &&
      !window.confirm('重新生成大纲会替换当前页面，可在完成后撤销。继续吗？')
    )
      return;
    void run('正在生成大纲', async (signal) => {
      const result = await requestPage(
        { action: 'outline', source: original.source, brief: original.brief, count },
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
        setBusy(all ? '正在生成正文 ' + (i + 1) + ' / ' + targets.length : '正在重写本页正文');
        const response = await requestPage(
          {
            action: 'slide',
            source: now.source,
            brief: now.brief,
            title: active.title,
            layout: active.layout,
            outline: now.slides.map((s) => s.title).join('\n'),
            current: JSON.stringify(active.items),
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
          <header className="office-bar">
            <div>
              <button onClick={() => enter('home')} disabled={!!busy || stage === 'home'}>
                办公
              </button>
              {stage !== 'home' && (
                <>
                  <span>／</span>
                  <strong>演示文稿</strong>
                </>
              )}
            </div>
            <div>
              {stage === 'edit' && (
                <>
                  <button disabled={!!busy} onClick={() => enter('source')}>
                    参考材料
                  </button>
                  <button disabled={!history.current.length || !!busy} onClick={undo}>
                    撤销
                  </button>
                  <button onClick={() => save('json')}>保存源文件</button>
                  <button className="office-primary" onClick={() => save('pptx')}>
                    导出 PPTX
                  </button>
                </>
              )}
              <button
                aria-label="关闭办公"
                onClick={() => {
                  if (job.current) stop();
                  dialog.current.close();
                }}
              >
                ×
              </button>
            </div>
          </header>
          <input hidden ref={fileInput} type="file" accept=".json" onChange={openFile} />
          {stage === 'home' && (
            <main className="office-home">
              <h1>办公</h1>
              <section className="office-card">
                <div className="office-card-art" aria-hidden="true">
                  <i />
                  <b />
                  <em />
                </div>
                <h2>演示文稿</h2>
                <p>从项目材料生成大纲，逐页编辑并导出 PowerPoint。</p>
                <button className="office-primary" disabled={!ready} onClick={newPresentation}>
                  新建演示文稿
                </button>
                <button disabled={!ready} onClick={() => fileInput.current.click()}>
                  打开源文件
                </button>
              </section>
              {deck && (
                <section className="office-recent">
                  <h3>本工作区草稿</h3>
                  <button onClick={() => enter('edit')}>
                    {deck.title} <span>{deck.slides.length} 页　→</span>
                  </button>
                </section>
              )}
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
                  <button onClick={() => reportInput.current.click()}>导入材料</button>
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
                <div className="office-actions">
                  <button
                    className="office-primary"
                    disabled={!deck.brief.trim() && !deck.source.trim()}
                    onClick={outline}
                  >
                    生成大纲
                  </button>
                  <button onClick={() => enter('edit')}>手动编辑</button>
                </div>
              </fieldset>
            </main>
          )}
          {stage === 'edit' && slide && (
            <div className="office-editor">
              <aside className="office-pages">
                <h3>页面</h3>
                {deck.slides.map((s, i) => (
                  <button
                    key={s.id}
                    className="office-thumb"
                    aria-current={s.id === slide.id ? 'page' : undefined}
                    onClick={() => select(s.id)}
                  >
                    <Canvas slide={s} index={i} total={deck.slides.length} />
                    <span>
                      {i + 1}　{s.title || '无标题'}
                    </span>
                  </button>
                ))}
                <button
                  disabled={!!busy || deck.slides.length >= 20}
                  onClick={() => {
                    const s = newSlide();
                    commit({ ...deck, slides: [...deck.slides, s] });
                    select(s.id);
                  }}
                >
                  ＋ 添加页面
                </button>
              </aside>
              <main className="office-canvas">
                <label className="office-name">
                  文稿名称
                  <input
                    maxLength={120}
                    value={deck.title}
                    onChange={(e) => commit({ ...deck, title: e.target.value })}
                  />
                </label>
                <Canvas
                  slide={slide}
                  index={index}
                  total={deck.slides.length}
                  onEdit={(field) => {
                    const input = document.getElementById('office-field-' + field);
                    input?.focus();
                    input?.select();
                  }}
                />
                <div className="office-actions">
                  <span>
                    {index + 1} / {deck.slides.length} · {layouts[slide.layout]}
                  </span>
                  <button disabled={!index || !!busy} onClick={() => move(-1)}>
                    前移
                  </button>
                  <button disabled={index === deck.slides.length - 1 || !!busy} onClick={() => move(1)}>
                    后移
                  </button>
                  <button
                    disabled={deck.slides.length < 2 || !!busy}
                    onClick={() =>
                      commit({ ...deck, slides: deck.slides.filter((s) => s.id !== slide.id) })
                    }
                  >
                    删除本页
                  </button>
                </div>
                {!!pending && (
                  <button className="office-primary" disabled={!!busy} onClick={() => generate(true)}>
                    生成剩余 {pending} 页正文
                  </button>
                )}
              </main>
              <Inspector
                key={slide.id}
                slide={slide}
                edit={(patch) => editSlide(slide.id, patch)}
                change={change}
                setChange={setChange}
                rewrite={() => generate(false)}
                busy={!!busy}
                error={setError}
              />
            </div>
          )}
          {(error || busy || message) && (
            <footer className="office-status" role={error ? 'alert' : 'status'}>
              {error || busy || message}
              {busy && <button onClick={stop}>停止生成</button>}
            </footer>
          )}
        </dialog>,
        document.body,
      )}
    </>
  );
}
