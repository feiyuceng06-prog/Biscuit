export function releaseFixture(version = '0.88.0') {
  const base = `https://github.com/feiyuceng06-prog/Biscuit/releases/download/desktop-v${version}`;
  return { tag_name: `desktop-v${version}`, draft: false, prerelease: false,
    assets: [`Biscuit.Setup.${version}.exe`, `Biscuit-${version}.AppImage`, `feiyu-desktop_${version}_amd64.deb`]
      .map(name => ({ name, state: 'uploaded', size: 100, browser_download_url: `${base}/${name}` })) };
}
