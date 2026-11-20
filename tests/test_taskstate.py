"""Critical persistence faults, process crash windows and task lifecycle."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from feiyu import session
from feiyu.taskstate import TaskState, TaskStore, PersistenceError, workspace_id


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'workspace'
        self.root.mkdir()
        self.patch = patch.object(session, 'DIR', str(Path(self.tmp.name) / 'sessions'))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.store = TaskStore(self.root, 'one')
        self.addCleanup(self.store.close)
        self.state = TaskState('one', 'task', workspace_id(self.root))
        self.state.revise('原请求\n' + '完整要求' * 10000)

    def test_full_request_revision_and_checksum(self):
        self.state.revise('修订')
        self.state.acceptance = [{'text': '必须验收', 'status': 'pending'}]
        self.store.save(self.state)
        loaded = self.store.load('task')
        self.assertEqual(loaded.requests, self.state.requests)
        self.assertNotEqual(loaded.requests[0]['id'], loaded.requests[1]['id'])
        data = json.loads(self.store.path('task').read_text())
        data['payload']['requests'][0]['text'] = 'tampered'
        self.store.path('task').write_text(json.dumps(data))
        original = self.store.path('task').read_bytes()
        with self.assertRaises(PersistenceError):
            self.store.load('task')
        self.assertEqual(original, self.store.path('task').read_bytes())

    def test_single_writer_and_multiple_sessions(self):
        with self.assertRaises(PersistenceError):
            TaskStore(self.root, 'one')
        other = TaskStore(self.root, 'two')
        self.addCleanup(other.close)
        other_state = TaskState('two', 'task', workspace_id(self.root))
        other_state.revise('another')
        self.store.save(self.state)
        other.save(other_state)
        self.assertNotEqual(other.load('task').requests, self.store.load('task').requests)

    def test_future_sidecar_preserved(self):
        self.store.save(self.state)
        path = self.store.path('task')
        data = json.loads(path.read_text())
        data['schema_version'] = 900
        path.write_text(json.dumps(data))
        original = path.read_bytes()
        with self.assertRaises(PersistenceError):
            self.store.load('task')
        self.assertEqual(path.read_bytes(), original)

    def executor(self):
        from feiyu.tools import Toolbox
        box = Toolbox(self.root)
        self.addCleanup(box.lsp.close)
        box.execution.durable = (self.store, self.state)
        return box.execution

    def test_prepare_failure_starts_no_effect(self):
        executor = self.executor()
        marker = self.root / 'marker'
        with patch('feiyu.taskstate.atomic_json', side_effect=PersistenceError('full')):
            with self.assertRaises(PersistenceError):
                executor.invoke('write_file', {}, lambda: marker.write_text('written'))
        self.assertFalse(marker.exists())
        with self.assertRaises(PersistenceError):
            executor.invoke('write_file', {}, lambda: marker.write_text('retry'))
        self.assertFalse(marker.exists())

    def test_finished_failure_unknown_no_replay(self):
        executor = self.executor()
        marker = self.root / 'marker'
        original = self.store.save
        def save(state):
            if state.operations and state.operations[-1]['state'] != 'prepared':
                raise PersistenceError('full after effect')
            original(state)
        with patch.object(self.store, 'save', side_effect=save):
            with self.assertRaises(PersistenceError):
                executor.invoke('write_file', {}, lambda: marker.write_text('written'))
        self.assertEqual(marker.read_text(), 'written')
        self.assertEqual(self.state.operations[-1]['state'], 'unknown')
        with self.assertRaises(PersistenceError):
            executor.invoke('write_file', {}, lambda: marker.write_text('replayed'))
        self.assertEqual(marker.read_text(), 'written')
        self.assertNotIn('args', self.state.operations[-1])

    def test_crash_windows_in_real_process(self):
        # Isolated child state and a hard timeout; no inherited HOME/config/secrets.
        script = '''
import os, sys
from pathlib import Path
from feiyu import session
from feiyu.taskstate import TaskStore, TaskState, workspace_id
from feiyu.tools import Toolbox
root = Path(sys.argv[1]); session.DIR = sys.argv[2]
store = TaskStore(root, 'crash')
state = TaskState('crash', 'task', workspace_id(root))
box = Toolbox(root); box.execution.durable = (store, state)
if sys.argv[3] == 'before':
    original = store.prepare
    def prepare(*args):
        original(*args); os._exit(71)
    store.prepare = prepare
else:
    store.finish = lambda *args: os._exit(72)
box.execution.invoke('write_file', {}, lambda: (root / 'marker').write_text('effect'))
'''
        for phase in ('before', 'after'):
            with self.subTest(phase=phase):
                child_root = Path(self.tmp.name) / phase
                child_root.mkdir()
                storage = str(child_root / 'sessions')
                env = {'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(Path.cwd())}
                for name in ('HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                    directory = child_root / name
                    directory.mkdir()
                    env[name] = str(directory)
                result = subprocess.run([sys.executable, '-c', script, str(child_root), storage, phase],
                                        env=env, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 71 if phase == 'before' else 72, result.stderr)
                self.assertEqual((child_root / 'marker').exists(), phase == 'after')
                with patch.object(session, 'DIR', storage):
                    recovered = TaskStore(child_root, 'crash')
                    try:
                        state = recovered.load('task')
                        self.assertEqual(state.operations[0]['state'], 'unknown')
                        with self.assertRaises(PersistenceError):
                            recovered.prepare(state, {})
                    finally:
                        recovered.close()

    def test_agent_continues_unfinished_task_and_explicit_new(self):
        from feiyu.agent import Feiyu
        from feiyu.__main__ import _task
        from tests.fakes import FakeBackend
        agent = Feiyu(self.root)
        agent.backend = FakeBackend([('done claim', []), ('another claim', []), ('new task', [])])
        self.addCleanup(lambda: agent._task_store.close() if agent._task_store else None)
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('request')
            tid = agent.task_id
            agent.task_state.acceptance = [{'text': 'still unverified'}]
            agent.send('revision')
            self.assertEqual(agent.task_id, tid)
            self.assertEqual(len(agent.task_state.requests), 2)
            self.assertEqual(agent.task_state.result, 'unfinished')
            self.assertEqual(agent.task_state.acceptance, [{'text': 'still unverified', 'status': 'unverified'}])
            self.assertIn('不能完成', _task(agent, 'complete'))
            agent.task_state.acceptance = []
            _task(agent, 'complete')
            agent.send('new request')
            self.assertNotEqual(agent.task_id, tid)
            self.assertEqual(agent._task_store.load(tid).result, 'completed')

    def test_legacy_save_never_overwrites_original(self):
        from tests.test_session import Agentish
        from tests.fakes import FakeBackend
        Path(session.DIR).mkdir(exist_ok=True)
        legacy = Path(session._legacy_path(self.root))
        data = {'model': 'fake', 'messages': [{'role': 'user', 'content': 'original'}]}
        legacy.write_text(json.dumps(data))
        original = legacy.read_bytes()
        backend = FakeBackend([])
        backend.messages.append({'role': 'user', 'content': 'new'})
        agent = Agentish(backend)
        session.save(self.root, agent, session.LEGACY)
        self.assertEqual(legacy.read_bytes(), original)
        self.assertNotEqual(agent.session_id, session.LEGACY)
        self.assertEqual(session.load(self.root, session.LEGACY)['messages'], data['messages'])

class RecoveryClosureTests(unittest.TestCase):
    setUp = TaskTests.setUp
    executor = TaskTests.executor
    def test_stale_object_and_unloaded_writer_cannot_overwrite(self):
        self.store.save(self.state)
        old = self.store.load('task')
        self.state.revise('new fact')
        self.store.save(self.state)
        with self.assertRaises(PersistenceError):
            self.store.save(old)
        self.assertEqual(len(self.store.load('task').requests), 2)
        self.store.close()
        other = TaskStore(self.root, 'one')
        try:
            with self.assertRaises(PersistenceError):
                other.save(self.state)
        finally:
            other.close()

    def test_inner_schema_and_legacy_identity(self):
        from dataclasses import asdict
        from feiyu.taskstate import legacy_workspace_id
        self.state.workspace_id = legacy_workspace_id(self.root)
        self.store.save(self.state)
        self.assertEqual(self.store.load('task').workspace_id, self.state.workspace_id)
        for key, value in [('goals', [4]), ('verification_refs', [None]), ('run_state', 'forged')]:
            data = asdict(self.state)
            data[key] = value
            with self.subTest(key=key), self.assertRaises(PersistenceError):
                TaskState.read(data)

    def test_git_common_worktree_identity_and_unsafe_link(self):
        from feiyu.taskstate import workspace_identity
        git = self.root / '.git'
        git.mkdir()
        first = workspace_id(self.root)
        common = self.root / 'common'
        common.mkdir()
        (git / 'commondir').write_text('../common')
        self.assertNotEqual(first, workspace_id(self.root))
        self.assertEqual(workspace_identity(self.root)['common']['path'], str(common))
        (git / 'commondir').unlink()
        os.mkfifo(git / 'commondir')
        with self.assertRaises(PersistenceError):
            workspace_id(self.root)

    def test_diagnostics_do_not_change_facts_and_unexpected_exception_unknown(self):
        executor = self.executor()
        executor.emit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('diagnostic'))
        self.assertEqual(executor.invoke('write_file', {}, lambda: 42), 42)
        self.assertEqual(self.state.operations[-1]['state'], 'completed')
        with self.assertRaises(RuntimeError):
            executor.invoke('write_file', {}, lambda: (_ for _ in ()).throw(RuntimeError('after effect')))
        self.assertEqual(self.state.operations[-1]['state'], 'unknown')

    def test_raw_handler_critical_failure_is_not_tool_result(self):
        executor = self.executor()
        with patch.object(executor.box, '_tool_write_file', side_effect=PersistenceError('critical')):
            with self.assertRaises(PersistenceError):
                executor.run('write_file', {'path': 'a', 'content': 'x'})
        self.assertEqual(self.state.operations[-1]['state'], 'unknown')
        self.assertIn('authorization', self.state.operations[-1])

    def test_unknown_reconcile_change_and_explicit_acknowledgement(self):
        executor = self.executor()
        target = self.root / 'a'
        target.write_text('before')
        with self.assertRaises(RuntimeError):
            executor.invoke('write_file', {'path': 'a'}, lambda: (_ for _ in ()).throw(RuntimeError()))
        op = self.state.operations[-1]
        target.write_text('after')
        self.store.reconcile(self.state)
        self.assertNotEqual(op['before']['local'], op['observation']['local'])
        self.assertEqual(op['state'], 'unknown')
        target.unlink()
        self.store.reconcile(self.state)
        self.assertEqual(op['state'], 'unknown')
        self.store.resolve(self.state, op['id'], '用户已向服务方核对；接受剩余不确定性，不重跑')
        self.assertEqual(op['state'], 'resolved')
        self.assertIn('no replay authorization', op['resolution']['conclusion'])
        self.assertFalse(op['authorization']['reusable'])

    def make_agent(self):
        from feiyu.agent import Feiyu
        from tests.fakes import FakeBackend
        agent = Feiyu(self.root)
        agent.backend = FakeBackend([('model says passed', [])])
        agent.name = 'fake'
        self.addCleanup(agent.toolbox.lsp.close)
        self.addCleanup(lambda: agent._task_store.close() if agent._task_store else None)
        return agent

    def test_cli_control_requirement_binding_rejects_forgery(self):
        from feiyu.__main__ import _task
        agent = self.make_agent()
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('full original request')
        rid = agent.task_state.requests[0]['id']
        row = json.loads(_task(agent, json.dumps(dict(action='add', kind='acceptance', text='test outcome', request_id=rid))))
        self.assertEqual(row['request_id'], rid)
        self.assertIn('full original request', agent.backend.system)
        self.assertIn(row['id'], agent.backend.system)
        with self.assertRaises(PersistenceError):
            agent.task_control(dict(action='bind', acceptance_id=row['id'], verification_id='invented'))
        self.assertIn('不能完成', _task(agent, 'complete'))
        with self.assertRaises(PersistenceError):
            agent.task_control(dict(action='add', kind='constraints', text='x', request_id='invented'))

    def test_cli_cancel_final_session_and_unknown_reset_blocked(self):
        from feiyu.__main__ import _run_turn
        agent = self.make_agent()
        with patch.object(agent, '_send', side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            # Preserve a real user message as a provider would before cancellation.
            agent.backend.messages.append({'role': 'user', 'content': 'cancel'})
            self.assertEqual(_run_turn(agent, 'cancel'), 130)
        saved = session.load(self.root, agent.session_id)
        self.assertEqual(saved['task_id'], agent.task_id)
        self.assertEqual(agent._task_store.load(agent.task_id).run_state, 'interrupted')
        from feiyu.runcontrol import RunStopped
        with self.assertRaises(RunStopped):
            agent.toolbox.execution.invoke('write_file', {}, lambda: self.fail('cancel must prevent execution'))
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('explicit resume')
        with self.assertRaises(RuntimeError):
            agent.toolbox.execution.invoke('write_file', {}, lambda: (_ for _ in ()).throw(RuntimeError()))
        for action in (agent.reset, agent.new_task):
            with self.assertRaises(PersistenceError):
                action()
        op = agent.task_state.operations[-1]
        with self.assertRaises(PersistenceError):
            agent.task_control(dict(action='resolve', operation_id=op['id'], acknowledgement='claim', state='completed'))
        agent.task_control(dict(action='resolve', operation_id=op['id'], acknowledgement='用户人工核对，接受不确定性'))
        agent.reset()

    def test_serve_exception_final_checkpoint(self):
        from feiyu.serve import Server, Protocol
        agent = self.make_agent()
        output = io.StringIO()
        server = Server(agent, self.root, None, Protocol(output))
        with patch.object(agent.backend, 'run_turn', side_effect=RuntimeError('provider failure')), contextlib.redirect_stdout(io.StringIO()):
            server.handle_prompt('retained on exception')
        self.assertFalse(server.busy)
        self.assertEqual(agent._task_store.load(agent.task_id).run_state, 'blocked')
        self.assertEqual(session.load(self.root, agent.session_id)['task_id'], agent.task_id)

    def test_real_verification_binding_rechecks_files_and_logs(self):
        from feiyu import hooks
        agent = self.make_agent()
        agent.mode = 'auto'
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('verify requirement')
        agent.verify = 'printf verified'
        row = agent.task_control(dict(action='add', kind='acceptance', text='command succeeds',
                                      request_id=agent.task_state.requests[0]['id']))
        with contextlib.redirect_stdout(io.StringIO()):
            agent._run_verification(hooks.Hook('PreWrite', {'command': agent.verify}, 'verify:'), {}, 'post_change')
        record = agent.verifications.records[-1]
        result = agent.task_control(dict(action='bind', acceptance_id=row['id'], verification_id=record['verification_id']))
        self.assertEqual(result['acceptance'][0]['status'], 'verified')
        Path(record['log']).write_text('forged log')
        self.assertEqual(agent.task_control({'action': 'check'})['acceptance'][0]['status'], 'unverified')

    def test_restore_reconciles_unknown_and_recovers_full_facts(self):
        agent = self.make_agent()
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('long original ' + '完整' * 5000)
        row = agent.task_control(dict(action='add', kind='constraints', text='keep source',
                                      request_id=agent.task_state.requests[0]['id']))
        with self.assertRaises(RuntimeError):
            agent.toolbox.execution.invoke('write_file', {'path': 'changed'}, lambda: (_ for _ in ()).throw(RuntimeError()))
        session.save(self.root, agent, agent.session_id)
        saved = session.load(self.root, agent.session_id)
        agent._task_store.close()
        (self.root / 'changed').write_text('external change')
        resumed = self.make_agent()
        with patch.object(resumed, 'use_model', return_value=True):
            self.assertTrue(resumed.restore(saved))
        self.assertIn(row['id'], resumed.backend.system)
        self.assertIn('完整' * 5000, resumed.backend.system)
        self.assertEqual(resumed.task_state.operations[-1]['state'], 'unknown')
        self.assertIn('observation', resumed.task_state.operations[-1])
        with self.assertRaises(PersistenceError):
            resumed.new_task()
        self.assertEqual(resumed._command_approvals, set())

    def test_new_task_hook_binds_new_journal(self):
        from feiyu import hooks
        agent = self.make_agent()
        agent.mode = 'auto'
        with contextlib.redirect_stdout(io.StringIO()):
            agent.send('initial')
        old = agent.task_id
        agent.new_task()
        self.assertIs(agent.toolbox.execution.durable[1], agent.task_state)
        self.assertEqual(agent._task_store.recover().task_id, agent.task_id)
        agent.verify = 'true'
        agent._execute_hook(hooks.Hook('PreWrite', {'command': 'true'}, 'verify:'), {})
        self.assertNotEqual(agent.task_id, old)
        self.assertEqual(len(agent._task_store.load(agent.task_id).operations), 1)
        self.assertEqual(len(agent._task_store.load(old).operations), 0)

    def test_local_path_rejected_by_schema_and_observer(self):
        from dataclasses import asdict
        op = dict(id='op', name='write_file', source='model', cwd=str(self.root),
                  parameter_digest='hash', started=1.0, sequence=1, state='unknown')
        for value in ('/etc/passwd', '../outside', 'a/../../outside', 'a/./b', '', 42, 'C:\\secret'):
            bad = dict(op, local_path=value)
            data = asdict(self.state)
            data['operations'] = [bad]
            with self.assertRaises(PersistenceError):
                TaskState.read(data)
            with patch('feiyu.verification._read_safe') as read:
                with self.assertRaises(ValueError):
                    self.store.observe(bad)
                read.assert_not_called()

    def test_finish_cleans_every_resource_after_checkpoint_failure(self):
        from unittest.mock import Mock
        from feiyu.__main__ import _finish
        agent, tracer = Mock(), Mock()
        failure = PersistenceError('checkpoint failed')
        agent._task_checkpoint.side_effect = failure
        agent.toolbox.lsp.close.side_effect = OSError('also failed')
        with self.assertRaises(PersistenceError) as caught:
            _finish(agent, tracer, 1)
        self.assertIs(caught.exception, failure)
        for cleanup in (agent.toolbox.lsp.close, agent.toolbox.mcp.close,
                        agent.toolbox.shell_reset, agent.toolbox.jobs.kill_all):
            cleanup.assert_called_once()


class ActivePointerTests(unittest.TestCase):
    setUp = TaskTests.setUp
    make_agent = RecoveryClosureTests.make_agent

    def test_pointer_failure_prevents_hook_even_without_backend(self):
        from feiyu import hooks
        import feiyu.taskstate as storage
        agent = self.make_agent()
        agent.backend = None
        agent.mode = 'auto'
        agent.verify = 'printf effect > marker'
        real = storage.atomic_json
        def write(path, data):
            if Path(path).name == 'active.json':
                raise PersistenceError('injected active pointer failure')
            return real(path, data)
        with patch.object(storage, 'atomic_json', side_effect=write), patch('feiyu.hooks.run') as run:
            with self.assertRaises(PersistenceError):
                agent._execute_hook(hooks.Hook('PreWrite', {'command': agent.verify}, 'verify:'), {})
        run.assert_not_called()
        self.assertFalse((self.root / 'marker').exists())
        # Saved empty sidecar is still discoverable, despite no pointer/messages.
        self.assertEqual(session.load(self.root, agent.session_id)['journal_only'], True)

    def test_pointer_corruption_future_missing_and_escape_preserve_originals(self):
        self.store.save(self.state)
        self.store.activate(self.state)
        path = self.store.directory / 'active.json'
        original = path.read_bytes()
        cases = [b'broken', original.replace(b'"schema_version": 1', b'"schema_version": 999')]
        import hashlib
        for tid in ('../outside', 'missing'):
            data = json.loads(original)
            data['payload']['task_id'] = tid
            data['sha256'] = hashlib.sha256(json.dumps(data['payload'], sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            cases.append(json.dumps(data).encode())
        for raw in cases:
            path.write_bytes(raw)
            before = self.store.path('task').read_bytes()
            with self.assertRaises(PersistenceError):
                self.store.recover('task')
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(self.store.path('task').read_bytes(), before)
            self.store.blocked = False
        path.unlink()
        self.assertEqual(self.store.recover('task').task_id, 'task')

    def test_multiple_pending_selection_does_not_bypass_guard_or_rewrite_history(self):
        agent = self.make_agent()
        agent._ensure_task_storage()
        store = agent._task_store
        for tid in ('a', 'b'):
            state = TaskState(agent.session_id, tid, workspace_id(self.root))
            store.prepare(state, dict(id=tid, call_id=tid, name='bash', source='hook', cwd=str(self.root), started=1, args={}))
            # Synthetic pre-fix history with several independent prepared journals.
            store._states = {}
        original = {p: p.read_bytes() for p in store.directory.glob('*.task.json')}
        store.close()
        resumed = self.make_agent()
        self.assertTrue(resumed.restore(session.load(self.root, agent.session_id)))
        self.assertEqual(set(resumed.task_control({'action': 'pending'})['pending']), {'a', 'b'})
        for path, raw in original.items():
            if path.name in ('a.task.json', 'b.task.json') and path.name != resumed.task_id + '.task.json':
                self.assertEqual(path.read_bytes(), raw)
        for tid in ('a', 'b'):
            resumed.task_control(dict(action='select', task_id=tid))
            with self.assertRaises(PersistenceError):
                resumed.new_task()
            with self.assertRaises(PersistenceError):
                resumed._guard_task_switch()
            from feiyu.__main__ import _task
            self.assertIn('未知', _task(resumed, 'complete'))
            resumed.task_control(dict(action='resolve', operation_id=tid, acknowledgement='人工接受未知；未证明执行'))
            if tid == 'a':
                with self.assertRaises(PersistenceError):
                    resumed._guard_task_switch()
        resumed._guard_task_switch()
        self.assertEqual(resumed.task_state.operations[0]['state'], 'resolved')
        self.assertIn('no replay authorization', resumed.task_state.operations[0]['resolution']['conclusion'])
        # The unrelated original active task was the only automatic checkpoint.
        for path, raw in original.items():
            if path.stem.split('.')[0] in ('a', 'b'):
                self.assertNotEqual(path.read_bytes(), raw)  # only explicit user resolutions

    def test_isolated_hook_crashes_restart_via_session_and_serve(self):
        script = r"""
