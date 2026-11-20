// Real old/new Electron processes, synthetic retained Chromium + backend data only.
import {_electron as electron,expect} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const desktop=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
import {dialogueFixture} from './dialogue-fixture.mjs';
const [mode,executable,baseArg]=process.argv.slice(2);
const base=path.resolve(baseArg),workspace=path.join(base,'workspace');
if(mode==='seed') await fs.mkdir(workspace,{recursive:true});
const fixture=await dialogueFixture();
const env={...process.env,HOME:base,USERPROFILE:base,XDG_CONFIG_HOME:path.join(base,'config'),XDG_STATE_HOME:path.join(base,'state'),XDG_DATA_HOME:path.join(base,'data'),XDG_CACHE_HOME:path.join(base,'cache'),APPDATA:path.join(base,'AppData','Roaming'),LOCALAPPDATA:path.join(base,'AppData','Local')};
for(const name of ['XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_DATA_HOME','APPDATA','LOCALAPPDATA']) await fs.mkdir(env[name],{recursive:true});
const config=path.join(env.XDG_CONFIG_HOME,'feiyu');await fs.mkdir(config,{recursive:true});
await fs.writeFile(path.join(config,'models.json'),JSON.stringify({offline:{kind:'openai',model:'offline',key:'synthetic',base_url:fixture.url}}));
await fs.writeFile(path.join(config,'state.json'),JSON.stringify({last:'offline'}));
delete env.ELECTRON_RUN_AS_NODE;delete env.FEIYU_BIN;
const args=[...(executable==='source'?[desktop]:[]),...(mode==='seed'?['-w',workspace]:['--resume'])];
let app;
try{
  app=await electron.launch({...(executable==='source'?{}:{executablePath:path.resolve(executable)}),args,env,cwd:base,timeout:30000});
  const page=await app.firstWindow();page.setDefaultTimeout(15000);
  await expect(page.locator('#s-ver')).not.toHaveText('—',{timeout:30000});
  await expect(page.locator('#startup')).toHaveCount(0,{timeout:15000});
  const identity=await app.evaluate(({app})=>({name:app.getName(),userData:app.getPath('userData'),appData:app.getPath('appData'),packaged:app.isPackaged}));
  await expect(page.locator('#desk-path')).toHaveAttribute('title',await fs.realpath(workspace));
  if(mode==='seed'){
    await page.evaluate(()=>setTheme('retro'));
    await page.locator('#input').fill('旧名称合成历史 中文 😀');await page.locator('#send').click();
    await expect(page.locator('body')).toContainText('GUI reply 1 中文 😀 𠮷',{timeout:30000});
    const theme=await page.evaluate(()=>localStorage.getItem('feiyu.theme'));
    expect(theme).toBe('retro');
    await fs.writeFile(path.join(base,'legacy-identity.json'),JSON.stringify({...identity,theme},null,2));
  }else{
    const old=JSON.parse(await fs.readFile(path.join(base,'legacy-identity.json'),'utf8'));
    expect(identity.userData).toBe(old.userData);expect(identity.name).toBe('Biscuit');
    expect(await page.title()).toBe('Biscuit');
    expect(await page.evaluate(()=>localStorage.getItem('feiyu.theme'))).toBe(old.theme);
    await expect(page.locator('html')).toHaveAttribute('data-theme','retro');
    await expect(page.locator('body')).toContainText('旧名称合成历史 中文 😀');
    await expect(page.locator('body')).toContainText('GUI reply 1 中文 😀 𠮷');
    await page.locator('#input').fill('更名后继续');await page.locator('#send').click();
    await expect.poll(()=>fixture.requests.length).toBe(1);
    expect(fixture.requests[0].messages.filter(m=>m.role==='user').length).toBeGreaterThanOrEqual(2);
    await fs.writeFile(path.join(base,'biscuit-identity.json'),JSON.stringify(identity,null,2));
    const results=path.join(desktop,'test-results');await fs.mkdir(results,{recursive:true});
    await page.screenshot({path:path.join(results,`brand-compat-${process.platform}-${identity.packaged?'packaged':'source'}.png`)});
  }
  console.log('PASS brand compatibility',mode,JSON.stringify(identity));
}finally{await app?.close();await fixture.close();}
