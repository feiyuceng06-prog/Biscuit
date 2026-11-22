import { app, BrowserWindow, ipcMain, dialog, shell, Notification, Menu, net } from 'electron';
import { randomUUID } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readDeck } from './office/deck.mjs';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
import { AgentProcess, resolveBackend } from './agent.mjs';
import { underRoot, readBounded, listFiles, previewFile, uploadFile, MAX_IMAGE } from './files.mjs';
import { pickWorkspace, readLast, writeLast } from './workspace.mjs';
import { installTarget, downloadPackage, installPackage } from './install-update.mjs';
import { createUpdateChecker } from './updates.mjs';

// Preserve Chromium workspace/localStorage identity across the display-name change.
app.setPath('userData', path.join(app.getPath('appData'), 'feiyu-desktop'));
app.setName('Biscuit');
const checkUpdates = createUpdateChecker({ current: app.getVersion(), platform: process.platform,
  linuxDeb: process.platform === 'linux' && !process.env.APPIMAGE && process.execPath === '/opt/Biscuit/feiyu-desktop',
  arch: process.arch, request: (...args) => net.fetch(...args) });

const target = installTarget({ packaged: app.isPackaged, platform: process.platform,
  executable: process.execPath, env: process.env, current: app.getVersion() });
let updateState = { phase: 'idle' };
let prepared, staging;
const updateCache = path.join(app.getPath('userData'), 'updates');
async function clearOldUpdates() {
  for (const entry of await fsp.readdir(updateCache, {withFileTypes:true}).catch(()=>[])) {
    const match = /^stage-(\d+\.\d+\.\d+)-[a-zA-Z0-9]+$/.exec(entry.name);
    if (!match || !entry.isDirectory()) continue;
    const dir = path.join(updateCache, entry.name);
    const stat = await fsp.stat(dir).catch(()=>null);
    if (match[1] === app.getVersion() || (stat && Date.now()-stat.mtimeMs > 2*86400_000))
      await fsp.rm(dir,{recursive:true,force:true}).catch(()=>{});
  }
}
function updatePhase(phase, details = {}) {
  updateState = { phase, ...details };
  emit('feiyu://update', updateState);
}
async function prepareUpdate(latest) {
  if (!target || !['idle', 'error'].includes(updateState.phase)) return;
  updatePhase('downloading', { percent: 0, latest });
  try {
    const release = await checkUpdates();
    if (release.status !== 'available' || release.latest !== latest) throw Error('版本信息已变化，请重新检查');
    await fsp.mkdir(updateCache, {recursive:true, mode:0o700});
    staging = await fsp.mkdtemp(path.join(updateCache, 'stage-' + release.latest + '-'));
    const file = path.join(staging, path.basename(release.downloadUrl));
    await downloadPackage(release, file, (...args) => net.fetch(...args),
      percent => updatePhase('downloading', { percent, latest }));
    prepared = { file, release };
    updatePhase('ready', { latest });
  } catch (error) {
    if (staging) await fsp.rm(staging, {recursive:true,force:true}).catch(()=>{});
    staging = null; prepared = null;
    updatePhase('error', { message: error.message, latest });
  }
}
async function applyUpdate() {
  if (!target || !prepared || updateState.phase !== 'ready') return;
  const { file, release } = prepared;
  updatePhase('installing', { latest: release.latest });
  try {
    await installPackage(target, file, release.digest, process.resourcesPath, workspace ? ['-w',workspace] : []);
  } catch (error) {
    await fsp.rm(staging, {recursive:true,force:true}).catch(()=>{});
    prepared = null; staging = null;
    updatePhase('error', { latest: release.latest, message: '更新失败：' + error.message });
    return;
  }
  if (target.kind !== 'nsis') await fsp.rm(staging, {recursive:true,force:true}).catch(()=>{});
  staging = null;
  app.quit();
}

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const rendererURL = pathToFileURL(path.resolve(here, '../dist/index.html')).href;
const require = createRequire(import.meta.url);
const options = { workspace: null, resume: false, model: null };
const argv = process.argv.slice(app.isPackaged ? 1 : 2);
for (let i = 0; i < argv.length; i++) {
  if (['-w', '--workspace'].includes(argv[i])) options.workspace = argv[++i] || options.workspace;
  else if (['-m', '--model'].includes(argv[i])) options.model = argv[++i];
  else if (['-r', '--resume'].includes(argv[i])) options.resume = true;
}
let lastFile;
let win, agent, terminal, workspace, transition, shown;
let state = { state: 'starting' };
let quitting = false;
const logDir = path.join(process.env.XDG_STATE_HOME || path.join(os.homedir(), '.local/state'), 'feiyu');
fs.mkdirSync(logDir, { recursive: true, mode: 0o700 });
const logPath = path.join(logDir, 'desktop.log');
function log(data) {
  try {
    if (fs.existsSync(logPath) && fs.statSync(logPath).size > 4 * 1024 * 1024) fs.truncateSync(logPath);
    fs.appendFileSync(logPath, data, { mode: 0o600 });
    fs.chmodSync(logPath, 0o600);
  } catch { /* Logging must not prevent a desktop launch. */ }
  if (process.env.FEIYU_DESKTOP_STDERR) process.stderr.write(data);
}
function emit(channel, payload) { if (win && !win.isDestroyed()) win.webContents.send(channel, payload); }
function setState(next) { state = next; emit('feiyu://state', next); }
function trusted(event) {
  if (!win || event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame || event.senderFrame.url !== rendererURL) {
    throw new Error('不允许的桌面调用来源');
  }
}
function stopTerminal() { const old = terminal; terminal = null; try { old?.kill(); } catch {} }
function dimensions(args) {
  return { cols: Math.max(2, Math.min(500, Number(args.cols) || 80)), rows: Math.max(2, Math.min(300, Number(args.rows) || 24)) };
}
async function startAgent(next, resume = false) {
  if (transition) throw new Error('工作台正在切换，请稍后再试');
  transition = (async () => {
    const target = await fsp.realpath(next);
    if (!(await fsp.stat(target)).isDirectory()) throw new Error('请选择文件夹');
    stopTerminal();
    if (!agent) agent = new AgentProcess({
      backend: resolveBackend({ packaged: app.isPackaged, resources: process.resourcesPath, root }),
      onEvent: line => emit('feiyu://event', line), onState: setState, onLog: log,
    });
    await agent.start(target, { model: options.model, resume });
    workspace = target;
    writeLast(lastFile, target);
    return workspace;
  })();
  try { return await transition; }
  catch (error) { setState({ state: 'error', message: error.message }); throw error; }
  finally { transition = null; }
}
ipcMain.handle('feiyu:directory', async event => {
  trusted(event);
  const result = await dialog.showOpenDialog(win, { title: '选择工作台', properties: ['openDirectory'] });
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('feiyu:window', (event, action) => {
  trusted(event);
  if (action === 'minimize') win.minimize();
  else if (action === 'maximize') win.isMaximized() ? win.unmaximize() : win.maximize();
  else if (action === 'close') win.close();
});
ipcMain.handle('feiyu:command', async (event, command, args = {}) => {
  trusted(event);
  switch (command) {
    case 'presentation_design_enabled': return process.env.presentation_design_engine === '1';
    case 'presentation_content':
    case 'presentation_reference': {
      const content = command === 'presentation_content';
      const selected = await dialog.showOpenDialog(win, { title: content ? '导入 PPTX 内容' : '分析参考演示文稿', properties: ['openFile'],
        filters: [{ name: 'PowerPoint', extensions: ['pptx'] }] });
      if (selected.canceled || !selected.filePaths.length) return null;
      const backend = resolveBackend({ packaged: app.isPackaged, resources: process.resourcesPath, root });
      try {
        const { stdout } = await promisify(execFile)(backend.command,
          [...backend.args, content ? '--presentation-content' : '--presentation-reference', selected.filePaths[0]],
          { windowsHide: true, timeout: 15000, maxBuffer: content ? 1024 * 1024 : 65536, env: { ...process.env, PYTHONUTF8: '1' } });
        return JSON.parse(stdout);
      } catch (error) {
        if (content) {
          if (error.killed) throw Error('读取 PPTX 超时');
          const reason = error.stderr?.trim();
          throw Error(reason && reason.length <= 320 ? reason : '无法导入 PPTX 内容，请检查文件和本机后端');
        }
        throw Error('无法读取参考 PPTX。请选择有效的 .pptx 文件（最多 16 MB、100 页）。');
      }
    }
    case 'presentation_save': {
      const deck = readDeck(args.deck);
      if (!['pptx', 'json'].includes(args.format)) throw Error('未知文件格式');
      const pptx = args.format === 'pptx';
      const suffix = pptx ? '.pptx' : '.deck.json';
      const name = deck.title.replace(/[^\p{L}\p{N} _-]/gu, '').trim() || '演示文稿';
      const result = await dialog.showSaveDialog(win, {
        title: pptx ? '导出 PowerPoint' : '保存演示文稿源文件',
        defaultPath: path.join(workspace || app.getPath('documents'), name + suffix),
        filters: [{ name: pptx ? 'PowerPoint' : 'Biscuit 演示文稿', extensions: [pptx ? 'pptx' : 'json'] }],
      });
      if (result.canceled || !result.filePath) return null;
      const destination = result.filePath;
      if (!destination.toLowerCase().endsWith(pptx ? '.pptx' : '.json')) throw Error('请选择匹配的文件扩展名');
      if (pptx && deck.design?.version === 2 && deck.design.direction === 'photography') {
        const { deliverPhotography } = await import('./office/photo-delivery.mjs');
        let backend, backendError;
        try {
          backend = resolveBackend({ packaged: app.isPackaged, resources: process.resourcesPath, root });
        } catch (error) {
          backendError = error.message;
        }
        return deliverPhotography(destination, deck, { backend, backendError });
      }
      const data = pptx ? await (await import('./office/pptx.mjs')).powerPoint(deck) : JSON.stringify(deck, null, 2);
      const temp = path.join(path.dirname(destination), '.' + randomUUID() + '.tmp');
      try {
        await fsp.writeFile(temp, data, { flag: 'wx', mode: 0o600 });
        await fsp.rename(temp, destination);
      } finally { await fsp.rm(temp, { force: true }); }
      if (pptx && process.env.presentation_design_engine === '1') {
        try {
          const backend = resolveBackend({ packaged: app.isPackaged, resources: process.resourcesPath, root });
          return await (await import('./office/review.mjs')).reviewExport(destination, data, deck, backend);
        } catch {
          return { destination, status: 'preview_unavailable' };
        }
      }
      return destination;
    }
    case 'update_state': return updateState;
    case 'prepare_update': return prepareUpdate(args.latest);
    case 'apply_update': return applyUpdate();
    case 'check_updates':
      if (args.automatic === true && process.env.FEIYU_DISABLE_UPDATE_CHECK === '1') {
        return { status: 'idle', current: app.getVersion() };
      }
      return { ...await checkUpdates({ automatic: args.automatic === true }), inApp: !!target };
    case 'connect':
      if (agent?.child && !transition) { emit('feiyu://state', state); return workspace; }
      return startAgent(workspace || options.workspace, options.resume);
    case 'send': return agent?.send(args.line) ?? Promise.reject(new Error('Agent 未连接'));
    case 'where_am_i': return workspace || options.workspace;
    case 'switch': return startAgent(args.dir);
    case 'upload': return uploadFile(workspace, args.name, args.data);
    case 'read_image': return new Uint8Array(await readBounded(workspace, args.path, MAX_IMAGE)).buffer;
    case 'list_files': return listFiles(workspace, args.path);
    case 'preview_file': return previewFile(workspace, args.path);
    case 'open_url': {
      const url = new URL(args.url);
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error('只允许 http/https 链接');
      return shell.openExternal(url.href);
    }
    case 'notify':
      if (Notification.isSupported()) {
        const notification = new Notification({ title: String(args.title).slice(0, 80), body: String(args.body).slice(0, 240), icon: path.join(here, '../dist/icon.png') });
        notification.on('click', () => { win.show(); win.focus(); });
        notification.show();
      }
      return;
    case 'term_start': {
      stopTerminal();
      const cwd = await underRoot(workspace, args.cwd || '.');
      const pty = require('node-pty');
      const command = process.platform === 'win32' ? (process.env.COMSPEC || 'cmd.exe') : (process.env.SHELL || '/bin/sh');
      const child = pty.spawn(command, process.platform === 'win32' ? [] : ['-i'], {
        ...dimensions(args), cwd, name: 'xterm-256color', env: { ...process.env, TERM: 'xterm-256color' },
      });
      terminal = child;
      child.onData(data => { if (terminal === child) emit('feiyu://term', data); });
      child.onExit(() => { if (terminal === child) { terminal = null; emit('feiyu://term', '\r\n（shell 已结束）\r\n'); } });
      return;
    }
    case 'term_write':
      if (!terminal) throw new Error('终端未启动');
      if (typeof args.data !== 'string' || args.data.length > 1_000_000) throw new Error('无效终端输入');
      terminal.write(args.data); return;
    case 'term_resize': { const size = dimensions(args); terminal?.resize(size.cols, size.rows); return; }
    case 'term_stop': stopTerminal(); return;
    case 'shown': return shown;
    default: throw new Error('未知桌面能力');
  }
});

app.whenReady().then(async () => {
await clearOldUpdates();
lastFile = path.join(app.getPath('userData'), 'workspace.json');
options.workspace = pickWorkspace({ given: options.workspace, cwd: process.cwd(), home: os.homedir(), last: readLast(lastFile) });
Menu.setApplicationMenu(null);
win = new BrowserWindow({
  title: 'Biscuit', width: 1440, height: 920, minWidth: 800, minHeight: 560,
  frame: false, backgroundColor: '#ffffff', show: false,
  icon: path.join(here, '../dist/icon.png'),
  webPreferences: { preload: path.join(here, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true },
});
win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
win.webContents.on('will-navigate', event => event.preventDefault());
win.webContents.on('will-attach-webview', event => event.preventDefault());
win.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
win.webContents.session.setPermissionCheckHandler(() => false);
// The page paints before the window is mapped (ready-to-show waits for that), and
// visibilityState already reads "visible" then; the startup animation waits for this instead.
shown = new Promise(resolve => win.once('show', () => resolve(true)));
win.once('ready-to-show', () => win.show());
win.webContents.on('render-process-gone', () => { stopTerminal(); void agent?.stop(); });
app.on('before-quit', event => {
  if (quitting) return;
  event.preventDefault();
  quitting = true;
  stopTerminal();
  Promise.allSettled([agent?.stop(), staging && updateState.phase !== 'installing' ? fsp.rm(staging,{recursive:true,force:true}) : null]).finally(() => app.quit());
});
app.on('window-all-closed', () => app.quit());
await win.loadURL(rendererURL);

}).catch(error => { log(error.stack + "\n"); dialog.showErrorBox("Biscuit 启动失败", error.message); app.quit(); });
