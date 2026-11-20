"""Task accounting through real model entry points, with no paid requests."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from feiyu import session
from feiyu.agent import Feiyu
from feiyu.runcontrol import RunControl, RunStopped
from feiyu.taskstate import TaskState, TaskStore, workspace_id, PersistenceError
from tests.fakes import FakeBackend


class ParentControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'workspace'
        self.root.mkdir()
        p = patch.object(session, 'DIR', str(Path(self.tmp.name) / 'sessions'))
        p.start()
        self.addCleanup(p.stop)
        self.agent = Feiyu(self.root)
        self.agent.backend = FakeBackend([])
        self.agent.name = 'fake'
        self.addCleanup(lambda: self.agent._task_store and self.agent._task_store.close())
        self.addCleanup(self.agent.toolbox.lsp.close)

    def charge(self, backend, cost=.3):
        backend.tokens_total += 10
        backend.cost += cost
        backend.usage_reports += 1

    def test_shared_main_helper_compact_reviewer_and_failed_attempt(self):
        a = self.agent
        a.budget = 1.0
        # The session already spent money on a different task.
        a.backend.cost = 99
        side, judge = FakeBackend([]), FakeBackend([])
        def main(**kw):
            self.charge(a.backend)
            return SimpleNamespace(text='done', tool_calls=[], truncated=False)
        def helper(*args, **kw):
            self.charge(side)
            return 'summary'
        def review(*args, **kw):
            self.charge(judge)
            raise RuntimeError('failed after reported usage')
        with patch.object(a.backend, 'run_turn', side_effect=main), contextlib.redirect_stdout(io.StringIO()):
            a.send('request')
        with patch.object(a, '_side_backend', return_value=side), patch.object(side, 'ask', side_effect=helper):
            self.assertEqual(a._ask_model('page'), 'summary')
            self.assertEqual(a.compact(), 'summary')
        with patch.object(a, 'changes', return_value='diff'), patch('feiyu.agent.keys.load', return_value={'fake': {}}), patch('feiyu.agent.build_backend', return_value=judge), patch.object(judge, 'ask', side_effect=review):
            self.assertIn('failed after', a.review('request'))
        self.assertAlmostEqual(a.task_state.budget['cost'], 1.2)
        self.assertEqual(a.task_state.budget['attempts'], 4)
        self.assertEqual(a.task_state.budget['tokens'], 40)
        with self.assertRaises(RunStopped):
            a._ask_model('blocked')
        self.assertGreater(a.cost, 99)

    def test_missing_usage_is_unknown_and_blocks_finite_budget(self):
        a = self.agent
        a.budget = 1
        with contextlib.redirect_stdout(io.StringIO()):
            a.send('first')
            a.send('second')
        self.assertEqual(a.task_state.budget['attempts'], 1)
        self.assertEqual(a.task_state.budget['unknown_attempts'], 1)
        self.assertEqual(a.task_state.run_state, 'budget_stopped')
        self.assertEqual(a.task_state.result, 'unfinished')

    def test_deadline_and_allowance_survive_new_control(self):
        a = self.agent
        a.budget, a.time_budget = 1, 60
        a._ensure_task_storage()
        c = a._control()
        with c.attempt(a.backend):
            self.charge(a.backend, .6)
        deadline = a.task_state.budget['deadline']
        loaded = a._task_store.load(a.task_id)
        restored = RunControl(a._task_store, loaded, cost_limit=10, time_limit=600)
        self.assertAlmostEqual(loaded.budget['cost'], .6)
        self.assertEqual(loaded.budget['cost_limit'], 1)
        self.assertEqual(loaded.budget['deadline'], deadline)
        with patch('feiyu.runcontrol.time.time', return_value=deadline + 1):
            with self.assertRaises(RunStopped):
                restored.wait(.1)
        self.assertEqual(loaded.run_state, 'deadline_stopped')

    def test_cancel_blocks_helper_reviewer_and_executor(self):
        a = self.agent
        a._ensure_task_storage()
        a._control()
        a.cancel()
        with self.assertRaises(RunStopped):
            a._ask_model('page')
        with patch.object(a, 'changes', return_value='diff'), patch('feiyu.agent.keys.load', return_value={'fake': {}}), patch('feiyu.agent.build_backend', return_value=FakeBackend([])):
            with self.assertRaises(RunStopped):
                a.review('request')
        with self.assertRaises(RunStopped):
            a.toolbox.execution.invoke('write_file', {}, lambda: self.fail('must not execute'))

    def test_critical_attempt_write_failure_prevents_request(self):
        a = self.agent
        a._ensure_task_storage()
        a._control()
        with patch.object(a._task_store, 'save', side_effect=PersistenceError('disk full')), patch.object(a.backend, 'ask') as request:
            with self.assertRaises(PersistenceError):
                a._ask_model('request')
        request.assert_not_called()

    def test_crash_pending_usage_is_not_reset_on_restart(self):
        # Separate processes with fresh HOME/XDG and a hard timeout each.
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONPATH': os.getcwd()}
        for key in ('HOME', 'XDG_STATE_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
            path = Path(self.tmp.name) / key
            path.mkdir()
            env[key] = str(path)
        source = '''
import os, sys
from pathlib import Path
from types import SimpleNamespace
from feiyu.taskstate import TaskStore, TaskState, workspace_id
from feiyu.runcontrol import RunControl, RunStopped
root=Path(sys.argv[1]); store=TaskStore(root,'session')
if sys.argv[2]=='crash':
 state=TaskState('session','task',workspace_id(root)); state.revise('request')
 store.save(state)
 control=RunControl(store,state,cost_limit=1,time_limit=60)
 with control.attempt(SimpleNamespace(tokens_total=0,cost=0,priced=True)):
  os._exit(73)
else:
 state=store.load('task'); control=RunControl(store,state,cost_limit=100,time_limit=600)
 assert state.budget['pending_attempts']==1
 assert state.budget['cost_limit']==1
 try: control.check()
 except RunStopped as e: assert e.reason=='budget_stopped'
 else: raise AssertionError('reset allowance')
'''
        first = subprocess.run([sys.executable, '-c', source, str(self.root), 'crash'], env=env, timeout=15, capture_output=True)
        self.assertEqual(first.returncode, 73, first.stderr)
        second = subprocess.run([sys.executable, '-c', source, str(self.root), 'recover'], env=env, timeout=15, capture_output=True)
        self.assertEqual(second.returncode, 0, second.stderr)

    def test_child_failure_accounts_usage_and_session_even_without_report(self):
        from feiyu import subagent
        child = FakeBackend([])
        def fail(**kwargs):
            self.charge(child, .4)
            raise RuntimeError('child failed')
        a = self.agent
        a.budget = 1
        with patch.object(a, '_helper_entry', return_value={}), patch('feiyu.providers.build_backend', return_value=child), patch.object(child, 'run_turn', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'child failed'):
                a._spawn('investigate')
        self.assertAlmostEqual(a.task_state.budget['known_cost'], .4)
        self.assertAlmostEqual(a.subagent_cost, .4)
        self.assertEqual(a.subagent_tokens, 10)

    def test_unknown_usage_keeps_known_lower_bound_and_explicit_zero(self):
        a = self.agent
        a._ensure_task_storage()
        c = a._control()
        with c.attempt(a.backend):
            a.backend.usage_reports += 1  # explicit zero usage is a known zero
        self.assertEqual(a.task_state.budget['unknown_attempts'], 0)
        with c.attempt(a.backend):
            self.charge(a.backend, .4)
        with c.attempt(a.backend):
            pass  # missing usage must never masquerade as another zero
        self.assertIsNone(a.task_state.budget['cost'])
        self.assertAlmostEqual(a.task_state.budget['known_cost'], .4)
        self.assertEqual(a.task_state.budget['unknown_attempts'], 1)

    def test_deadline_during_controlled_wait(self):
        a = self.agent
        a.time_budget = .15
        a._ensure_task_storage()
        c = a._control()
        started = time.monotonic()
        with self.assertRaises(RunStopped):
            c.wait(10)
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(a.task_state.run_state, 'deadline_stopped')

    def test_legacy_session_totals_are_not_task_spending(self):
        a = self.agent
        a._ensure_task_storage()
        a.task_state.budget = dict(cost=22, tokens=123, cost_limit=1, time_limit=60)
        c = a._control()
        b = a.task_state.budget
        self.assertIsNone(b['cost'])
        self.assertEqual(b['known_cost'], 0)
        self.assertEqual(b['tokens'], 0)
        self.assertEqual(b['legacy_session_cost'], 22)
        with self.assertRaises(RunStopped):
            c.check()
