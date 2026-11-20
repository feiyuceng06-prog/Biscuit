"""Offline preparation and strict aggregation, deliberately no provider imports.

Live execution is fail-closed until a protected supervisor, billing adapter and
pinned dual-source runner exist. Synthetic rows never measure model benefit.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

from evals import architecture_cases as cases

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'evals/architecture.json'
STATUSES = ('success', 'agent_failure', 'environment_failure', 'budget_stop', 'provider_failure', 'judge_failure')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_lock():
    names = subprocess.check_output(['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    names = sorted(set(n for n in names if n and (n.startswith(('feiyu/', 'evals/')) or n == 'pyproject.toml')))
    return {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names if (ROOT / n).is_file()}


def head_lock(baseline):
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', baseline, '--', 'feiyu', 'evals', 'pyproject.toml'], cwd=ROOT).decode().splitlines()
    return {n: hashlib.sha256(subprocess.check_output(['git', 'show', baseline + ':' + n], cwd=ROOT)).hexdigest() for n in names}


CONTRACT = {'schema_version': 1, 'groups': ['executor', 'verification', 'compaction', 'recovery'], 'splits': ['development', 'holdout'], 'repeat': 6, 'baseline': 'd82d943e64dcf4129e5bc44f4798abff6949da83', 'comparison': 'confounded_full_snapshot', 'live_ready': False, 'model': {'provider': 'openai', 'version': 'gpt-4.1-2025-04-14', 'temperature': 0, 'top_p': 1, 'seed': None, 'auxiliary': 'same_exact_version', 'availability_verified': False}, 'tools': ['read_file', 'write_file', 'edit_file', 'bash'], 'budget': {'rounds': 30, 'seconds': 120, 'cny': 3.0, 'attempts': 2}, 'environment': {'network': 'provider_only_after_authorization', 'agent_isolation': 'separate_uid_no_controller_access', 'home': 'fresh_per_observation', 'dependencies': 'both_arms_same_frozen_environment_required', 'system_prompt': 'source_native_prompt_sha256_per_arm_required', 'provider_credentials': 'dedicated_evaluation_credentials_only'}}


ANTHROPIC_MODEL = 'claude-sonnet-4-5-20250929'

def anthropic_config():
    import copy
    config = copy.deepcopy(CONTRACT)
    config['model'].update(provider='anthropic', version=ANTHROPIC_MODEL, temperature=None, top_p=None)
    return config


def same_shape_value(value, expected):
    assert type(value) is type(expected), 'configuration type mismatch'
    if isinstance(expected, dict):
        assert value.keys() == expected.keys(), 'configuration fields mismatch'
        for key in expected:
            same_shape_value(value[key], expected[key])
    elif isinstance(expected, list):
        assert len(value) == len(expected)
        for actual, wanted in zip(value, expected):
            same_shape_value(actual, wanted)
    else:
        assert value == expected, 'configuration value mismatch'


def validate(config):
    assert type(config) is dict
    assert type(config.get('repeat')) is int and config['repeat'] >= 3
    same_shape_value(dict(config, repeat=CONTRACT['repeat']),
                     anthropic_config() if config.get('model', {}).get('provider') == 'anthropic' else CONTRACT)
    return config


def sha256(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_manifest(manifest):
    assert type(manifest) is dict and manifest, 'empty source manifest'
    for name, value in manifest.items():
        assert type(name) is str and name and '\\' not in name
        path = PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and str(path) == name
        assert name.startswith(('feiyu/', 'evals/')) or name == 'pyproject.toml'
        assert sha256(value), 'invalid source digest'
    assert {'feiyu/__init__.py', 'feiyu/agent.py', 'pyproject.toml'} <= manifest.keys()


def validate_lock(lock):
    assert type(lock) is dict
    assert type(lock['schema_version']) is int and lock['schema_version'] == 1
    # No live evidence is accepted before a protected controller exists.
    assert lock['mode'] == 'offline_synthetic' and lock['artifact_type'] == 'fixture_self_check'
    validate(lock['config'])
    assert lock['baseline_commit'] == lock['config']['baseline']
    assert type(lock['schedule']) is list
    same_shape_value(lock['schedule'], plan(lock['config']))
    for key in ('source', 'head_source'):
        validate_manifest(lock[key])
    assert sha256(lock['judge_sha256'])
    assert lock['source'].get('evals/architecture_cases.py') == lock['judge_sha256']
    for key in ('python', 'platform'):
        assert type(lock[key]) is str and lock[key]
    assert sha256(lock['executable_sha256'])
    assert type(lock['packages']) is list and lock['packages']
    for package in lock['packages']:
        assert type(package) is list and len(package) == 2
        assert all(type(v) is str and v for v in package)
    return lock


def plan(config):
    validate(config)
    rows = []
    for group in config['groups']:
        for split in config['splits']:
            case = cases.spec(group, split)
            for repeat in range(config['repeat']):
                # Counterbalance order; task/repeat identity is stable across arms.
                arms = ['head', 'snapshot'] if repeat % 2 == 0 else ['snapshot', 'head']
                for arm in arms:
                    rows.append(dict(group=group, split=split, task=case['id'], repeat=repeat,
                                     arm=arm, prompt_sha256=digest(case['prompt']), case_sha256=digest(case)))
    return rows


def number(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def validate_row(row):
    assert type(row) is dict
    assert type(row['schema_version']) is int and row['schema_version'] == 1
    assert type(row['synthetic']) is bool
    assert type(row['accounting_complete']) is bool
    assert row['status'] in STATUSES
    assert row['arm'] in ('head', 'snapshot') and row['group'] in cases.GROUPS
    assert row['split'] in ('development', 'holdout')
    assert row['task'] == row['group'] + '-' + row['split']
    assert type(row['repeat']) is int and row['repeat'] >= 0
    for key in ('seconds', 'human_interventions'):
        assert number(row[key])
    assert type(row['human_interventions']) is int
    for key in ('plan_sha256', 'source_sha256', 'judge_sha256', 'prompt_sha256', 'case_sha256'):
        assert sha256(row[key])
    assert type(row['model_version']) is str and row['model_version']
    assert isinstance(row['attempts'], list) and row['attempts']
    for attempt in row['attempts']:
        assert type(attempt) is dict
        assert attempt['kind'] in ('primary', 'auxiliary', 'failed')
        assert attempt['cost_cny'] is None or number(attempt['cost_cny'])
    return row


def interval(k, n):
    if not n:
        return None
    z = 1.959963984540054
    p = k / n
    center = (p + z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0, center-half), min(1, center+half)]


def finite_sum(values):
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError('aggregate exceeds finite numeric range') from exc
    if not number(total):
        raise ValueError('aggregate exceeds finite numeric range')
    return total


def summarize(rows):
    seen = set()
    synthetic = {r['synthetic'] for r in rows}
    assert len(synthetic) <= 1, 'cannot mix synthetic and real evidence'
    for row in rows:
        validate_row(row)
        assert row['synthetic'] is True, 'only synthetic evidence is currently supported'
        key = tuple(row[k] for k in ('group', 'split', 'task', 'repeat', 'arm'))
        assert key not in seen, 'duplicate observation'
        seen.add(key)
    groups = {}
    for group in cases.GROUPS:
        for split in ('development', 'holdout'):
            for arm in ('head', 'snapshot'):
                selected = [r for r in rows if (r['group'], r['split'], r['arm']) == (group, split, arm)]
                if not selected:
                    continue
                counts = Counter(r['status'] for r in selected)
                n = sum(counts[s] for s in ('success', 'agent_failure', 'budget_stop'))
                costs = [a['cost_cny'] for r in selected for a in r['attempts']]
                unknown = sum(c is None for c in costs)
                incomplete = sum(not r['accounting_complete'] for r in selected)
                groups['/'.join((group, split, arm))] = dict(
                    observations=len(selected), unique_tasks=len({r['task'] for r in selected}),
                    judged_denominator=n, successes=counts['success'],
                    success_rate=counts['success']/n if n else None,
                    wilson95=interval(counts['success'], n),
                    all_attempt_success_rate=counts['success']/len(selected),
                    status_counts=dict(counts), known_cost_cny=finite_sum(c for c in costs if c is not None),
                    unknown_cost_attempts=unknown, incomplete_accounting_rows=incomplete,
                    total_cost_cny=None if unknown or incomplete else finite_sum(costs),
                    seconds=finite_sum(r['seconds'] for r in selected),
                    human_interventions=sum(r['human_interventions'] for r in selected))
    return dict(schema_version=1, synthetic=next(iter(synthetic), None), groups=groups,
                uncertainty='Wilson descriptive only; repeats of one task are correlated; no causal or population claim')


def dry_run(config, output):
    output.mkdir(parents=True, exist_ok=False)
    schedule = plan(config)
    lock = source_lock()
    judge_hash = hashlib.sha256((ROOT/'evals/architecture_cases.py').read_bytes()).hexdigest()
    payload = dict(schema_version=1, mode='offline_synthetic', artifact_type='fixture_self_check',
                   baseline_commit=config['baseline'], config=config, schedule=schedule, source=lock,
                   head_source=head_lock(config['baseline']),
                   python=sys.version, platform=platform.platform(), judge_sha256=judge_hash,
                   executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                   packages=sorted([d.metadata['Name'], d.version] for d in importlib.metadata.distributions()))
    (output/'lock.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    rows = []
    for item in schedule:
        case = cases.spec(item['group'], item['split'])
        with tempfile.TemporaryDirectory(prefix='feiyu-architecture-') as temp:
            root = Path(temp)
            cases.setup(case, root)
            assert not cases.judge(case, root, {}), 'unsolved fixture incorrectly accepted'
            observations = cases.golden(case, root)
            assert cases.judge(case, root, observations), 'golden solution rejected'
            (root/'injected-test.txt').write_text('fake pass')
            assert not cases.judge(case, root, observations), 'scope tampering accepted'
        # Exercise classification and unknown accounting, never simulate model benefit.
        status = STATUSES[item['repeat'] % len(STATUSES)]
        row = dict(schema_version=1, synthetic=True, **item, status=status,
                   plan_sha256=digest(payload), source_sha256=digest(payload['head_source'] if item['arm'] == 'head' else lock),
                   model_version=config['model']['version'], judge_sha256=judge_hash,
                   seconds=0.0, human_interventions=0, accounting_complete=False,
                   attempts=[dict(kind='primary', cost_cny=0.1),
                             dict(kind='auxiliary', cost_cny=None),
                             dict(kind='failed', cost_cny=0.2)])
        rows.append(row)
    (output/'synthetic.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in rows))
    (output/'summary.json').write_text(json.dumps(validate_bundle(rows, payload), ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    return dict(offline=True, synthetic=True, rows=len(rows), fixture_checks=len(rows)*3,
                source_sha256=digest(lock), plan_sha256=digest(payload), live_ready=False)


def validate_bundle(rows, lock):
    validate_lock(lock)
    expected = {tuple(r[k] for k in ('group', 'split', 'task', 'repeat', 'arm')): r
                for r in plan(lock['config'])}
    seen = set()
    for row in rows:
        validate_row(row)
        assert row['synthetic'] is True, 'only synthetic evidence is currently supported'
        key = tuple(row[k] for k in ('group', 'split', 'task', 'repeat', 'arm'))
        assert key in expected and key not in seen, 'unplanned or duplicate observation'
        seen.add(key)
        for field in ('prompt_sha256', 'case_sha256'):
            assert row[field] == expected[key][field], 'task/prompt changed'
        assert row['plan_sha256'] == digest(lock), 'plan changed'
        assert row['model_version'] == lock['config']['model']['version'], 'model changed'
        source = lock['head_source'] if row['arm'] == 'head' else lock['source']
        assert row['source_sha256'] == digest(source), 'source changed'
        assert row['judge_sha256'] == lock['judge_sha256'], 'judge changed'
    result = summarize(rows)
    result['validation_scope'] = 'structural_and_self_consistent_only; source authenticity not attested'
    for group in cases.GROUPS:
        for split in lock['config']['splits']:
            for arm in ('head', 'snapshot'):
                name = '/'.join((group, split, arm))
                cell = result['groups'].setdefault(name, dict(observations=0, unique_tasks=0, judged_denominator=0, successes=0, success_rate=None, all_attempt_success_rate=None, wilson95=None, status_counts={}, known_cost_cny=0, total_cost_cny=None, unknown_cost_attempts=0, incomplete_accounting_rows=0, seconds=0, human_interventions=0))
                cell['planned_observations'] = lock['config']['repeat']
                cell['missing_observations'] = lock['config']['repeat'] - cell['observations']
    result['planned_observations'] = len(expected)
    result['missing_observations'] = len(expected) - len(seen)
    return result


def main():
    if not __debug__:
        raise SystemExit('validation requires Python without -O')
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('command', choices=['validate', 'dry-run', 'fake', 'loopback', 'anthropic-loopback', 'aggregate', 'live'])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--lock', type=Path)
    args = parser.parse_args()
    if args.command == 'live':
        parser.exit(2, 'BLOCKED: authorization, credentials, source/environment lock and live supervisor/billing adapters required; no provider called\n')
    config = validate(anthropic_config() if args.command == 'anthropic-loopback' and not args.config else json.loads((args.config or CONFIG).read_text())) if args.command != 'aggregate' or args.config else None
    if args.command in ('fake', 'loopback', 'anthropic-loopback'):
        if args.out is None:
            parser.error('--out required (new directory)')
        from evals.architecture_execution import run
        observations = run(config, args.out, loopback=args.command in ('loopback', 'anthropic-loopback'))
        print(json.dumps(observations, allow_nan=False))
        return int(any(r['status'] in ('environment_failure', 'judge_failure', 'provider_failure') for r in observations))
    if args.command == 'aggregate':
        if args.input is None or args.lock is None:
            parser.error('--input and --lock required')
        lock = json.loads(args.lock.read_text())
        if config is not None:
            same_shape_value(config, lock['config'])
        result = validate_bundle([json.loads(l) for l in args.input.read_text().splitlines() if l.strip()], lock)
    elif args.command == 'dry-run':
        if args.out is None:
            parser.error('--out required (new directory)')
        result = dry_run(config, args.out)
    else:
        result = dict(valid=True, planned_rows=len(plan(config)), live_ready=False)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
