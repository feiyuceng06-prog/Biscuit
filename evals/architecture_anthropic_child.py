"""One physical Anthropic SDK attempt, no product/config imports."""
import importlib.metadata
import json
import sys
from pathlib import Path

# Frozen sibling modules, never mutable checkout imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.architecture_sdk_child import send, raw_usage_guard
from evals.architecture_anthropic import validate_usage


def main():
    req = json.loads(sys.stdin.readline())
    from urllib.parse import urlsplit
    u = urlsplit(req['endpoint'])
    if (u.scheme != 'http' or u.hostname != '127.0.0.1' or not u.port or
            u.username or u.password or u.query or u.fragment or u.path != '/v1'):
        raise ValueError('remote SDK endpoint disabled')
    import anthropic
    import importlib
    import inspect
    annotation = str(inspect.signature(anthropic.Anthropic).parameters['http_client'].annotation)
    httpx = importlib.import_module('httpx2' if 'httpx2' in annotation else 'httpx')
    send('sdk', version=importlib.metadata.version('anthropic'))
    try:
        params = dict(req['params'])
        streaming = params.pop('stream', False)
        with httpx.Client(trust_env=False, follow_redirects=False,
                event_hooks={'response': [raw_usage_guard(httpx, streaming, validate_usage)]}) as http:
            with anthropic.Anthropic(api_key='synthetic-evaluation-key', base_url=req['endpoint'],
                    max_retries=0, http_client=http) as client:
                if streaming:
                    with client.messages.stream(**params) as stream:
                        for event in stream:
                            send('value', value=event.model_dump(mode='json'))
                        send('value', value=stream.get_final_message().model_dump(mode='json'))
                else:
                    send('value', value=client.messages.create(**params).model_dump(mode='json'))
        send('done')
    except Exception as exc:
        send('error', error=type(exc).__name__+': '+str(exc))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
