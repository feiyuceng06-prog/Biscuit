import { createHash } from 'node:crypto';
import { expect } from '@playwright/test';
import { releaseFixture } from './update-fixture.mjs';

async function showUpdates(page) {
  const panel = page.getByRole('region', { name: '软件更新' });
  // Narrow windows can give the sidebar's space to the file preview.
  if (!await panel.isVisible() && await page.locator('.files-panel').isVisible()) {
    await page.locator('#act-files').click();
  }
  await expect(panel).toBeVisible();
  return panel;
}

export async function checkUpdateFailure(application, page) {
  await application.evaluate(({ net }) => {
    net.fetch = async () => { throw new Error('Synthetic offline response'); };
    delete process.env.FEIYU_DISABLE_UPDATE_CHECK;
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  const panel = await showUpdates(page);
  const check = panel.getByRole('button', { name: '检查更新', exact: true });
  await expect(check).toBeEnabled();
  await expect(panel.getByRole('status')).toHaveCount(0);
  await check.click();
  await expect(panel).toContainText('暂时无法检查更新，请稍后重试');
  await expect(check).toBeEnabled();
  await expect(page.locator('#input')).toBeEditable();
  await expect(page.locator('#s-ver')).not.toHaveText('—', { timeout: 30000 });
  await expect(page.locator('#send')).toBeVisible();
  console.log('PASS: offline automatic check is quiet; manual failure is visible and chat remains usable');
}

export async function checkUpdateNotice(application, page) {
  const fixture = releaseFixture('99.0.0');
  for (const asset of fixture.assets) asset.digest = 'sha256:' + createHash('sha256').update(Buffer.alloc(asset.size)).digest('hex');
  await application.evaluate(({ net, shell }, release) => {
    net.fetch = async url => String(url).includes('/releases/download/') ? new Response(new Uint8Array(100)) : ({ ok: true, json: async () => release });
    shell.openExternal = async url => { globalThis.__updateOpenedURL = url; };
    delete process.env.FEIYU_DISABLE_UPDATE_CHECK;
  }, fixture);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  const panel = await showUpdates(page);
  await expect(panel).toContainText('发现新版本 99.0.0');
  const inApp = await panel.getByRole('button', {name:'立即更新'}).count() > 0;
  const action = inApp ? '立即更新' : '下载更新';
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => setTheme(value), theme);
    await panel.getByRole('button', { name: action }).click({ trial: true });
    await page.screenshot({ path: `test-results/update-${theme}.png`, animations: 'disabled' });
  }
  await panel.getByRole('button', { name: '稍后' }).click();
  await expect(panel).not.toContainText('发现新版本');
  await page.reload();
  await expect(panel.getByRole('button', { name: '检查更新', exact: true })).toBeEnabled();
  await expect(panel).not.toContainText('发现新版本');
  await panel.getByRole('button', { name: '检查更新', exact: true }).click();
  await expect(panel).toContainText('发现新版本 99.0.0');
  await panel.getByRole('button', { name: '更新说明' }).click();
  await expect.poll(() => application.evaluate(() => globalThis.__updateOpenedURL))
    .toBe('https://github.com/feiyuceng06-prog/Biscuit/releases/tag/desktop-v99.0.0');
  if (inApp) {
    await panel.getByRole('button', { name: action }).click();
    await expect(panel.getByRole('button',{ name:'重启并更新' })).toBeVisible();
    await page.reload();
    await expect(panel.getByRole('button',{ name:'重启并更新' })).toBeVisible();
  } else {
    await panel.getByRole('button', { name: action }).click();
    const filename = process.platform === 'win32' ? 'Biscuit.Setup.99.0.0.exe'
      : await application.evaluate(() => process.execPath === '/opt/Biscuit/feiyu-desktop' && !process.env.APPIMAGE)
        ? 'feiyu-desktop_99.0.0_amd64.deb' : 'Biscuit-99.0.0.AppImage';
    await expect.poll(() => application.evaluate(() => globalThis.__updateOpenedURL))
      .toBe('https://github.com/feiyuceng06-prog/Biscuit/releases/download/desktop-v99.0.0/' + filename);
  }
  console.log('PASS: automatic release notice, both themes, persisted dismissal, manual rediscovery, canonical release link');
}
