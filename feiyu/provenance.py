"""Program-owned attribution references, never an authorization or verification store."""
from contextlib import nullcontext
import hashlib
import json

from . import native_history

KINDS = {'unknown', 'external_data', 'assistant_claim', 'user_request', 'program_state'}


def ref(kind, text, *, identity='', refs=()):
    digest = hashlib.sha256(str(text).encode()).hexdigest()
    return dict(id=identity or digest, source_kind=kind if kind in KINDS else 'unknown',
                digest=digest, source_refs=[r['id'] for r in clean(refs)])


def clean(rows):
    # Do not infer a category from model text or accept execution_evidence here.
    if not isinstance(rows, (list, tuple)):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            continue
        kind = row.get('source_kind')
        item = dict(id=row['id'], source_kind=kind if kind in KINDS else 'unknown',
                    digest=str(row.get('digest', '')))
        # References are flat: derived entries point to existing IDs, not nested claims.
        item['source_refs'] = [r for r in row.get('source_refs', []) if isinstance(r, str)] if isinstance(row.get('source_refs'), list) else []
        out.append(item)
    return out


def collect(agent, workspace=None):
    with getattr(agent, '_provenance_lock', nullcontext()):
        return _collect(agent, workspace)


def _collect(agent, workspace=None):
    rows = clean(getattr(agent, 'source_refs', []))
    known = {(r['id'], r['digest']) for r in rows}
    for msg in native_history.export_session(agent.backend):
        if msg.get('role') == 'system':
            continue
        text = json.dumps(msg, ensure_ascii=False, sort_keys=True)
        row = ref('assistant_claim' if msg.get('role') == 'assistant' else 'unknown', text)
        if (row['id'], row['digest']) not in known:
            rows.append(row)
            known.add((row['id'], row['digest']))
    from . import memory
    root = workspace or getattr(getattr(agent, 'toolbox', None), 'root', None)
    for item in memory.load(root) if root is not None else []:
        inherited = clean(getattr(item, 'source_refs', []))
        for row in inherited + [ref(getattr(item, 'source_kind', 'unknown'), item[1], refs=inherited)]:
            if (row['id'], row['digest']) not in known:
                rows.append(row)
                known.add((row['id'], row['digest']))
    agent.source_refs = rows
    return rows


def merge(agent, incoming):
    with getattr(agent, '_provenance_lock', nullcontext()):
        rows = clean(getattr(agent, 'source_refs', []))
        for row in clean(incoming):
            if row not in rows:
                rows.append(row)
        agent.source_refs = rows


def append(agent, kind, text, identity=''):
    merge(agent, [ref(kind, text, identity=identity)])


class Report(str):
    pass


def report(text, rows):
    result = Report(text)
    result.source_refs = clean(rows)
    return result
