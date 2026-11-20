// Run before styles and body paint, including the startup overlay.
(() => {
  const key = 'feiyu.theme'; // Keep the existing desktop preference location.
  const media = matchMedia('(prefers-color-scheme: dark)');
  const normalize = value => {
    if (['light', 'dark', 'system'].includes(value)) return value;
    if (value === 'inception') return 'dark';
    if (['retro', 'anthropic', 'openai', 'grove', 'grandline'].includes(value)) return 'light';
    return 'system';
  };
  let stored;
  try { stored = localStorage.getItem(key); } catch { /* Storage can be unavailable. */ }
  let preference = normalize(stored);
  const apply = () => {
    document.documentElement.dataset.theme = preference === 'system'
      ? (media.matches ? 'dark' : 'light') : preference;
    window.dispatchEvent(new Event('biscuit:theme'));
  };
  const save = () => {
    try { localStorage.setItem(key, preference); } catch { /* Keep this window usable. */ }
  };
  window.BiscuitTheme = {
    get preference() { return preference; },
    set(value) { preference = normalize(value); save(); apply(); },
  };
  media.addEventListener('change', () => { if (preference === 'system') apply(); });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) {
      preference = normalize(event.newValue);
      apply();
    }
  });
  save();
  apply();
})();
