"""One physical SDK attempt; imports no product modules or credential loaders."""
import importlib.metadata
import json
import sys


def send(kind, **fields):
    print(json.dumps(dict(kind=kind, **fields), allow_nan=False), flush=True)


def validate_usage(value):
    usage = value.get('usage')
    if usage is not None:
        if not isinstance(usage, dict):
            raise ValueError('invalid raw usage')
        for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            n = usage.get(key)
            if type(n) is not int or n < 0:
                raise ValueError('invalid raw token usage')


def raw_usage_guard(httpx, streaming, validator=validate_usage):
    def hook(response):
        if response.status_code != 200:
            return
        original = response.stream
        class CheckedStream(httpx.SyncByteStream):
            def __iter__(self):
                pending = b''
                data = []
                previous_cr = False
                def event():
                    if data:
                        raw = b'\n'.join(data)
                        if raw != b'[DONE]':
                            validator(json.loads(raw))
                        data.clear()
                for chunk in original:
                    if streaming:
                        normalized = bytearray()
                        for byte in chunk:
                            if byte == 10 and previous_cr:
                                previous_cr = False
                                continue
                            normalized.append(10 if byte == 13 else byte)
                            previous_cr = byte == 13
                        pending += normalized
                    else:
                        pending += chunk
                    if len(pending) + sum(map(len, data)) > 8*1024*1024:
                        raise ValueError('raw response too large')
                    if streaming:
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            line = line.rstrip(b'\r')
                            if not line:
                                event()
                            elif line.startswith(b'data:'):
                                data.append(line[5:].lstrip(b' '))
                    yield chunk
                if streaming:
                    if pending.startswith(b'data:'):
                        data.append(pending[5:].strip())
                    event()
                else:
                    validator(json.loads(pending))
            def close(self):
                original.close()
        response.stream = CheckedStream()
    return hook


def main():
    req = json.loads(sys.stdin.readline())
    from urllib.parse import urlsplit
    url = urlsplit(req['endpoint'])
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or
            url.username or url.password or url.query or url.fragment or url.path != '/v1'):
        raise ValueError('remote SDK endpoint disabled')
    import importlib
    import inspect
    from openai import OpenAI
    annotation = str(inspect.signature(OpenAI).parameters['http_client'].annotation)
    httpx = importlib.import_module('httpx2' if 'httpx2' in annotation else 'httpx')
    send('sdk', version=importlib.metadata.version('openai'))
    try:
        with httpx.Client(trust_env=False, follow_redirects=False, event_hooks={'response': [raw_usage_guard(httpx, req['params'].get('stream') is True)]}) as http:
            with OpenAI(api_key='synthetic-evaluation-key', base_url=req['endpoint'],
                        max_retries=0, http_client=http) as client:
                response = client.chat.completions.create(**req['params'])
                if req['params'].get('stream'):
                    with response:
                        for chunk in response:
                            send('value', value=chunk.model_dump(mode='json'))
                else:
                    send('value', value=response.model_dump(mode='json'))
        send('done')
    except Exception as exc:
        send('error', error=type(exc).__name__)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
