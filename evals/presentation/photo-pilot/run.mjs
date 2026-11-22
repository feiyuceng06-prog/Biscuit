// Run from the repository root with desktop dependencies, a display and a configured model.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
const suite = path.dirname(fileURLToPath(import.meta.url));
const desktop = path.resolve('desktop');
const { _electron: electron, expect } = createRequire(path.join(desktop, 'package.json'))('@playwright/test');
const [name, output, reopen] = process.argv.slice(2);
const { cases } = JSON.parse(await fs.readFile(path.join(suite, 'cases.json')));
const sources = JSON.parse(await fs.readFile(path.join(suite, 'sources.json')));
const sample = cases.find(c => c.id === name);
const dest = path.resolve(output);
await fs.mkdir(dest); // Never replace an earlier attempt.
const work = await fs.mkdtemp(path.join(os.tmpdir(), 'biscuit-photo-session-'));
const config = path.join(work, 'config');
const profile = path.join(config, 'feiyu');
const model = process.env.BISCUIT_PILOT_MODEL || 'deepseek-flash';
await fs.mkdir(profile, { recursive: true, mode: 0o700 });
await fs.symlink(path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'), 'feiyu/models.json'), path.join(profile, 'models.json'));
await fs.writeFile(path.join(profile, 'state.json'), JSON.stringify({ last: model }));
const env = { ...process.env, FEIYU_DISABLE_UPDATE_CHECK: '1', XDG_CONFIG_HOME: config,
  XDG_STATE_HOME: path.join(work, 'state'), presentation_design_engine: '1' };
delete env.ELECTRON_RUN_AS_NODE;
const log = { name, model, reopen: Boolean(reopen), started: new Date().toISOString(), events: [], manualPageEdits: 0 };
const start = Date.now();
const event = (action, extra = {}) => log.events.push({ action, ms: Date.now() - start, ...extra });
const app = await electron.launch({ args: [desktop, '--user-data-dir=' + path.join(work, 'profile'), '-w', work, '-m', model], env });
let page;
try {
  page = await app.firstWindow();
  page.setDefaultTimeout(25000);
  page.on('dialog', d => d.accept());
  await page.locator('#startup').waitFor({ state: 'detached' });
  const button = name => page.getByRole('button', { name, exact: true });
  if (!await page.locator('dialog.office[open]').count()) await button('办公').click();
  async function save(name, file) {
    await app.evaluate(({ dialog }, target) => { dialog.showSaveDialog = async () => ({ canceled: false, filePath: target }); }, file);
    if (name === '保存源文件') await button('文稿选项').click();
    await button(name).click();
    await expect(page.locator('.office-status')).toContainText(path.basename(file), { timeout: 360000 });
    event(name, { status: await page.locator('.office-status').innerText() });
  }
  async function generate(phase, findButton, finished) {
    for (let attempt = 1; attempt <= 2; attempt++) {
      event(phase, { attempt });
      await findButton().click();
      await Promise.race([finished(), page.locator('.office-status[role=alert]').waitFor({ timeout: 360000 })]);
      const error = page.locator('.office-status[role=alert]');
      if (!await error.count()) return;
      event('generation-error', { phase, attempt, error: await error.innerText() });
      await page.screenshot({ path: path.join(dest, phase + '-' + attempt + '.png') });
      if (attempt === 2) throw Error(await error.innerText());
    }
  }
  if (reopen) {
    await page.locator('input[type=file][accept*="json"]').setInputFiles(path.resolve(reopen));
  } else {
    await button('新建演示文稿').click();
    await page.getByLabel('制作要求').fill(sample.brief);
    const text = sample.photos.map(id => {
      const s = sources.find(row => row.objectID === id);
      return [s.objectID, s.artistDisplayName, s.title, s.objectDate, s.objectURL].join(' | ');
    }).join('\n');
    await page.getByLabel('参考材料').fill([text, sample.copy].filter(Boolean).join('\n'));
    await page.locator('.office-actions select').first().selectOption(String(sample.pages));
    await page.locator('.office-photo-intake summary').click();
    await page.getByLabel('首页标题（原样保留）').fill(sample.title);
    if (sample.copy) await page.getByLabel('末页正文（原样保留）').fill(sample.copy);
    await page.getByLabel('待排版照片').setInputFiles(sample.photos.map(id => path.join(suite, 'media', id + '.jpg')));
    await expect(page.locator('.office-photo-intake')).toContainText('待排版 ' + sample.photos.length + ' 张');
    await generate('outline', () => button('生成大纲'),
      () => page.locator('.office-thumb').first().waitFor({ timeout: 180000 }));
    await generate('body', () => page.getByRole('button', { name: /^生成剩余 .* 页正文$/ }),
      () => expect(page.locator('.office-status')).toContainText('逐页生成完成', { timeout: 640000 }));
  }
  await expect(page.locator('.office-thumb')).toHaveCount(sample.pages);
  await save('保存源文件', path.join(dest, 'source.deck.json'));
  await save('导出 PPTX', path.join(dest, 'deck.pptx'));
} catch (e) {
  log.failure = String(e.message).slice(0, 2200);
  if (page) {
    log.status = await page.locator('.office-status').innerText({ timeout: 2000 }).catch(() => '');
    await page.screenshot({ path: path.join(dest, 'failure.png') }).catch(() => {});
  }
  process.exitCode = 1;
} finally {
  log.totalMs = Date.now() - start;
  await fs.writeFile(path.join(dest, 'run.json'), JSON.stringify(log, null, 2) + '\n');
  await app.close();
}
