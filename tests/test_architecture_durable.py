"""Durable boundaries, actual child processes and v2 measurement integration."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from evals import architecture as a
from evals import architecture_authorization as auth
from evals import architecture_measurement as measurement
from evals import architecture_durable as d
from tests.test_architecture_authorization import fixture


def inputs():
    p = fixture()['plan']
    p.update(issued_at=time.time()-60, expires_at=time.time()+3600, schema_version=2,
             prompt_semantics='initial_constructor_and_system_not_full_requests')
    static = dict(runtime=d.environment(), config=copy.deepcopy(a.CONTRACT))
    p['measurement_lock'] = auth.digest(static)
    p['source_lock']['snapshot'] = auth.digest(a.source_lock())
    approval = dict(approved=True, approver='SYNTHETIC test only', record_id='SYNTHETIC-record',
                    plan_sha256=auth.digest(p), granted_at=time.time()-1, expires_at=time.time()+1800)
    receipt = auth.require_remote_contract(dict(plan=p, fee_authorization=approval), p)
    receipt.update(measurement_lock=p['measurement_lock'], trust='local_remeasurement_not_host_attestation')
    return p, approval, receipt, dict(static=static)


def call(c, observation='head/executor/development/0', request='one', **kwargs):
    p = c.run['plan']
    params = dict(model=p['model']['version'], **{k:p['sampling'][k] for k in ('temperature','top_p','seed')})
    return c.invoke_fake(observation, request, 1, 'primary', params, 'actual system', **kwargs)


class DurableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = inputs()

    def setUp(self):
        evidence = os.environ.get('FEIYU_DURABLE_EVIDENCE')
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName+'-', dir=evidence))
        else:
            self.tmp = tempfile.TemporaryDirectory()
            self.addCleanup(self.tmp.cleanup)
            self.root = Path(self.tmp.name)
        self.commands = []
        self.registry = self.root/'registry'
        self.seed = list(copy.deepcopy(self.seed))

    def opened(self):
        c = d.Controller(self.registry)
        c._consume(*copy.deepcopy(self.seed))
        self.addCleanup(c.close)
        return c

    def child(self, code, expected=0):
        seed = self.root/'seed.json'; seed.write_text(json.dumps(self.seed))
        prelude = ('from tests.test_architecture_durable import *\n'
                   'root=Path('+repr(str(self.registry))+')\n'
                   'seed=auth.load(Path('+repr(str(seed))+'))\n')
        result = subprocess.run([sys.executable, '-c', prelude+code], capture_output=True, text=True, timeout=40)
        self.commands.append(dict(argv=[sys.executable, '-c', prelude+code], cwd=os.getcwd(),
            env=dict(os.environ), exit_code=result.returncode, expected=expected,
            stdout=result.stdout, stderr=result.stderr))
        (self.root/'commands.json').write_text(json.dumps(self.commands, indent=2))
        self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
        return result

    def test_single_writer_and_reuse_conflicts(self):
        c = self.opened()
        self.child("try: d.Controller(root)\nexcept BlockingIOError: pass\nelse: raise RuntimeError('concurrent writer admitted')")
        c.close()
        self.child("with d.Controller(root) as c:\n c.resume(seed[0]['run_id'])\n try: c._consume(*seed)\n except auth.RemoteBlocked: pass\n else: raise RuntimeError('reuse admitted')")
        with d.Controller(self.registry) as c:
            for index in (0, 1):
                seed = copy.deepcopy(self.seed)
                if index == 0: seed[0]['run_id'] += '-new'
                else: seed[1]['record_id'] += '-new'
                seed[1]['plan_sha256'] = auth.digest(seed[0])
                seed[2]['plan_sha256'] = auth.digest(seed[0]); seed[2]['authorization_sha256'] = auth.digest(seed[1])
                with self.assertRaises(auth.RemoteBlocked): c._consume(*seed)

    def test_crash_before_after_consumption_and_reservation_dispatch(self):
        self.child("c=d.Controller(root)\ndef crash(*args): os._exit(71)\nd.os.replace=crash\nc._consume(*seed)", 71)
        self.assertFalse((self.registry/'registry.json').exists())
        self.child("c=d.Controller(root); c._consume(*seed); os._exit(72)", 72)
        self.child("with d.Controller(root) as c:\n c.resume(seed[0]['run_id'])\n if c.run['entries']: raise RuntimeError('unexpected request')")
        for sent in (False, True):
            registry = self.root/('sent' if sent else 'reserved')
            self.registry = registry
            code = "c=d.Controller(root); c._consume(*seed)\n"
            code += ("original=c._physical\ndef crash(*args):\n original(*args)\n (root/'physical-marker').write_text('sent')\n os._exit(74)\n" if sent else
                     "def crash(*args): os._exit(73)\n")
            code += 'c._physical=crash\ncall(c)'
            self.child(code, 74 if sent else 73)
            self.child("with d.Controller(root) as c:\n c.resume(seed[0]['run_id'])\n if c.run['entries'][0]['state']!='unknown': raise RuntimeError('unknown lost')\n try: call(c)\n except d.Blocked: pass\n else: raise RuntimeError('replayed')")
            self.assertEqual((registry/'physical-marker').exists(), sent)

    def test_known_failure_partial_unknown_and_global_count(self):
        for outcome in ('ok', 'failed', 'partial', 'unknown'):
            self.registry = self.root/outcome
            c = self.opened()
            first = call(c, outcome=outcome)
            self.assertIsNone(first['supplier_invoice'])
            if outcome in ('partial', 'unknown'):
                self.assertIsNone(first['cost_cny'])
                with self.assertRaises(d.Blocked): call(c, request='two')
            else:
                self.assertGreater(first['cost_cny'], 0)
                with self.assertRaises(auth.RemoteBlocked): call(c)
                call(c, observation='snapshot/recovery/holdout/5', request='aux')
                with self.assertRaises(d.Blocked): call(c, request='third')
            c.close()
            with d.Controller(self.registry) as recovered:
                r = recovered.resume(self.seed[0]['run_id'])
                self.assertEqual(r['entries'][0], first)

    def test_failed_resume_poison_and_slow_observation_reservation(self):
        c = self.opened()
        c.close()
        with d.Controller(self.registry) as c:
            with patch.object(a, 'source_lock', return_value={}):
                with self.assertRaises(auth.RemoteBlocked): c.resume(self.seed[0]['run_id'])
            with patch.object(c, '_physical') as physical:
                with self.assertRaises(d.PersistenceFailure): call(c)
                with self.assertRaises(d.PersistenceFailure): c.resume(self.seed[0]['run_id'])
                physical.assert_not_called()
        self.registry = self.root/'slow'
        c = self.opened()
        original = c._save
        clock = time.monotonic()
        def slow_save():
            nonlocal clock
            original()
            clock += c.run['bundle']['static']['config']['budget']['seconds']+1
        with patch.object(d.time, 'monotonic', side_effect=lambda: clock), patch.object(c, '_save', slow_save), patch.object(c, '_physical') as physical:
            with self.assertRaises(d.Blocked): call(c)
            physical.assert_not_called()
        self.assertEqual(c.run['entries'][0]['state'], 'unknown')
        self.assertIsNone(c.run['entries'][0]['cost_cny'])

    def test_observation_timeout_and_post_call_facts(self):
        c = self.opened()
        # Adding 120 to this tick rounds the absolute deadline up to 520.0.
        clock = math.nextafter(400.0, 0.0)
        c.run['deadline'] = clock + 300
        seen = []
        def completed(*args, **kwargs):
            nonlocal clock
            seen.append(kwargs['timeout'])
            clock += 121
            return subprocess.CompletedProcess(args, 0, json.dumps(dict(outcome='ok',
                usage_lower_bound={'input': 1, 'output': 1}, supplier_invoice=None)), '')
        with patch.object(d.time, 'monotonic', side_effect=lambda: clock), patch.object(d.subprocess, 'run', completed):
            with self.assertRaises(d.Blocked): call(c)
        self.assertLessEqual(seen[0], 120)
        self.assertEqual(c.run['entries'][0]['state'], 'complete')
        self.assertIsNotNone(auth.load(c.path)['runs'][c.run['plan']['run_id']]['entries'][0]['cost_cny'])

    def test_write_failures_preserve_original_and_reservation(self):
        c = self.opened()
        with patch.object(d, 'atomic_json', side_effect=OSError('disk full')), patch.object(c,'_physical') as physical:
            with self.assertRaises(d.PersistenceFailure): call(c)
            physical.assert_not_called()
        c.close()
        with d.Controller(self.registry) as c:
            c.resume(self.seed[0]['run_id'])
            original = c._physical
            def dispatched(*args):
                result = original(*args)
                c._save = lambda: (_ for _ in ()).throw(d.PersistenceFailure('post-dispatch disk'))
                return result
            with patch.object(c, '_physical', dispatched), self.assertRaises(d.PersistenceFailure): call(c)
        with d.Controller(self.registry) as c:
            self.assertEqual(c.resume(self.seed[0]['run_id'])['entries'][0]['state'], 'unknown')
        self.registry = self.root/'exception'
        c = self.opened()
        original_error = RuntimeError('original physical failure')
        original_error.sdk_receipt = dict(usage_lower_bound={'input':8}, cost_cny=None, outcome='partial')
        def failed(*args):
            c._save = lambda: (_ for _ in ()).throw(d.PersistenceFailure('disk too'))
            raise original_error
        with patch.object(c, '_physical', failed), self.assertRaises(RuntimeError) as caught: call(c)
        self.assertIs(caught.exception, original_error)
        self.assertIsInstance(caught.exception.persistence_error, d.PersistenceFailure)
        self.assertEqual(caught.exception.durable_attempt['usage_lower_bound'], {'input':8})
        c.close()

    def test_tightening_deadline_invalid_and_exhaustion(self):
        c = self.opened()
        original_deadline = c.run['deadline']
        for field in c.run['limits']:
            b = dict(c.run['limits']); b[field] *= 2
            with self.assertRaises(auth.RemoteBlocked): c.tighten(b)
        with self.assertRaises(auth.RemoteBlocked): call(c, usage={'input':-1,'output':0})
        limits = dict(c.run['limits'], max_cny=.0002, max_seconds=30)
        c.tighten(limits)
        self.assertLess(c.run['deadline'], original_deadline)
        call(c)
        with self.assertRaises(auth.RemoteBlocked): call(c, request='two')
        deadline = c.run['deadline']; started = c.run['started']; c.close()
        with d.Controller(self.registry) as c:
            c.resume(self.seed[0]['run_id'])
            self.assertEqual(c.run['deadline'], deadline); self.assertEqual(c.run['started'], started)
            with patch.object(d.time,'monotonic',return_value=deadline+1), self.assertRaises(d.Blocked): call(c)
        self.registry = self.root/'invalid'
        with d.Controller(self.registry) as c:
            bad = copy.deepcopy(self.seed); bad[1]['approved'] = False
            with self.assertRaises(auth.RemoteBlocked): c._consume(*bad)
            self.assertFalse(c.path.exists())
        (self.registry/'registry.json').write_text('{broken')
        with self.assertRaises(ValueError): d.Controller(self.registry)

    def test_atomic_commit_windows_and_cross_boot(self):
        for stage in ('replace', 'fsync'):
            self.registry = self.root/stage
            with d.Controller(self.registry) as c:
                with patch.object(d.os,stage,side_effect=OSError(stage)), self.assertRaises(d.PersistenceFailure):
                    c._consume(*copy.deepcopy(self.seed))
                self.assertTrue(c.poisoned)
            self.assertFalse((self.registry/'registry.json').exists())
        self.registry = self.root/'boot'
        c = self.opened(); c.close()
        with d.Controller(self.registry) as c, patch.object(d,'boot_id',return_value='different-boot'):
            with self.assertRaises(auth.RemoteBlocked): c.resume(self.seed[0]['run_id'])
        result = subprocess.run([sys.executable,'-O','-c',
            'from evals.architecture_durable import Controller; Controller('+repr(str(self.root/'optimized'))+')'],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'optimized').exists())

    def test_post_reservation_deadline_and_directory_sync_failure(self):
        c = self.opened()
        original = c._save
        def slow_save():
            original()
            c.run['deadline'] = time.monotonic()-1
        with patch.object(c,'_save',slow_save), patch.object(d.subprocess,'run') as physical:
            with self.assertRaises(d.Blocked): call(c)
            physical.assert_not_called()
        self.assertEqual(c.run['entries'][0]['state'],'unknown')
        c.close()
        self.registry = self.root/'directory-sync'
        with d.Controller(self.registry) as c:
            real_sync = d.os.fsync
            calls = []
            def sync(fd):
                calls.append(fd)
                if len(calls)==2: raise OSError('directory fsync failed after replace')
                return real_sync(fd)
            with patch.object(d.os,'fsync',sync), self.assertRaises(d.PersistenceFailure):
                c._consume(*copy.deepcopy(self.seed))
        with d.Controller(self.registry) as c:
            c.resume(self.seed[0]['run_id'])
            with self.assertRaises(auth.RemoteBlocked): c._consume(*copy.deepcopy(self.seed))

    def test_actual_preflight_fake_dispatch_new_process_resume(self):
        config = copy.deepcopy(a.CONTRACT)
        cp = self.root/'config.json'; cp.write_text(json.dumps(config))
        policy = fixture()['plan']; policy.update(issued_at=time.time()-60, expires_at=time.time()+3600)
        policy['model']['version'] = config['model']['version']
        plan = measurement.measure(policy, cp, self.root/'prepare')
        approval = dict(approved=True, approver='SYNTHETIC integration', record_id='SYNTHETIC-integration',
                        plan_sha256=auth.digest(plan), granted_at=time.time()-1, expires_at=time.time()+1800)
        with d.Controller(self.registry) as c:
            c.create(plan,approval,policy,cp,self.root/'preflight',synthetic=True)
            result = call(c)
            self.assertEqual(result['state'],'complete')
            self.assertFalse(c.run['remote_execution_allowed'])
        self.seed[0] = plan
        self.child("with d.Controller(root) as c:\n r=c.resume(seed[0]['run_id'])\n if len(r['entries'])!=1 or r['entries'][0]['cost_cny'] is None: raise RuntimeError('lost accounting')\n print(auth.canonical(r['entries']))")
        # Stored source locks cannot be bypassed on restart.
        with d.Controller(self.registry) as c, patch.object(a,'source_lock',return_value={}):
            with self.assertRaises(auth.RemoteBlocked): c.resume(plan['run_id'])
