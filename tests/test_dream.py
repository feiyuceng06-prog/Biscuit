import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from feiyu import dream, memory, session


class DreamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = dream.DIR, memory.DIR, session.DIR
        dream.DIR = os.path.join(self.tmp.name, 'dream')
        memory.DIR = os.path.join(self.tmp.name, 'memory')
        session.DIR = os.path.join(self.tmp.name, 'sessions')
        self.ws = '/workspace'
        self.data = {'messages': [
            {'role': 'user', 'content': '以后测试用 pytest。\n\n附带的文件正文 SECRET'},
            {'role': 'assistant', 'content': '知道了，测试用 pytest。'},
            {'role': 'tool', 'content': 'SECRET TOOL OUTPUT'},
            {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'SECRET RESULT'}]},
        ]}
        self.listing = mock.patch.object(session, 'listing', return_value=[{'id': 's1'}])
        self.loading = mock.patch.object(session, 'load', return_value=self.data)
        self.listing.start(); self.loading.start()

    def tearDown(self):
        self.listing.stop(); self.loading.stop()
        dream.DIR, memory.DIR, session.DIR = self.old
        self.tmp.cleanup()

    def change(self, **kwargs):
        return dict({'action': 'add', 'old': '', 'new': '测试使用 pytest', 'session': 's1',
                     'quote': '以后测试用 pytest。', 'reason': '用户明确要求'}, **kwargs)

    def prepare(self, changes):
        return dream.prepare(self.ws, lambda prompt: json.dumps({'changes': changes}, ensure_ascii=False))

    def test_review_then_apply_and_private_storage(self):
        self.prepare([self.change()])
        self.assertEqual(memory.load(self.ws), [])
        self.assertEqual(os.stat(dream._path(self.ws)).st_mode & 0o777, 0o600)
        self.assertEqual(dream.apply(self.ws), 1)
        self.assertEqual(memory.load(self.ws)[0][1], '测试使用 pytest')
        self.assertIsNone(dream.load(self.ws))

    def test_no_tool_or_attached_file_in_prompt(self):
        prompts = []
        dream.prepare(self.ws, lambda prompt: prompts.append(prompt) or '{"changes":[]}')
        self.assertNotIn('SECRET', prompts[0])
        self.assertIn('以后测试用 pytest', prompts[0])

    def test_reject_fabricated_evidence_and_unknown_old(self):
        p = self.prepare([self.change(quote='不存在的原文'), self.change(action='remove', old='无此记忆', new='')])
        self.assertEqual(p['changes'], [])

    def test_detect_memory_and_source_changes(self):
        self.prepare([self.change()])
        memory.add(self.ws, '用户新加的记忆')
        with self.assertRaisesRegex(ValueError, '发生了变化'):
            dream.apply(self.ws)
        memory.clear(self.ws)
        self.data['messages'][0]['content'] = '已经删除旧内容'
        with self.assertRaisesRegex(ValueError, '来源会话'):
            dream.apply(self.ws)
        self.assertEqual(memory.load(self.ws), [])

    def test_replace_and_remove_no_silent_eviction(self):
        memory.add(self.ws, '旧测试命令')
        self.prepare([self.change(action='replace', old='旧测试命令')])
        dream.apply(self.ws)
        self.assertEqual([x[1] for x in memory.load(self.ws)], ['测试使用 pytest'])
        self.prepare([self.change(action='remove', old='测试使用 pytest', new='')])
        dream.apply(self.ws)
        self.assertEqual(memory.load(self.ws), [])
        for i in range(memory.MAX_ITEMS):
            memory.add(self.ws, '记忆 %s' % i)
        self.prepare([self.change()])
        with self.assertRaisesRegex(ValueError, '超出上限'):
            dream.apply(self.ws)
        self.assertEqual(len(memory.load(self.ws)), memory.MAX_ITEMS)

    def test_invalid_model_reply_does_not_overwrite_pending(self):
        self.prepare([self.change()])
        with self.assertRaises(ValueError):
            dream.prepare(self.ws, lambda _: '不是 JSON')
        self.assertEqual(len(dream.load(self.ws)['changes']), 1)

    def test_whitespace_in_model_suggestion_is_normalized_before_preview(self):
        proposal = self.prepare([self.change(new='  测试\u2028使用  pytest  ')])
        self.assertEqual(proposal['changes'][0]['new'], '测试 使用 pytest')
        self.assertEqual(dream.apply(self.ws), 1)
        self.assertEqual(memory.load(self.ws)[0][1], '测试 使用 pytest')

    def test_auto_disabled_by_default_and_toggle(self):
        self.assertFalse(dream.schedule(self.ws, {'model': 'x'}))
        dream.set_auto(self.ws, True)
        self.assertTrue(dream.config(self.ws)['enabled'])
        dream.set_auto(self.ws, False)
        self.assertFalse(dream.config(self.ws)['enabled'])

    def test_auto_uses_separate_backend_and_preserves_pending(self):
        class ImmediateThread:
            def __init__(self, *, target, **kwargs):
                self.target = target
            def start(self):
                self.target()
        backend = mock.Mock()
        backend.ask.return_value = json.dumps({'changes': [self.change()]}, ensure_ascii=False)
        dream.set_auto(self.ws, True)
        with mock.patch.object(dream.threading, 'Thread', ImmediateThread), \
             mock.patch('feiyu.providers.build_backend', return_value=backend):
            self.assertTrue(dream.schedule(self.ws, {'model': 'x'}))
            self.assertEqual(len(dream.load(self.ws)['changes']), 1)
            self.assertEqual(memory.load(self.ws), [])
            self.assertTrue(dream.schedule(self.ws, {'model': 'x'}))
            self.assertEqual(backend.ask.call_count, 1)

    def test_manual_command_review_and_apply(self):
        from feiyu import __main__ as cli
        backend = mock.Mock()
        backend.ask.return_value = json.dumps({'changes': [self.change()]}, ensure_ascii=False)
        agent = SimpleNamespace(toolbox=SimpleNamespace(root=self.ws), ready=True,
                                session_id='current', _side_backend=lambda: backend,
                                _refresh_system=mock.Mock())
        with mock.patch.object(session, 'save'):
            self.assertIn('用户明确要求', cli._dream(agent, 'run'))
        self.assertEqual(memory.load(self.ws), [])
        self.assertIn('已应用', cli._dream(agent, 'apply'))
        agent._refresh_system.assert_called_once()
        self.assertEqual(memory.load(self.ws)[0][1], '测试使用 pytest')

    def test_background_will_not_overwrite_manual_proposal(self):
        self.prepare([self.change()])
        original = dream.load(self.ws)
        dream.prepare(self.ws, lambda _: json.dumps({'changes': [self.change(new='另一条')]}, ensure_ascii=False),
                      only_if_absent=True)
        self.assertEqual(dream.load(self.ws), original)


if __name__ == '__main__':
    unittest.main()
