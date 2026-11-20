import { expect } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../test-results');
const prefix = `${process.platform}-${process.env.FEIYU_TEST_STAGE || (process.env.FEIYU_TEST_EXECUTABLE ? 'packaged' : 'source')}-${process.env.FEIYU_TEST_SCALE || 'system'}`;
export async function retainLayout(page, label) {
  await fs.mkdir(root, {recursive:true});
  const geometry = await page.evaluate(() => {
    const selectors = ['.side','.sheet','.composer','#input','#send','.files-panel','.preview-empty','.file-preview'];
    return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio,files:document.body.dataset.files,
      rects:Object.fromEntries(selectors.map(selector => {
        const el = document.querySelector(selector);
        if (!el) return [selector,null];
        const r = el.getBoundingClientRect();
        const hit = document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
        return [selector,{x:r.x,y:r.y,width:r.width,height:r.height,hit:hit?.outerHTML.slice(0,300),
          receivesPointer:!!hit && (hit === el || el.contains(hit)),position:getComputedStyle(el).position}];
      }))};
  });
  await fs.writeFile(path.join(root,`${prefix}-${label}.json`),JSON.stringify(geometry,null,2));
  await page.screenshot({path:path.join(root,`${prefix}-${label}.png`)});
  return geometry;
}
export async function checkLayout(application,page,content) {
  const original = await application.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0].getContentSize());
  await application.evaluate(({BrowserWindow}) => BrowserWindow.getAllWindows()[0].unmaximize());
  try {
    for (const [width,height] of [[800,560],[1024,768],[1098,768],[1102,768],[1440,920]]) {
      await application.evaluate(({BrowserWindow},size) => BrowserWindow.getAllWindows()[0].setContentSize(...size),[width,height]);
      // Windows fractional device scales round native frame/content bounds by up to 2 CSS px.
      await expect.poll(async () => {
        const size = await page.evaluate(() => [innerWidth,innerHeight]);
        return Math.max(Math.abs(size[0]-width), Math.abs(size[1]-height));
      }).toBeLessThanOrEqual(process.platform === 'win32' ? 2 : 0);
      for (const open of [false,true]) {
        if (await page.locator('body').getAttribute('data-files') !== (open?'on':'off')) await page.locator('#act-files').click();
        await expect(page.locator('.files-panel'))[open?'toBeVisible':'toBeHidden']();
        if (!open) await expect(page.locator('#nav-shelf')).toBeVisible();
        await page.locator('#input').fill('布局输入 中文 😀');
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const g = await retainLayout(page,`${content}-${width}x${height}-${open?'on':'off'}`);
        await page.locator('#input').click();
        await expect(page.locator('#input')).toBeFocused();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        // Ordinary click actionability checks include pointer interception; no dispatch/force.
        await page.locator('#send').click({trial:true});
        for (const selector of ['#input','#send']) {
          const r = g.rects[selector];
          expect(r.receivesPointer,JSON.stringify(g)).toBe(true);
          expect(r.x).toBeGreaterThanOrEqual(0); expect(r.y).toBeGreaterThanOrEqual(0);
          expect(r.x+r.width).toBeLessThanOrEqual(g.width+1);
          expect(r.y+r.height).toBeLessThanOrEqual(g.height+1);
        }
        if (open) {
          expect(g.rects['.files-panel'].x).toBeGreaterThanOrEqual(g.rects['.composer'].x+g.rects['.composer'].width);
          if (content === 'file') await expect(page.locator('.file-preview')).toContainText('Electron + Python agent.');
        }
      }
    }
  } catch (error) {
    await retainLayout(page,`${content}-layout-failure`);
    throw error;
  } finally {
    await page.locator('#input').fill('');
    await application.evaluate(({BrowserWindow},size) => BrowserWindow.getAllWindows()[0].setContentSize(...size),original);
  }
  console.log(`PASS ordinary input/Send hit testing, preview on/off (${content}), five window sizes; device scale recorded`);
}
