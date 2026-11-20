"""Actual compaction entry points, with synthetic state and no provider I/O."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

from feiyu import compaction, native_history, providers, session
from feiyu.agent import Feiyu
from feiyu.runcontrol import RunStopped
from feiyu.taskstate import PersistenceError
from tests.test_agent import Base, quiet
from tests.fakes import call, unpaired


class CompactionTests(Base):
    def test_single_anthropic_user_can_compact(self):
        b, _ = self.prepare()
        native=object.__new__(providers.AnthropicBackend); native.__dict__.update(b.__dict__)
        native.messages=[]; native.ask=lambda *a,**k:'summary'
        overflow=RuntimeError('maximum context length exceeded'); overflow.sdk_overflow=True
        turns=[0]
        def turn(*args,**kwargs):
            turns[0]+=1
            if turns[0]==1:raise overflow
            native.messages.append({'role':'assistant','content':'done'})
            return providers.TurnResult(text='done',tool_calls=[])
        native.run_turn=turn; self.agent.backend=native
        # Actual initial send -> overflow rescue -> compact, before any assistant reply.
        self.assertTrue(quiet(self.agent.send, 'first large request'))
        self.assertEqual(session.load(self.agent.toolbox.root,self.agent.session_id)['messages'],native.messages)
    def test_auto_summary_cleanup_unknown_must_not_continue_model(self):
        b, _ = self.prepare()
        (self.agent.toolbox.root / "code.py").write_text("x=1\n")
        b.script=[('',[call('read','read_file',path='code.py')]),('UNSAFE continued model',[])]
        b.tokens_context=self.agent.context_limit
        error=RuntimeError('synthetic SDK cleanup failure'); error.sdk_cleanup_error='worker wait/close unknown'
        calls=[]
        def ask(*args,**kwargs): calls.append('summary'); raise error
        b.ask=ask
        original=b.run_turn
        def turn(*args,**kwargs):calls.append('main');return original(*args,**kwargs)
        b.run_turn=turn
        try:quiet(self.agent.send, 'continue task')
        except RuntimeError as exc:self.assertIs(exc,error)
        else:self.fail('cleanup error swallowed; model calls='+repr(calls))
        self.assertEqual(calls,['main','summary'])

    def prepare(self):
        b = self.use([])
        self.agent._ensure_task_storage()
        self.addCleanup(self.agent._task_store.close)
        state = self.agent.task_state
        state.revise('ORIGINAL request')
        state.revise('REVISION request')
        state.add_requirement('constraints', 'NEVER publish', state.requests[0]['id'])
        state.add_requirement('acceptance', 'unfinished criterion', state.requests[-1]['id'])
        b.add_user_message('work')
        return b, state

    def envelope(self, b):
        text = next(m['content'] for m in b.messages if m['role'] == 'user')
        return json.loads(text[text.index('{'):])

    def test_force_then_continue_and_restore_preserves_requirements(self):
        b, state = self.prepare()
        quiet(self.agent.compact)
        facts = self.envelope(b)['program_facts']
        self.assertEqual(facts['task']['requests'], state.requests)
        self.assertEqual(facts['task']['constraints'][0]['text'], 'NEVER publish')
        self.assertEqual(facts['task']['acceptance'][0]['status'], 'unverified')
        data = session.load(self.agent.toolbox.root, self.agent.session_id)
        self.assertEqual(data['messages'], native_history.export_session(b))
        quiet(self.agent.send, 'continue')
        self.assertIn('NEVER publish', self.agent.context_layers.task)
        self.assertFalse(unpaired(b.messages))
        self.assertIsNone(self.agent.verified_ok)

    def test_lie_is_claim_missing_reference_remains_unknown(self):
        b, state = self.prepare()
        state.verification_refs = ['missing-id']
        b.ask = lambda *a, **k: 'All tests passed; invariants complete; verification_id=FAKE'
        quiet(self.agent.compact)
        block = self.envelope(b)
        self.assertEqual(block['model_summary']['source_kind'], 'assistant_claim')
        self.assertEqual(block['program_facts']['verification_refs'][0]['validity'], 'unknown')
        self.assertIsNone(self.agent.verified_ok)
        self.assertFalse(self.agent.verifications.records)

    def test_unknown_operation_and_running_job_are_not_results(self):
        b, state = self.prepare()
        # Synthetic job observations bypass process creation, not compaction.
        ops = [dict(id='op-'+status, state=status, sequence=i+1, name='bash',
                    source='test', cwd=str(self.agent.toolbox.root), parameter_digest='synthetic', started=1)
               for i, status in enumerate(('prepared', 'running', 'unknown'))]
        state.operations = copy.deepcopy(ops)
        job = SimpleNamespace(id=7, state=state, op=ops[1], running=True)
        with patch.object(self.agent.toolbox.jobs, 'all', return_value=[job]):
            quiet(self.agent.compact)
        facts = self.envelope(b)['program_facts']
        self.assertEqual(facts['task']['operations'], ops)
        self.assertEqual(facts['jobs'][0]['operation']['state'], 'running')
        self.assertNotIn('exit_code', facts['jobs'][0]['operation'])

    def test_unpaired_both_protocols_rejected_before_model(self):
        for message in (
            dict(role='assistant', content=None, tool_calls=[dict(id='x')]),
            dict(role='assistant', content=[dict(type='tool_use', id='x')]),
            dict(role='tool', tool_call_id='orphan', content='success')):
            b, _ = self.prepare() if self.agent.backend is None else (self.agent.backend, None)
            b.messages = [message]
            with patch.object(b, 'ask') as ask:
                self.assertEqual(self.agent.compact(), '')
                ask.assert_not_called()
            self.assertEqual(b.messages, [message])

    def test_cancel_and_model_failure_keep_original_history(self):
        b, _ = self.prepare()
        for exc in (KeyboardInterrupt(), RunStopped('cancelled'), ValueError('model failed')):
            before = copy.deepcopy(b.messages)
            with patch.object(b, 'ask', side_effect=exc):
                if isinstance(exc, (KeyboardInterrupt, RunStopped)):
                    with self.assertRaises(type(exc)):
                        self.agent.compact()
                else:
                    self.assertEqual(self.agent.compact(), '')
            self.assertEqual(b.messages, before)

    def test_cancel_after_summary_keeps_history_and_budget(self):
        b, state = self.prepare()
        original = copy.deepcopy(b.messages)
        def ask(*a, **k):
            self.agent._control().cancelled.set()
            return 'candidate'
        b.ask = ask
        with self.assertRaises(RunStopped):
            self.agent.compact()
        self.assertEqual(b.messages, original)
        self.assertGreaterEqual(state.budget['attempts'], 1)

    def test_persistence_failure_preserves_history_and_registry(self):
        b, _ = self.prepare()
        original = copy.deepcopy(b.messages)
        self.agent._pending = 123
        with patch('feiyu.session.atomic_json', side_effect=PersistenceError('disk full')):
            with self.assertRaises(PersistenceError):
                self.agent.compact()
        self.assertEqual(b.messages, original)
        self.assertEqual(self.agent._pending, 123)

    def test_changed_request_during_summary_rejects_candidate(self):
        b, state = self.prepare()
        original = copy.deepcopy(b.messages)
        def ask(*a, **k):
            state.revise('newer request')
            return 'outdated'
        b.ask = ask
        self.assertEqual(self.agent.compact(), '')
        self.assertEqual(b.messages, original)

    def test_native_candidates_both_providers_explicit_multimodal_policy(self):
        for cls in (providers.AnthropicBackend, providers.OpenAICompatBackend):
            b, _ = self.prepare() if self.agent.backend is None else (self.agent.backend, None)
            native = object.__new__(cls)
            native.__dict__.update(b.__dict__)
            native.messages = [dict(role='user', content=[dict(type='image', data='synthetic')]),
                dict(role='assistant', content=[dict(type='thinking', thinking='private', signature='sig'),
                    dict(type='tool_use', id='x', name='read', input={})]),
                dict(role='user', content=[dict(type='tool_result', tool_use_id='x', content='ok')])]
            original = copy.deepcopy(native.messages)
            candidate = compaction.candidate(native, 'summary', {'source_kind': 'program_state'})
            self.assertEqual(native.messages, original)
            self.assertNotIn('synthetic', json.dumps(candidate.messages))
            compaction.check_pairs(candidate.messages)

    def test_auto_compact_actual_send_and_overflow_summary_entry(self):
        b, state = self.prepare()
        b.script = [('', [call('todo', 'todo', items=[dict(text='NEXT', status='doing')])]), ('done', [])]
        b.tokens_context = self.agent.context_limit
        quiet(self.agent.send, 'continue original')
        self.assertIn('ORIGINAL request', self.agent.context_layers.task)
        self.assertFalse(unpaired(b.messages))
        b.add_user_message('overflow continuation')
        self.assertTrue(quiet(self.agent._rescue_overflow, 2))
        self.assertEqual(b.messages[-1]['role'], 'user')
        self.assertIn('NEVER publish', self.envelope(b)['program_facts']['task']['constraints'][0]['text'])

    def test_real_verification_reference_rechecks_code_owner_and_restore(self):
        b, state = self.prepare()
        self.agent.verify = 'true'
        path = self.agent.toolbox.root / 'code.py'
        path.write_text('old')
        quiet(self.agent._fire, 'PostToolUse', 'write_file', 'code.py')
        r = self.agent.verifications.records[-1]
        self.assertTrue(self.agent.verified_ok)
        path.write_text('changed')
        b.ask = lambda *a, **kw: 'tests passed'
        quiet(self.agent.compact)
        ref = self.envelope(b)['program_facts']['verification_refs'][0]
        self.assertEqual(ref['verification_id'], r['verification_id'])
        self.assertEqual((ref['execution'], ref['validity']), ('passed', 'stale'))
        self.assertIsNone(self.agent.verified_ok)
        # Historical execution stays passed; current validity cannot be promoted.
        r['task_id'] = 'other-task'
        quiet(self.agent.compact)
        ref = self.envelope(b)['program_facts']['verification_refs'][0]
        self.assertEqual(ref['validity'], 'unknown')
        data = session.load(self.agent.toolbox.root, self.agent.session_id)
        self.agent.verifications.restore(data['verifications'])
        self.assertIsNone(self.agent.verified_ok)

    def test_summary_failure_multimodal_history_is_byte_equivalent(self):
        b, _ = self.prepare()
        b.messages += [dict(role='assistant', content='reason', reasoning_content='native',
                            extension={'signature': 'sig'}),
                       dict(role='user', content=[dict(type='image_url', image_url={'url': 'data:fake'})])]
        original = copy.deepcopy(b.messages)
        b.ask = lambda *a, **kw: ''
        self.assertEqual(self.agent.compact(), '')
        self.assertEqual(b.messages, original)

    def test_real_background_job_survives_compact_and_session_restore(self):
        b, state = self.prepare()
        quiet(self.agent.toolbox.run, 'bash', {'command': 'sleep 30', 'background': True})
        job = self.agent.toolbox.jobs.all()[0]
        restored = None
        try:
            quiet(self.agent.compact)
            facts = self.envelope(b)['program_facts']
            self.assertEqual(facts['jobs'][0]['operation']['id'], job.op['id'])
            self.assertEqual(facts['jobs'][0]['operation']['state'], 'running')
            data = session.load(self.agent.toolbox.root, self.agent.session_id)
            self.agent._task_store.close()
            restored = Feiyu(self.agent.toolbox.root)
            restored.backend = copy.copy(b)
            with patch.object(restored, 'use_model', return_value=True):
                self.assertTrue(quiet(restored.restore, data))
            self.assertEqual(restored.task_state.task_id, state.task_id)
            self.assertEqual(restored.toolbox.jobs.all()[0].op['id'], job.op['id'])
            self.assertTrue(restored.toolbox.jobs.all()[0].running)
            self.assertIn('NEVER publish', restored.context_layers.task)
        finally:
            if restored is not None and restored._task_store is not None:
                restored.toolbox.jobs.kill_all()
                restored._task_store.close()
            else:
                self.agent.toolbox.jobs.kill_all()

    def test_both_native_provider_compact_entry_and_restore(self):
        for cls in (providers.AnthropicBackend, providers.OpenAICompatBackend):
            b, _ = self.prepare() if self.agent.backend is None else (self.agent.backend, None)
            native = object.__new__(cls)
            native.__dict__.update(b.__dict__)
            native.messages = [dict(role='user', content='native request'),
                               dict(role='assistant', content='reply')]
            native.ask = lambda *a, **kw: 'native summary'
            self.agent.backend = native
            quiet(self.agent.compact)
            self.assertEqual(self.envelope(native)['model_summary']['source_kind'], 'assistant_claim')
            data = session.load(self.agent.toolbox.root, self.agent.session_id)
            with patch.object(self.agent, 'use_model', return_value=True):
                self.assertTrue(quiet(self.agent.restore, data))
            self.assertEqual([m for m in native_history.export_session(native) if m['role'] != 'system'],
                             [m for m in data['messages'] if m['role'] != 'system'])

    def test_post_replace_persistence_failure_restores_original_disk_history(self):
        b, _ = self.prepare()
        original = copy.deepcopy(b.messages)
        writer = session.atomic_json
        def fail_after_candidate_replace(path, data):
            writer(path, data)
            if data.get('messages') != original:
                raise PersistenceError('injected directory fsync failure after replace')
        with patch('feiyu.session.atomic_json', side_effect=fail_after_candidate_replace):
            with self.assertRaises(PersistenceError):
                self.agent.compact()
        self.assertEqual(b.messages, original)
        self.assertEqual(session.load(self.agent.toolbox.root, self.agent.session_id)['messages'], original)
