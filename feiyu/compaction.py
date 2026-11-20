"""Program-owned compaction facts. Model prose is never execution evidence."""
import copy
import json
from dataclasses import asdict

from . import native_history, provenance


class UnsafeCompaction(ValueError):
    pass


def check_pairs(messages):
    """Check both native protocols, including duplicates and orphan results."""
    pending, seen = set(), set()
    for message in native_history.plain(messages):
        calls = [c.get('id') for c in message.get('tool_calls', []) or []]
        results = ([message.get('tool_call_id')] if message.get('role') == 'tool' else [])
        content = message.get('content')
        if isinstance(content, list):
            calls += [b.get('id') for b in content if isinstance(b, dict) and b.get('type') == 'tool_use']
            results += [b.get('tool_use_id') for b in content if isinstance(b, dict) and b.get('type') == 'tool_result']
        if pending and not results:
            raise UnsafeCompaction('message interrupts tool results')
        for cid in results:
            if not cid or cid not in pending:
                raise UnsafeCompaction('orphan/duplicate tool result')
            pending.remove(cid)
        if pending and calls:
            raise UnsafeCompaction('new calls before previous results')
        for cid in calls:
            if not cid or cid in seen:
                raise UnsafeCompaction('missing/duplicate tool id')
            seen.add(cid)
            pending.add(cid)
    if pending:
        raise UnsafeCompaction('unpaired tool calls')


def protected(agent):
    state = asdict(agent.task_state) if agent.task_state is not None else None
    if state is not None:
        # Attempt accounting and observation may advance; never restore a budget.
        state = {k: v for k, v in state.items() if k not in (
            'budget', 'revision', 'run_state', 'operations', 'verification_refs',
            'acceptance', 'result', 'result_details')}
        # Acceptance validity may be demoted by a fresh Ledger check.
        state['acceptance'] = [{k: v for k, v in row.items() if k != 'status'}
                               for row in agent.task_state.acceptance]
    return copy.deepcopy(state)


def facts(agent):
    jobs = []
    for job in agent.toolbox.jobs.all():
        refresh = getattr(job, 'refresh', None)
        if callable(refresh):
            refresh()
        if getattr(job, 'error', None):
            raise job.error
        jobs.append(dict(job_id=job.id, operation=copy.deepcopy(getattr(job, 'op', {})),
                         task_id=getattr(getattr(job, 'state', None), 'task_id', None)))
    refs = set(agent.task_state.verification_refs if agent.task_state else [])
    refs.update(r.get('verification_id') for r in agent.verifications.records)
    records = [agent.verifications.reference(ref, agent.toolbox.root, agent.toolbox.cwd,
                    agent._verification_config(), agent._verification_busy(),
                    owner=(agent.session_id, agent.task_id)) for ref in sorted(refs) if ref]
    agent._check_task_acceptance()
    return dict(schema_version=1, source_kind='program_state',
                source_refs=provenance.collect(agent),
                task=asdict(agent.task_state) if agent.task_state else None,
                jobs=jobs, unpaired_calls=[], verification_refs=records)


def handoff(summary, snapshot):
    # JSON escaping prevents model text from closing/replacing the program block.
    return json.dumps(dict(schema_version=1, model_summary=dict(
        source_kind='assistant_claim', text=summary), program_facts=snapshot),
        ensure_ascii=False, sort_keys=True)


def candidate(backend, summary, snapshot):
    staged = copy.copy(backend)
    staged.messages = native_history.export_session(backend)
    block = handoff(summary, snapshot)
    staged.compact_to(block)
    check_pairs(staged.messages)
    # Custom compact_to implementations must retain the exact program envelope.
    if not any(isinstance(m.get('content'), str) and block in m['content']
               for m in staged.messages):
        raise UnsafeCompaction('backend discarded program facts')
    return staged
