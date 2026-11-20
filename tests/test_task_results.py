"""D3 offline product controls: declarations are never execution evidence."""
import contextlib
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from feiyu import session, hooks
from feiyu.__main__ import _task, _run_turn
from feiyu.agent import Feiyu
from feiyu.serve import Server, Protocol
from feiyu.taskstate import TaskState, PersistenceError
from tests.fakes import FakeBackend


class Results(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir='/var/tmp')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'workspace'
        self.root.mkdir()
        p = patch.object(session, 'DIR', str(Path(tmp.name) / 'sessions'))
        p.start()
        self.addCleanup(p.stop)
        self.agent = self.make_agent()
        with contextlib.redirect_stdout(io.StringIO()):
            self.agent.send('deliver A and B')

    def make_agent(self):
        agent = Feiyu(self.root)
        agent.backend = FakeBackend([('completed partial unverifiable: claims only', [])])
        agent.name = 'fake'
        self.addCleanup(agent.toolbox.lsp.close)
        self.addCleanup(lambda: agent._task_store.close() if agent._task_store else None)
        return agent

    def command(self, result, reason='human explanation'):
        return json.loads(_task(self.agent, json.dumps(dict(action='result', result=result, reason=reason))))

    def requirements(self):
        a = self.agent
        return [a.task_control(dict(action='add', kind='acceptance', text=t,
                    request_id=a.task_state.requests[0]['id'])) for t in ('A', 'B')]

    def verify(self, row):
        a = self.agent
        a.mode = 'auto'
        a.verify = 'printf verified'
        with contextlib.redirect_stdout(io.StringIO()):
            a._run_verification(hooks.Hook('PreWrite', {'command': 'printf verified'}, 'verify:'), {}, 'post_change')
        record = a.verifications.records[-1]
        a.task_control(dict(action='bind', acceptance_id=row['id'], verification_id=record['verification_id']))
        return record

    def test_partial_preserves_verified_and_unfinished_acceptance_then_continue(self):
        a = self.agent
        rows = self.requirements()
        record = self.verify(rows[0])
        result = self.command('partial', 'A delivered; B remains')
        self.assertEqual([r['status'] for r in result['acceptance']], ['verified', 'unverified'])
        self.assertEqual(result['result_details']['source'], 'user-control')
        self.assertEqual(result['result_details']['acceptance'][0]['verification_id'], record['verification_id'])
        self.assertEqual(a._task_store.load(a.task_id).result_details, result['result_details'])
        self.assertIn('A delivered; B remains', a.backend.system)
        self.assertIn('partial', _task(a, ''))
        with self.assertRaises(PersistenceError):
            self.command('completed')
        tid = a.task_id
        with contextlib.redirect_stdout(io.StringIO()):
            a.send('finish B')
        self.assertEqual(a.task_id, tid)
        self.assertEqual(a.task_state.result, 'unfinished')
        self.assertEqual(len(a.task_state.acceptance), 2)
        self.verify(rows[1])
        # Only the last verification is eligible; explicitly bind both to current evidence.
        a.task_control(dict(action='bind', acceptance_id=rows[0]['id'],
            verification_id=a.verifications.records[-1]['verification_id']))
        _task(a, 'complete')
        self.assertEqual(a.task_state.result, 'completed')
        Path(a.verifications.records[-1]['log']).write_text('changed')
        self.assertEqual(a.task_control({'action': 'check'})['result'], 'unfinished')

    def test_unverifiable_serve_status_note_and_restore(self):
        a = self.agent
        self.requirements()
        output = io.StringIO()
        server = Server(a, self.root, None, Protocol(output))
        before = a.task_state.run_state
        server.run_command('/task ' + json.dumps(dict(action='result', result='unverifiable', reason='offline dependency unavailable')))
        self.assertEqual(server.status()['task']['result'], 'unverifiable')
        self.assertEqual(a.task_state.run_state, before)
        self.assertTrue(any(e['kind'] == 'note' and 'unverifiable' in e['text']
                            for e in map(json.loads, output.getvalue().splitlines())))
        self.assertTrue(all(r['status'] == 'unverified' for r in a.task_state.acceptance))
        self.assertEqual(a.verifications.records, [])
        session.save(self.root, a, a.session_id)
        saved = session.load(self.root, a.session_id)
        a._task_store.close()
        resumed = self.make_agent()
        with patch.object(resumed, 'use_model', return_value=True):
            self.assertTrue(resumed.restore(saved))
        self.assertEqual(resumed.task_state.result, 'unverifiable')
        self.assertEqual(resumed.task_state.result_details, a.task_state.result_details)
        self.assertIn('offline dependency unavailable', resumed.backend.system)
        self.assertEqual(resumed.resumed['result'], 'unverifiable')

    def test_interrupt_wait_budget_and_deadline_do_not_infer_results(self):
        a = self.agent
        self.assertEqual(a.task_state.run_state, 'waiting_user')
        self.assertEqual(a.task_state.result, 'unfinished')
        self.command('partial')
        with patch.object(a, '_send', side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(_run_turn(a, 'continue then interrupt'), 130)
        self.assertEqual(a.task_state.run_state, 'interrupted')
        self.assertEqual(a.task_state.result, 'unfinished')
        from feiyu.runcontrol import RunStopped
        for reason in ('budget_stopped', 'deadline_stopped'):
            with patch.object(a, '_send', side_effect=RunStopped(reason)), contextlib.redirect_stdout(io.StringIO()):
                a.send('continue')
            self.assertEqual(a.task_state.run_state, reason)
            self.assertEqual(a.task_state.result, 'unfinished')

    def test_unknown_still_blocks_and_no_authorization_changes(self):
        a = self.agent
        with self.assertRaises(RuntimeError):
            a.toolbox.execution.invoke('write_file', {}, lambda: (_ for _ in ()).throw(RuntimeError()))
        before = asdict(a.task_state)['operations']
        for result in ('partial', 'unverifiable', 'unfinished'):
            self.command(result)
            self.assertEqual(a.task_state.operations, before)
            with self.assertRaises(PersistenceError):
                a.toolbox.execution.invoke('write_file', {}, lambda: self.fail('replayed'))
            with self.assertRaises(PersistenceError):
                a.new_task()
        with self.assertRaises(PersistenceError):
            self.command('completed')
        self.assertFalse(a.task_state.operations[-1]['authorization']['reusable'])

    def test_legacy_results_and_malformed_new_provenance(self):
        payload = asdict(self.agent.task_state)
        payload.pop('result_details')
        for result in ('unfinished', 'completed'):
            payload['result'] = result
            self.assertEqual(TaskState.read(payload).result, result)
            self.assertEqual(TaskState.read(payload).result_details, {})
        for result in ('partial', 'unverifiable', 'invented'):
            payload['result'] = result
            with self.assertRaises(PersistenceError):
                TaskState.read(payload)
        self.command('partial')
        payload = asdict(self.agent.task_state)
        payload['result_details']['source'] = 'model'
        with self.assertRaises(PersistenceError):
            TaskState.read(payload)

    def test_declaration_rejects_forgery_and_persistence_failure_blocks(self):
        for command in (dict(action='result', result='partial'),
                        dict(action='result', result='unverifiable', reason=''),
                        dict(action='result', result='partial', reason='x', status='verified')):
            with self.assertRaises(PersistenceError):
                self.agent.task_control(command)
        with patch('feiyu.taskstate.atomic_json', side_effect=PersistenceError('disk full')):
            with self.assertRaises(PersistenceError):
                self.command('unverifiable')
        self.assertTrue(self.agent._task_store.blocked)

    def test_old_checksummed_sidecars_load_without_rewriting(self):
        import hashlib
        a = self.agent
        path = a._task_store.path(a.task_id)
        data = json.loads(path.read_text())
        data['payload'].pop('result_details')
        for result in ('unfinished', 'completed'):
            data['payload']['result'] = result
            packed = json.dumps(data['payload'], ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
            data['sha256'] = hashlib.sha256(packed).hexdigest()
            path.write_text(json.dumps(data))
            before = path.read_bytes()
            loaded = a._task_store.load(a.task_id)
            self.assertEqual(loaded.result, result)
            self.assertEqual(loaded.result_details, {})
            self.assertEqual(path.read_bytes(), before)

    def test_restore_completed_rechecks_evidence_without_losing_acceptance(self):
        a = self.agent
        rows = self.requirements()
        record = self.verify(rows[0])
        a.task_control(dict(action='bind', acceptance_id=rows[1]['id'], verification_id=record['verification_id']))
        self.command('completed')
        self.assertEqual(a.task_state.result, 'completed')
        session.save(self.root, a, a.session_id)
        saved = session.load(self.root, a.session_id)
        a._task_store.close()
        resumed = self.make_agent()
        with patch.object(resumed, 'use_model', return_value=True):
            self.assertTrue(resumed.restore(saved))
        self.assertEqual(resumed.task_state.result, 'unfinished')
        self.assertEqual(len(resumed.task_state.acceptance), 2)
        self.assertIn(record['verification_id'], resumed.task_state.verification_refs)


    def test_select_updates_result_view(self):
        a = self.agent
        self.command('partial', 'first task')
        first = a.task_id
        _task(a, 'new')
        with contextlib.redirect_stdout(io.StringIO()):
            a.send('second task')
        self.command('unverifiable', 'second task')
        server = Server(a, self.root, None, Protocol(io.StringIO()))
        server.run_command('/task ' + json.dumps(dict(action='select', task_id=first)))
        self.assertEqual(server.status()['task']['task_id'], first)
        self.assertEqual(a.resumed['task_id'], first)
        self.assertEqual(a.resumed['result_details'], a.task_state.result_details)
        self.assertEqual(a.resumed['result'], 'partial')

    def test_select_rechecks_completed_evidence(self):
        a = self.agent
        row = a.task_control(dict(action='add', kind='acceptance', text='delivery',
                                 request_id=a.task_state.requests[0]['id']))
        record = self.verify(row)
        self.command('completed')
        first = a.task_id
        _task(a, 'new')
        with contextlib.redirect_stdout(io.StringIO()):
            a.send('second task')
        Path(record['log']).write_text('evidence changed')
        server = Server(a, self.root, None, Protocol(io.StringIO()))
        server.run_command('/task ' + json.dumps(dict(action='select', task_id=first)))
        self.assertEqual(server.status()['task']['result'], 'unfinished')
        self.assertEqual(a.task_state.result_details, {})
        self.assertEqual(a._task_store.load(first).result, 'unfinished')
        self.assertEqual(a.resumed['result'], 'unfinished')
