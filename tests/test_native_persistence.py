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
        from feiyu.files import private_dir
        parent = Path(self.temporary.name) / 'private'
        private_dir(parent)
        target = parent / 'snapshot.json'
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
    if sys.platform == 'win32':
        from tests.fakes import call
        from feiyu.providers import ToolCall
        agent.mode = 'auto'
        agent.backend.script = [('', [call('bg', 'bash', command='echo forbidden', background=True),
                                     ToolCall(id='lsp', name='symbol', input=dict(action='definition', path='x.py', name='x'))]),
                                ('continued after refused tools', [])]
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('exercise unsupported tools')
        assert not agent._task_store.blocked
        results = [m['content'] for m in agent.backend.messages if m['role'] == 'tool']
        assert len(results) == 2, results
        assert all('Windows' in str(r) for r in results), results
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
        from feiyu.files import private_dir
        private_dir(target)
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

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows native failure windows')
    def test_windows_failure_and_crash_windows(self):
        import subprocess
        import sys
        from feiyu.files import private_dir
        parent = Path(self.temporary.name) / 'private'
        private_dir(parent)
        path = parent / 'snapshot.json'
        # Child runs real NTFS writes; only the precise failure/crash boundary is injected.
        code = '''
import os, sys
from unittest.mock import patch
from feiyu import windows_storage as w
from feiyu.taskstate import atomic_json, PersistenceError
stage, mode, path = sys.argv[1:]
def stop(*args, **kwargs):
    if mode == 'crash': os._exit(73)
    # Ask the native API to flush an invalid handle: real Win32 error, not ignored.
    w.flush(-1)
if stage == 'serialize':
    target = 'json.dump'
elif stage == 'data-flush':
    target = 'os.fsync'
elif stage == 'before-replace':
    target = 'feiyu.windows_storage.replace'
else:
    target = 'feiyu.windows_storage.flush'
# Preserve original flush to avoid recursion when testing its failure.
original = w.flush
def at_flush(*args, **kwargs):
    if mode == 'crash': os._exit(73)
    original(-1)
try:
    with patch(target, side_effect=at_flush if stage == 'after-replace' else stop):
        atomic_json(path, {'value':'new'})
except PersistenceError:
    sys.exit(74)
raise AssertionError('write unexpectedly acknowledged')
'''
        for stage in ('serialize', 'data-flush', 'before-replace', 'after-replace'):
            for mode in ('error', 'crash'):
                with self.subTest(stage=stage, mode=mode):
                    atomic_json(path, {'value': 'old'})
                    done = subprocess.run([sys.executable, '-c', code, stage, mode, str(path)],
                                          capture_output=True, timeout=20)
                    self.assertEqual(done.returncode, 73 if mode == 'crash' else 74, done.stderr)
                    observed = json.loads(_read_safe(path, 1024)[0])
                    self.assertEqual(observed['value'], 'new' if stage == 'after-replace' else 'old')

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows ACL/identity')
    def test_windows_owner_migration_acl_and_pinned_directory(self):
        import ctypes as C
        from ctypes import wintypes as W
        import os
        from feiyu import windows_storage as w
        # mkdir uses the real token default owner; private_dir must tighten it by handle.
        parent = Path(self.temporary.name) / 'default-owner'
        parent.mkdir()
        w.private_dir(parent)
        with w.guard(parent):
            h = w.open_handle(parent, 0x20080, 1)
            self.addCleanup(w.close, h)
            sd = W.LPVOID()
            owner = W.LPVOID()
            result = w.bind(w.A, 'GetSecurityInfo', [W.HANDLE, C.c_int, W.DWORD,
                C.POINTER(W.LPVOID), W.LPVOID, W.LPVOID, W.LPVOID, C.POINTER(W.LPVOID)], W.DWORD)(
                    h, 1, 5, C.byref(owner), None, None, None, C.byref(sd))
            self.assertEqual(result, 0)
            text = W.LPWSTR()
            try:
                w.checked(w.bind(w.A, 'ConvertSecurityDescriptorToStringSecurityDescriptorW',
                    [W.LPVOID, W.DWORD, W.DWORD, C.POINTER(W.LPWSTR), W.LPVOID])(
                        sd, 1, 5, C.byref(text), None))
                value = text.value
                sid = value.split('O:')[1].split('D:')[0]
                self.assertIn('D:P', value)
                self.assertEqual(value.count('(A;'), 1, value)
                self.assertIn(';;;' + sid + ')', value)
            finally:
                w.free(text)
                w.free(sd)
        store = TaskStore(self.root, 'native')
        self.addCleanup(store.close)
        with self.assertRaises(OSError):
            os.rename(store.directory, store.directory.with_name('substituted'))
        with self.assertRaises(OSError):
            os.rename(store.directory/'writer.lock', store.directory/'substituted.lock')

    def test_crashed_model_admission_never_refunds_budget(self):
        import subprocess
        import sys
        from feiyu.runcontrol import RunControl, RunStopped
        code = '''
import os,sys
from types import SimpleNamespace
from feiyu import session
from feiyu.taskstate import TaskStore, TaskState, workspace_id
from feiyu.runcontrol import RunControl
session.DIR=sys.argv[2]
s=TaskStore(sys.argv[1], 'native')
t=TaskState('native','task',workspace_id(sys.argv[1]))
t.revise('synthetic admission')
c=RunControl(s,t,cost_limit=1)
t.budget.update(cost=.25,known_cost=.25)
with c.attempt(SimpleNamespace(tokens_total=0,cost=0,usage_reports=0,model='synthetic')):
    os._exit(73)
'''
        done = subprocess.run([sys.executable, '-c', code, str(self.root), session.DIR],
                              capture_output=True, timeout=20)
        self.assertEqual(done.returncode, 73, done.stderr)
        store = TaskStore(self.root, 'native')
        self.addCleanup(store.close)
        state = store.recover()
        control = RunControl(store, state, cost_limit=2)
        self.assertEqual(state.budget['attempts'], 1)
        self.assertEqual(state.budget['pending_attempts'], 1)
        self.assertEqual(state.budget['known_cost'], .25)
        self.assertEqual(state.budget['cost_limit'], 1)
        self.assertIsNone(state.budget['cost'])
        with self.assertRaises(RunStopped):
            control.check()

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows critical flush failure')
    def test_native_flush_failure_blocks_store_and_preserves_unknown(self):
        from feiyu import windows_storage as w
        store = TaskStore(self.root, 'native')
        self.addCleanup(store.close)
        state = TaskState('native', 'task', workspace_id(self.root))
        store.prepare(state, dict(id='operation', call_id='call', name='write_file',
            source='native-test', cwd=str(self.root), started=1.0, args={}))
        original = w.flush
        with patch.object(w, 'flush', side_effect=lambda h: original(-1)):
            with self.assertRaises(PersistenceError):
                store.save(state)
        self.assertTrue(store.blocked)
        with self.assertRaises(PersistenceError):
            store.save(state)
        store.close()
        restored = TaskStore(self.root, 'native')
        self.addCleanup(restored.close)
        self.assertEqual(restored.recover().operations[0]['state'], 'unknown')