import contextlib, io, json, os, sys
from pathlib import Path
from unittest.mock import patch
from feiyu.agent import Feiyu
from feiyu import session, hooks
from feiyu.taskstate import PersistenceError
from tests.fakes import FakeBackend
root = Path(sys.argv[1]); phase = sys.argv[2]
agent = Feiyu(root)
if phase in ('old', 'empty'):
    agent.mode = 'auto'
    if phase == 'old':
        agent.backend = FakeBackend([('done', [])]); agent.name = 'fake'
        with contextlib.redirect_stdout(io.StringIO()): agent.send('old request')
        old = agent.task_id
        from feiyu.__main__ import _task
        _task(agent, 'new')
    else:
        old = None  # no backend, model messages or session JSON
    agent.verify = 'printf effect >> marker'
    agent._ensure_task_storage()
    (root / 'ids').write_text(json.dumps(dict(sid=agent.session_id, tid=agent.task_id, old=old)))
    agent._task_store.finish = lambda *args: os._exit(73)
    agent._execute_hook(hooks.Hook('PreWrite', {'command': agent.verify}, 'verify:'), {})
    raise AssertionError('did not crash')
ids = json.loads((root / 'ids').read_text())
assert any(r['id'] == ids['sid'] for r in session.listing(root))
saved = session.load(root)  # real default resume discovery
assert saved['session_id'] == ids['sid']
if ids['old']:
    assert saved['task_ref'] == ids['old']  # deliberately stale session
