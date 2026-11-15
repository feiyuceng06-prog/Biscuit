"""Exercise the installed bundled shell with system Git removed from PATH."""
import importlib
import os
from pathlib import Path
import sys
import tempfile

if os.name != 'nt':
    raise SystemExit('This test requires Windows')

# Import the application first, then simulate the frozen backend location and
# reload shell discovery as it runs at startup. No system Git is discoverable.
from feiyu import sandbox
from feiyu.tools import Toolbox
backend = Path(sys.argv[1]).resolve()
sys.frozen = True
sys.executable = str(backend)
os.environ['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
os.environ['ProgramFiles'] = str(backend.parent / 'no-system-git')
os.environ['ProgramFiles(x86)'] = os.environ['ProgramFiles']
importlib.reload(sandbox)
expected = backend.parent.parent / 'git' / 'bin' / 'bash.exe'
assert Path(sandbox.SHELL).resolve() == expected.resolve(), (sandbox.SHELL, expected)
with tempfile.TemporaryDirectory(prefix='feiyu shell ') as directory:
    root = Path(directory)
    (root / 'sub dir').mkdir()
    box = Toolbox(root)
    try:
        first = box.run('bash', {'command': "cd 'sub dir'; export FEIYU_PROBE=works"})
        assert not first.is_error, first.content
        second = box.run('bash', {'command': 'printf "%s\\n" "$FEIYU_PROBE"; git --version; printf file | cat'})
        assert not second.is_error, second.content
        assert 'works' in second.content and 'git version' in second.content and 'file' in second.content, second.content
        assert Path(box.cwd).resolve() == (root / 'sub dir').resolve(), box.cwd
        print('PASS: installed bundled bash, Git and utilities work without system Git')
    finally:
        box.shell_reset()
        box.lsp.close()
