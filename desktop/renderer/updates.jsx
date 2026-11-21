import React, { useEffect, useRef, useState } from 'react';
const invoke = (command, args) => window.feiyuDesktop.core.invoke(command, args);
const readDismissed = () => { try { return localStorage.getItem('biscuit.update.dismissed'); } catch { return null; } };

export function UpdateNotice() {
  const [update, setUpdate] = useState({ status: 'idle' });
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState(false);
  const [dismissed, setDismissed] = useState(readDismissed);
  const checking = useRef(false);
  async function check(automatic = false) {
    if (checking.current) return;
    checking.current = true; setBusy(true);
    if (!automatic) setManual(true);
    try {
      const result = await invoke('check_updates', { automatic });
      setUpdate(previous => result.status === 'error' && automatic && previous.status === 'available' ? previous : result);
      if (!automatic) setDismissed(null);
    } catch { setUpdate({ status: 'error', message: '暂时无法检查更新，请稍后重试' }); }
    finally { checking.current = false; setBusy(false); }
  }
  useEffect(() => {
    void check(true);
    const timer = setInterval(() => void check(true), 6 * 60 * 60 * 1000);
    return () => clearInterval(timer);
  }, []);
  function open(url) {
    invoke('open_url', { url }).catch(() => {
      setManual(true);
      setUpdate({ status: 'error', message: '无法打开浏览器，请稍后重试' });
    });
  }
  const available = update.status === 'available' && update.latest !== dismissed;
  return <section className="update-panel" aria-label="软件更新">
    {available && <>
      <p role="status">发现新版本 <strong>{update.latest}</strong></p>
      <div className="update-actions">
        <button type="button" className="update-download" onClick={() => open(update.downloadUrl)}>下载更新</button>
        <button type="button" onClick={() => open(update.url)}>更新说明</button>
        <button type="button" onClick={() => {
          setDismissed(update.latest);
          try { localStorage.setItem('biscuit.update.dismissed', update.latest); } catch { /* Session only. */ }
        }}>稍后</button>
      </div>
    </>}
    {!available && manual && <p role="status">{update.status === 'current' ? '当前已是最新版本'
      : update.status === 'unavailable' ? `新版本 ${update.latest} 暂无适用的安装包`
      : update.status === 'error' ? update.message : ''}</p>}
    <button type="button" className="update-check" disabled={busy} onClick={() => check(false)}
      title={update.current ? `当前版本 ${update.current}` : undefined}>{busy ? '正在检查…' : '检查更新'}</button>
  </section>;
}
