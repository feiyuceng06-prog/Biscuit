"""Fetch the pinned official PortableGit distribution for the Windows installer."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

if sys.platform != 'win32':
    raise SystemExit('Build the Windows command environment on Windows x64.')

VERSION = '2.56.1'
SHA256 = '9dd04a608ceb5f6ab32a73709e0ecb159d211da71b697c45ff81f6dd0c6b49c7'
URL = ('https://github.com/git-for-windows/git/releases/download/'
       f'v{VERSION}.windows.1/PortableGit-{VERSION}-64-bit.7z.exe')
destination = Path(__file__).resolve().parents[1] / 'build' / 'git'
destination.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='feiyu-portable-git-') as directory:
    archive = Path(directory) / 'portable-git.exe'
    urllib.request.urlretrieve(URL, archive)
    with archive.open('rb') as source:
        digest = hashlib.sha256(source.read()).hexdigest()
    if digest != SHA256:
        raise RuntimeError('PortableGit SHA-256 mismatch; refusing to extract')
    unpacked = Path(directory) / 'git'
    unpacked.mkdir()
    subprocess.run([str(archive), '-y', f'-o{unpacked}'], check=True)
    for filename in ('bin/bash.exe', 'usr/bin/tail.exe', 'cmd/git.exe'):
        if not (unpacked / filename).is_file():
            raise RuntimeError(f'PortableGit missing {filename}')
    # Preserve the upstream distribution in full, including its license notices.
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(unpacked, destination)
print(f'PortableGit {VERSION} ready: {destination}')
