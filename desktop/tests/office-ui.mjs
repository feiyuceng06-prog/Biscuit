import { expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

export async function checkOffice(application, page, workspace, output, fixture) {
  await page.getByRole('button', { name: '办公', exact: true }).click();
  await page.getByRole('button', { name: '打开示例文稿' }).click();
  await expect(page.locator('.office-thumb')).toHaveCount(5);
  await expect(page.locator('.office-canvas svg image')).toBeVisible();
  await page.locator('.office-thumb').nth(1).click();
  await page.getByRole('button', { name: '模板与版式' }).click();
  await expect(page.locator('.studio-themes button svg')).toHaveCount(3);
  await page.getByRole('button', { name: '午夜' }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await expect(page.locator('.office-canvas')).toContainText('48 人次');
  await page.getByRole('button', { name: '返回办公' }).click();
  page.once('dialog', (dialog) => dialog.accept());
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
  await page.getByRole('button', { name: '模板与版式' }).click();
  await page.getByRole('button', { name: '陶土', exact: false }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await page.screenshot({ path: path.join(output, 'office-presentation.png') });
  await page.locator('.office-thumb').first().click();
  await page.getByRole('button', { name: '模板与版式' }).click();
  await page.getByRole('button', { name: '午夜', exact: false }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await page.evaluate(() => setTheme('dark'));
  await page.screenshot({ path: path.join(output, 'office-midnight.png') });
  await page.evaluate(() => setTheme('light'));
  await page.getByRole('button', { name: '模板与版式' }).click();
  await page.getByRole('button', { name: '陶土', exact: false }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await page.locator('.office-thumb').nth(4).click();
  await page.getByRole('button', { name: '放映', exact: true }).click();
  await page.getByRole('button', { name: '下一页' }).click();
  await page.keyboard.press('Escape');
  await page.locator('.office-thumb').nth(4).click();
  await page.getByRole('button', { name: 'AI 修改' }).click();
  await page.getByLabel('让 AI 修改本页正文').fill('重点写延期风险');
  await page.getByRole('button', { name: '重新生成本页正文' }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await page.locator('.office-canvas .office-slide-text').filter({ hasText: '交付进度' }).click();
  await page.getByLabel('画布文字').fill('手改标题：项目交付风险');
  await page.getByLabel('画布文字').press('Enter');
  await page.getByRole('button', { name: '编辑内容' }).click();
  const title = page.getByLabel('页面标题', { exact: true });
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
    if (button === '保存源文件') await page.getByRole('button', { name: '文稿选项' }).click();
    await page.getByRole('button', { name: button, exact: true }).click();
    await expect(page.locator('.office-status')).toContainText(filename, { timeout: 15000 });
    expect((await fs.stat(out)).size).toBeGreaterThan(100);
    await fs.copyFile(out, path.join(output, filename));
  }
  await page.getByRole('button', { name: '关闭办公' }).click();
}
