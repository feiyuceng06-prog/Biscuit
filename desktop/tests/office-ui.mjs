import { expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export async function checkOffice(application, page, workspace, output, fixture) {
  await page.getByRole('button', { name: '办公', exact: true }).click();
  const office = page.locator('dialog.office');
  await expect(office.getByRole('button', { name: '新建演示文稿' })).toBeEnabled();
  for (const theme of ['light', 'dark']) {
    await page.evaluate(theme => setTheme(theme), theme);
    const paletteMatches = await office.evaluate(dialog => {
      const app = getComputedStyle(document.documentElement);
      const local = getComputedStyle(dialog);
      return ['--accent', '--bg', '--raised', '--muted', '--alert', '--selected']
        .every(token => local.getPropertyValue(token) === app.getPropertyValue(token));
    });
    expect(paletteMatches).toBe(true);
    const create = office.getByRole('button', { name: '新建演示文稿' });
    await expect.poll(() => create.evaluate(button =>
      getComputedStyle(button).backgroundColor ===
      getComputedStyle(document.getElementById('send'), '::before').backgroundColor
    )).toBe(true);
    await office.screenshot({ animations: 'disabled', path: path.join(output, 'office-library-' + theme + '.png') });
  }
  await page.evaluate(() => setTheme('system'));
  for (const colorScheme of ['dark', 'light']) {
    await page.emulateMedia({ colorScheme });
    await expect(page.locator('html')).toHaveAttribute('data-theme', colorScheme);
    await expect(office).toHaveCSS('color-scheme', colorScheme);
  }
  await page.emulateMedia({ colorScheme: null });
  await page.evaluate(() => setTheme('light'));
  await page.getByRole('button', { name: '打开示例文稿' }).click();
  await expect(page.locator('.office-thumb')).toHaveCount(5);
  await expect(page.locator('.office-canvas svg image')).toBeVisible();
  await page.locator('.office-thumb').nth(1).click();
  await page.getByRole('button', { name: '复制本页' }).click();
  await expect(page.locator('.office-thumb')).toHaveCount(6);
  await page.getByRole('button', { name: '撤销' }).click();
  await expect(page.locator('.office-thumb')).toHaveCount(5);
  await page.locator('.office-thumb').nth(1).click();
  await page.getByRole('button', { name: '模板与版式' }).click();
  await expect(page.locator('.studio-themes button svg')).toHaveCount(3);
  const design = office.locator('.office-director');
  await design.locator('summary').click();
  await design.getByLabel('受众').fill('运营管理层');
  await design.getByLabel('视觉方向').selectOption('corporate');
  const referencePath = fileURLToPath(new URL('../../docs/presentation/evidence/before/monthly.pptx', import.meta.url));
  await application.evaluate(({ dialog }, file) => {
    const original = dialog.showOpenDialog;
    dialog.showOpenDialog = async () => {
      dialog.showOpenDialog = original;
      return { canceled: false, filePaths: [file] };
    };
  }, referencePath);
  await design.getByRole('button', { name: '分析参考 PPTX' }).click();
  await expect(design).toContainText('monthly · 5 页', { timeout: 20000 });
  await design.getByRole('button', { name: '应用设计方案' }).click();
  await expect(design.locator('summary')).toContainText('企业汇报');
  await expect(design.locator('p')).not.toBeEmpty();
  const reason = design.getByRole('region', { name: '本页构图' }).locator('span');
  await expect(reason).not.toBeEmpty();
  const chartReason = await reason.textContent();
  await page.locator('.office-thumb').first().click();
  await expect(reason).not.toHaveText(chartReason);
  await page.locator('.office-thumb').nth(1).click();
  await expect(reason).toHaveText(chartReason);
  await design.getByLabel('根据每页内容规划构图').uncheck();
  await design.getByRole('button', { name: '应用设计方案' }).click();
  await expect(reason).toHaveCount(0);
  await design.getByLabel('根据每页内容规划构图').check();
  await design.getByRole('button', { name: '应用设计方案' }).click();
  await expect(reason).toHaveText(chartReason);
  await expect(page.locator('.office-canvas')).toContainText('48 人次');
  await design.locator('summary').click();
  const plannedSource = path.join(workspace, '逐页规划.deck.json');
  await application.evaluate(({ dialog }, file) => {
    const original = dialog.showSaveDialog;
    dialog.showSaveDialog = async () => {
      dialog.showSaveDialog = original;
      return { canceled: false, filePath: file };
    };
  }, plannedSource);
  await page.getByRole('button', { name: '文稿选项' }).click();
  await page.getByRole('button', { name: '保存源文件', exact: true }).click();
  await expect(page.locator('.office-status')).toContainText('逐页规划.deck.json');
  const plannedDeck = JSON.parse(await fs.readFile(plannedSource, 'utf8'));
  expect(plannedDeck.design.version).toBe(2);
  expect(plannedDeck.design.slidePlans.map(plan => plan.slideId)).toEqual(plannedDeck.slides.map(slide => slide.id));
  await page.getByRole('button', { name: '模板与版式' }).click();
  await page.getByRole('button', { name: '午夜' }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await expect(page.locator('.office-canvas')).toContainText('48 人次');
  await page.getByRole('button', { name: 'AI 修改' }).click();
  await page.locator('.office-task summary').press('Enter');
  await expect(page.locator('.office-task li')).toHaveCount(5);
  await page.getByRole('button', { name: '收起面板' }).click();
  await page.getByRole('button', { name: '返回办公' }).click();
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '新建演示文稿' }).click();
  const source = page.locator('.office-report');
  await source.fill('已有材料');
  await application.evaluate(({ dialog }, file) => {
    const original = dialog.showOpenDialog;
    dialog.showOpenDialog = async () => {
      dialog.showOpenDialog = original;
      return { canceled: false, filePaths: [file] };
    };
  }, referencePath);
  await page.getByRole('button', { name: '导入 PPTX 内容' }).click();
  await expect(source).toHaveValue(/^已有材料\n\nPPTX 共 5 页[\s\S]*演讲者备注/, { timeout: 15000 });
  await source.fill('');
  const viewport = await page.evaluate(() => ({ width: innerWidth, height: innerHeight }));
  try {
    await page.setViewportSize({ width: 390, height: 740 });
    await expect(page.getByRole('button', { name: '生成大纲' })).toBeDisabled();
    await expect(page.getByRole('button', { name: '手动编辑' })).toBeInViewport();
    await page.getByLabel('制作要求').focus();
    await office.screenshot({ animations: 'disabled', path: path.join(output, 'office-source-narrow.png') });
    await page.getByRole('button', { name: '手动编辑' }).click();
    await expect(page.locator('.studio-rail')).toHaveCount(0);
    await page.getByRole('button', { name: '页面缩略图' }).click();
    await expect(page.locator('.studio-rail')).toBeInViewport();
    await page.locator('.office-thumb').first().click();
    await expect(page.locator('.studio-rail')).toHaveCount(0);
    await page.getByRole('button', { name: '文稿选项' }).click();
    await page.getByRole('button', { name: '参考材料' }).click();
  } finally {
    await page.setViewportSize(viewport);
  }
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
  await page.screenshot({ animations: 'disabled', path: path.join(output, 'office-presentation.png') });
  await page.locator('.office-thumb').first().click();
  await page.getByRole('button', { name: '模板与版式' }).click();
  await page.getByRole('button', { name: '午夜', exact: false }).click();
  await page.getByRole('button', { name: '收起面板' }).click();
  await page.evaluate(() => setTheme('dark'));
  await page.screenshot({ animations: 'disabled', path: path.join(output, 'office-midnight.png') });
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
  await page.locator('.office-task summary').click();
  await page.getByLabel('让 AI 修改本页正文').fill('重点写延期风险');
  await page.getByRole('button', { name: '重新生成本页正文' }).click();
  await expect(page.locator('.office-task li').nth(4)).toContainText('生成中');
  await page.screenshot({ animations: 'disabled', path: path.join(output, 'office-task-running.png') });
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
    if (filename.endsWith('.pptx') && process.env.presentation_design_engine === '1') {
      const folder = (await fs.readdir(workspace)).find(name => name.startsWith(filename + '.review-'));
      const report = JSON.parse(await fs.readFile(path.join(workspace, folder, 'report.json')));
      expect(['checked', 'needs_review', 'blocked']).toContain(report.status);
      expect(report.pages).toHaveLength(8);
      await expect(page.locator('.office-status')).toContainText('report.json');
    }
    expect((await fs.stat(out)).size).toBeGreaterThan(100);
    await fs.copyFile(out, path.join(output, filename));
  }
  await page.getByRole('button', { name: '关闭办公' }).click();
}
