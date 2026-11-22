import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs/promises';
import { installTarget, downloadPackage, installPackage } from '../electron/install-update.mjs';

const data = Buffer.from('new package');
const digest = 'sha256:' + createHash('sha256').update(data).digest('hex');
async function temp(t) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'biscuit-update-test-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  return dir;
}
test('release bytes must match both digest and length before installation', async (t) => {
  const dir = await temp(t);
  for (const [label, size, hash] of [
    ['wrong', data.length, 'sha256:' + '0'.repeat(64)],
    ['long', 1, digest],
    ['short', data.length + 1, digest],
  ]) {
    await assert.rejects(
      downloadPackage(
        { size, digest: hash },
        path.join(dir, label),
        async () => new Response(data),
        () => {},
      ),
    );
  }
  const progress = [];
  await downloadPackage(
    { size: data.length, digest },
    path.join(dir, 'good'),
    async () => new Response(data),
    (n) => progress.push(n),
  );
  assert.deepEqual(progress, [99]);
});
test(
  'AppImage preserves a shortcut target and restores the old file if launching fails',
  { skip: process.platform === 'win32' },
  async (t) => {
    const dir = await temp(t),
      original = path.join(dir, 'Biscuit 0.1.AppImage'),
      file = path.join(dir, 'next');
    await fs.writeFile(original, 'old');
    await fs.writeFile(file, data);
    const link = path.join(dir, 'shortcut');
    await fs.symlink(original, link);
    const args = ['-w', 'a folder'];
    const target = { kind: 'appimage', file: link };
    await assert.rejects(
      installPackage(target, file, digest, '', args, async () => {
        throw Error('launch failed');
      }),
    );
    assert.equal(await fs.readFile(link, 'utf8'), 'old');
    await installPackage(target, file, digest, '', args, async (exe, argv) => {
      assert.equal(exe, original);
      assert.deepEqual(argv, args);
      assert.deepEqual(await fs.readFile(exe), data);
    });
    assert.deepEqual(await fs.readFile(link), data);
    await fs.writeFile(file, 'tampered');
    await assert.rejects(installPackage(target, file, digest, '', args), /改变/);
  },
);
test('unmanaged Linux builds never overwrite an unrelated image', () => {
  const config = {
    packaged: true,
    platform: 'linux',
    executable: '/tmp/build/feiyu-desktop',
    current: '1.0.0',
    env: { APPIMAGE: '/home/user/other.AppImage', APPDIR: '/tmp/another-app' },
    home: '/home/user',
  };
  assert.equal(installTarget(config), null);
  assert.equal(
    installTarget({ ...config, executable: '/opt/Biscuit/feiyu-desktop', env: {} }).kind,
    'deb',
  );
  if (process.platform !== 'win32')
    assert.equal(
      installTarget({
        ...config,
        executable: '/home/user/.local/share/feiyu-desktop/app-1.0.0/feiyu-desktop',
        env: {},
      }).kind,
      'extracted',
    );
});

test('restart executes the replacement at the existing path', { skip: process.platform !== 'linux' }, async t => {
  const dir = await temp(t);
  const original = path.join(dir, 'Biscuit.AppImage');
  const downloaded = path.join(dir, 'package');
  const marker = path.join(dir, 'workspace starting');
  const script = Buffer.from('#!/bin/sh\nprintf "%s" "new version" > "$1"\n');
  await fs.writeFile(original, 'old version');
  await fs.writeFile(downloaded, script);
  const sha = 'sha256:' + createHash('sha256').update(script).digest('hex');
  await installPackage({ kind: 'appimage', file: original }, downloaded, sha, dir, [marker]);
  for (let attempt = 0; attempt < 100; attempt++) {
    if ((await fs.readFile(marker,'utf8').catch(()=>'')) === 'new version') return;
    await new Promise(resolve=>setTimeout(resolve,20));
  }
  assert.fail('replacement did not start');
});
