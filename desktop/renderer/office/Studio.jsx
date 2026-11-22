import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowDownToLine,
  ChevronDown,
  CircleCheck,
  LoaderCircle,
  Circle,
  ChevronLeft,
  ChevronRight,
  FileText,
  Layers,
  Palette,
  PanelLeft,
  Play,
  Plus,
  Save,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Undo2,
  X,
} from 'lucide-react';
import { themes, layouts } from '../../electron/office/deck.mjs';
import { hasPhotos } from '../../electron/office/photos.mjs';
import { DesignBrief } from './DesignBrief.jsx';
import { Canvas } from './Canvas.jsx';
import { Inspector } from './Inspector.jsx';

function Tool({ icon: Icon, label, caption, pressed, ...props }) {
  return (
    <button type="button" aria-label={label} title={label} aria-pressed={pressed} {...props}>
      <Icon size={17} strokeWidth={1.65} aria-hidden="true" />
      {caption && <span>{caption}</span>}
    </button>
  );
}
export function Studio({
  deck,
  index,
  select,
  commit,
  edit,
  appendPhotos,
  onError,
  move,
  busy,
  workingPage,
  canUndo,
  undo,
  save,
  enter,
  close,
  add,
  pending,
  generate,
  change,
  setChange,
}) {
  const [pages, setPages] = useState(() => !window.matchMedia('(max-width: 700px)').matches),
    [panel, setPanel] = useState(null),
    [playing, setPlaying] = useState(false);
  const slide = deck.slides[index],
    total = deck.slides.length,
    theme = deck.theme || 'paper';
  const shell = useRef(null);
  const toggle = (name) => setPanel((value) => (value === name ? null : name));
  function step(delta) {
    const next = deck.slides[index + delta];
    if (next) select(next.id);
  }
  useEffect(() => {
    const host = shell.current?.closest('dialog');
    function cancel(e) {
      const drawerOpen = pages && window.matchMedia('(max-width: 700px)').matches;
      if (playing || panel || drawerOpen) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (!playing && !panel && drawerOpen) {
          setPages(false);
          shell.current.querySelector('button[aria-label="页面缩略图"]')?.focus();
        }
        setPlaying(false);
        setPanel(null);
      }
    }
    host?.addEventListener('cancel', cancel, true);
    return () => host?.removeEventListener('cancel', cancel, true);
  }, [playing, panel, pages]);
  function write(field, row, value) {
    if (field === 'title' || field === 'unit') edit({ [field]: value });
    else if (field === 'caption')
      edit({ photos: slide.photos.map((photo, i) => i === Number(row) ? { ...photo, caption: value } : photo) });
    else
      edit({
        items: slide.items.map((item, i) => (i === Number(row) ? { ...item, [field]: value } : item)),
      });
  }
  const popupTitle = {
    content: '页面内容',
    design: '模板与版式',
    ai: '让 Biscuit 修改本页',
    document: '文稿选项',
  };
  return (
    <div
      ref={shell}
      className={'studio' + (playing ? ' presenting' : '')}
      onKeyDown={(e) => {
        if (playing && ['ArrowRight', 'ArrowLeft'].includes(e.key)) {
          e.preventDefault();
          step(e.key === 'ArrowRight' ? 1 : -1);
        }
      }}
    >
      {!playing && (
        <header className="studio-header">
          <div>
            <Tool icon={ChevronLeft} label="返回办公" disabled={busy} onClick={() => enter('home')} />
            <input
              aria-label="文稿名称"
              value={deck.title}
              maxLength={120}
              onChange={(e) => commit({ ...deck, title: e.target.value })}
            />
            <Tool
              icon={ChevronDown}
              label="文稿选项"
              pressed={panel === 'document'}
              onClick={() => toggle('document')}
            />
          </div>
          <div>
            <Tool icon={Undo2} label="撤销" disabled={!canUndo} onClick={undo} />
            <Tool
              className="studio-primary"
              icon={ArrowDownToLine}
              label="导出 PPTX"
              caption="导出 PPTX"
              onClick={() => save('pptx')}
            />
            <Tool icon={X} label="关闭办公" onClick={close} />
          </div>
        </header>
      )}
      <div className="studio-workspace">
        {!playing && (
          <div className="studio-tools">
            <div className="studio-island">
              <Tool
                icon={PanelLeft}
                label="页面缩略图"
                pressed={pages}
                onClick={() => setPages(!pages)}
              />
              <Tool
                icon={Plus}
                label="添加页面"
                caption="添加页面"
                disabled={busy || total >= 20}
                onClick={add}
              />
            </div>
            <div className="studio-island">
              <Tool
                icon={Play}
                label="放映"
                caption="放映"
                onClick={() => {
                  setPanel(null);
                  setPlaying(true);
                }}
              />
            </div>
          </div>
        )}
        <div className="studio-body">
          {pages && !playing && (
            <aside className="studio-rail">
              <div className="studio-rail-head">
                <span>页面</span>
                <span>{total}</span>
              </div>
              <div className="studio-list">
                {deck.slides.map((s, i) => (
                  <button
                    key={s.id}
                    className="office-thumb"
                    aria-label={'第 ' + (i + 1) + ' 页 ' + s.title}
                    aria-current={s.id === slide.id ? 'page' : undefined}
                    onClick={() => {
                      select(s.id);
                      if (window.matchMedia('(max-width: 700px)').matches) setPages(false);
                    }}
                  >
                    <Canvas slide={s} index={i} total={total} theme={theme} design={deck.design} />
                    <span>
                      {i + 1}　{s.title || '无标题'}
                    </span>
                  </button>
                ))}
              </div>
              <div className="studio-page-ops">
                <Tool
                  icon={ChevronLeft}
                  label="前移"
                  disabled={busy || index === 0}
                  onClick={() => move(-1)}
                />
                <Tool
                  icon={ChevronRight}
                  label="后移"
                  disabled={busy || index === total - 1}
                  onClick={() => move(1)}
                />
                <Tool
                  icon={Trash2}
                  label="删除本页"
                  disabled={busy || total === 1}
                  onClick={() =>
                    commit({ ...deck, slides: deck.slides.filter((s) => s.id !== slide.id) })
                  }
                />
              </div>
            </aside>
          )}
          <main className="office-canvas" onPointerDown={() => setPanel(null)}>
            <Canvas
              key={slide.id + String(playing)}
              slide={slide}
              theme={theme} design={deck.design}
              index={index}
              total={total}
              onEdit={playing ? undefined : write}
            />
          </main>
        </div>
        <div className="studio-bottom">
          <div className="studio-island">
            {playing ? (
              <>
                <Tool icon={ChevronLeft} label="上一页" disabled={!index} onClick={() => step(-1)} />
                <span>
                  {index + 1} / {total}
                </span>
                <Tool
                  icon={ChevronRight}
                  label="下一页"
                  disabled={index === total - 1}
                  onClick={() => step(1)}
                />
                <Tool autoFocus icon={X} label="结束放映" onClick={() => setPlaying(false)} />
              </>
            ) : (
              <>
                <Tool
                  icon={SlidersHorizontal}
                  label="编辑内容"
                  caption="内容"
                  pressed={panel === 'content'}
                  onClick={() => toggle('content')}
                />
                <Tool
                  icon={Palette}
                  label="模板与版式"
                  caption="设计"
                  pressed={panel === 'design'}
                  onClick={() => toggle('design')}
                />
                <i />
                <Tool
                  icon={Sparkles}
                  label="AI 修改"
                  caption="AI 修改"
                  pressed={panel === 'ai'}
                  onClick={() => toggle('ai')}
                />
                {!!pending && (
                  <Tool
                    icon={Layers}
                    label={'生成剩余 ' + pending + ' 页正文'}
                    caption={'生成 ' + pending + ' 页'}
                    disabled={busy}
                    onClick={() => generate(true)}
                  />
                )}
              </>
            )}
          </div>
        </div>
        {panel && !playing && (
          <section
            className={'studio-popup ' + (panel === 'document' ? 'doc-options' : '')}
            aria-label={popupTitle[panel]}
          >
            <header>
              <strong>{popupTitle[panel]}</strong>
              <Tool icon={X} label="收起面板" onClick={() => setPanel(null)} />
            </header>
            {panel === 'document' && (
              <div className="studio-menu">
                <Tool
                  icon={FileText}
                  label="参考材料"
                  caption="参考材料"
                  disabled={busy}
                  onClick={() => enter('source')}
                />
                <Tool icon={Save} label="保存源文件" caption="保存源文件" onClick={() => save('json')} />
              </div>
            )}
            {panel === 'content' && (
              <Inspector key={slide.id} slide={slide} planned={deck.design?.version === 2} edit={edit}
                appendPhotos={appendPhotos} error={onError} />
            )}
            {panel === 'design' && (
              <>
                <DesignBrief key={deck.id} deck={deck} slideId={slide.id} commit={commit} onError={onError} disabled={!!busy} />
                {!hasPhotos(deck) && <><h4>整份文稿风格</h4>
                <div className="studio-themes">
                  {Object.entries(themes).map(([key, t]) => (
                    <button
                      key={key}
                      aria-pressed={!deck.design && theme === key}
                      onClick={() => commit({ ...deck, theme: key, design: undefined })}
                    >
                      <span className="studio-layout-preview" aria-hidden="true">
                        <Canvas slide={slide} index={index} total={total} theme={key} />
                      </span>
                      {t.name}
                    </button>
                  ))}
                </div></>}
                <h4>本页版式</h4>
                <div className="studio-layouts">
                  {Object.entries(layouts).map(([key, name]) => (
                    <button
                      key={key}
                      aria-label={name}
                      aria-pressed={slide.layout === key}
                      onClick={() => edit({ layout: key })}
                    >
                      <span className="studio-layout-preview" aria-hidden="true">
                        <Canvas
                          slide={{ ...slide, layout: key }}
                          index={index}
                          total={total}
                          theme={theme} design={deck.design}
                        />
                      </span>
                      {name}
                    </button>
                  ))}
                </div>
              </>
            )}
            {panel === 'ai' && (
              <>
                <details className="office-task">
                  <summary>页面正文 <span>{total - pending} / {total} 页已处理</span></summary>
                  <ol>{deck.slides.map((page, n) => {
                    const writing = page.id === workingPage;
                    const Icon = writing ? LoaderCircle : page.generated ? CircleCheck : Circle;
                    return (
                      <li key={page.id}>
                        <Icon size={16} aria-hidden="true" className={writing ? 'office-loading' : undefined} />
                        <span>{n + 1}. {page.title || '无标题'}</span>
                        <small>{writing ? '生成中' : page.generated ? '已处理' : '待生成'}</small>
                      </li>
                    );
                  })}</ol>
                </details>
                <label>
                  让 AI 修改本页正文
                  <textarea
                    autoFocus
                    maxLength={800}
                    value={change}
                    onChange={(e) => setChange(e.target.value)}
                    placeholder="希望这页怎么改？"
                  />
                </label>
                <button className="studio-primary" disabled={busy} onClick={() => generate(false)}>
                  重新生成本页正文
                </button>
              </>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
