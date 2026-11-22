import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { createReadStream, createWriteStream, existsSync } from 'node:fs';
import { Readable, Transform } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';

const exec = promisify(execFile);
export function installTarget({ packaged, platform, executable, env, current, home = os.homedir() }) {
  if (!packaged) return null;
  if (platform === 'win32')
    return existsSync(path.join(path.dirname(executable), 'Uninstall Biscuit.exe'))
      ? { kind: 'nsis' }
      : null;
  if (platform !== 'linux') return null;
  if (
    env.APPIMAGE &&
    path.isAbsolute(env.APPIMAGE) &&
    env.APPDIR &&
    path.dirname(executable) === env.APPDIR
  )
    return { kind: 'appimage', file: env.APPIMAGE };
  if (executable === '/opt/Biscuit/feiyu-desktop') return { kind: 'deb', file: executable };
  const base = path.join(env.XDG_DATA_HOME || path.join(home, '.local/share'), 'feiyu-desktop');
  if (executable === path.join(base, 'app-' + current, 'feiyu-desktop'))
    return { kind: 'extracted', file: path.join(home, '.local/bin/feiyu-desktop') };
  return null;
}

export async function downloadPackage(release, file, request, progress) {
  if (
    !release.digest ||
    !/^sha256:[0-9a-f]{64}$/.test(release.digest) ||
    !Number.isSafeInteger(release.size) ||
    release.size <= 0 ||
    release.size > 1024 ** 3
  )
    throw Error('安装包缺少有效的校验信息');
  const response = await request(release.downloadUrl, {
    credentials: 'omit',
    signal: AbortSignal.timeout(15 * 60_000),
  });
  if (!response.ok || !response.body) throw Error('下载安装包失败，请重试');
  const hash = createHash('sha256');
  let received = 0,
    lastPercent = -1;
  const verify = new Transform({
    transform(chunk, encoding, done) {
      received += chunk.length;
      if (received > release.size) return done(Error('安装包大小不符'));
      hash.update(chunk);
      const percent = Math.min(99, Math.floor((received / release.size) * 100));
      if (percent !== lastPercent) {
        lastPercent = percent;
        progress(percent);
      }
      done(null, chunk);
    },
  });
  await pipeline(
    Readable.fromWeb(response.body),
    verify,
    createWriteStream(file, { flags: 'wx', mode: 0o600 }),
  );
  if (received !== release.size || 'sha256:' + hash.digest('hex') !== release.digest)
    throw Error('安装包校验失败，请重新下载');
}

async function launch(file, args = [], env = process.env) {
  const child = spawn(file, args, { env, detached: true, stdio: 'ignore' });
  await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('spawn', resolve);
  });
  child.unref();
}

export async function installPackage(target, file, digest, resources, args, start = launch) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  if ('sha256:' + hash.digest('hex') !== digest) throw Error('安装包已改变，请重新下载');
  if (target.kind === 'nsis') {
    await start(file, ['--updated', '/S', '--force-run']);
    return;
  }
  if (target.kind === 'deb') {
    await exec('/usr/bin/pkexec', ['/usr/bin/apt-get', '-y', '--no-remove', 'install', file]);
    await start(target.file, args);
    return;
  }
  if (target.kind === 'extracted') {
    await exec('/bin/bash', [path.join(resources, 'get.sh'), file], {
      env: { ...process.env, FEIYU_NO_MODIFY_PATH: '1' },
    });
    await start(target.file, args);
    return;
  }
  if (target.kind !== 'appimage') throw Error('未知安装方式');
  // Stage on the same filesystem so the launcher always names one complete executable.
  const original = await fs.realpath(target.file);
  const dir = await fs.mkdtemp(path.join(path.dirname(original), '.biscuit-update-'));
  const backup = path.join(dir, 'previous'),
    next = path.join(dir, 'next');
  try {
    await fs.copyFile(file, next);
    await fs.chmod(next, 0o755);
    try {
      await fs.link(original, backup);
    } catch (error) {
      if (!['EPERM', 'EOPNOTSUPP', 'ENOSYS', 'EMLINK'].includes(error.code)) throw error;
      await fs.copyFile(original, backup);
    }
    await fs.rename(next, original);
    const env = { ...process.env };
    delete env.APPIMAGE;
    delete env.APPDIR;
    delete env.OWD;
    delete env.ARGV0;
    try {
      await start(original, args, env);
    } catch (error) {
      await fs.rename(backup, original);
      throw error;
    }
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
}