agent.backend = FakeBackend([])
agent.name = 'fake'
from feiyu.serve import Server, Protocol
server = Server(agent, root, None, Protocol(io.StringIO()))
with patch.object(agent, 'use_model', return_value=True):
    server.open_session(ids['sid'])
assert agent.task_id == ids['tid']
assert agent.task_state.operations[0]['state'] == 'unknown'
try: agent.new_task()
except PersistenceError: pass
else: raise AssertionError('switch bypassed unknown')
assert (root / 'marker').read_text() == 'effect'
assert agent.task_control({'action':'pending'})['pending'] == [ids['tid']]
print('recovered unknown; no replay; switch blocked')
"""
        for phase in ('old', 'empty'):
            root = Path(self.tmp.name) / phase
            root.mkdir()
            env = {'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(Path.cwd()), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
            for key in ('HOME', 'XDG_STATE_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                directory = root.parent / (phase + '-' + key)
                directory.mkdir()
                env[key] = str(directory)
            for mode, code in ((phase, 73), ('restart', 0)):
                result = subprocess.run([sys.executable, '-c', script, str(root), mode], env=env, capture_output=True, timeout=25)
                self.assertEqual(result.returncode, code, result.stderr.decode())

    def test_recovery_validates_all_journals_before_rewriting_and_missing_pointer_blocks(self):
        agent = self.make_agent()
        agent._ensure_task_storage()
        store = agent._task_store
        old = agent.task_id
        other = TaskState(agent.session_id, 'orphan', workspace_id(self.root))
        store.prepare(other, dict(id='effect', call_id='call', name='bash', source='hook', cwd=str(self.root), started=1, args={}))
        (store.directory / 'active.json').unlink()
        selected = store.recover(old)
        self.assertEqual(selected.task_id, old)
        self.assertEqual(store.pending(), ['orphan'])
        with self.assertRaises(PersistenceError):
            store.prepare(selected, {})
        # Corruption in any same-session task must protect every original.
        store.path('orphan').write_text('broken')
        original = {p: p.read_bytes() for p in store.directory.glob('*.task.json')}
        store.close()
        resumed = self.make_agent()
        with self.assertRaises(PersistenceError):
            resumed.restore(session.load(self.root, agent.session_id))
        with self.assertRaises(PersistenceError):
            resumed._guard_task_switch()
        self.assertEqual(original, {p: p.read_bytes() for p in store.directory.glob('*.task.json')})

    def test_session_directory_symlink_is_not_followed(self):
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        link = Path(session.folder(self.root)) / 'escape'
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(PersistenceError):
            TaskStore(self.root, 'escape')
        self.assertEqual(list(outside.iterdir()), [])
