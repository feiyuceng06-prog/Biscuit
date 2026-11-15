// Verify startup consent through the real renderer and stdio backend.
import { _electron as electron, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 'feiyu-verify-trust-'));
const workspace = path.join(temporary, 'workspace');
const other = path.join(temporary, 'other');
const command = 'printf "%s\\n" "<verify-trust>"';
for (const directory of [workspace, other, path.join(temporary, 'config')]) {
  await fs.mkdir(directory, { recursive: true });
}
await fs.writeFile(path.join(workspace, 'AGENTS.md'), 'verify: ' + command + '\n');
const env = { ...process.env, HOME: temporary, XDG_CONFIG_HOME: path.join(temporary, 'config'),
  XDG_STATE_HOME: path.join(temporary, 'state'), XDG_DATA_HOME: path.join(temporary, 'data'),
  FEIYU_BIN: process.env.FEIYU_TEST_EXECUTABLE ? '/nonexistent-backend-override'
    : path.join(desktop, 'build/backend', process.platform === 'win32' ? 'feiyu-backend.exe' : 'feiyu-backend') };
if (process.platform === 'win32') {
  env.USERPROFILE = temporary;
  env.APPDATA = path.join(temporary, 'AppData', 'Roaming');
  env.LOCALAPPDATA = path.join(temporary, 'AppData', 'Local');
  await fs.mkdir(env.APPDATA, { recursive: true });
  await fs.mkdir(env.LOCALAPPDATA, { recursive: true });
}
delete env.ELECTRON_RUN_AS_NODE;
let application;
try {
  application = await electron.launch({
    ...(process.env.FEIYU_TEST_EXECUTABLE ? { executablePath: process.env.FEIYU_TEST_EXECUTABLE } : {}),
    args: [...(process.env.FEIYU_TEST_EXECUTABLE ? [] : [desktop]), '-w', workspace], env,
  });
  const page = await application.firstWindow();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await expect(page.locator('#startup')).toHaveCount(0, { timeout: 15000 });
  const question = () => page.locator('.ask').filter({ hasText: '自动校验会在沙箱外执行' });
  await expect(question()).toContainText(command);
  await expect(question()).toContainText('AGENTS.md');
  await question().getByRole('button', { name: '不启用', exact: true }).click();
  await expect(page.locator('#s-ver')).not.toHaveText('—');
  const trustPath = path.join(temporary, 'config', 'feiyu', 'trusted-verify.json');
  expect(await fs.stat(trustPath).then(() => true, () => false)).toBe(false);
  await page.evaluate(dir => goDesk(dir), other);
  await expect(page.locator('#desk-path')).toHaveAttribute('title', await fs.realpath(other));
  await page.evaluate(dir => goDesk(dir), workspace);
  await expect(question()).toContainText(command);
  await question().getByRole('button', { name: '启用', exact: true }).click();
  const workspaceKey = await fs.realpath(workspace);
  await expect.poll(async () => fs.readFile(trustPath, 'utf8')
    .then(raw => Boolean(JSON.parse(raw)[workspaceKey]), () => false)).toBe(true);
  await page.evaluate(dir => goDesk(dir), other);
  await expect(page.locator('#desk-path')).toHaveAttribute('title', await fs.realpath(other));
  await page.evaluate(dir => goDesk(dir), workspace);
  await expect(page.locator('#desk-path')).toHaveAttribute('title', await fs.realpath(workspace));
  await expect(page.locator('.backend-error')).toHaveCount(0);
  await page.evaluate(() => send({ op: 'command', text: '/verify' }));
  await expect(page.locator('#stream')).toContainText('当前校验命令');
  await expect(page.locator('#stream')).not.toContainText('未启用');
  await expect(question()).toHaveCount(0);
  expect(errors).toEqual([]);
  console.log('PASS: verify startup consent, literal command display, rejection, approval and persisted trust');
} finally {
  await application?.close();
  await fs.rm(temporary, { recursive: true, force: true });
}
