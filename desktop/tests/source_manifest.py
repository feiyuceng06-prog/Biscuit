"""Bind diagnostic/installer evidence to the exact tracked checkout and CI run."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
output = root / 'desktop/test-results/source-manifest.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dict(
    commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
    run=os.environ.get('GITHUB_RUN_ID'), attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
    files={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files if name and (root/name).is_file()},
), indent=2), encoding='utf-8')
