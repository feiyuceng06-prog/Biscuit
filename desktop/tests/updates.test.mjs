import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createUpdateChecker, releaseStatus, RELEASE_API } from '../electron/updates.mjs';
import { releaseFixture } from './update-fixture.mjs';

test('compare stable versions numerically, including major/minor boundaries', () => {
  for (const [installed, latest, expected] of [
    ['0.9.9', '0.10.0', 'available'], ['0.99.9', '1.0.0', 'available'],
    ['1.0.0', '0.99.9', 'current'], ['0.88.0', '0.88.0', 'current'],
    ['0.88.2', '0.88.3', 'available'], ['0.88.2', '0.88.1', 'current'],
  ]) assert.equal(releaseStatus(installed, releaseFixture(latest), 'linux', 'x64').status, expected);
});

test('only stable desktop tags count; malformed responses fail closed', () => {
  for (const patch of [{ tag_name: 'v1.0.0' }, { tag_name: 'desktop-v1.0.0-beta' },
    { tag_name: 'desktop-v01.0.0' }, { tag_name: 1 }, { draft: true }, { prerelease: true },
    { tag_name: 'desktop-v9007199254740992.0.0' }]) {
    assert.throws(() => releaseStatus('0.87.2', { ...releaseFixture(), ...patch }, 'linux', 'x64'));
  }
  assert.throws(() => releaseStatus('0.87.2', null, 'linux', 'x64'));
});

test('only complete, uploaded packages for this platform trigger a notice', () => {
  const release = releaseFixture();
  assert.equal(releaseStatus('0.87.2', release, 'win32', 'x64').status, 'available');
  release.assets.pop();
  assert.equal(releaseStatus('0.87.2', release, 'linux', 'x64').status, 'unavailable');
  assert.equal(releaseStatus('0.87.2', release, 'win32', 'x64').status, 'available');
  for (const [platform, arch] of [['darwin', 'x64'], ['linux', 'arm64']]) {
    assert.equal(releaseStatus('0.87.2', releaseFixture(), platform, arch).status, 'unavailable');
  }
  for (const patch of [{ state: 'new' }, { size: 0 }, { browser_download_url: 'https://example.org/installer' }]) {
    const invalid = releaseFixture(); Object.assign(invalid.assets[0], patch);
    assert.equal(releaseStatus('0.87.2', invalid, 'win32', 'x64').status, 'unavailable');
  }
});

test('release links are constructed locally, not accepted from remote metadata', () => {
  const result = releaseStatus('0.87.2', { ...releaseFixture(), html_url: 'https://example.org/' }, 'linux', 'x64');
  assert.equal(result.url, 'https://github.com/feiyuceng06-prog/Biscuit/releases/tag/desktop-v0.88.0');
});

test('checks deduplicate requests, cache automatic results, and allow manual refresh', async () => {
  let clock = 0, calls = 0;
  const check = createUpdateChecker({ current: '0.87.2', platform: 'linux', arch: 'x64', now: () => clock,
    request: async (url, options) => {
      calls++;
      assert.equal(url, RELEASE_API);
      assert.equal(options.credentials, 'omit'); assert.equal(options.redirect, 'error');
      assert.ok(options.signal instanceof AbortSignal);
      return { ok: true, json: async () => releaseFixture() };
    } });
  const first = check({ automatic: true });
  assert.equal(check(), first);
  assert.equal((await first).status, 'available'); assert.equal(calls, 1);
  clock = 31_000;
  await check({ automatic: true }); assert.equal(calls, 1);
  await check(); assert.equal(calls, 2);
  clock += 3_600_000;
  await check({ automatic: true }); assert.equal(calls, 3);
});

test('HTTP, offline, timeout, invalid JSON and synchronous failures are retryable errors', async () => {
  for (const fail of [() => ({ ok: false }), () => Promise.reject(new Error('offline')),
    () => Promise.reject(new DOMException('timeout', 'TimeoutError')),
    () => ({ ok: true, json: async () => { throw new Error('invalid JSON'); } }),
    () => { throw new Error('synchronous failure'); }]) {
    let calls = 0, clock = 0;
    const check = createUpdateChecker({ current: '0.87.2', platform: 'win32', arch: 'x64', now: () => clock,
      request: () => ++calls === 1 ? fail() : { ok: true, json: async () => releaseFixture() } });
    assert.equal((await check()).status, 'error');
    clock = 29_000; assert.equal((await check()).status, 'error'); assert.equal(calls, 1);
    clock = 30_000; assert.equal((await check()).status, 'available'); assert.equal(calls, 2);
  }
});
