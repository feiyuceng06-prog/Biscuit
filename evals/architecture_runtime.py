"""Environment byte identity shared by the isolated worker and parent."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import sysconfig


def dependency_manifest():
    files = {}
    for folder in sorted(set(sysconfig.get_paths()[k] for k in ('purelib', 'platlib'))):
        root = Path(folder)
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def environment():
    manifest = dependency_manifest()
    return dict(python=sys.version,
                executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                dependency_tree_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                packages=[list(x) for x in sorted(set((d.metadata['Name'], d.version)
                    for d in importlib.metadata.distributions() if d.metadata['Name'] != 'feiyu-agent'))])
