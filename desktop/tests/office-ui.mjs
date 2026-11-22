import { expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

export async function checkOffice(application, page, workspace, output, fixture) {
  await page.getByRole('button', { name: '办公', exact: true }).click();
  await page.getByRole('button', { name: '新建演示文稿' }).click();
  await page.getByLabel('制作要求').fill('给管理层做八页汇报，重点讲风险');
  await page
    .getByLabel('参考材料')
    .fill('试点项目：北区完成 42 个站点，南区完成 28 个站点。延期风险来自备件交付。');
  await page.getByRole('button', { name: '生成大纲' }).click();
  await expect(page.locator('.office-thumb')).toHaveCount(8, { timeout: 30000 });
  await page.getByRole('button', { name: '生成剩余 8 页正文' }).click();
  await expect(page.locator('.office-status')).toContainText('逐页生成完成', { timeout: 60000 });
  await page.locator('.office-thumb').nth(4).click();
  await expect(page.getByRole('combobox', { name: '版式', exact: true })).toHaveValue('chart');
  await page.locator('.office-canvas .office-slide-text').filter({ hasText: '交付进度' }).dblclick();
  await expect(page.getByLabel('页面标题', { exact: true })).toBeFocused();
  await page.screenshot({ path: path.join(output, 'office-presentation.png') });
  const title = page.getByLabel('页面标题', { exact: true });
  await page.getByLabel('让 AI 修改本页正文').fill('重点写延期风险');
  await page.getByRole('button', { name: '重新生成本页正文' }).click();
  await title.fill('手改标题：项目交付风险');
  fixture.releaseRewrite();
  await expect(page.locator('.office-status')).toContainText('本页正文已更新', { timeout: 30000 });
  await expect(title).toHaveValue('手改标题：项目交付风险');
  await expect(page.getByLabel('小标题').first()).toHaveValue('备件风险');
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(title).toHaveValue('手改标题：项目交付风险');
  await expect(page.getByLabel('小标题').first()).toHaveValue('北区');
  for (const [button, filename] of [
    ['保存源文件', '办公.deck.json'],
    ['导出 PPTX', '办公.pptx'],
  ]) {
    // Select a real destination while keeping the OS-native chooser out of automation.
    const out = path.join(workspace, filename);
    await application.evaluate(({ dialog }, dest) => {
      dialog.showSaveDialog = async () => ({ canceled: false, filePath: dest });
    }, out);
    await page.getByRole('button', { name: button, exact: true }).click();
    await expect(page.locator('.office-status')).toContainText(filename, { timeout: 15000 });
    expect((await fs.stat(out)).size).toBeGreaterThan(100);
    await fs.copyFile(out, path.join(output, filename));
  }
  await page.getByRole('button', { name: '关闭办公' }).click();
}
