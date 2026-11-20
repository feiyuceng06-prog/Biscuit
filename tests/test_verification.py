import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from feiyu import hooks, verification as v, session
from feiyu.providers import ToolOutput
from tests.test_agent import Base, quiet
from tests.fakes import call, unpaired


class VerificationEntrances(Base):
    def setUp(self):
        super().setUp()
        self.agent.verify = 'true'
        self.agent._baseline_done = True
        self.path = Path(self.tmp.name) / 'a.py'
        self.path.write_text('old')

    def verify(self):
        quiet(self.agent._fire, 'PostToolUse', 'write_file', 'a.py')
        return self.agent.verifications.records[-1]

    def test_real_auto_verify_and_log(self):
        self.agent.verify = 'echo success; echo diagnostic >&2'
        r = self.verify()
        self.assertTrue(self.agent.verified_ok)
        self.assertEqual(r['category'], 'post_change')
        self.assertIn('diagnostic', Path(r['log']).read_text())
        self.assertEqual(r['exit_code'], 0)
        self.assertTrue(r['task_id'])
        self.assertEqual(r['cwd'], self.tmp.name)

    def test_external_same_stat_change(self):
        self.verify()
        st = self.path.stat()
        self.path.write_text('new')
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertIsNone(self.agent.verified_ok)
        self.assertEqual(self.agent.verifications.records[-1]['validity'], 'stale')

    def test_verify_itself_changes_code(self):
        self.agent.verify = 'echo changed > a.py'
        r = self.verify()
        self.assertEqual(r['execution'], 'passed')
        self.assertEqual(r['validity'], 'stale')
        self.assertIsNone(self.agent.verified_ok)

    def test_shell_write_restore_still_invalidates(self):
        self.verify()
        quiet(self.agent.toolbox.run, 'bash', {'command': 'true'})
        self.assertIsNone(self.agent.verified_ok)

    def test_mcp_readonly_hint_does_not_preserve_pass(self):
        self.verify()
        with patch.object(self.agent.toolbox.mcp, 'schemas', return_value=[{'name': 'remote', 'input_schema': {'type': 'object'}}]), patch.dict(self.agent.toolbox.mcp.tools, {'remote': {}}), patch.object(
                self.agent.toolbox.mcp, 'call', return_value=('ok', False)):
            self.agent.toolbox.run('remote', {})
        self.assertIsNone(self.agent.verified_ok)

    def test_edit_real_turn_records_baseline_and_post_change(self):
        self.agent._baseline_done = False
        b = self.use([('', [call('w', 'write_file', path='new.py', content='x')]), ('done', [])])
        quiet(self.agent.send, 'write code')
        rows = self.agent.verifications.records
        self.assertEqual([r['category'] for r in rows], ['baseline', 'post_change'])
        self.assertTrue(self.agent.verified_ok)
        self.assertFalse(unpaired(b.messages))

    def test_original_failure_baseline_is_not_current_pass(self):
        self.agent._baseline_done = False
        self.agent.verify = 'exit 3'
        quiet(self.agent._reproduce_first)
        r = self.agent.verifications.records[-1]
        self.assertEqual((r['category'], r['execution'], r['exit_code']), ('baseline', 'failed', 3))
        self.assertIsNone(self.agent.verified_ok)

    def test_failure_and_timeout(self):
        self.agent.verify = 'echo fail >&2; exit 7'
        r = self.verify()
        self.assertEqual(r['execution'], 'failed')
        self.assertFalse(self.agent.verified_ok)
        h = hooks.Hook('PostToolUse', {'command': 'sleep 2', 'timeout': 1}, 'verify:')
        self.agent.verify = h.command
        quiet(self.agent._run_verification, h, {}, 'post_change')
        r = self.agent.verifications.records[-1]
        self.assertTrue(r['timed_out'])
        self.assertEqual(r['exit_code'], -9)
        self.assertEqual(r['execution'], 'unknown')
        self.assertIsNone(self.agent.verified_ok)

    def test_cancellation_records_before_propagation(self):
        import threading
        self.agent.verify = 'sleep 30'
        self.agent._control()
        timer = threading.Timer(.15, self.agent.cancel)
        timer.start()
        try:
            with self.assertRaises(KeyboardInterrupt):
                self.verify()
        finally:
            timer.cancel()
        self.assertTrue(self.agent.verifications.records[-1]['cancelled'])

    def test_missing_shell_is_environment_blocked(self):
        with patch.object(hooks.sandbox, 'wrap', return_value=None), patch.object(hooks.sandbox, 'SHELL', '/not/a/shell'):
            r = self.verify()
        self.assertEqual(r['execution'], 'environment_blocked')
        self.assertIsNone(self.agent.verified_ok)

    def test_cwd_config_and_log_consumption(self):
        self.verify()
        folder = Path(self.tmp.name) / 'sub'
        folder.mkdir()
        self.agent.toolbox.cwd = folder
        self.assertIsNone(self.agent.verified_ok)
        self.verify()
        self.agent.context_text += ' changed'
        self.assertIsNone(self.agent.verified_ok)
        r = self.verify()
        Path(r['log']).unlink()
        self.assertIsNone(self.agent.verified_ok)

    def test_background_job_prevents_current_pass(self):
        self.agent.toolbox.run('bash', {'command': 'sleep 2', 'background': True})
        try:
            from feiyu.taskstate import PersistenceError
            with self.assertRaises(PersistenceError):
                self.verify()
            self.assertIsNone(self.agent.verified_ok)
        finally:
            for job in self.agent.toolbox.jobs.running():
                job.kill()

    def test_session_snapshot_and_restore_never_reuses_pass(self):
        self.use([('done', [])])
        quiet(self.agent.send, 'hello')
        self.verify()
        with patch.object(session, 'DIR', str(Path(self.tmp.name).parent / ('sessions-' + self.agent.task_id))):
            self.addCleanup(__import__('shutil').rmtree, session.DIR, True)
            session.save(self.tmp.name, self.agent, self.agent.session_id)
            data = session.load(self.tmp.name, self.agent.session_id)
        self.path.write_text('new')
        with patch.object(self.agent, 'use_model', return_value=True):
            self.assertTrue(quiet(self.agent.restore, data))
        self.assertIsNone(self.agent.verified_ok)
        self.assertEqual(self.agent.task_id, data['task_id'])

    def test_unknown_scan_and_no_git(self):
        r = v.fingerprint(self.tmp.name, self.tmp.name, {}, max_files=0)
        self.assertIsNone(r['digest'])
        self.assertTrue(v.fingerprint(self.tmp.name, self.tmp.name, {})['digest'])
        (Path(self.tmp.name) / 'external').symlink_to('/etc')
        self.assertIsNone(v.fingerprint(self.tmp.name, self.tmp.name, {})['digest'])

    def test_git_tracked_ignored_and_untracked(self):
        root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        (root / '.gitignore').write_text('a.py\n')
        subprocess.run(['git', '-C', str(root), 'add', '-f', 'a.py'], check=True)
        first = v.fingerprint(root, root, {})['digest']
        self.path.write_text('changed')
        second = v.fingerprint(root, root, {})['digest']
        self.assertNotEqual(first, second)
        (root / 'untracked').write_text('new')
        self.assertNotEqual(second, v.fingerprint(root, root, {})['digest'])

    def test_chat_does_not_show_validation_footer(self):
        self.use([('hello', [])])
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.agent.send('hello')
        self.assertNotIn('验证：', out.getvalue())

    def test_budgets_deleted_files_and_state_overlap(self):
        root = Path(self.tmp.name)
        self.assertIsNone(v.fingerprint(root, root, {}, max_bytes=1)['digest'])
        self.assertIsNone(v.fingerprint(root, root, {}, max_seconds=0)['digest'])
        self.verify()
        self.path.unlink()
        self.assertIsNone(self.agent.verified_ok)
        with patch.object(session, 'DIR', str(root / 'state' / 'sessions')):
            self.assertIsNone(v.fingerprint(root, root, {})['digest'])

    def test_epoch_change_during_verification_even_if_content_restored(self):
        run = hooks.run
        def mutation(*args, **kwargs):
            self.agent.verifications.invalidate()
            return run(*args, **kwargs)
        with patch.object(hooks, 'run', mutation):
            r = self.verify()
        self.assertEqual(r['execution'], 'passed')
        self.assertEqual(r['validity'], 'stale')

    def test_other_hooks_invalidate_and_log_failure_does_not_execute(self):
        self.verify()
        self.agent.hooks = [hooks.Hook('Stop', {'command': 'true'}, 'test')]
        quiet(self.agent._fire, 'Stop')
        self.assertIsNone(self.agent.verified_ok)
        marker = Path(self.tmp.name) / 'must-not-exist'
        self.agent.verify = 'touch ' + str(marker)
        with patch('feiyu.verification.storage', return_value=Path('/dev/null/blocked')):
            r = self.verify()
        self.assertEqual(r['execution'], 'environment_blocked')
        self.assertFalse(marker.exists())

    def test_config_control_and_later_chat(self):
        from feiyu import __main__ as cli
        self.verify()
        with patch.object(cli.sandbox_mod, 'set_level'), patch.object(cli.sandbox_mod, 'effective', return_value=('off', '')):
            quiet(cli._sandbox, 'off', self.agent)
        self.assertIsNone(self.agent.verified_ok)
        self.agent._code_task = False
        self.test_chat_does_not_show_validation_footer()

    def test_restore_old_or_corrupt_snapshot_clears_previous_evidence(self):
        self.verify()
        self.agent.verifications.restore(None)
        self.assertIsNone(self.agent.verified_ok)
        self.verify()
        corrupt = self.agent.verifications.export()
        corrupt['records'][0]['execution'] = []
        self.agent.verifications.restore(corrupt)
        self.assertIsNone(self.agent.verified_ok)

    def test_undo_and_readonly_git_boundaries(self):
        self.verify()
        quiet(self.agent.undo)
        self.assertIsNone(self.agent.verified_ok)
        self.agent._code_task = False
        self.agent.toolbox.run('git', {'action': 'status'})
        self.assertFalse(self.agent._code_task)
