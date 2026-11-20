"""Offline SDK responses through the agent's actual model entry points."""
import contextlib
import io
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from feiyu import providers, session
from feiyu.runcontrol import RunControl, RunStopped
from feiyu.taskstate import PersistenceError
from tests import test_runcontrol


class Stream:
    def __init__(self, events, error=None, final=None):
        self.events, self.error, self.final = events, error, final
        self.closed = False

    def __iter__(self):
        yield from self.events
        if self.error:
            raise self.error

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_final_message(self):
        return self.final


def usage(i=10, o=2):
    return NS(prompt_tokens=i, completion_tokens=o)


def chunk(u, finished=True):
    return NS(usage=u, choices=[NS(finish_reason='stop', delta=NS())] if finished else [])


class SDKAccounting(unittest.TestCase):
    setUp = test_runcontrol.ParentControlTests.setUp

    def backend(self, create, anthropic=False):
        cls = providers.AnthropicBackend if anthropic else providers.OpenAICompatBackend
        b = cls.__new__(cls)
        b.model, b.system, b.tools, b.messages = 'offline', 'system', [], []
        b.max_tokens, b.cache, b.thinking = 100, False, False
        b._reset_usage()
        b.rates = (1, 1, 1)
        b.client = NS(messages=NS(create=create, stream=create),
                      chat=NS(completions=NS(create=create)))
        self.agent.backend = b
        return b

    def ask(self, b):
        return self.agent._model_call(b, 'ask', 'offline prompt')

    def turn(self, b):
        return self.agent._model_call(b, 'run_turn', on_text=lambda t: None)

    def reply(self, u):
        return NS(usage=u, choices=[NS(message=NS(content='answer'))])

    def test_retry_success_counts_each_attempt(self):
        class Busy(Exception):
            status_code = 503
        responses = [Busy(), self.reply(usage())]
        def create(**kw):
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        b = self.backend(create)
        with patch('feiyu.providers.time.sleep'):
            self.assertEqual(self.ask(b), 'answer')
        budget = self.agent.task_state.budget
        self.assertEqual(budget['attempts'], 2)
        self.assertEqual([r['usage_status'] for r in budget['attempt_records']], ['unknown', 'complete'])
        self.assertIsNone(budget['cost'])
        self.assertGreater(budget['known_cost'], 0)

    def test_retry_exhaustion_and_finite_budget_blocks_retry(self):
        class Busy(Exception):
            status_code = 503
        for finite in (False, True):
            with self.subTest(finite=finite):
                self.agent.budget = 1 if finite else 0
                count = []
                def create(**kw):
                    count.append(1)
                    raise Busy()
                b = self.backend(create)
                # Fresh task for each independent allowance.
                if self.agent.task_state:
                    self.agent.new_task()
                with patch('feiyu.providers.time.sleep'), patch('feiyu.runcontrol.RunControl.wait', lambda c, n: c.check()):
                    with self.assertRaises(RunStopped if finite else Busy):
                        self.ask(b)
                self.assertEqual(len(count), 1 if finite else providers.RETRIES + 1)

    def test_fallback_is_separate_attempt(self):
        class Rejected(Exception):
            status_code = 400
        for anthropic in (False, True):
            calls = []
            def create(**kw):
                calls.append(kw)
                if len(calls) == 1:
                    raise Rejected('cache unsupported')
                if anthropic:
                    return Stream([], final=NS(usage=NS(input_tokens=10, output_tokens=2), content=[], stop_reason='end_turn'))
                return Stream([chunk(usage())])
            b = self.backend(create, anthropic)
            b.cache = True
            before = self.agent.task_state.budget['attempts'] if self.agent.task_state else 0
            self.turn(b)
            self.assertEqual(len(calls), 2)
            self.assertEqual(self.agent.task_state.budget['attempts'] - before, 2)

    def test_partial_input_missing_and_duplicate_usage(self):
        for events, error, status, tokens in (
            ([chunk(usage()), chunk(usage(10, 4)), chunk(usage(10, 4))], None, 'complete', 14),
            ([chunk(usage())], RuntimeError('stream cut'), 'partial', 12),
            ([chunk(usage(), finished=False)], None, 'partial', 12),
            ([chunk(NS(prompt_tokens=10))], None, 'partial', 10),
            ([], None, 'unknown', 0),
            ([chunk(NS())], None, 'unknown', 0),
        ):
            with self.subTest(status=status, tokens=tokens):
                stream = Stream(events, error)
                b = self.backend(lambda **kw: stream)
                if error:
                    with self.assertRaisesRegex(RuntimeError, 'stream cut'):
                        self.turn(b)
                else:
                    self.turn(b)
                row = self.agent.task_state.budget['attempt_records'][-1]
                self.assertEqual(row['usage_status'], status)
                self.assertEqual(row['tokens'], tokens)
                self.assertTrue(stream.closed)

    def test_anthropic_partial_cumulative_preserves_input_and_cache(self):
        stream = Stream([
            NS(type='message_start', message=NS(usage=NS(input_tokens=10, output_tokens=0, cache_read_input_tokens=5))),
            NS(type='message_delta', usage=NS(output_tokens=3)),
            NS(type='message_delta', usage=NS(output_tokens=3)),
        ], RuntimeError('cut'))
        b = self.backend(lambda **kw: stream, True)
        with self.assertRaisesRegex(RuntimeError, 'cut'):
            self.turn(b)
        row = self.agent.task_state.budget['attempt_records'][-1]
        self.assertEqual(row['tokens'], 18)
        self.assertEqual(row['usage_status'], 'partial')
        self.assertIsNone(self.agent.cost)

    def test_unknown_price_and_explicit_zero(self):
        b = self.backend(lambda **kw: self.reply(usage(0, 0)))
        self.ask(b)
        self.assertEqual(self.agent.task_state.budget['cost'], 0)
        b.rates = None
        self.ask(b)
        self.assertIsNone(self.agent.cost)
        self.assertFalse(self.agent.task_state.budget['attempt_records'][-1]['price_known'])

    def test_parallel_helpers_share_parent_allowance(self):
        self.agent.budget = .000015
        b = self.backend(lambda **kw: self.reply(usage()))
        def call():
            try:
                return self.ask(b)
            except RunStopped:
                return 'stopped'
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: call(), range(4)))
        self.assertIn('stopped', results)
        self.assertLess(self.agent.task_state.budget['attempts'], 4)

    def test_running_limit_tightening_and_restore_never_refills(self):
        b = self.backend(lambda **kw: self.reply(usage()))
        self.agent.budget = 1
        self.ask(b)
        spent = self.agent.task_state.budget['cost']
        self.agent.budget = spent / 2
        with self.assertRaises(RunStopped):
            self.ask(b)
        state = self.agent._task_store.load(self.agent.task_id)
        c = RunControl(self.agent._task_store, state, cost_limit=100)
        self.assertEqual(state.budget['cost'], spent)
        self.assertEqual(state.budget['cost_limit'], spent / 2)
        with self.assertRaises(RunStopped):
            c.check()

    def test_pending_and_finish_save_failure_block_later_calls(self):
        for at in (1, 2):
            calls = []
            b = self.backend(lambda **kw: calls.append(1) or self.reply(usage()))
            c = self.agent._control()
            real_save = c.store.save
            writes = []
            def save(state):
                writes.append(1)
                if len(writes) == at:
                    raise PersistenceError('injected disk error')
                real_save(state)
            with patch.object(c.store, 'save', side_effect=save):
                with self.assertRaises(PersistenceError):
                    self.ask(b)
            with self.assertRaises(PersistenceError):
                self.ask(b)
            self.assertEqual(len(calls), 0 if at == 1 else 1)
            c.store.blocked = c.blocked = False  # fault fixture reset only

    def test_session_unknown_survives_task_switch_and_restore(self):
        b = self.backend(lambda **kw: self.reply(None))
        self.ask(b)
        b.messages = [{'role': 'user', 'content': 'offline'}, {'role': 'assistant', 'content': 'reply'}]
        session.save(self.root, self.agent, self.agent.session_id)
        data = session.load(self.root, self.agent.session_id)
        self.assertTrue(data['unknown_cost'])
        self.agent.new_task()
        self.assertIsNone(self.agent.cost)
        self.agent._task_store.close()
        from feiyu.agent import Feiyu
        restored = Feiyu(self.root)
        self.addCleanup(lambda: restored._task_store and restored._task_store.close())
        self.addCleanup(restored.toolbox.lsp.close)
        with patch.object(restored, 'use_model', side_effect=lambda name: setattr(restored, 'backend', b) or True):
            self.assertTrue(restored.restore(data))
        self.assertIsNone(restored.cost)
        # Journal-only restore has no backend counters or session price flag.
        restored._task_store.close()
        restored._task_store = None
        restored.backend = None
        self.assertTrue(restored.restore(dict(journal_only=True, session_id=data['session_id'], task_ref=restored.task_id)))
        self.assertIsNone(restored.cost)

    def test_sdk_constructors_disable_hidden_retries(self):
        with patch('openai.OpenAI') as client:
            providers.OpenAICompatBackend(system='', tools=[], model='offline', api_key='fake')
            self.assertEqual(client.call_args.kwargs['max_retries'], 0)
        with patch('anthropic.Anthropic') as client:
            providers.AnthropicBackend(system='', tools=[], model='offline', api_key='fake')
            self.assertEqual(client.call_args.kwargs['max_retries'], 0)

    def test_cancel_during_sync_call_accounts_return_without_background_thread(self):
        c = self.agent._control()
        def create(**kw):
            c.cancel()
            return self.reply(usage())
        b = self.backend(create)
        with self.assertRaises(RunStopped):
            self.ask(b)
        self.assertEqual(c.state.budget['tokens'], 12)
        self.assertEqual(c.state.budget['pending_attempts'], 0)
        self.assertEqual(c.state.budget['attempts'], 1)

    def test_live_time_limit_uses_original_task_origin(self):
        b = self.backend(lambda **kw: self.reply(usage()))
        with patch('feiyu.runcontrol.time.time', return_value=100):
            self.ask(b)
        c = self.agent._control()
        self.agent.time_budget = 5
        with patch('feiyu.runcontrol.time.time', return_value=110):
            with self.assertRaises(RunStopped):
                self.ask(b)
        self.assertEqual(c.state.budget['deadline'], 105)
        self.assertEqual(c.state.budget['attempts'], 1)

    def test_limit_changes_inside_sdk_wait_apply_to_next_admission(self):
        self.agent.budget = 1
        def create(**kw):
            self.agent.budget = .000001
            return self.reply(usage())
        b = self.backend(create)
        self.ask(b)
        c = self.agent._control()
        self.assertEqual(c.state.budget['cost_limit'], .000001)
        self.agent.budget = 100  # cannot relax the durable restriction
        with self.assertRaises(RunStopped):
            self.ask(b)
        self.assertEqual(c.state.budget['attempts'], 1)

    def test_main_helper_compact_reviewer_and_subagent_sdk_seams(self):
        def create(**kw):
            if kw.get('stream'):
                return Stream([chunk(usage())])
            return self.reply(usage())
        child = self.backend(create)
        judge = self.backend(create)
        side = self.backend(create)
        main = self.backend(create)
        main.messages = [{'role': 'system', 'content': 'offline'}]
        a = self.agent
        a.budget = 1
        with contextlib.redirect_stdout(io.StringIO()):
            a.send('offline user request')
        with patch.object(a, '_side_backend', return_value=side):
            self.assertEqual(a._ask_model('page'), 'answer')
            self.assertEqual(a.compact(), 'answer')
        with patch.object(a, 'changes', return_value='diff'), patch('feiyu.agent.keys.load', return_value={'fake': {}}), patch('feiyu.agent.build_backend', return_value=judge):
            self.assertEqual(a.review('request'), 'answer')
        with patch.object(a, '_helper_entry', return_value={}), patch('feiyu.providers.build_backend', return_value=child):
            a._spawn('offline investigation')
        self.assertEqual(a.task_state.budget['attempts'], 5)
        self.assertEqual(a.task_state.budget['tokens'], 60)
        self.assertTrue(all(r['usage_status'] == 'complete' for r in a.task_state.budget['attempt_records']))

    def test_cost_tightening_does_not_extend_monotonic_deadline_after_clock_rollback(self):
        self.agent.time_budget = 60
        self.agent.budget = 10
        b = self.backend(lambda **kw: self.reply(usage()))
        self.ask(b)
        c = self.agent._control()
        old_deadline = c.monotonic_deadline
        import time
        earlier = time.time() - 1000
        self.agent.budget = 1
        with patch('feiyu.runcontrol.time.time', return_value=earlier):
            self.agent._control()
        self.assertLessEqual(c.monotonic_deadline, old_deadline)

    def test_anthropic_eof_without_message_stop_is_partial_even_with_usage(self):
        for terminal in (False, True):
            events = [NS(type='message_start', message=NS(usage=NS(input_tokens=10, output_tokens=2)))]
            if terminal:
                events.append(NS(type='message_stop'))
            final = NS(usage=NS(input_tokens=10, output_tokens=2), content=[], stop_reason='end_turn')
            stream = Stream(events, final=final)
            b = self.backend(lambda **kw: stream, True)
            self.turn(b)
            row = self.agent.task_state.budget['attempt_records'][-1]
            self.assertEqual(row['usage_status'], 'complete' if terminal else 'partial')
            self.assertEqual(row['tokens'], 12)
