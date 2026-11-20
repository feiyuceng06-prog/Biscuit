// Real Electron + Python + PTY integration. No provider requests or user config.
import { _electron as electron, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkModelForm } from './model-form.mjs';
import { checkLayout, retainLayout } from './layout.mjs';
import { dialogueFixture } from './dialogue-fixture.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'feiyu-desktop-test-'));
const workspace = path.join(temporary, 'workspace');
const other = path.join(temporary, 'other');
await fs.mkdir(workspace); await fs.mkdir(other);
await fs.writeFile(path.join(workspace, 'README.md'), '# Feiyu Workbench\n\nElectron + Python agent.\n');
await fs.writeFile(path.join(other, 'second.txt'), 'Second workspace');
await fs.mkdir(path.join(temporary, 'config'), { recursive: true });
const env = { ...process.env, HOME: temporary, XDG_CONFIG_HOME: path.join(temporary, 'config'),
  XDG_STATE_HOME: path.join(temporary, 'state'), XDG_DATA_HOME: path.join(temporary, 'data'),
  FEIYU_BIN: process.env.FEIYU_TEST_EXECUTABLE ? '/nonexistent-backend-override' : path.join(desktop, 'build/backend', process.platform === 'win32' ? 'feiyu-backend.exe' : 'feiyu-backend'), SHELL: '/bin/sh' };
