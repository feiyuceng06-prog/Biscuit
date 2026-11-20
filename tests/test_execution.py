"""Stage C exercises product entry points with fake models and real commands."""
from pathlib import Path
import subprocess
from unittest.mock import patch

from feiyu import hooks, permissions, sandbox, subagent
from feiyu.providers import ToolCall
from feiyu.tools import ToolResult
from tests.test_agent import Base, quiet
from tests.fakes import call, unpaired, FakeBackend


class ExecutionPaths(Base):
    def turn(self, calls):
        backend = self.use([('', calls), ('done', [])])
        quiet(self.agent.send, 'work')
        self.assertFalse(unpaired(backend.messages))
        results = [m for m in backend.messages if m['role'] == 'tool']
        self.assertEqual(len(results), len(calls))
        return results

    def test_invalid_parameters_do_not_start_hooks_serial_and_parallel(self):
        for calls in ([call('a', 'write_file', path=42, content='x')],
                      [call('b', 'read_file', path=42), call('c', 'read_file', path=43)]):
            with patch.object(self.agent, '_fire') as fire, patch.object(self.agent.toolbox, '_run_raw') as raw:
                quiet(self.agent._run_tools, calls, [])
                fire.assert_not_called()
                raw.assert_not_called()

    def test_denied_model_does_not_start_hook_or_tool(self):
        permissions.save({'allow': ['Bash(*)'], 'deny': ['Bash(*)']})
        with patch.object(self.agent, '_pre_tool') as pre, patch.object(self.agent.toolbox, '_run_raw') as raw:
            self.turn([call('a', command='touch marker')])
            pre.assert_not_called()
            raw.assert_not_called()
        self.assertFalse((Path(self.tmp.name)/'marker').exists())

    def test_hook_deny_wins_even_for_explicit_verify(self):
        self.agent.verify = 'touch marker'
        permissions.save({'allow': ['Bash(*)'], 'deny': ['Bash(*)']})
        with patch('feiyu.hooks.run') as popen:
            quiet(self.agent._fire, 'PostToolUse', 'write_file', 'a')
            trusted = hooks.Hook('PreToolUse', {'command': 'touch marker'}, 'trusted-project')
            self.assertFalse(self.agent._execute_hook(trusted, {}).ok)
            popen.assert_not_called()
        self.assertFalse(self.agent.verified_ok)
        self.assertEqual(self.agent.toolbox.execution.records[-1]['state'], 'rejected')

    def test_hook_uses_sandbox_and_offline_without_recursive_hook(self):
        self.agent.toolbox.outside = 'web'
        h = hooks.Hook('PreToolUse', {'command': 'true'}, 'trusted-project')
        self.agent.hooks = [h]
        with patch.object(sandbox, 'wrap', return_value=None) as wrap, patch.object(sandbox, 'can_cut_net', return_value=True):
            self.turn([call('a', 'read_file', path='missing')])
        self.assertEqual(wrap.call_count, 1)
        self.assertTrue(wrap.call_args.kwargs['offline'])
        self.assertEqual(wrap.call_args.kwargs['workspace'], self.agent.toolbox.root)

    def test_project_verify_source_not_bypassed_by_auto(self):
        self.agent._verify = 'touch marker'
        self.agent._verify_project = True
        self.agent._verify_decision = None
        self.agent.approve_verify = None
        self.agent.context_file = 'CLAUDE.md'
        with patch.object(hooks, 'allow_verify', return_value=False), patch('feiyu.hooks.subprocess.Popen') as popen:
            quiet(self.agent._fire, 'PostToolUse', 'write_file', 'a')
            popen.assert_not_called()

    def test_mcp_hint_still_guarded_and_serial_and_validated(self):
        name = 'mcp_remote_read'
        registry = self.agent.toolbox.mcp
        registry.tools[name] = ('remote', 'read')
        registry.readonly.add(name)
        schema = {'name': name, 'input_schema': {'type': 'object', 'required': ['path'], 'properties': {'path': {'type': 'string'}}}}
        self.agent.mode = 'default'
        with patch.object(registry, 'schemas', return_value=[schema]), patch.object(registry, 'call') as remote, patch.object(self.agent, '_run_parallel') as parallel:
            self.turn([ToolCall(id='a', name=name, input={}), ToolCall(id='b', name=name, input={'path': 'x'})])
            remote.assert_not_called()
            parallel.assert_not_called()
        self.agent.mode = 'readonly'
        self.assertFalse(self.agent._gate(ToolCall(id='x', name=name, input={}), False)[0])

    def test_image_budget_record_and_no_retry(self):
        image = ('image/png', 'encoded')
        with patch.object(self.agent.toolbox, '_run_raw', return_value=ToolResult('x'*40000, image=image)) as raw:
            result = self.agent.toolbox.run('read_file', {'path': 'a'})
            self.assertTrue(result.truncated)
            self.assertEqual(result.image, image)
            self.assertEqual(raw.call_count, 1)
        with patch.object(self.agent.toolbox, '_run_raw', side_effect=RuntimeError('failed')) as raw:
            self.turn([call('a', 'write_file', path='a', content='x')])
            self.assertEqual(raw.call_count, 1)
        self.assertEqual(self.agent.toolbox.execution.records[-1]['state'], 'unknown')

    def test_model_origin_field_cannot_bypass_deny(self):
        permissions.save({'allow': [], 'deny': ['Bash(*)']})
        self.turn([call('a', command='touch marker', origin='user')])
        self.assertFalse((Path(self.tmp.name)/'marker').exists())

    def test_background_start_cancel_actual_path(self):
        self.turn([call('a', command='sleep 30', background=True)])
        jobs = self.agent.toolbox.jobs.running()
        self.assertEqual(len(jobs), 1)
        self.turn([call('kill', 'job', action='kill', id=jobs[0].id)])
        self.assertFalse(jobs[0].running)
        self.assertEqual(jobs[0].op['state'], 'cancelled')
        self.assertTrue(any(r['name'] == 'bash' and r['state'] == 'running' for r in self.agent.toolbox.execution.records))

    def test_readonly_investigation_respects_deny(self):
        backend = FakeBackend([('', [call('a', 'read_file', path='secret')]), ('report', [])])
        permissions.save({'allow': [], 'deny': ['Read(*)']})
        with patch('feiyu.providers.build_backend', return_value=backend), patch('feiyu.tools.Toolbox._run_raw') as raw:
            subagent.run('question', entry={}, workspace=Path(self.tmp.name))
            raw.assert_not_called()
        self.assertFalse(unpaired(backend.messages))

    def test_hook_exact_approval_is_not_broad_allow(self):
        self.agent.mode = 'default'
        self.agent.approve = lambda *_: 'remember'
        permissions.save({'allow': [], 'deny': []})
        h = hooks.Hook('PreToolUse', {'command': 'true'}, 'project')
        with patch.object(hooks, 'run', return_value=hooks.Outcome(h, 0, '')) as run:
            self.assertTrue(self.agent._execute_hook(h, {}).ok)
            self.agent.approve = None
            self.assertTrue(self.agent._execute_hook(h, {}).ok)
            changed = hooks.Hook('PreToolUse', {'command': 'echo other'}, 'project')
            self.assertFalse(self.agent._execute_hook(changed, {}).ok)
            self.assertEqual(run.call_count, 2)
        self.assertEqual(permissions.load()['allow'], [])
        self.agent.reset()
        self.assertFalse(self.agent._execute_hook(h, {}).ok)

    def test_cancelled_model_call_is_paired_and_recorded(self):
        with patch.object(self.agent.toolbox, '_run_raw', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.turn([call('a', 'read_file', path='a'), call('b', 'write_file', path='b', content='x')])
        self.assertFalse(unpaired(self.agent.backend.messages))
        self.assertEqual(self.agent.toolbox.execution.records[-1]['state'], 'cancelled')
        self.assertFalse((Path(self.tmp.name)/'b').exists())

    def test_true_reads_parallel_mixed_writes_serial(self):
        import threading
        threads = []
        barrier = threading.Barrier(2)
        def read(name, args):
            threads.append(threading.current_thread().name)
            barrier.wait(timeout=3)
            return ToolResult('image', image=('image/png', 'encoded'))
        with patch.object(self.agent.toolbox, '_run_raw', side_effect=read):
            results = self.turn([call('a', 'read_file', path='a'), call('b', 'read_file', path='b')])
        self.assertEqual(len(set(threads)), 2)
        images = [part for m in self.agent.backend.messages if m['role'] == 'user' and isinstance(m['content'], list) for part in m['content'] if part['type'] == 'image_url']
        self.assertEqual(len(images), 2)
        threads.clear()
        def write(name, args):
            threads.append(threading.current_thread().name)
            return ToolResult('ok')
        with patch.object(self.agent.toolbox, '_run_raw', side_effect=write):
            self.turn([call('c', 'read_file', path='a'), call('d', 'write_file', path='b', content='x')])
        self.assertEqual(set(threads), {threading.current_thread().name})

    def test_mcp_union_boolean_and_invalid_schema_are_paired(self):
        name = 'mcp_remote_union'
        registry = self.agent.toolbox.mcp
        registry.tools[name] = ('remote', 'union')
        for field, value, executed in [({'type': ['string', 'null']}, None, True),
                                       (True, 'anything', True), (False, 'x', False),
                                       ({'type': {'bad': 'type'}}, 'x', False)]:
            schema = {'name': name, 'input_schema': {'type': 'object', 'properties': {'x': field}}}
            with patch.object(registry, 'schemas', return_value=[schema]), patch.object(registry, 'call', return_value=('ok', False)) as remote:
                results = self.turn([ToolCall(id='union', name=name, input={'x': value})])
                self.assertEqual(remote.called, executed)
                self.assertNotIn('esc', results[0]['content'])

    def test_hook_yes_is_single_use(self):
        self.agent.mode = 'default'
        permissions.save({'allow': [], 'deny': []})
        h = hooks.Hook('PreToolUse', {'command': 'printf x >> count'}, 'project')
        self.agent.approve = lambda *_: 'yes'
        self.assertTrue(self.agent._execute_hook(h, {}).ok)
        self.agent.approve = lambda *_: 'no'
        self.assertFalse(self.agent._execute_hook(h, {}).ok)
        self.assertEqual((self.agent.toolbox.root / 'count').read_text(), 'x')

    def test_rejected_verify_is_not_execution_failure(self):
        self.agent.verify = 'touch marker'
        permissions.save({'allow': [], 'deny': ['Bash(*)']})
        quiet(self.agent._fire, 'PostToolUse', 'write_file', 'a')
        record = self.agent.verifications.records[-1]
        self.assertEqual(record['execution'], 'not_run')
        self.assertIsNone(record['exit_code'])
        self.assertTrue(record['rejected'])
        self.assertFalse((self.agent.toolbox.root / 'marker').exists())

    def test_real_pre_hook_policy_change_blocks_serial_and_parallel(self):
        import json
        import os
        import shlex
        import sys
        root = self.agent.toolbox.root
        (root / 'secret').write_text('isolated-secret')
        script = root / 'policy.py'
        script.write_text('from pathlib import Path\nPath(' + repr(permissions.STORE) + ').write_text(' +
                          repr(json.dumps({'allow': [], 'deny': ['Read(*)']})) + ')\n')
        h = hooks.Hook('PreToolUse', {'matcher': 'Read', 'command': shlex.join([sys.executable, str(script)])}, 'global')
        self.agent.hooks = [h]
        with patch.dict(os.environ, {'FEIYU_SANDBOX': 'off'}):
            for calls in ([call('one', 'read_file', path='secret')],
                          [call('one', 'read_file', path='secret'), call('two', 'read_file', path='secret')]):
                permissions.save({'allow': ['Read(*)'], 'deny': []})
                results = self.turn(calls)
                self.assertTrue(all('isolated-secret' not in r['content'] for r in results))
                self.assertTrue(all('权限规则' in r['content'] for r in results))

    def test_pre_hook_new_egress_requires_new_approval(self):
        self.agent.mode = 'auto'
        with patch.object(self.agent, '_egress', side_effect=lambda _: 'new boundary' if self.agent.toolbox.outside else ''), \
             patch.object(self.agent, '_pre_tool', side_effect=lambda _: setattr(self.agent.toolbox, 'outside', 'new') or ''), \
             patch.object(self.agent.toolbox, '_run_raw') as raw:
            self.turn([call('one', command='echo hello')])
            raw.assert_not_called()

    def test_real_hook_sandbox_allows_workspace_but_blocks_outside(self):
        import os
        import shlex
        import tempfile
        if not sandbox.available():
            self.skipTest('bwrap unavailable')
        with tempfile.TemporaryDirectory(dir='/var/tmp') as folder:
            outside = Path(folder) / 'blocked'
            inside = self.agent.toolbox.root / 'allowed'
            with patch.dict(os.environ, {'FEIYU_SANDBOX': 'workspace'}):
                good = hooks.Hook('PreToolUse', {'command': 'printf ok > ' + shlex.quote(str(inside))}, 'global')
                bad = hooks.Hook('PreToolUse', {'command': 'printf bad > ' + shlex.quote(str(outside))}, 'global')
                self.assertTrue(self.agent._execute_hook(good, {}).ok)
                self.assertFalse(self.agent._execute_hook(bad, {}).ok)
            self.assertEqual(inside.read_text(), 'ok')
            self.assertFalse(outside.exists())
