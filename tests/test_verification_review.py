"""Stage B independent-review regressions; real Git/processes, no model calls."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from feiyu import hooks, session, verification as v, lsp
from tests.test_agent import Base, quiet


class ReviewEntrances(Base):
    def setUp(self):
        super().setUp()
        self.agent.verify = 'true'
        self.agent._baseline_done = True
        self.path = Path(self.tmp.name) / 'a.py'
        self.path.write_text('old')

    def verify(self):
        quiet(self.agent._fire, 'PostToolUse', 'write_file', 'a.py')
        return self.agent.verifications.records[-1]

    def test_git_executable_configuration_marker(self):
        root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'add', 'a.py'], check=True)
        marker = root / '.git/marker'
        script = root / '.git/monitor'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nprintf "token\\000"\n')
        script.chmod(0o700)
        subprocess.run(['git', '-C', str(root), 'config', 'core.fsmonitor', str(script)], check=True)
        subprocess.run(['git', '-C', str(root), 'ls-files'], stdout=subprocess.DEVNULL, check=True)
        self.assertTrue(marker.exists(), 'reproducer must actually execute monitor')
        marker.unlink()
        self.assertTrue(v.fingerprint(root, root, {})['digest'])
        self.assertFalse(marker.exists())

    def test_ignore_sources_even_when_inventory_unchanged(self):
        root = Path(self.tmp.name)
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        exclude = root / '.git/info/exclude'
        first = v.fingerprint(root, root, {})['digest']
        exclude.write_text('# different comment, same inventory\n')
        second = v.fingerprint(root, root, {})['digest']
        self.assertTrue(first and second)
        self.assertNotEqual(first, second)
        with tempfile.TemporaryDirectory() as external:
            source = Path(external) / 'ignore'
            source.write_text('# external\n')
            for key in ('core.excludesFile', 'include.path'):
                source.write_text('# valid config or ignore\n')
                subprocess.run(['git', '-C', str(root), 'config', key, str(source)], check=True)
                self.assertIsNone(v.fingerprint(root, root, {})['digest'])
                source.write_text('# changed without affecting listing\n')
                self.assertIsNone(v.fingerprint(root, root, {})['digest'])
                subprocess.run(['git', '-C', str(root), 'config', '--unset', key], check=True)

    def test_new_session_bot_clear_and_owner_checks(self):
        from feiyu import serve, __main__ as cli
        self.use([])
        server = serve.Server(self.agent, Path(self.tmp.name), self.agent.trace, serve.Protocol(io.StringIO()))
        for action in (server.new_session, lambda: server._dispatch(cli, '/clear', ''),
                       lambda: cli._bot(self.agent, Path(self.tmp.name), 'off')):
            self.verify()
            old_task = self.agent.task_id
            quiet(action)
            self.assertNotEqual(old_task, self.agent.task_id)
            self.assertFalse(self.agent.verifications.records)
            self.assertFalse(self.agent._baseline_done)
            self.assertFalse(self.agent._code_task)
            self.assertIsNone(self.agent.verified_ok)
        self.verify()
        self.agent.session_id = session.new_id()
        self.assertIsNone(self.agent.verified_ok)
        self.assertIn('未运行', self.agent.verification_summary())

    def test_cli_clear_actual_main_loop(self):
        from feiyu import __main__ as cli
        self.use([])
        self.verify()
        old = self.agent.task_id
        with patch.object(sys, 'argv', ['feiyu', '-w', self.tmp.name]), \
             patch.object(cli, 'Feiyu', return_value=self.agent), \
             patch.object(sys.stdin, 'isatty', return_value=True), \
             patch.object(cli.ide_mod, 'Link'), \
             patch.object(cli.ui, 'enter_screen'), \
             patch.object(cli.ui, 'InputBox') as box, \
             patch.object(cli, '_finish', return_value=0):
            box.return_value.ask.side_effect = ['/clear', '/exit']
            self.assertEqual(quiet(cli.main), 0)
        self.assertNotEqual(old, self.agent.task_id)
        self.assertFalse(self.agent.verifications.records)
        self.assertFalse(self.agent._baseline_done)

    def test_budget_stop_retains_pending_until_completion(self):
        from tests.fakes import call
        self.use([('', [call('w', 'write_file', path='new.py', content='x')])])
        with patch.object(self.agent, '_over_budget', return_value='test budget'):
            quiet(self.agent.send, 'write')
        self.assertTrue(self.agent._code_task)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.agent.send('finish summary')
        self.assertIn('验证：', out.getvalue())
        self.assertFalse(self.agent._code_task)

    def test_model_switch_retains_task_and_ledger(self):
        from feiyu import agent as mod, keys
        from tests.fakes import FakeBackend
        self.use([])
        self.verify()
        task = self.agent.task_id
        with patch.object(keys, 'load', return_value={'new': {}}), patch.object(mod, 'build_backend', return_value=FakeBackend([])):
            self.assertTrue(self.agent.use_model('new'))
        self.assertEqual(task, self.agent.task_id)
        self.assertTrue(self.agent.verifications.records)

    def test_write_interrupt_save_resume_summary_then_chat(self):
        from tests.fakes import call
        self.use([('', [call('w', 'write_file', path='new.py', content='x')])])
        with patch.object(self.agent.backend, 'run_turn', wraps=self.agent.backend.run_turn) as turn:
            original = turn._mock_wraps
            n = [0]
            def run(*args, **kwargs):
                n[0] += 1
                if n[0] == 2:
                    raise KeyboardInterrupt()
                return original(*args, **kwargs)
            turn.side_effect = run
            with self.assertRaises(KeyboardInterrupt):
                quiet(self.agent.send, 'write')
        self.assertTrue(self.agent._code_task)
        with tempfile.TemporaryDirectory() as state, patch.object(session, 'DIR', state):
            session.save(self.tmp.name, self.agent, self.agent.session_id)
            data = session.load(self.tmp.name, self.agent.session_id)
        self.agent.reset()
        with patch.object(self.agent, 'use_model', return_value=True):
            quiet(self.agent.restore, data)
        self.assertTrue(self.agent._code_task)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.agent.send('just summarize completion')
        self.assertIn('验证：', out.getvalue())
        self.assertFalse(self.agent._code_task)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.agent.send('hello')
        self.assertNotIn('验证：', out.getvalue())

    def test_real_lsp_process_write_restore_and_live_server(self):
        # Minimal local JSON-RPC server: writes/restores before responding and
        # stays alive. Exercises Pool/Client via the actual symbol tool.
        script = Path(self.tmp.name) / 'server.py'
        script.write_text('''import sys,json,pathlib
p=pathlib.Path('a.py'); old=p.read_bytes(); p.write_text('changed'); p.write_bytes(old)
while True:
 line=sys.stdin.buffer.readline()
 if not line: break
 if not line.lower().startswith(b'content-length:'): continue
 n=int(line.split(b':')[1]); sys.stdin.buffer.readline(); msg=json.loads(sys.stdin.buffer.read(n))
 if 'id' in msg:
  result={'capabilities':{}} if msg['method']=='initialize' else []
  raw=json.dumps({'jsonrpc':'2.0','id':msg['id'],'result':result}).encode()
  sys.stdout.buffer.write(b'Content-Length: '+str(len(raw)).encode()+b'\\r\\n\\r\\n'+raw);sys.stdout.buffer.flush()
''')
        self.verify()
        epoch = self.agent.verifications.epoch
        with patch.object(lsp, 'server_for', return_value=[sys.executable, str(script)]):
            try:
                result = self.agent.toolbox.run('symbol', {'action': 'outline', 'path': 'a.py'})
                self.assertFalse(result.is_error, result.content)
                self.assertGreater(self.agent.verifications.epoch, epoch)
                self.assertEqual(self.path.read_text(), 'old')
                self.assertIsNone(self.agent.verified_ok)
                self.assertEqual(self.verify()['validity'], 'unknown')
            finally:
                self.agent.toolbox.lsp.close()

    def test_fsync_failure_keeps_execution_and_exit_code(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        # Target the diagnostic log, not the new critical journal's shared os module.
        log_os = SimpleNamespace(**dict(vars(os), fsync=Mock(side_effect=OSError('injected disk failure'))))
        with patch.object(hooks, 'os', log_os):
            row = self.verify()
        self.assertEqual(row['execution'], 'passed')
        self.assertEqual(row['exit_code'], 0)
        self.assertEqual(row['validity'], 'unknown')
        self.assertTrue(row['evidence_error'])
        self.assertFalse(row['environment_error'])
        self.assertIn('命令已执行', self.agent.verification_summary())

    def test_large_output_and_real_descendant_timeout_cancel(self):
        for cancel in (False, True):
            marker = Path(self.tmp.name) / ('late-' + str(cancel))
            self.agent.verify = '(sleep 2; touch ' + str(marker) + ') & python3 -c "print(\'x\'*2000000)"; wait'
            hook = hooks.Hook('PostToolUse', {'command': self.agent.verify, 'timeout': 1}, 'verify:')
            # Each interrupted verification leaves unresolved effects. Use a new
            # task only after an explicit synthetic-fixture acknowledgement.
            import threading
            self.agent._control()
            timer = threading.Timer(.6, self.agent.cancel)
            if cancel:
                timer.start()
                try:
                    with self.assertRaises(KeyboardInterrupt):
                        quiet(self.agent._run_verification, hook, {}, 'post_change')
                finally:
                    timer.cancel()
            else:
                quiet(self.agent._run_verification, hook, {}, 'post_change')
            row = self.agent.verifications.records[-1]
            self.assertTrue(row['cancelled'] if cancel else row['timed_out'])
            self.assertGreater(Path(row['log']).stat().st_size, 2000000)
            time.sleep(2.1)
            self.assertFalse(marker.exists(), 'descendant escaped process-group cleanup')
            for op in self.agent.task_state.operations:
                if op['state'] == 'unknown':
                    self.agent._task_store.resolve(self.agent.task_state, op['id'], 'synthetic fixture cleaned')
            self.agent._control().cancelled.clear()


@unittest.skipUnless(os.name == 'posix', 'requires POSIX descriptor primitives')
class DescriptorRaceTests(unittest.TestCase):
    def test_fifo_symlink_and_parent_replacement_in_bounded_real_process(self):
        script = r'''
import os, pathlib, tempfile
from unittest.mock import patch
from feiyu import verification as v
with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as outside:
 root=pathlib.Path(work); parent=root/'sub'; parent.mkdir(); target=parent/'a.py'; target.write_text('old')
 external=pathlib.Path(outside)/'a.py'; external.write_text('SECRET-NEVER-READ')
 original=os.open; read=os.read; fired=[False]; external_inode=external.stat().st_ino
 def injecting(path, flags, *args, **kw):
  if str(path)=='a.py' and not fired[0]:
   fired[0]=True
   if MODE=='fifo': target.unlink(); os.mkfifo(target)
   elif MODE=='link': target.unlink(); target.symlink_to(external)
   else: parent.rename(root/'detached'); parent.symlink_to(outside, target_is_directory=True)
  return original(path,flags,*args,**kw)
 def guarded(fd,n):
  assert os.fstat(fd).st_ino != external_inode, 'external data read'
  return read(fd,n)
 with patch.object(os,'open',injecting), patch.object(os,'read',guarded):
  result=v.fingerprint(root,root,{})
 assert fired[0], 'injection did not run'
 assert result['digest'] is None, result
'''
        for mode in ('fifo', 'link', 'parent'):
            with self.subTest(mode=mode):
                done = subprocess.run([sys.executable, '-c', 'MODE=' + repr(mode) + '\n' + script],
                                      capture_output=True, text=True, timeout=8)
                self.assertEqual(done.returncode, 0, done.stderr)
