import json
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from feiyu.presentations import generate
from feiyu.serve import Server


class PresentationTests(unittest.TestCase):
    def test_bad_outline_never_replaces_a_draft(self):
        agent = SimpleNamespace(ready=True, backend=object(), _model_call=Mock(return_value='{"slides":[]}'))
        with self.assertRaisesRegex(ValueError, "格式不完整"):
            generate(agent, {"action": "outline", "count": 8})
        self.assertEqual(agent._model_call.call_args.args[:2], (agent.backend, "ask"))

    def test_no_model_gives_actionable_message(self):
        with self.assertRaisesRegex(ValueError, "配置"):
            generate(SimpleNamespace(ready=False), {"action": "outline", "count": 1})

    def test_only_idle_desktop_requests_enter_the_model_queue(self):
        for trusted, busy in ((False, False), (True, True), (True, False)):
            with self.subTest(trusted=trusted, busy=busy):
                server = SimpleNamespace(trusted=trusted, busy=busy, inbox=queue.Queue(), proto=Mock())
                line = json.dumps({"op": "presentation", "ticket": "r1"})
                Server._dispatch_in(server, line)
                if trusted and not busy:
                    self.assertEqual(server.inbox.get_nowait(), ("presentation", line))
                else:
                    self.assertTrue(server.inbox.empty())
                    self.assertEqual(server.proto.send.call_args.kwargs["ticket"], "r1")
