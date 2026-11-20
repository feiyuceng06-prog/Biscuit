"""Anthropic Messages semantics, exclusively for synthetic offline evaluation."""
from pathlib import Path
from evals.architecture_sdk import SDKTransport

KEYS = ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')


def validate_usage(value):
    kind = value.get('type')
    if kind not in ('message', 'message_start', 'message_delta', 'message_stop',
                    'content_block_start', 'content_block_delta', 'content_block_stop', 'ping'):
        raise ValueError('unknown Anthropic event')
    obj = value.get('message', {}) if kind == 'message_start' else value
    if 'usage' not in obj:
        if kind in ('message', 'message_start', 'message_delta'):
            raise ValueError('missing Anthropic usage')
        return
    usage = obj['usage']
    if not isinstance(usage, dict) or not set(usage) <= set(KEYS) | {'cache_creation', 'server_tool_use', 'service_tier', 'inference_geo'}:
        raise ValueError('unknown Anthropic usage')
    required = ('output_tokens',) if kind == 'message_delta' else ('input_tokens', 'output_tokens')
    if any(k not in usage for k in required):
        raise ValueError('missing Anthropic token counter')
    for k in KEYS:
        if k in usage and (type(usage[k]) is not int or usage[k] < 0):
            raise ValueError('invalid raw Anthropic token counter')
    # Non-token metadata is deliberately unsupported in this limited fixture path.
    if set(usage) & {'server_tool_use', 'service_tier', 'inference_geo'}:
        raise ValueError('unsupported Anthropic usage metadata')
    if 'cache_creation' in usage:
        nested = usage['cache_creation']
        if (not isinstance(nested, dict) or set(nested) != {'ephemeral_5m_input_tokens', 'ephemeral_1h_input_tokens'} or
                any(type(n) is not int or n < 0 for n in nested.values()) or
                sum(nested.values()) != usage.get('cache_creation_input_tokens')):
            raise ValueError('invalid cache creation breakdown')


class AnthropicTransport(SDKTransport):
    usage_keys = KEYS

    def __init__(self, endpoint, model, rates=(1., 2., .1, 1.25), child_path=None):
        super().__init__(endpoint, model, rates, child_path or Path(__file__).with_name('architecture_anthropic_child.py'))

    def observe(self, value, receipt):
        # Final SDK Message may add optional null fields; raw validation happened
        # before SDK conversion. Initial and delta counters are cumulative maxima.
        obj = value.get('message', {}) if value.get('type') == 'message_start' else value
        super().observe(obj, receipt)

    def complete(self, chunks, receipt, params):
        if params.get('stream'):
            state = 'initial'
            for event in chunks[:-1]:
                kind = event.get('type')
                if kind == 'ping':
                    continue
                if kind == 'message_start' and state == 'initial':
                    if event.get('message', {}).get('stop_reason') is not None:
                        raise RuntimeError('premature Anthropic stop reason')
                    state = 'active'
                elif kind == 'message_delta' and state == 'active':
                    reason = event.get('delta', {}).get('stop_reason')
                    output = event.get('usage', {}).get('output_tokens')
                    if type(output) is not int or output < 0:
                        raise RuntimeError('missing Anthropic terminal usage')
                    if reason in ('end_turn', 'tool_use'):
                        state = 'terminal_delta'
                    elif reason is not None:
                        raise RuntimeError('incomplete Anthropic stop reason')
                elif kind == 'message_stop' and state == 'terminal_delta':
                    state = 'stopped'
                elif kind in ('content_block_start', 'content_block_delta', 'content_block_stop',
                              'text', 'input_json', 'citation', 'thinking', 'signature') and state == 'active':
                    continue
                else:
                    raise RuntimeError('invalid Anthropic terminal event order')
            if state != 'stopped':
                raise RuntimeError('missing Anthropic message_stop')
        final = chunks[-1] if chunks else {}
        if final.get('type') != 'message' or final.get('stop_reason') not in ('end_turn', 'tool_use'):
            raise RuntimeError('missing/incomplete Anthropic final message')
        usage = final.get('usage') or {}
        for key in KEYS:
            n = usage.get(key, 0) if key.startswith('cache_') else usage.get(key)
            # SDK optional cache null represents absence in raw response.
            if key.startswith('cache_') and n is None:
                n = 0
            if type(n) is not int or n < 0 or n < receipt['usage_lower_bound'].get(key, 0):
                raise RuntimeError('unknown/nonmonotonic Anthropic usage')
            receipt['usage_lower_bound'][key] = n
        return dict(version=self.model, text=''.join(b['text'] for b in final['content'] if b['type'] == 'text'),
                    calls=[dict(id=b['id'], name=b['name'], input=b['input']) for b in final['content'] if b['type'] == 'tool_use'])
