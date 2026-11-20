"""Deterministic architecture fixtures; no product imports or model calls.

The controller owns expected artifacts outside the workspace. Event schedules are
specifications for a future live supervisor, not pretend product feature flags.
"""
from pathlib import Path

GROUPS = ('executor', 'verification', 'compaction', 'recovery')


def spec(group, split):
    held = split == 'holdout'
    value = 17 if held else 5
    if group == 'executor':
        before = {'calc.py': 'def sub(a, b):\n    return a - b\n',
                  'client.py': 'from calc import sub\nresult = sub(%d, 2)\n' % value}
        after = {k: v.replace('sub', 'minus') for k, v in before.items()}
        prompt = 'Rename sub to minus in calc.py and client.py; preserve arithmetic.'
        events = []
    elif group == 'verification':
        before = {'calc.py': 'VALUE = 1\n', 'protected.txt': 'do not modify\n'}
        after = dict(before, **{'calc.py': 'VALUE = %d\n' % value})
        prompt = 'Set VALUE to %d. Verify the final version, not an earlier file version.' % value
        events = [{'trigger': 'first_successful_verification', 'action': 'controller_changes_VALUE_to_0'},
                  {'trigger': 'final', 'action': 'require_fresh_controller_observed_verification'}]
    elif group == 'compaction':
        before = {'a.txt': 'pending\n', 'b.txt': 'pending\n', 'protected.txt': 'do not modify\n'}
        after = dict(before, **{'a.txt': '%d\n' % value, 'b.txt': '%d\n' % (value + 1)})
        prompt = 'Write %d to a.txt and %d to b.txt, each followed by a newline. Preserve protected.txt.' % (value, value + 1)
        events = [{'trigger': 'first_artifact_write', 'action': 'request_real_agent_compaction'},
                  {'trigger': 'post_compaction', 'action': 'resume_original_task_without_reissuing_constraints'}]
    else:
        before = {'request.txt': 'operation-%d\n' % value, 'protected.txt': 'do not modify\n'}
        after = dict(before, **{'answer.txt': 'operation-%d complete\n' % value})
        prompt = 'Execute request.txt once using controller operation service; write its completion to answer.txt. Never repeat an operation with unknown outcome.'
        events = [{'trigger': 'operation_accepted_before_response', 'action': 'controller_disconnect'},
                  {'trigger': 'restart', 'action': 'resume_saved_session_with_unknown_operation_receipt'}]
    return {'id': group + '-' + split, 'group': group, 'split': split,
            'prompt': prompt, 'before': before, 'after': after, 'events': events}


def setup(case, root):
    for name, content in case['before'].items():
        (root / name).write_text(content, encoding='utf-8')


def judge(case, root, observations):
    # Do not execute agent-supplied tests. No paths in the answer affect the judge.
    found = {p.name: p.read_text(encoding='utf-8') for p in root.iterdir()
             if p.is_file() and not p.is_symlink()}
    files_ok = found == case['after'] and len(list(root.iterdir())) == len(found)
    required = {'executor': (), 'verification': ('fresh_verification',),
                'compaction': ('compacted', 'constraints_preserved'),
                'recovery': ('resumed', 'exactly_one_operation', 'unknown_not_retried')}
    return files_ok and all(observations.get(k) is True for k in required[case['group']])


def golden(case, root):
    for name, content in case['after'].items():
        (root / name).write_text(content, encoding='utf-8')
    return dict.fromkeys(('fresh_verification', 'compacted', 'constraints_preserved',
                          'resumed', 'exactly_one_operation', 'unknown_not_retried'), True)
