"""Windows shell integration: state survives calls in paths containing spaces."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from feiyu import tools


class ShellPaths(unittest.TestCase):
    def test_windows_paths_use_forward_slashes(self):
        with patch.object(tools.os, 'name', 'nt'):
            self.assertEqual(tools._shell_path(r'C:\Users\Test User\state'),
                             'C:/Users/Test User/state')

    @unittest.skipUnless(os.name == 'nt', 'requires Windows and Git Bash')
    def test_git_bash_preserves_directory_and_environment(self):
        with tempfile.TemporaryDirectory(prefix='feiyu space ') as directory:
            root = Path(directory)
            (root / 'sub dir').mkdir()
            box = tools.Toolbox(root)
            try:
                first = box.run('bash', {'command': "cd 'sub dir'; export FEIYU_PROBE=works"})
                self.assertFalse(first.is_error, first.content)
                second = box.run('bash', {'command': 'printf "%s" "$FEIYU_PROBE"'})
                self.assertFalse(second.is_error, second.content)
                self.assertIn('works', second.content)
                self.assertEqual(Path(box.cwd).resolve(), (root / 'sub dir').resolve())
            finally:
                box.shell_reset()
                box.lsp.close()
