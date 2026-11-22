export async function requestPage(input, signal) {
  signal.throwIfAborted();
  const desktop = window.feiyuDesktop;
  const ticket = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const abort = () => finish(reject, new Error('已停止生成'));
    const timer = setTimeout(() => finish(reject, new Error('模型响应超时，请重试')), 150000);
    const off = desktop.event.listen('feiyu://event', ({ payload }) => {
      const event = JSON.parse(payload);
      if (event.kind !== 'presentation' || event.ticket !== ticket) return;
      if (event.error) finish(reject, new Error(event.error));
      else finish(resolve, event.data);
    });
    const offState = desktop.event.listen('feiyu://state', ({ payload }) => {
      if (payload.state === 'error' || payload.state === 'starting')
        finish(reject, new Error('模型连接已断开'));
    });
    function finish(fn, value) {
      clearTimeout(timer);
      signal.removeEventListener('abort', abort);
      off();
      offState();
      fn(value);
    }
    signal.addEventListener('abort', abort, { once: true });
    desktop.core
      .invoke('send', { line: JSON.stringify({ ...input, op: 'presentation', ticket }) })
      .catch((e) => finish(reject, e));
  });
}
