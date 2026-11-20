"""Offline contract checks only. No credentials, SDKs or remote admission."""
import argparse
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit


class RemoteBlocked(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise RemoteBlocked(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(value, names):
    need(type(value) is dict and set(value) == set(names.split()), 'missing or unexpected fields')


def string(value):
    need(type(value) is str and bool(value.strip()) and value == value.strip() and
         not any(ord(c) < 32 for c in value), 'invalid string')


def number(value, positive=True):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0)
    except OverflowError:
        valid = False
    need(valid, 'invalid finite number')


def sha(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'invalid digest')


def validate_plan(p):
    version = p.get('schema_version') if type(p) is dict else None
    extra = ' measurement_lock prompt_semantics' if version == 2 else ''
    fields(p, 'schema_version kind run_id provider endpoint model sdk_version source_lock runtime_lock prompt_lock task_lock sampling budget billing_policy dedicated_credential_file issued_at expires_at' + extra)
    if version == 2:
        sha(p['measurement_lock'])
        need(p['prompt_semantics'] == 'initial_constructor_and_system_not_full_requests', 'invalid prompt semantics')
    need(type(p['schema_version']) is int and p['schema_version'] in (1, 2) and p['kind'] == 'remote_plan', 'invalid plan version/kind')
    for k in ('run_id', 'sdk_version'):
        string(p[k])
    need(p['provider'] in ('openai', 'anthropic'), 'unsupported provider')
    string(p['endpoint'])
    try:
        u = urlsplit(p['endpoint'])
        need(u.scheme == 'https' and u.hostname and u.username is None and u.password is None and
             not u.query and not u.fragment and u.port in (None, 443), 'invalid HTTPS endpoint')
        need(re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', u.hostname) is not None and '.' in u.hostname,
             'invalid endpoint host')
        try:
            ipaddress.ip_address(u.hostname)
        except ValueError:
            pass
        else:
            raise RemoteBlocked('IP endpoint disallowed')
        need(p['endpoint'] == 'https://' + u.hostname + u.path and
             re.fullmatch(r'(?:/[A-Za-z0-9_-]+)*', u.path) is not None, 'noncanonical endpoint')
    except (ValueError, TypeError) as exc:
        raise RemoteBlocked('invalid HTTPS endpoint') from exc
    fields(p['model'], 'id version')
    for v in p['model'].values(): string(v)
    for k in ('source_lock', 'prompt_lock'):
        fields(p[k], 'head snapshot')
        for v in p[k].values(): sha(v)
    fields(p['runtime_lock'], 'head snapshot')
    for arm in p['runtime_lock'].values():
        fields(arm, 'interpreter_sha256 dependencies_sha256')
        for v in arm.values(): sha(v)
    sha(p['task_lock'])
    fields(p['sampling'], 'temperature top_p seed auxiliary')
    for k in ('temperature', 'top_p'):
        if p['sampling'][k] is not None: number(p['sampling'][k], False)
    need(p['sampling']['top_p'] is None or 0 < p['sampling']['top_p'] <= 1, 'invalid top_p')
    need(p['sampling']['seed'] is None or type(p['sampling']['seed']) is int, 'invalid seed')
    need(p['sampling']['auxiliary'] == 'same_exact_version_and_sampling', 'auxiliary drift')
    fields(p['budget'], 'max_cny max_seconds max_requests')
    for v in p['budget'].values(): number(v)
    need(type(p['budget']['max_requests']) is int, 'invalid request count')
    b = p['billing_policy']
    fields(b, 'basis currency rate_source rates_per_million token_ceiling_per_request unknown_cost replenishment evidence')
    need(b['basis'] == 'fixed_price_estimate' and b['currency'] == 'CNY' and
         b['unknown_cost'] == 'block' and b['replenishment'] == 'forbidden' and
         b['evidence'] == 'real_only_no_synthetic_merge', 'invalid billing policy')
    string(b['rate_source'])
    keys = ('input output' if p['provider'] == 'openai' else 'input output cache_read cache_creation')
    fields(b['rates_per_million'], keys)
    fields(b['token_ceiling_per_request'], keys)
    for v in b['rates_per_million'].values(): number(v, False)
    for v in b['token_ceiling_per_request'].values():
        need(type(v) is int and v >= 0, 'invalid token ceiling')
    need(b['token_ceiling_per_request']['output'] > 0, 'missing output ceiling')
    try:
        estimate = sum(b['rates_per_million'][k] * b['token_ceiling_per_request'][k] / 1000000 for k in keys.split()) * p['budget']['max_requests']
        number(estimate)
    except (OverflowError, ValueError) as exc:
        raise RemoteBlocked('invalid estimate') from exc
    need(estimate <= p['budget']['max_cny'], 'estimated allowance exceeds cap')
    string(p['dedicated_credential_file'])
    path = Path(p['dedicated_credential_file'])
    need(path.is_absolute() and '..' not in path.parts and str(path) == p['dedicated_credential_file'], 'invalid credential reference')
    for k in ('issued_at', 'expires_at'): number(p[k])
    need(p['issued_at'] < p['expires_at'], 'invalid plan interval')
    return estimate


def require_remote_contract(contract=None, observed=None, now=None):
    """Return local validation receipt; never authorize a remote call or consume approval."""
    fields(contract, 'plan fee_authorization')
    p, auth = contract['plan'], contract['fee_authorization']
    estimate = validate_plan(p)
    validate_plan(observed)
    need(canonical(p) == canonical(observed), 'input drift or budget enlargement')
    fields(auth, 'approved approver record_id plan_sha256 granted_at expires_at')
    need(auth['approved'] is True, 'explicit approval missing')
    for k in ('approver', 'record_id'): string(auth[k])
    sha(auth['plan_sha256'])
    need(auth['plan_sha256'] == digest(p), 'authorization plan mismatch')
    for k in ('granted_at', 'expires_at'): number(auth[k])
    checked = time.time() if now is None else now
    number(checked)
    need(p['issued_at'] <= auth['granted_at'] <= checked < auth['expires_at'] <= p['expires_at'], 'expired or invalid authorization interval')
    return dict(schema_version=1, status='local_contract_valid', run_id=p['run_id'],
                plan_sha256=digest(p), observed_sha256=digest(observed),
                authorization_sha256=digest(auth), checked_at=checked,
                estimated_allowance_cny=estimate, invoice=None, supplier_invoice=None,
                remote_execution_allowed=False, session_fee_authorization=False,
                approval_consumed=False, host_attestation=False,
                trust='caller_supplied_inputs_only')


def template(p):
    validate_plan(p)
    return dict(plan_sha256=digest(p), approved=False, approver=None, record_id=None,
                granted_at=None, expires_at=None)


def load(path):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON field')
            out[k] = v
        return out
    return json.loads(path.read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('command', choices=('template', 'preflight'))
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--observed', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'template':
            receipt = dict(status='unapproved_template', plan=load(args.plan))
            receipt['fee_authorization'] = template(receipt['plan'])
        else:
            need(args.authorization is not None and args.observed is not None, 'missing authorization/observed input')
            receipt = require_remote_contract(dict(plan=load(args.plan), fee_authorization=load(args.authorization)), load(args.observed))
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
        print(json.dumps(dict(status='rejected', error=str(exc), remote_execution_allowed=False), allow_nan=False))
        return 2
    print(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