if (process.platform === 'win32') {
  env.USERPROFILE = temporary; env.FEIYU_TEST_MARKER = 'OK';
  env.APPDATA = path.join(temporary, 'AppData', 'Roaming');
  env.LOCALAPPDATA = path.join(temporary, 'AppData', 'Local');
  await fs.mkdir(env.APPDATA, { recursive: true });
  await fs.mkdir(env.LOCALAPPDATA, { recursive: true });
}
const fixture = await dialogueFixture();
const config = path.join(temporary, 'config', 'feiyu');
await fs.mkdir(config, {recursive:true});
await fs.writeFile(path.join(config, 'models.json'), JSON.stringify({offline:{kind:'openai',model:'offline',key:'synthetic-not-a-key',base_url:fixture.url}}));
await fs.writeFile(path.join(config, 'state.json'), JSON.stringify({last:'offline'}));
delete env.ELECTRON_RUN_AS_NODE;
let application, page;
try {
  const launch = (resume = false) => electron.launch({
    ...(process.env.FEIYU_TEST_EXECUTABLE ? { executablePath: process.env.FEIYU_TEST_EXECUTABLE } : {}),
    args: [...(process.env.FEIYU_TEST_EXECUTABLE ? [] : [desktop]), '-w', workspace, ...(resume ? ['--resume'] : []), ...(process.env.FEIYU_TEST_SCALE ? ['--force-device-scale-factor=' + process.env.FEIYU_TEST_SCALE] : [])], env, timeout: 30000,
  });
  application = await launch();
  page = await application.firstWindow();
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await expect(page.locator('#s-ver')).not.toHaveText('—', { timeout: 30000 });
  expect(await page.evaluate(() => window.feiyuDesktop.core.invoke('shown'))).toBe(true);
  const reduced = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  if (!reduced) {
    await expect(page.locator('#startup')).toBeVisible();
    expect(await page.evaluate(() => {
      const r = document.querySelector('#startup').getBoundingClientRect();
      return r.width === innerWidth && r.height === innerHeight && !!document.querySelector('#input').closest('[inert]');
    })).toBe(true);
    await expect(page.locator('#startup-text')).toHaveText(/^Biscuit/);
    expect(await page.locator('#startup-text').textContent()).not.toBe('Biscuit帮助您工作。');
    await expect(page.locator('#startup-text')).toHaveText('Biscuit帮助您工作。', { timeout: 6000 });
    await expect(page.locator('#startup')).toHaveAttribute('data-phase', 'play');
    if (process.env.FEIYU_SPLASH_SCREENSHOT) {
      await expect(page.locator('#startup')).toHaveAttribute('data-phase', 'play');
      await page.evaluate(() => document.querySelector('#startup').getAnimations({subtree: true}).forEach(a => { a.pause(); a.currentTime = 4000; }));
      await page.screenshot({path: process.env.FEIYU_SPLASH_SCREENSHOT});
    }
  }
  await expect(page.locator('#startup')).toHaveCount(0, { timeout: 6500 });
  await expect(page.locator('#input')).toBeFocused();
  await expect(page.locator('.backend-error')).toHaveCount(0);
  await checkLayout(application, page, 'empty');
  await page.locator('#input').fill('synthetic GUI 中文 😀 𠮷');
  await page.locator('#send').click();
  await expect(page.locator('body')).toContainText('GUI reply 1 中文 😀 𠮷', {timeout:30000});
  const sessionsRoot = path.join(temporary, 'state', 'feiyu', 'sessions');
  await expect.poll(async () => (await fs.readdir(sessionsRoot, {recursive:true})).filter(p => p.endsWith('.task.json')).length).toBe(1);
  const journal = (await fs.readdir(sessionsRoot, {recursive:true})).find(p => p.endsWith('.task.json'));
  const saved = JSON.parse(await fs.readFile(path.join(sessionsRoot, journal), 'utf8')).payload;
  await application.close();
  application = await launch(true);
  page = await application.firstWindow();
  page.setDefaultTimeout(10000);
  page.on('pageerror', error => errors.push(error.message));
  await expect(page.locator('#startup')).toHaveCount(0, {timeout:15000});
  await expect(page.locator('#s-ver')).not.toHaveText('—', {timeout:30000});
  await expect(page.locator('body')).toContainText('GUI reply 1 中文 😀 𠮷', {timeout:30000});
  await page.locator('#input').fill('synthetic resumed 中文 😀 𠮷');
  await page.locator('#send').click();
  await expect(page.locator('body')).toContainText('GUI reply 2 中文 😀 𠮷', {timeout:30000});
  expect(fixture.requests).toHaveLength(2);
  await expect.poll(async () => JSON.parse(await fs.readFile(path.join(sessionsRoot, journal), 'utf8')).payload.budget.attempts).toBe(2);
  expect(JSON.parse(await fs.readFile(path.join(sessionsRoot, journal), 'utf8')).payload.session_id).toBe(saved.session_id);
  expect(fixture.requests[1].messages.filter(m => m.role === 'user').length).toBeGreaterThanOrEqual(2);
  console.log('PASS: actual GUI streamed synthetic conversation and durable session restore after actual application restart');
  await expect(page.getByRole('button', { name: '· README.md', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '· README.md', exact: true }).click();
  await expect(page.locator('.file-preview')).toContainText('Electron + Python agent.');
  await checkLayout(application, page, 'file');
  const isolation = await page.evaluate(() => ({ require: typeof window.require, process: typeof window.process }));
  expect(isolation).toEqual({ require: 'undefined', process: 'undefined' });
  const denied = await page.evaluate(async () => {
    try { await window.feiyuDesktop.core.invoke('preview_file', { path: '../other/second.txt' }); return false; }
    catch { return true; }
  });
  expect(denied).toBe(true);
  await page.locator('#act-term').click();
  await page.waitForFunction(() => document.querySelector('.xterm-screen') !== null);
  await page.evaluate(() => {
    window.__terminalOutput = '';
    window.feiyuDesktop.event.listen('feiyu://term', event => { window.__terminalOutput += event.payload; });
  });
  // Await a successful PTY write, rather than racing the asynchronous shell startup.
  await expect.poll(async () => page.evaluate(async () => {
    try { await window.feiyuDesktop.core.invoke('term_write', { data: window.feiyuDesktop.platform === 'win32' ? "echo FEIYU_TERMINAL_%FEIYU_TEST_MARKER%\r" : "printf 'FEIYU_%s_OK\\n' TERMINAL\n" }); return true; }
    catch { return false; }
  })).toBe(true);
  await page.waitForFunction(() => window.__terminalOutput.includes('FEIYU_TERMINAL_OK'));
  await fs.mkdir(path.join(desktop, 'test-results'), { recursive: true });
  await page.screenshot({ path: path.join(desktop, 'test-results/workbench.png') });
  await page.evaluate(dir => goDesk(dir), other);
  await expect(page.locator('#desk-path')).toHaveAttribute('title', await fs.realpath(other));
  await expect(page.getByRole('button', { name: '· second.txt', exact: true })).toBeVisible();
  await expect(page.locator('.file-tabs')).not.toContainText('README.md');
  // Narrow layouts share space with the sidebar: restore it through the visible preview toggle.
  if (!await page.locator('#nav-shelf').isVisible()) {
    await expect(page.locator('.files-panel')).toBeVisible();
    await page.locator('#act-files').click();
    await expect(page.locator('.files-panel')).toBeHidden();
  }
  await expect(page.locator('#nav-shelf')).toBeVisible();
  await page.locator('#nav-shelf').click();
  await expect(page.locator('#shelf')).toBeVisible();
  await checkModelForm(page);
  await expect(page.locator('#startup')).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.reload();
  await expect(page.locator('#startup')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#startup')).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  await expect(page.locator('#startup')).toHaveCount(0);
  expect(await page.locator('[inert]').count()).toBe(0);
  expect(errors).toEqual([]);
  console.log('PASS: fullscreen intro, streamed caption, automatic exit, Escape, reduced motion, focus restoration');
  console.log('PASS: real backend, file preview, isolated renderer, path boundary, PTY, workspace switching, settings');
} catch (error) {
  try { await retainLayout(page, 'failure'); } catch {}
  try { console.error('Terminal display:', await page?.locator('.xterm-rows').innerText()); } catch {}
  try { console.error(await fs.readFile(path.join(temporary, 'state/feiyu/desktop.log'), 'utf8')); } catch {}
  throw error;
} finally {
  await application?.close();
  await fixture.close();
  await fs.rm(temporary, { recursive: true, force: true });
}
