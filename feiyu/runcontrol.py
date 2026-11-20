"""Durable parent-task model accounting; synchronous SDK calls stay synchronous."""
import threading
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar

active_control = ContextVar("model_control", default=None)


class RunStopped(KeyboardInterrupt):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class RunControl:
    def __init__(self, store, state, *, cost_limit=0, time_limit=0):
        self.store, self.state = store, state
        self.cancelled = threading.Event()
        self.lock = threading.RLock()
        self._background_lock = threading.Lock()
        self._background_cost = self._background_time = 0
        self._background_deadline = self._background_mono = None
        b = state.budget
        if not b.get('control_version'):
            # Historical costs are session totals, never a fresh task allowance.
            legacy = bool(b)
            if legacy:
                if b.get('cost') is not None:
                    b['legacy_session_cost'] = b.get('cost', 0)
                b['legacy_session_tokens'] = b.get('tokens', 0)
            b.update(control_version=1, cost=None if legacy else 0.0,
                     tokens=0, known_cost=0.0, unknown_attempts=int(legacy),
                     pending_attempts=0, attempts=0)
        if b.get('pending_attempts'):
            b['cost'] = None  # an interrupted request has no trustworthy final total
        old = b.get('cost_limit', 0)
        b['cost_limit'] = min(old, cost_limit) if old and cost_limit else old or cost_limit
        old_time = b.get('time_limit', 0)
        b['time_limit'] = min(old_time, time_limit) if old_time and time_limit else old_time or time_limit
        origin = min((r['at'] for r in state.requests), default=b.get('started_at', time.time()))
        b.setdefault('started_at', origin)
        if b['time_limit']:
            candidate = b['started_at'] + b['time_limit']
            b['deadline'] = min(b.get('deadline') or candidate, candidate)
        self.monotonic_deadline = (time.monotonic() + max(0, b['deadline'] - time.time())
                                   if b.get('deadline') else None)
        self._save()

    def tighten(self, cost_limit=0, time_limit=0):
        # Publish before waiting for the request ledger lock. The owner observes
        # these monotonic limits while its SDK process is silent.
        with self._background_lock:
            self._background_cost = min((v for v in (cost_limit, self._background_cost) if v), default=0)
            self._background_time = min((v for v in (time_limit, self._background_time) if v), default=0)
        if not self.lock.acquire(blocking=False):
            return  # request owner persists published limits on its next poll
        try:
            cost_limit = min((v for v in (cost_limit, self._background_cost) if v), default=0)
            time_limit = min((v for v in (time_limit, self._background_time) if v), default=0)
            b = self.state.budget
            changed = False
            for key, value in (('cost_limit', cost_limit), ('time_limit', time_limit)):
                old = b.get(key, 0)
                if value and (not old or value < old):
                    b[key] = value
                    changed = True
            if changed:
                if b.get('time_limit'):
                    b.setdefault('started_at', min((r['at'] for r in self.state.requests), default=time.time()))
                    candidate = b['started_at'] + b['time_limit']
                    b['deadline'] = min(b.get('deadline') or candidate, candidate)
                    candidate_mono = time.monotonic() + max(0, b['deadline'] - time.time())
                    self.monotonic_deadline = min(self.monotonic_deadline or candidate_mono, candidate_mono)
                self._save()
        finally:
            self.lock.release()

    def _save(self):
        try:
            self.store.save(self.state)
        except BaseException:
            self.blocked = True
            self.store.blocked = True
            raise

    def check(self, *, inflight=False):
        if getattr(self, 'background_error', None) is not None:
            raise self.background_error
        if getattr(self, 'limit_source', None):
            self.tighten(*self.limit_source())
        if getattr(self, 'blocked', False) or getattr(self.store, 'blocked', False):
            from .taskstate import PersistenceError
            raise PersistenceError('模型记账持久化受阻；禁止后续请求')
        b = self.state.budget
        reason = ('cancelled' if self.cancelled.is_set() else
                  'deadline_stopped' if b.get('deadline') and (time.time() >= b['deadline'] or time.monotonic() >= self.monotonic_deadline) else
                  'budget_stopped' if not inflight and b.get('cost_limit') and (
                      b.get('pending_attempts') or b.get('unknown_attempts') or
                      b.get('cost') is None or b['cost'] >= b['cost_limit']) else '')
        if reason:
            self.state.run_state = 'interrupted' if reason == 'cancelled' else reason
            raise RunStopped(reason)

    def background_limits(self):
        """Never wait behind a synchronous request holding the admission lock."""
        limits = self.limit_source() if getattr(self, 'limit_source', None) else (0, 0)
        with self._background_lock:
            b = dict(self.state.budget)
            self._background_cost = min((v for v in (
                self._background_cost, b.get('cost_limit', 0), limits[0]) if v), default=0)
            self._background_time = min((v for v in (
                self._background_time, b.get('time_limit', 0), limits[1]) if v), default=0)
            deadline = b.get('deadline')
            if self._background_time:
                candidate = b['started_at'] + self._background_time
                deadline = min(deadline or candidate, candidate)
            if deadline:
                self._background_deadline = min(self._background_deadline or deadline, deadline)
                candidate = time.monotonic() + max(0, self._background_deadline - time.time())
                self._background_mono = min(self._background_mono or candidate, candidate)
            cost, duration = self._background_cost, self._background_time
            deadline, mono = self._background_deadline, self._background_mono
        if self.lock.acquire(blocking=False):
            try:
                self.tighten(cost, duration)
            finally:
                self.lock.release()
        if getattr(self, 'background_error', None) is not None:
            raise self.background_error
        if getattr(self, 'blocked', False) or getattr(self.store, 'blocked', False):
            from .taskstate import PersistenceError
            raise PersistenceError('任务持久化受阻；停止后台任务')
        reason = ('cancelled' if self.cancelled.is_set() else
                  'deadline_stopped' if deadline and (
                      time.time() >= deadline or
                      mono is not None and time.monotonic() >= mono) else
                  'budget_stopped' if cost and (b.get('unknown_attempts') or
                      b.get('cost') is None or b['cost'] >= cost) else '')
        return deadline, reason

    def cancel(self):
        self.cancelled.set()

    def wait(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.check()
            self.cancelled.wait(min(.05, max(0, end - time.monotonic())))
        self.check()

    @contextmanager
    def attempt(self, backend, report=None):
        if report is None and getattr(backend, 'attempt_accounting', False) and hasattr(backend, 'client'):
            token = active_control.set(self)
            try:
                yield
            finally:
                active_control.reset(token)
            return
        # Serialize model branches under a finite shared allowance: no concurrent
        # admission against the same remaining funds. A request can overshoot.
        while not self.lock.acquire(timeout=.05):
            _, reason = self.background_limits()
            if reason:
                raise RunStopped(reason)
        try:
            self.check()
            b = self.state.budget
            before_tokens = getattr(backend, 'tokens_total', 0)
            before_cost = getattr(backend, 'cost', 0.0)
            before_reports = getattr(backend, 'usage_reports', 0)
            b['attempts'] += 1
            b['pending_attempts'] += 1
            row = dict(sequence=b['attempts'], state='pending', usage_status='unknown',
                       started_at=time.time(), model=str(getattr(backend, 'model', '')))
            b.setdefault('attempt_records', []).append(row)
            self._save()  # failure must prevent the request
            try:
                yield
            finally:
                tokens = getattr(backend, 'tokens_total', 0) - before_tokens
                cost = getattr(backend, 'cost', 0.0) - before_cost
                reported = getattr(backend, 'usage_reports', 0) > before_reports
                # Counter deltas also support existing provider/test adapters.
                known = (reported or tokens > 0 or cost > 0) if report is None else report.get('complete', False)
                b['tokens'] += max(0, tokens)
                b['known_cost'] += max(0, cost)
                if b['cost'] is not None:
                    b['cost'] += max(0, cost)
                price_known = (getattr(backend, 'priced', False) if report is None
                               else getattr(backend, 'rates', None) is not None)
                row.update(state='finished', finished_at=time.time(), tokens=max(0, tokens),
                           known_cost=max(0, cost), price_known=price_known,
                           usage_status='complete' if known else 'partial' if reported else 'unknown')
                if report is not None:
                    row['usage'] = dict(report.get('usage', {}))
                    row['outcome'] = 'returned' if report.get('succeeded') else 'failed_or_interrupted'
                if report is not None and reported and not known:
                    b['partial_attempts'] = b.get('partial_attempts', 0) + 1
                if not known or tokens < 0 or cost < 0 or not price_known:
                    b['unknown_attempts'] += 1
                    b['cost'] = None
                b['pending_attempts'] -= 1
                original = sys.exc_info()[1]
                try:
                    self._save()
                except BaseException as save_error:
                    if original is None:
                        raise
                    original.accounting_error = save_error
        finally:
            self.lock.release()
