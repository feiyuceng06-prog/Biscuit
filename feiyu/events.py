"""Run-owned diagnostic routing; never an execution grant or durable journal."""
from contextvars import ContextVar, copy_context
from contextlib import contextmanager
from functools import wraps
import threading
import uuid

_sink = ContextVar('event_sink', default=None)
_route = ContextVar('event_route', default=None)


def install(fn) -> None:
    """Legacy installation affects only the calling context."""
    _sink.set(fn)


def clear() -> None:
    _sink.set(None)


def active() -> bool:
    return _sink.get() is not None


class binding:
    def __init__(self, sink, route=None):
        self.sink, self.route = sink, route

    def __enter__(self):
        self.tokens = (_sink.set(self.sink), _route.set(self.route))
        return self

    def __exit__(self, *exc):
        _route.reset(self.tokens[1])
        _sink.reset(self.tokens[0])
        return False


class paused(binding):
    """Suppress presentation only in this context, including nested failures."""
    def __init__(self):
        super().__init__(None)


class capturing(binding):
    RANK = {'notice': 0, 'warn': 1, 'error': 2}

    def __init__(self):
        self.level = 'notice'
        super().__init__(self._take)

    def _take(self, kind, payload):
        if kind == 'note':
            got = payload.get('level', 'notice')
            if self.RANK.get(got, 0) > self.RANK[self.level]:
                self.level = got


def _deliver(sink, kind, payload):
    if sink is not None:
        try:
            sink(kind, payload)
        except Exception:
            pass  # Only frontend delivery is best effort.


class Route:
    def __init__(self, sink, session_id=None, task_id=None):
        self.sink = sink
        self.session_id, self.task_id = session_id, task_id
        self.run_id = uuid.uuid4().hex
        self.seq = 0
        self.closed = False
        self.lock = threading.RLock()

    def emit(self, kind, **payload):
        # Serialize allocation AND delivery so concurrent workers cannot reorder seq.
        with self.lock:
            if self.closed:
                return
            self.seq += 1
            payload = dict(payload, session_id=self.session_id, task_id=self.task_id,
                           run_id=self.run_id, seq=self.seq)
            _deliver(self.sink, kind, payload)

    def close(self):
        with self.lock:
            self.closed = True


def emit(kind: str, **payload) -> None:
    route = _route.get()
    if route is not None:
        route.emit(kind, **payload)
    else:
        _deliver(_sink.get(), kind, payload)


def fact(kind, **payload):
    emit(kind, **dict({'source_kind': 'program_state'}, **payload))


def admitted(session_id, task_id):
    route = _route.get()
    if route is not None:
        route.session_id, route.task_id = session_id, task_id


def submit(pool, fn, *args, **kwargs):
    """One context per submission; never assume threads inherit ContextVars."""
    return pool.submit(copy_context().run, fn, *args, **kwargs)


def running(fn):
    @wraps(fn)
    def call(agent, *args, **kwargs):
        sink = getattr(agent, 'event_sink', None)
        if sink is None and _route.get() is None:
            sink = _sink.get()
        if sink is None:
            from . import ui
            sink = ui.runtime_event
        route = Route(sink, agent.session_id, agent.task_id)
        route.owner = agent
        try:
            with binding(sink, route):
                return fn(agent, *args, **kwargs)
        finally:
            route.close()
    return call


def owned_fact(agent, kind, **payload):
    route = _route.get()
    if route is not None and getattr(route, 'owner', None) is agent:
        route.emit(kind, **dict({'source_kind': 'program_state'}, **payload))
        return
    # Commands outside send have their own one-fact run. Never borrow another
    # agent's current route/sink, including in nested calls.
    sink = getattr(agent, 'event_sink', None)
    if sink is None and route is None:
        sink = _sink.get()
    if sink is None:
        from . import ui
        sink = ui.runtime_event
    command = Route(sink, agent.session_id, agent.task_id)
    command.emit(kind, **dict({'source_kind': 'program_state'}, **payload))
    command.close()


@contextmanager
def frontend(agent, sink):
    previous = getattr(agent, 'event_sink', None)
    agent.event_sink = sink
    try:
        with binding(sink):
            yield
    finally:
        agent.event_sink = previous
