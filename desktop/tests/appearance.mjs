import { expect } from '@playwright/test';

export async function checkAppearance(page) {
  const root = page.locator('html');
  await page.evaluate(() => { shelf.tab = 'general'; shelf.find = ''; shelf.pick.general = '外观'; showShelf(true); });
  await expect(page.locator('.opt__name')).toHaveText(['浅色', '深色', '跟随系统']);
  const choose = async name => page.locator('.opt').filter({ has: page.getByText(name, { exact: true }) }).click();
  await page.emulateMedia({ colorScheme: 'light' });
  await choose('深色');
  await expect(root).toHaveAttribute('data-theme', 'dark');
  await page.emulateMedia({ colorScheme: 'dark' });
  await choose('浅色');
  await expect(root).toHaveAttribute('data-theme', 'light');
  await choose('跟随系统');
  await expect(root).toHaveAttribute('data-theme', 'dark');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(root).toHaveAttribute('data-theme', 'light');
  expect(await page.evaluate(() => localStorage.getItem('feiyu.theme'))).toBe('system');
  // A reload must preserve the preference, not persist the last resolved color.
  await page.reload();
  await page.keyboard.press('Escape');
  await expect(root).toHaveAttribute('data-theme', 'light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(root).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => theme())).toBe('system');
  // Existing skins migrate to a matching brightness without retaining old assets.
  for (const [old, next] of [['retro', 'light'], ['inception', 'dark'], ['unknown', 'system']]) {
    await page.evaluate(value => localStorage.setItem('feiyu.theme', value), old);
    await page.reload();
    await page.keyboard.press('Escape');
    expect(await page.evaluate(() => theme())).toBe(next);
    await expect(root).toHaveAttribute('data-theme', next === 'system' ? 'dark' : next);
  }
  // The already-open terminal updates alongside the page.
  await page.locator('#act-term').click();
  await page.waitForFunction(() => !!document.querySelector('.xterm-screen'));
  for (const name of ['light', 'dark']) {
    await page.evaluate(value => setTheme(value), name);
    expect(await page.evaluate(() => term.options.theme.background)).toBe(
      await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()));
    await expect.poll(() => page.locator('.side__tab[aria-selected="true"]').evaluate(
      el => getComputedStyle(el).color)).toBe(name === 'dark' ? 'rgb(238, 240, 244)' : 'rgba(0, 0, 0, 0.8)');
    await page.screenshot({ path: `test-results/appearance-${name}.png`, animations: 'disabled' });
  }
  await page.locator('#act-term').click();
  console.log('PASS: three appearance choices, live system changes, persistence, legacy migration, terminal colors');
}
