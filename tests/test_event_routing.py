"""Actual send/worker routing and legacy frontend compatibility."""
import concurrent.futures
import contextlib
import io
import threading
from unittest.mock import patch
from feiyu import events, ui, serve
from feiyu.agent import Feiyu
from feiyu.taskstate import PersistenceError
from tests.test_agent import Base, quiet
from tests.fakes import FakeBackend, call


class EventPaths(Base):
    def setUp(self):
        super().setUp()
        self.seen = []
        self.agent.event_sink = lambda k, p: self.seen.append((k, p))

    def test_two_agents_threads_parallel_tools_own_exact_facts(self):
        other = Feiyu(self.agent.toolbox.root)
        other.name, other.mode = 'fake', 'auto'
        other_seen = []
        other.event_sink = lambda k, p: other_seen.append((k, p))
        barrier = threading.Barrier(4)
        def raw(name, args):
            barrier.wait(timeout=10)
            return original(name, args)
        original = self.agent.toolbox._run_raw
        for agent in (self.agent, other):
            agent.backend = FakeBackend([('', [call('a', 'read_file', path='a'), call('b', 'read_file', path='b')]), ('done', [])])
            agent.toolbox._run_raw = raw
        try:
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(a.send, 'read files') for a in (self.agent, other)]
                for f in futures:
                    f.result(timeout=20)
            for agent, rows in ((self.agent, self.seen), (other, other_seen)):
                self.assertTrue(rows)
                self.assertEqual({p['session_id'] for _, p in rows}, {agent.session_id})
                self.assertEqual({p['task_id'] for _, p in rows}, {agent.task_id})
                self.assertEqual([p['seq'] for _, p in rows], list(range(1, len(rows)+1)))
                for kind in ('execution_start', 'execution_end', 'tool_start', 'tool_result'):
                    selected = [p for k, p in rows if k == kind]
                    self.assertEqual(len(selected), 2, kind)
                self.assertEqual({p['operation_id'] for k,p in rows if k == 'execution_start'},
                                 {p['operation_id'] for k,p in rows if k == 'execution_end'})
            self.assertNotEqual(self.seen[0][1]['run_id'], other_seen[0][1]['run_id'])
        finally:
            if other._task_store:
                other._task_store.close()

    def test_late_worker_drops_after_run_and_does_not_rebind(self):
        self.use([])
        release = threading.Event()
        pool = concurrent.futures.ThreadPoolExecutor(1)
        delayed = []
        def sending(_):
            delayed.append(events.submit(pool, lambda: (release.wait(10), ui.notice('late'))))
            return 'ok'
        try:
            with patch.object(self.agent, '_send', side_effect=sending):
                quiet(self.agent.send, 'one')
            first = list(self.seen)
            quiet(self.agent.send, 'two')
            self.assertNotEqual(first[0][1]['run_id'], self.seen[-1][1]['run_id'])
            release.set()
            delayed[0].result(timeout=10)
            self.assertFalse(any(p.get('text') == 'late' for _,p in self.seen))
            self.assertTrue(first)
        finally:
            release.set()
            pool.shutdown()

    def test_stop_resume_same_task_new_run_and_persistence_failure(self):
        self.use([])
        with patch.object(self.agent, '_send', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                quiet(self.agent.send, 'one')
        stopped = next(p for k,p in self.seen if k == 'task_stopped')
        quiet(self.agent.send, 'continue')
        resumed = [p for k,p in self.seen if k == 'task_resumed'][-1]
        self.assertEqual(stopped['task_id'], resumed['task_id'])
        self.assertEqual(resumed['previous_state'], 'interrupted')
        self.assertNotEqual(stopped['run_id'], resumed['run_id'])
        self.agent.event_sink = lambda *a: 1/0
        with patch.object(self.agent, '_task_checkpoint', side_effect=PersistenceError('disk')):
            with self.assertRaises(PersistenceError):
                quiet(self.agent.send, 'cannot save')

    def test_nested_capture_pause_exception_and_other_thread(self):
        self.use([])
        def sending(_):
            with events.capturing() as captured:
                ui.warn('captured')
                with self.assertRaises(ValueError):
                    with events.paused():
                        ui.error('ignored')
                        raise ValueError()
                ui.error('captured error')
            self.assertEqual(captured.level, 'error')
            ui.notice('visible')
            return 'ok'
        with patch.object(self.agent, '_send', side_effect=sending):
            quiet(self.agent.send, 'work')
        self.assertEqual([p['text'] for k,p in self.seen if k == 'note'], ['visible'])

    def test_frontend_adapter_and_legacy_wire(self):
        output = io.StringIO()
        protocol = serve.Protocol(output)
        self.agent.event_sink = lambda k,p: protocol.send(k, **p)
        self.use([('', [call('a', 'read_file', path='missing')]), ('done', [])])
        quiet(self.agent.send, 'read')
        import json
        wire = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len([x for x in wire if x['kind'] == 'execution_end']), 1)
        legacy = [x for x in wire if x['kind'] == 'tool_result']
        self.assertEqual(len(legacy), 1)
        self.assertIn('summary', legacy[0])
        self.assertEqual(legacy[0]['id'], 'a')
        with events.binding(lambda *a: self.fail('adapter recursively emits')):
            with contextlib.redirect_stdout(io.StringIO()) as text:
                ui.runtime_event('task_stopped', {'state': 'interrupted'})
            self.assertIn('interrupted', text.getvalue())

    def test_capture_in_one_agent_does_not_pause_another(self):
        self.use([])
        other = Feiyu(self.agent.toolbox.root)
        other.backend = FakeBackend([])
        rows = []
        other.event_sink = lambda k,p: rows.append((k,p))
        barrier = threading.Barrier(2)
        def one(_):
            with events.capturing() as captured:
                barrier.wait(5)
                ui.error('private')
                barrier.wait(5)
            self.assertEqual(captured.level, 'error')
            return 'one'
        def two(_):
            barrier.wait(5)
            ui.notice('other visible')
            barrier.wait(5)
            return 'two'
        try:
            with patch.object(self.agent, '_send', side_effect=one), patch.object(other, '_send', side_effect=two):
                with concurrent.futures.ThreadPoolExecutor(2) as pool:
                    fs = [pool.submit(a.send, 'work') for a in (self.agent, other)]
                    for f in fs:
                        f.result(10)
            self.assertEqual([p['text'] for k,p in rows if k == 'note'], ['other visible'])
            self.assertFalse(any(k == 'note' for k,p in self.seen))
        finally:
            if other._task_store:
                other._task_store.close()

    def test_verification_runtime_and_new_session_ownership(self):
        self.use([])
        def work(_):
            self.agent._verification_mutation('write_file')
            return 'ok'
        with patch.object(self.agent, '_send', side_effect=work):
            quiet(self.agent.send, 'one')
        fact = next(p for k,p in self.seen if k == 'verification_invalidated')
        self.assertEqual(fact['session_id'], self.agent.session_id)
        old = self.agent.session_id
        self.agent.reset()
        from feiyu import session
        self.agent.session_id = session.new_id()
        quiet(self.agent.send, 'two')
        self.assertNotEqual(old, self.seen[-1][1]['session_id'])

    def test_restore_stopped_session_resumes_owner_in_fresh_agent(self):
        self.use([])
        with patch.object(self.agent, '_send', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                quiet(self.agent.send, 'one')
        from feiyu import session
        data = session.load(self.agent.toolbox.root, self.agent.session_id)
        self.agent._task_store.close()
        restored = Feiyu(self.agent.toolbox.root)
        restored.backend = FakeBackend([])
        rows = []
        restored.event_sink = lambda k,p: rows.append((k,p))
        try:
            self.assertTrue(restored.restore(data))
            quiet(restored.send, 'continue')
            fact = next(p for k,p in rows if k == 'task_resumed')
            self.assertEqual(fact['session_id'], self.agent.session_id)
            self.assertEqual(fact['task_id'], self.agent.task_id)
            self.assertEqual(fact['previous_state'], 'interrupted')
        finally:
            if restored._task_store:
                restored._task_store.close()
