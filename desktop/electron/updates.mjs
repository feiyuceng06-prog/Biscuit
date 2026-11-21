export const RELEASE_API = 'https://api.github.com/repos/feiyuceng06-prog/Biscuit/releases/latest';
const releases = 'https://github.com/feiyuceng06-prog/Biscuit/releases';

function version(value) {
  if (typeof value !== 'string' || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(value)) return null;
  const parts = value.split('.').map(Number);
  return parts.every(Number.isSafeInteger) ? parts : null;
}

export function releaseStatus(current, release, platform, arch, linuxDeb = false) {
  const installed = version(current);
  const latest = typeof release?.tag_name === 'string' ? release.tag_name.replace(/^desktop-v/, '') : null;
  const available = version(latest);
  if (!installed || !available || release.tag_name !== `desktop-v${latest}` ||
      release.draft !== false || release.prerelease !== false) throw new Error('Invalid release');
  const newer = available.some((part, i) => part > installed[i] && available.slice(0, i).every((n, j) => n === installed[j]));
  if (!newer) return { status: 'current', current };
  const names = platform === 'win32' ? [`Biscuit.Setup.${latest}.exe`]
    : platform === 'linux' ? [`Biscuit-${latest}.AppImage`, `feiyu-desktop_${latest}_amd64.deb`] : [];
  const url = `${releases}/tag/desktop-v${latest}`;
  if (arch !== 'x64' || !names.length || !Array.isArray(release.assets) || !names.every(name => release.assets.some(asset =>
    asset?.name === name && asset.state === 'uploaded' && asset.size > 0 &&
    asset.browser_download_url === `${releases}/download/desktop-v${latest}/${name}`))) {
    return { status: 'unavailable', current, latest };
  }
  const filename = platform === 'linux' && linuxDeb ? names[1] : names[0];
  return { status: 'available', current, latest, url,
    downloadUrl: `${releases}/download/desktop-v${latest}/${filename}` };
}

export function createUpdateChecker({ current, platform, arch, linuxDeb = false, request = fetch, now = Date.now }) {
  let result;
  let checked = -Infinity;
  let pending;
  return function check({ automatic = false } = {}) {
    if (pending) return pending;
    const ttl = automatic && result?.status !== 'error' ? 60 * 60 * 1000 : 30 * 1000;
    if (result && now() - checked < ttl) return Promise.resolve(result);
    pending = Promise.resolve().then(async () => {
      try {
        const response = await request(RELEASE_API, {
          headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'Biscuit-Update-Check' },
          signal: AbortSignal.timeout(10000), redirect: 'error', credentials: 'omit',
        });
        if (!response.ok) throw new Error('Release check failed');
        result = releaseStatus(current, await response.json(), platform, arch, linuxDeb);
      } catch {
        result = { status: 'error', current, message: '暂时无法检查更新，请稍后重试' };
      } finally { checked = now(); pending = null; }
      return result;
    });
    return pending;
  };
}
