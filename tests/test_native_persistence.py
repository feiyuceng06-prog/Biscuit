"""Portable release contracts: run on the target OS, never mock persistence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from feiyu import session
from feiyu.taskstate import TaskStore, TaskState, PersistenceError, atomic_json, workspace_id
from feiyu.verification import _read_safe

TEXT = '中文 简繁體 😀 𠮷'


class NativePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='feiyu-native-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'workspace'
        self.root.mkdir()
        override = patch.object(session, 'DIR', str(Path(self.temporary.name) / 'sessions'))
        override.start()
        self.addCleanup(override.stop)

    def test_durable_atomic_replace_and_safe_read(self):
        target = Path(self.temporary.name) / 'snapshot.json'
        for value in (TEXT, TEXT * 10000):
            atomic_json(target, {'text': value})
            raw, _ = _read_safe(target, 1024 * 1024)
            self.assertEqual(json.loads(raw), {'text': value})

    def test_workspace_identity_is_stable_and_distinct(self):
        other = Path(self.temporary.name) / 'other'
        other.mkdir()
        identity = workspace_id(self.root)
        self.assertEqual(identity, workspace_id(self.root))
        self.assertNotEqual(identity, workspace_id(other))

    def test_writer_restore_unknown_never_replays(self):
        store = TaskStore(self.root, 'native')
        self.addCleanup(store.close)
        with self.assertRaises(PersistenceError):
            TaskStore(self.root, 'native')
        state = TaskState('native', 'task', workspace_id(self.root))
        state.revise(TEXT)
        record = dict(id='operation', call_id='call', name='write_file', source='native-test',
                      cwd=str(self.root), started=1.0, args={})
        store.prepare(state, record)
        store.close()
        restored = TaskStore(self.root, 'native')
        self.addCleanup(restored.close)
        loaded = restored.recover()
        self.assertEqual(loaded.requests[0]['text'], TEXT)
        self.assertEqual(loaded.operations[0]['state'], 'unknown')
        with self.assertRaises(PersistenceError):
            restored.prepare(loaded, dict(record, id='replay'))
        self.assertEqual(len(loaded.operations), 1)

    def test_cross_process_writer_and_crash_release(self):
        import subprocess
        import sys
        code = '''
import sys
from feiyu import session
from feiyu.taskstate import TaskStore
session.DIR = sys.argv[2]
s = TaskStore(sys.argv[1], 'native')
print('locked', flush=True)
sys.stdin.read()
'''
        child = subprocess.Popen([sys.executable, '-c', code, str(self.root), session.DIR],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, encoding='utf-8')
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            with self.assertRaises(PersistenceError):
                TaskStore(self.root, 'native')
            child.kill()
            child.communicate(timeout=10)
            with_store = TaskStore(self.root, 'native')
            with_store.close()
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=10)

    def test_stale_revision_blocks(self):
        from copy import deepcopy
        store = TaskStore(self.root, 'native')
        self.addCleanup(store.close)
        state = TaskState('native', 'task', workspace_id(self.root))
        store.save(state)
        stale = deepcopy(state)
        store.save(state)
        with self.assertRaises(PersistenceError):
            store.save(stale)
        self.assertTrue(store.blocked)

    def test_synthetic_agent_send_uses_native_storage(self):
        import os
        import subprocess
        import sys
        env = dict(os.environ)
        for key in ('HOME', 'USERPROFILE', 'XDG_STATE_HOME', 'XDG_CONFIG_HOME'):
            env[key] = str(Path(self.temporary.name) / key)
            Path(env[key]).mkdir()
        code = """
import contextlib, io, sys
from pathlib import Path
from feiyu.agent import Feiyu
from tests.fakes import FakeBackend
agent = Feiyu(Path(sys.argv[1]))
agent.backend = FakeBackend([('synthetic response', [])])
agent.name = 'synthetic'
try:
    with contextlib.redirect_stdout(io.StringIO()):
        agent.send('synthetic request')
    assert agent.task_state.requests[0]['text'] == 'synthetic request'
    assert agent.task_state.revision > 0
    assert agent.task_state.budget['attempts'] == 1
finally:
    if agent._task_store:
        agent._task_store.close()
"""
        done = subprocess.run([sys.executable, '-c', code, str(self.root)], env=env,
                              capture_output=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr.decode('utf-8', 'replace'))

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows native security')
    def test_windows_reparse_and_hardlink_refused(self):
        import os
        import subprocess
        target = Path(self.temporary.name) / 'target'
        target.mkdir()
        junction = Path(self.temporary.name) / 'junction'
        done = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(target)],
                              capture_output=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        try:
            with self.assertRaises((OSError, ValueError, PersistenceError)):
                workspace_id(junction)
            with self.assertRaises((OSError, ValueError, PersistenceError)):
                atomic_json(junction / 'data.json', {})
        finally:
            os.rmdir(junction)
        path = target / 'one.json'
        path.write_text('{}')
        os.link(path, target / 'two.json')
        with self.assertRaises((OSError, ValueError)):
            _read_safe(path, 100)
        with self.assertRaises(PersistenceError):
            atomic_json(path, {})
