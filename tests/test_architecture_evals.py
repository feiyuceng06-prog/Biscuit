"""Offline harness checks; no product/provider imports."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from evals import architecture as a, architecture_cases as c


class Preparation(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(a.CONFIG.read_text())

    def test_plan_disjoint_and_counterbalanced(self):
        rows = a.plan(self.config)
        self.assertEqual(len(rows), 96)
        self.assertEqual(rows[0]['arm'], 'head')
        self.assertEqual(rows[2]['arm'], 'snapshot')
        for group in c.GROUPS:
            self.assertNotEqual(a.digest(c.spec(group, 'development')),
                                a.digest(c.spec(group, 'holdout')))

    def test_bad_config(self):
        for key, value in [('repeat', 1), ('live_ready', True), ('comparison', 'isolated')]:
            bad = copy.deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(AssertionError):
                a.validate(bad)

    def test_artifacts_and_controller_facts(self):
        for group in c.GROUPS:
            for split in self.config['splits']:
                case = c.spec(group, split)
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    c.setup(case, root)
                    self.assertFalse(c.judge(case, root, {}))
                    facts = c.golden(case, root)
                    self.assertTrue(c.judge(case, root, facts))
                    if group != 'executor':
                        self.assertFalse(c.judge(case, root, {}))
                    (root / 'protected-by-agent-test.py').write_text('pass')
                    self.assertFalse(c.judge(case, root, facts))

    def test_end_to_end_and_unknown_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'run'
            got = a.dry_run(self.config, out)
            self.assertEqual(got['rows'], 96)
            rows = [json.loads(l) for l in (out/'synthetic.jsonl').read_text().splitlines()]
            lock = json.loads((out/'lock.json').read_text())
            summary = a.validate_bundle(rows, lock)
            self.assertEqual(summary['missing_observations'], 0)
            for g in summary['groups'].values():
                self.assertEqual(g['judged_denominator'], 3)
                self.assertEqual(g['successes'], 1)
                self.assertEqual(g['observations'], 6)
                self.assertIsNone(g['total_cost_cny'])
                self.assertAlmostEqual(g['known_cost_cny'], 1.8)
                self.assertEqual(g['unknown_cost_attempts'], 6)
                self.assertEqual(len(g['status_counts']), 6)
            self.assertEqual(a.validate_bundle(rows[:-1], lock)['missing_observations'], 1)
            known = copy.deepcopy(rows[:1])
            known[0]['accounting_complete'] = True
            known[0]['attempts'] = [dict(kind='primary', cost_cny=0)]
            self.assertEqual(next(iter(a.summarize(known)['groups'].values()))['total_cost_cny'], 0)
            known[0]['accounting_complete'] = False
            self.assertIsNone(next(iter(a.summarize(known)['groups'].values()))['total_cost_cny'])
            schema = json.loads((a.ROOT/'evals/architecture-result.schema.json').read_text())
            self.assertTrue(set(schema['required']) <= set(rows[0]))
            for field in ('model_version', 'source_sha256', 'judge_sha256', 'prompt_sha256', 'plan_sha256'):
                bad = copy.deepcopy(rows)
                bad[0][field] = 'changed'
                with self.assertRaises(AssertionError):
                    a.validate_bundle(bad, lock)
            with self.assertRaises(AssertionError):
                a.summarize(rows + rows[:1])
            bad = copy.deepcopy(rows)
            bad[0]['synthetic'] = False
            with self.assertRaises(AssertionError):
                a.summarize(bad)
            for cost in (-1, float('nan'), float('inf'), '0', True):
                bad = copy.deepcopy(rows[0])
                bad['attempts'][0]['cost_cny'] = cost
                with self.assertRaises(AssertionError):
                    a.validate_row(bad)

    def test_no_observations_no_rate(self):
        self.assertEqual(a.summarize([])['groups'], {})
        self.assertIsNone(a.interval(0, 0))
        lo, hi = a.interval(0, 6)
        self.assertAlmostEqual(lo, 0)
        self.assertGreater(hi, 0)


class ReviewRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        out = Path(cls.temp.name)/'fixture'
        a.dry_run(json.loads(a.CONFIG.read_text()), out)
        cls.rows = [json.loads(l) for l in (out/'synthetic.jsonl').read_text().splitlines()]
        cls.lock = json.loads((out/'lock.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_whole_package_relabel_and_live_lock_rejected(self):
        rows = copy.deepcopy(self.rows)
        for row in rows:
            row['synthetic'] = False
        with self.assertRaises(AssertionError):
            a.validate_bundle(rows, self.lock)
        lock = copy.deepcopy(self.lock)
        lock['mode'] = 'live'
        with self.assertRaises(AssertionError):
            a.validate_bundle([], lock)

    def test_lock_corruption_rejected_even_with_recomputed_rows(self):
        for field, value in [('schedule', []), ('source', {}), ('head_source', {}),
                             ('judge_sha256', 'bad'), ('packages', []),
                             ('baseline_commit', '0'*40), ('python', '')]:
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                lock[field] = value
                with self.assertRaises(AssertionError):
                    a.validate_bundle([], lock)
        lock = copy.deepcopy(self.lock)
        del lock['executable_sha256']
        with self.assertRaises(KeyError):
            a.validate_bundle([], lock)

    def test_config_fields_and_exact_types(self):
        for section, key, value in [('model', 'provider', 'other'), ('model', 'seed', 'bad'),
                                   ('environment', 'home', 'shared'), ('environment', 'dependencies', 'unfrozen'),
                                   ('environment', 'system_prompt', 'unlocked'),
                                   ('environment', 'provider_credentials', 'real-user-keys'),
                                   ('model', 'temperature', False), ('model', 'availability_verified', 0)]:
            config = copy.deepcopy(self.lock['config'])
            config[section][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                a.validate(config)

    def test_cli_explicit_config_conflict_and_historical_default(self):
        import subprocess
        import sys
        root = Path(self.temp.name)
        config = copy.deepcopy(self.lock['config'])
        config['repeat'] = 3
        path = root/'other.json'
        path.write_text(json.dumps(config))
        argv = [sys.executable, '-m', 'evals.architecture', 'aggregate', '--input',
                str(root/'fixture/synthetic.jsonl'), '--lock', str(root/'fixture/lock.json')]
        self.assertEqual(subprocess.run(argv, capture_output=True, timeout=15).returncode, 0)
        self.assertNotEqual(subprocess.run(argv+['--config', str(path)], capture_output=True, timeout=15).returncode, 0)

    def test_boolean_version_and_invalid_objects(self):
        for field, value in [('schema_version', True), ('attempts', [None]),
                             ('case_sha256', 42), ('prompt_sha256', []), ('seconds', True)]:
            row = copy.deepcopy(self.rows[0])
            row[field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                a.validate_row(row)

    def test_finite_inputs_cannot_overflow_summary(self):
        row = copy.deepcopy(self.rows[0])
        row['accounting_complete'] = True
        row['attempts'] = [dict(kind='primary', cost_cny=1e308), dict(kind='failed', cost_cny=1e308)]
        with self.assertRaises(ValueError):
            a.validate_bundle([row], self.lock)
        rows = copy.deepcopy(self.rows)
        for row in rows:
            row['seconds'] = 1e308
        with self.assertRaises(ValueError):
            a.validate_bundle(rows, self.lock)

    def test_missing_cells_are_explicit(self):
        result = a.validate_bundle([], self.lock)
        self.assertEqual(len(result['groups']), 16)
        for cell in result['groups'].values():
            self.assertEqual(cell['missing_observations'], 6)
            self.assertIsNone(cell['success_rate'])
            self.assertIsNone(cell['total_cost_cny'])

    def test_baseline_object_is_used(self):
        from unittest.mock import patch
        with patch.object(a.subprocess, 'check_output', side_effect=[b'feiyu/agent.py\n', b'original']) as call:
            a.head_lock('1'*40)
        self.assertIn('1'*40, call.call_args_list[0].args[0])
        self.assertIn('1'*40 + ':feiyu/agent.py', call.call_args_list[1].args[0])
