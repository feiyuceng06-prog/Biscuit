"""Offline context/request and lossless native-session regression seams."""
import copy
import json
from unittest.mock import patch

from feiyu import native_history, providers, session, keys
from feiyu.context import ContextLayers
from tests.test_agent import Base, quiet
from tests.fakes import FakeBackend, unpaired, call


class ContextTests(Base):
    def test_next_request_refreshes_task_without_rebuilding_stable_prefix(self):
        b = self.use([('', [call('todo-1', 'todo', items=[
            {'text': 'NEW-TODO-SENTINEL', 'status': 'done'}])]), ('done', [])])
        run = b.run_turn
        seen = []
        def wrapped(*args, **kwargs):
            seen.append(self.agent.context_layers)
            return run(*args, **kwargs)
        b.run_turn = wrapped
        with patch.object(self.agent, '_persona', wraps=self.agent._persona) as persona:
            quiet(self.agent.send, 'record a todo')
            self.assertEqual(persona.call_count, 1)
        self.addCleanup(self.agent._task_store.close)
        self.assertEqual(len(seen), 2)
        self.assertNotIn('NEW-TODO-SENTINEL', seen[0].task)
        self.assertIn('NEW-TODO-SENTINEL', seen[1].task)
        self.assertEqual(seen[0].stable, seen[1].stable)
        self.assertFalse(unpaired(b.messages))

    def test_task_updates_leave_stable_prefix_configuration_refreshes(self):
        b = self.use([])
        self.agent._ensure_task_storage()
        self.addCleanup(self.agent._task_store.close)
        self.agent.task_state.revise('implement feature')
        self.agent._refresh_system()
        first = self.agent.context_layers
        self.agent.task_state.todos = [{'text': 'next step', 'status': 'doing'}]
        self.agent.task_state.verification_refs = ['v-real']
        self.agent._refresh_system()
        second = self.agent.context_layers
        self.assertEqual(first.stable, second.stable)
        self.assertNotEqual(first.task, second.task)
        self.assertIn('v-real', second.task)
        for mode in ('plan', 'auto'):
            self.agent.set_mode(mode)
        self.agent.set_mode('plan')
        self.assertNotEqual(second.stable, self.agent.context_layers.stable)
        before = self.agent.context_layers.stable
        (self.agent.toolbox.root / 'FEIYU.md').write_text('project configuration changed')
        self.agent.reload_context()
        self.assertNotEqual(before, self.agent.context_layers.stable)
        self.assertEqual(b.system, self.agent.context_layers.stable + self.agent.context_layers.volatile)

    def test_both_provider_cache_boundaries_and_disabled_shape(self):
        for cls in (providers.AnthropicBackend, providers.OpenAICompatBackend):
            b = object.__new__(cls)
            b.messages = []
            b.cache = True
            b.tools = []
            for state in ('task-one', 'task-two'):
                ContextLayers('rules', 'project', state, 'evidence').apply(b)
                b.add_user_message('continue')
                blocks = (b._cached_system() if cls is providers.AnthropicBackend
                          else b._marked()[0]['content'])
                self.assertEqual(blocks[0], dict(type='text', text='rulesproject',
                                                cache_control=providers.CACHE_MARK))
                self.assertEqual(blocks[1], dict(type='text', text=state+'evidence'))
                self.assertNotIn('cache_control', blocks[1])
                if cls is providers.OpenAICompatBackend:
                    self.assertIsInstance(b.messages[0]['content'], str)
            b.cache = False
            if cls is providers.AnthropicBackend:
                self.assertEqual(b._cached_system(), 'rulesprojecttask-twoevidence')
            else:
                self.assertEqual(b.messages[0]['content'], 'rulesprojecttask-twoevidence')

    def test_actual_request_paths_use_layer_boundaries(self):
        class Captured(Exception):
            pass
        for cls in (providers.AnthropicBackend, providers.OpenAICompatBackend):
            b = object.__new__(cls)
            b.messages, b.tools, b.cache = [], [], True
            b.model, b.max_tokens, b.thinking = 'offline', 100, False
            b._reset_usage()
            ContextLayers('stable', task='changing').apply(b)
            b.add_user_message('continue')
            calls = []
            def capture(operation, **kwargs):
                calls.append((operation, kwargs))
                raise Captured()
            b._sdk_call = capture
            with self.assertRaises(Captured):
                b.run_turn(lambda text: None)
            self.assertEqual(len(calls), 1)
            operation, request = calls[0]
            self.assertEqual(operation, 'stream')
            blocks = request.get('system') if cls is providers.AnthropicBackend else request['messages'][0]['content']
            self.assertEqual(blocks[0]['text'], 'stable')
            self.assertIn('cache_control', blocks[0])
            self.assertEqual(blocks[1], dict(type='text', text='changing'))

    def test_custom_backend_and_evidence_does_not_promote_claims(self):
        class Custom:
            def set_system(self, text):
                self.system = text
        b = Custom()
        ContextLayers('rules', task='task').apply(b)
        self.assertEqual(b.system, 'rulestask')
        self.use([]).messages.append(dict(role='assistant', content='all tests passed'))
        self.agent._refresh_system()
        self.assertEqual(self.agent.context_layers.evidence, '')
        self.agent.verifications.records.append(dict(verification_id='real-v', execution='failed', validity='stale'))
        self.agent._refresh_system()
        self.assertIn('real-v', self.agent.context_layers.evidence)
        self.assertIn('failed', self.agent.context_layers.evidence)
        self.assertNotIn('all tests passed', self.agent.context_layers.evidence)

    def test_native_export_restore_and_same_model_switch(self):
        b = self.use([])
        b.messages += [dict(role='user', content=[dict(type='image_url', image_url={'url': 'data:image/png;base64,IMAGE'})]),
            dict(role='assistant', content='text', reasoning_content='reason', extra={'signature': 'keep'},
                 tool_calls=[dict(id='t1', type='function', function={'name': 'read_file', 'arguments': '{}'})]),
            dict(role='tool', tool_call_id='t1', content='result')]
        original = copy.deepcopy(b.messages[1:])
        snap = native_history.export_session(b)
        snap[1]['content'][0]['image_url']['url'] = 'different'
        self.assertEqual(b.messages[1: ], original)
        session.save(self.agent.toolbox.root, self.agent)
        data = session.load(self.agent.toolbox.root)
        with patch.object(keys, 'load', return_value={'other': {'model': 'fake'}, 'fake': {'model': 'fake'}}), \
             patch('feiyu.agent.build_backend', side_effect=lambda *a, **k: FakeBackend([])):
            self.assertTrue(self.agent.use_model('other'))
            self.assertEqual(self.agent.backend.messages[1:], original)
            self.assertTrue(quiet(self.agent.restore, data))
        self.assertEqual(self.agent.backend.messages[1:], original)
        self.assertEqual(unpaired(self.agent.backend.messages), set())

    def test_anthropic_sdk_blocks_round_trip_without_flattening(self):
        import anthropic.types as types
        b = object.__new__(providers.AnthropicBackend)
        b.messages = [dict(role='assistant', content=[
            types.ThinkingBlock(type='thinking', thinking='reason', signature='signed'),
            dict(type='tool_use', id='t', name='read_file', input={}, future={'x': 1})]),
            dict(role='user', content=[dict(type='tool_result', tool_use_id='t', content=[
                dict(type='image', source=dict(type='base64', media_type='image/png', data='IMAGE'))])])]
        exported = native_history.export_session(b)
        native_history.restore_session(b, json.loads(json.dumps(exported)))
        self.assertEqual(native_history.export_session(b), exported)
        self.assertEqual(b.messages[0]['content'][0]['signature'], 'signed')
        self.assertEqual(b.messages[0]['content'][1]['future'], {'x': 1})
        self.assertFalse(unpaired(b.messages))
