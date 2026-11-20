import contextlib
import io
import json
import os
from pathlib import Path
import queue
import shlex
import tempfile
import unittest
from unittest import mock

from feiyu import enabled, hooks, keys, permissions, serve
from feiyu.agent import Feiyu
from feiyu.providers import ToolCall


class ProjectVerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        # Source consent is independent of the hook filesystem sandbox.
        self.marker = self.workspace / "verification-marker.txt"
        self.command = "printf verified > " + shlex.quote(self.marker.as_posix())
        self.context = self.workspace / "AGENTS.md"
        self.context.write_text("verify: " + self.command + "\n", encoding="utf-8")
        for module, attribute, value in (
            (hooks, "VERIFY_TRUST", str(self.base / "config" / "trusted-verify.json")),
            (keys, "STORE", str(self.base / "models.json")),
            (keys, "STATE", str(self.base / "state.json")),
            (permissions, "STORE", str(self.base / "permissions.json")),
            (permissions, "_DIR", str(self.base)),
            (enabled, "STORE", str(self.base / "enabled.json")),
        ):
            patcher = mock.patch.object(module, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, agent):
        agent.approve = lambda *args: "yes"
        if (self.workspace / "new.txt").exists():
            agent.toolbox.run("read_file", {"path": "new.txt"})
        with contextlib.redirect_stdout(io.StringIO()):
            outputs = []
            agent._run_serial([ToolCall("w", "write_file", {"path": "new.txt", "content": "test"})],
                              outputs)
            agent._fire("PostToolUse", tool="write_file", subject="new.txt")
        self.assertFalse(outputs[0].is_error)

    def test_edit_approval_does_not_authorize_project_command(self):
        for mode in ("default", "auto"):
            with self.subTest(mode=mode):
                agent = Feiyu(self.workspace)
                agent.mode = mode
                self.write(agent)
                self.assertFalse(self.marker.exists())
                self.assertTrue((self.workspace / "new.txt").exists())
                self.assertIsNone(agent.verified_ok)

    def test_denial_covers_baseline_and_post_write_without_repeated_questions(self):
        agent = Feiyu(self.workspace)
        approve = mock.Mock(return_value=False)
        agent.approve_verify = approve
        self.write(agent)
        self.write(agent)
        approve.assert_called_once_with(str(self.context.resolve()), self.command)
        self.assertFalse(self.marker.exists())

    def test_consent_is_private_persistent_and_bound_to_context_content(self):
        agent = Feiyu(self.workspace)
        approve = mock.Mock(return_value=True)
        agent.approve_verify = approve
        self.write(agent)
        self.assertEqual(self.marker.read_text(), "verified")
        approve.assert_called_once()
        if os.name != "nt":
            self.assertEqual(os.stat(hooks.VERIFY_TRUST).st_mode & 0o777, 0o600)
        self.marker.unlink()
        restored = Feiyu(self.workspace)
        restored.approve_verify = mock.Mock(return_value=False)
        self.write(restored)
        restored.approve_verify.assert_not_called()
        self.assertTrue(self.marker.exists())
        self.marker.unlink()
        self.context.write_text("verify: " + self.command + "\n# changed\n", encoding="utf-8")
        restored.reload_context()
        self.write(restored)
        restored.approve_verify.assert_called_once()
        self.assertFalse(self.marker.exists())

    def test_changed_command_requires_new_consent(self):
        agent = Feiyu(self.workspace)
        agent.approve_verify = mock.Mock(return_value=True)
        self.write(agent)
        self.marker.unlink()
        self.context.write_text("verify: " + self.command + " changed\n", encoding="utf-8")
        agent.reload_context()
        agent.approve_verify = mock.Mock(return_value=False)
        self.write(agent)
        agent.approve_verify.assert_called_once()
        self.assertFalse(self.marker.exists())

    def test_explicit_verify_command_can_enable_and_disable_without_project_trust(self):
        agent = Feiyu(self.workspace)
        agent.approve_verify = mock.Mock(return_value=False)
        self.assertTrue(agent.load_verify())
        from feiyu.__main__ import _verify
        _verify(agent, self.command)
        self.write(agent)
        self.assertTrue(self.marker.exists())
        self.marker.unlink()
        _verify(agent, "off")
        self.write(agent)
        self.assertFalse(self.marker.exists())
        agent.approve_verify.assert_called_once()

    def test_startup_protocol_can_receive_verify_reply_before_main_loop(self):
        incoming = queue.Queue()
        seen = []

        class Input:
            def __iter__(self):
                while True:
                    try:
                        yield incoming.get(timeout=2)
                    except queue.Empty:
                        return

        class Output:
            def write(self, line):
                event = json.loads(line)
                seen.append(event)
                if event["kind"] == "ask":
                    incoming.put(json.dumps({"op": "reply", "id": event["id"], "value": "yes"}))
                if event["kind"] == "hello":
                    incoming.put('{"op":"stop"}')

            def flush(self):
                pass

        agent = Feiyu(self.workspace)
        with mock.patch("sys.stdin", Input()), mock.patch("sys.stdout", Output()), \
                mock.patch.object(serve, "REPLY_TIMEOUT", 1), \
                mock.patch.object(agent, "load_hooks", return_value=""), \
                mock.patch.object(agent, "load_mcp", return_value=""), \
                mock.patch.object(agent, "load_skills", return_value=""):
            result = serve.serve(agent, self.workspace, agent.trace, trusted=True)
        self.assertEqual(result, 0)
        requests = [event for event in seen if event["kind"] == "ask"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["what"], "verify")
        self.assertEqual(requests[0]["names"], [self.command])
        self.assertTrue(agent._verify_decision)
        self.assertFalse(self.marker.exists())  # Trusting never runs the command itself.
