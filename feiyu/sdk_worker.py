"""One SDK call per disposable process; no application configuration or ledger."""
import json
import os
import struct
import subprocess
import sys
import time

VERSION = 1
MAX_FRAME = 64 * 1024 * 1024
POLL = .05


class WorkerError(RuntimeError):
    pass


def plain(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def frame(kind, **data):
    raw = json.dumps(dict(v=VERSION, kind=kind, **data), ensure_ascii=True).encode()
    if len(raw) > MAX_FRAME:
        raise WorkerError('SDK IPC frame exceeds 64 MiB limit')
    return struct.pack('!I', len(raw)) + raw


def decode(raw):
    msg = json.loads(raw)
    if not isinstance(msg, dict) or msg.get('v') != VERSION:
        raise WorkerError('SDK IPC version mismatch')
    return msg


def restore(provider, kind, value):
    if provider == 'anthropic':
        from anthropic._models import construct_type
        from anthropic.types import Message, RawMessageStreamEvent
        typ = RawMessageStreamEvent if kind == 'event' else Message
    else:
        from openai._models import construct_type
        from openai.types.chat import ChatCompletion, ChatCompletionChunk
        typ = ChatCompletionChunk if kind == 'event' else ChatCompletion
    return construct_type(value=value, type_=typ)


def worker_main():
    def read(n):
        out = bytearray()
        while len(out) < n:
            part = sys.stdin.buffer.read(n - len(out))
            if not part:
                raise EOFError()
            out.extend(part)
        return bytes(out)

    def send(kind, **data):
        sys.stdout.buffer.write(frame(kind, **data))
        sys.stdout.buffer.flush()

    try:
        size = struct.unpack('!I', read(4))[0]
        if size > MAX_FRAME:
            return 2
        req = decode(read(size))
        if req['kind'] != 'request' or req['provider'] not in ('anthropic', 'openai'):
            return 2
        provider = req['provider']
        if provider == 'anthropic':
            from anthropic import Anthropic as Client
        else:
            from openai import OpenAI as Client
        with Client(**req['client'], max_retries=0) as client:
            api = client.messages if provider == 'anthropic' else client.chat.completions
            if req['operation'] == 'ask':
                send('result', value=plain(api.create(**req['kwargs'])))
            elif req['operation'] == 'stream':
                if provider == 'anthropic':
                    with api.stream(**req['kwargs']) as stream:
                        for event in stream:
                            send('event', value=plain(event))
                        send('result', value=plain(stream.get_final_message()))
                else:
                    with api.create(**req['kwargs']) as stream:
                        for event in stream:
                            send('event', value=plain(event))
            else:
                return 2
        send('done')
        return 0
    except Exception as exc:
        # Only predicates used by parent retry/cache policy cross the trust boundary.
        code = getattr(exc, 'status_code', None)
        directive = getattr(getattr(exc, 'response', None), 'headers', {}).get('x-should-retry')
        from .providers import _cache_rejected
        from .sdk_errors import OVERFLOW_WORDS, _LIMIT_IN_ERROR, MIN_LEARNED_LIMIT
        text = str(exc)
        overflow = (not isinstance(code, int) or code in (400, 413, 422)) and bool(OVERFLOW_WORDS.search(text))
        context_limit = next((int(m.group(1) or m.group(2)) for m in _LIMIT_IN_ERROR.finditer(text)
                              if int(m.group(1) or m.group(2)) >= MIN_LEARNED_LIMIT), 0)
        try:
            send('error', name=type(exc).__name__ if type(exc).__name__ in (
                'APIConnectionError', 'APITimeoutError', 'RetryableError') else 'SDKError',
                 status=code if type(code) is int else None,
                 retry=directive if directive in ('true', 'false') else None,
                 cache_rejected=bool(_cache_rejected(exc)), overflow=overflow, context_limit=context_limit)
        except Exception:
            pass
        return 1


def check(control):
    if control:
        from .runcontrol import RunStopped
        _, reason = control.background_limits()
        if reason:
            control.state.run_state = 'interrupted' if reason == 'cancelled' else reason
            raise RunStopped(reason)
        control.check(inflight=True)


class Exchange:
    def __init__(self, provider, client, operation, kwargs, control, observe=None):
        self.observe = observe
        self.provider, self.control = provider, control
        self.proc = None
        self.writer = None
        self.owner_fd = self.receipt_fd = None
        self.lifecycle = None
        self.result = None
        self.done = False
        self.buf = bytearray()
        self.request = frame('request', provider=provider, client=client,
                             operation=operation, kwargs=plain(kwargs))

    def __enter__(self):
        check(self.control)
        argv = [sys.executable, '--_sdk-worker'] if getattr(sys, 'frozen', False) else [
            sys.executable, '-m', 'feiyu', '--_sdk-worker']
        try:
            from .processwait import _defer_interrupt
            with _defer_interrupt() as pending:
                options = {}
                if sys.platform == 'linux':
                    from .sdk_lifecycle import reserve
                    self.receipt_fd, self.lifecycle = reserve()
                    # Persist correlation before any SDK child can exist. Receipts
                    # never finish an attempt or change the usage ledger.
                    if self.control:
                        rows = self.control.state.budget.get('attempt_records', [])
                        if rows and rows[-1]['state'] == 'pending':
                            rows[-1]['local_worker'] = self.lifecycle
                            self.control._save()
                    reader, self.owner_fd = os.pipe()
                    argv = argv[:-1] + ['--_sdk-supervisor', str(reader), str(self.receipt_fd),
                                        self.lifecycle['token'], str(os.getpid())]
                    options['pass_fds'] = (reader, self.receipt_fd)
                try:
                    self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                 stderr=subprocess.DEVNULL, bufsize=0, **options)
                finally:
                    if sys.platform == 'linux' and self.owner_fd is not None:
                        os.close(reader)
            if pending[0]:
                from .runcontrol import RunStopped
                raise RunStopped('cancelled')
            if os.name == 'nt':
                from .sdk_windows import Pipe
                self.pipe = Pipe(self.proc.stdin, self.proc.stdout)
                self.writer = self.pipe
                self.pipe.send(self.request, lambda: check(self.control))
            else:
                import select
                for stream in (self.proc.stdin, self.proc.stdout):
                    os.set_blocking(stream.fileno(), False)
                left = memoryview(self.request)
                while left:
                    check(self.control)
                    _, ready, _ = select.select([], [self.proc.stdin], [], POLL)
                    if ready:
                        try:
                            left = left[os.write(self.proc.stdin.fileno(), left[:65536]):]
                        except BlockingIOError:
                            pass
            self.request = None
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def _read(self):
        check(self.control)
        if os.name == 'nt':
            return self.pipe.read(POLL)
        import select
        ready, _, _ = select.select([self.proc.stdout], [], [], POLL)
        return os.read(self.proc.stdout.fileno(), 65536) if ready else None

    def __iter__(self):
        while not self.done:
            check(self.control)
            if len(self.buf) >= 4:
                size = struct.unpack('!I', self.buf[:4])[0]
                if size > MAX_FRAME:
                    raise WorkerError('SDK IPC oversized response')
                if len(self.buf) >= size + 4:
                    msg = decode(self.buf[4:4 + size])
                    del self.buf[:4 + size]
                    check(self.control)  # never import a late result after stop
                    kind = msg['kind']
                    if kind == 'done':
                        self.done = True
                    elif kind == 'error':
                        from types import SimpleNamespace
                        name = msg.get('name')
                        cls = type(name if name in ('APIConnectionError', 'APITimeoutError',
                            'RetryableError') else 'SDKError', (WorkerError,), {})
                        exc = cls('SDK worker request failed (details redacted)')
                        exc.status_code = msg.get('status')
                        exc.response = SimpleNamespace(headers={'x-should-retry': msg.get('retry')})
                        exc.sdk_cache_rejected = msg.get('cache_rejected', False)
                        exc.sdk_overflow = msg.get('overflow', False)
                        exc.sdk_context_limit = msg.get('context_limit', 0)
                        raise exc
                    elif kind == 'result':
                        self.result = restore(self.provider, kind, msg['value'])
                        if self.observe:
                            self.observe(getattr(self.result, 'usage', None))
                    elif kind == 'event':
                        yield restore(self.provider, kind, msg['value'])
                    else:
                        raise WorkerError('SDK IPC unexpected frame')
                    continue
            part = self._read()
            if part == b'':
                raise WorkerError('SDK worker exited without terminal frame; usage unknown')
            if part:
                self.buf.extend(part)

    def get_final_message(self):
        if not self.done or self.result is None:
            raise WorkerError('SDK worker missing final message')
        return self.result

    def close(self):
        self.__exit__(*sys.exc_info())

    def __exit__(self, typ, exc, tb):
        from .processwait import _defer_interrupt
        with _defer_interrupt() as pending:
            self._cleanup(exc)
        if pending[0] and exc is None:
            from .runcontrol import RunStopped
            raise RunStopped('cancelled')
        if exc is None:
            check(self.control)

    def _cleanup(self, exc):
        errors = []
        proc = self.proc
        if self.owner_fd is not None:
            os.close(self.owner_fd)
            self.owner_fd = None
        if proc is None:
            if self.receipt_fd is not None:
                os.close(self.receipt_fd)
                self.receipt_fd = None
            return
        try:
            if self.lifecycle is None and proc.poll() is None:
                proc.kill()
            proc.wait(timeout=3)
            if self.lifecycle is not None:
                from .sdk_lifecycle import read_receipt
                read_receipt(self.receipt_fd, self.lifecycle['token'])
        except BaseException as cleanup:
            errors.append(type(cleanup).__name__)
            # A failed supervisor is outside the confirmed-reap guarantee. Do
            # not leave its own process running or turn this into a retry.
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=1)
            except BaseException:
                pass
        if self.receipt_fd is not None:
            os.close(self.receipt_fd)
            self.receipt_fd = None
        if self.writer:
            try:
                self.writer.join()
            except BaseException as cleanup:
                errors.append(type(cleanup).__name__)
        for stream in (proc.stdin, proc.stdout):
            try:
                stream.close()
            except BaseException as cleanup:
                errors.append(type(cleanup).__name__)
        if errors:
            message = 'SDK worker cleanup unknown: ' + ', '.join(errors)
            if exc is not None:
                exc.sdk_cleanup_error = message
            else:
                raise WorkerError(message)


def ask(provider, client, kwargs, control, observe=None):
    with Exchange(provider, client, 'ask', kwargs, control, observe) as exchange:
        for _ in exchange:
            raise WorkerError('SDK ask received stream event')
        return exchange.get_final_message()
