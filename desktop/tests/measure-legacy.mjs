import {_electron as electron} from '@playwright/test';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const desktop=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const home=await fs.mkdtemp(path.join(os.tmpdir(),'feiyu-legacy-measure-'));
const env={...process.env,HOME:home,USERPROFILE:home,XDG_CONFIG_HOME:path.join(home,'config'),XDG_STATE_HOME:path.join(home,'state'),XDG_DATA_HOME:path.join(home,'data'),APPDATA:path.join(home,'AppData','Roaming'),LOCALAPPDATA:path.join(home,'AppData','Local')};
delete env.ELECTRON_RUN_AS_NODE;
const executable=process.argv[2];
const a=await electron.launch({...(executable?{executablePath:executable}:{}),args:executable?[]:[desktop],env,cwd:home,timeout:30000});
const page=await a.firstWindow();
await page.waitForFunction(() => { const el=document.querySelector('#s-ver'); return el && el.textContent !== '—'; });
try {
  const identity=await a.evaluate(({app})=>({name:app.getName(),appData:app.getPath('appData'),userData:app.getPath('userData'),packaged:app.isPackaged}));
  console.log(JSON.stringify(identity,null,2));
  await fs.mkdir(path.join(desktop,'test-results'),{recursive:true});
  await fs.writeFile(path.join(desktop,'test-results',`legacy-measured-${process.platform}-${identity.packaged?'packaged':'source'}.json`),JSON.stringify(identity,null,2));
}finally{await a.close();await fs.rm(home,{recursive:true,force:true});}
