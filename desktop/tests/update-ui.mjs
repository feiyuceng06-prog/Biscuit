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
  console.log('PASS: offline automatic check is quiet; manual failure is visible and chat remains usable');
}

export async function checkUpdateNotice(application, page) {
  await application.evaluate(({ net, shell }, release) => {
    net.fetch = async () => ({ ok: true, json: async () => release });
    shell.openExternal = async url => { globalThis.__updateOpenedURL = url; };
    delete process.env.FEIYU_DISABLE_UPDATE_CHECK;
  }, releaseFixture('99.0.0'));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  const panel = await showUpdates(page);
  await expect(panel).toContainText('发现新版本 99.0.0');
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => setTheme(value), theme);
    await panel.getByRole('button', { name: '查看更新' }).click({ trial: true });
    await page.screenshot({ path: `test-results/update-${theme}.png`, animations: 'disabled' });
  }
  await panel.getByRole('button', { name: '稍后' }).click();
  await expect(panel).not.toContainText('发现新版本');
  await page.reload();
  await expect(panel.getByRole('button', { name: '检查更新', exact: true })).toBeEnabled();
  await expect(panel).not.toContainText('发现新版本');
  await panel.getByRole('button', { name: '检查更新', exact: true }).click();
  await expect(panel).toContainText('发现新版本 99.0.0');
  await panel.getByRole('button', { name: '查看更新' }).click();
  expect(await application.evaluate(() => globalThis.__updateOpenedURL))
    .toBe('https://github.com/feiyuceng06-prog/Biscuit/releases/tag/desktop-v99.0.0');
  console.log('PASS: automatic release notice, both themes, persisted dismissal, manual rediscovery, canonical release link');
}
