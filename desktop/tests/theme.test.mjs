import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';

const source = await fs.readFile(new URL('../ui/theme.js', import.meta.url), 'utf8');
function start(stored, dark = false, blocked = false) {
  const window = new EventTarget();
  const media = new EventTarget();
  media.matches = dark;
  const document = { documentElement: { dataset: {} } };
  const localStorage = {
    getItem() { if (blocked) throw Error('denied'); return stored; },
    setItem(key, value) { if (blocked) throw Error('denied'); stored = value; },
  };
  vm.runInNewContext(source, { window, document, localStorage, matchMedia: () => media, Event });
  return { api: window.BiscuitTheme, root: document.documentElement, stored: () => stored,
    system(dark) { media.matches = dark; media.dispatchEvent(new Event('change')); } };
}
test('system tracks changes, explicit choices override them, and system remains the stored preference', () => {
  const t = start(null, true);
  assert.equal(t.root.dataset.theme, 'dark');
  t.system(false);
  assert.equal(t.root.dataset.theme, 'light');
  assert.equal(t.stored(), 'system');
  t.api.set('dark'); t.system(false);
  assert.equal(t.root.dataset.theme, 'dark');
  t.api.set('light'); t.system(true);
  assert.equal(t.root.dataset.theme, 'light');
  assert.equal(start(t.stored(), true).root.dataset.theme, 'light');
});
test('removed skins migrate by brightness and invalid values follow the system', () => {
  for (const old of ['retro', 'anthropic', 'openai', 'grove', 'grandline']) {
    assert.equal(start(old, true).stored(), 'light');
  }
  assert.equal(start('inception').stored(), 'dark');
  assert.equal(start('unknown', true).root.dataset.theme, 'dark');
});
test('unavailable storage does not prevent theme selection or system updates', () => {
  const t = start(null, false, true);
  t.api.set('dark'); t.system(false);
  assert.equal(t.root.dataset.theme, 'dark');
  t.api.set('system');
  assert.equal(t.root.dataset.theme, 'light');
  t.system(true);
  assert.equal(t.root.dataset.theme, 'dark');
});
