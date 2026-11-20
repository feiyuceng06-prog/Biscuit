"""Shared execution boundary. Records are diagnostic, not a durable recovery journal."""
from dataclasses import dataclass
from contextvars import ContextVar
import time
import uuid

from .schema import validate


PARALLEL_SAFE = frozenset({'read_file', 'list_files', 'search', 'web_fetch',
                           'web_search', 'task', 'skill'})


@dataclass(frozen=True)
class ToolSpec:
    schema: dict
    scope: str = 'workspace'
    effects: str = 'unknown'
    concurrency: str = 'serial'
    network: str = 'possible'
    retry: str = 'never'
    output_budget: int = 30000


class Executor:
    def __init__(self, box):
        self.box = box
        self.records = []
        self.emit = None
        self.durable = None
        self.control = None
        self.authorizations = {}
        self.active_operation = ContextVar("active_operation", default=None)
        self.call_id = ContextVar("execution_call_id", default=None)

    def job_control(self, name):
        return name == 'job' and name not in self.box.mcp.tools

    def spec(self, name):
        from .tools import TOOL_SCHEMAS
        remote = name in self.box.mcp.tools
        schemas = self.box.mcp.schemas() if remote else TOOL_SCHEMAS
        schema = next((s['input_schema'] for s in schemas if s['name'] == name), None)
        if schema is None:
            return None
        return ToolSpec(schema, scope='external' if remote else 'workspace',
                        effects='read/network' if name in PARALLEL_SAFE and not remote else 'unknown/write',
                        concurrency='parallel' if name in PARALLEL_SAFE and not remote else 'serial')

    def problem(self, name, args):
        if not isinstance(args, dict):
            return '参数应该是 object'
        try:
            spec = self.spec(name)
        except Exception as exc:
            return '工具 schema 不可用: %s' % exc
        if spec is None:
            return '未知工具: ' + name
        try:
            if isinstance(spec.schema, dict):
                missing = [k for k in spec.schema.get('required', ()) if k not in args]
                if missing:
                    return '缺少参数 ' + ' / '.join(missing)
            return ' / '.join(validate(args, spec.schema))
        except (TypeError, ValueError, AttributeError, RecursionError) as exc:
            return '工具参数 schema 校验失败: %s' % exc

    def parallel(self, call):
        try:
            spec = self.spec(call.name)
            return not call.error and spec is not None and spec.concurrency == 'parallel'
        except Exception:
            return False

    def dispatch(self, call, runner):
        if self.control and not self.job_control(call.name):
            self.control.check()
        token = self.call_id.set(call.id)
        try:
            return runner(call.name, call.input)
        finally:
            self.call_id.reset(token)

    def prepare(self, call, gate, pre, allow_all=False):
        if self.control and not self.job_control(call.name):
            self.control.check()
        problem = call.error or self.problem(call.name, call.input)
        if problem:
            self.reject(call.name, problem, call_id=call.id)
            return False, False, '参数错误', problem
        answer = gate(call, allow_all)
        if not answer[0]:
            self.reject(call.name, answer[3], call_id=call.id)
            return answer
        veto = pre(call)
        if veto:
            self.reject(call.name, veto, call_id=call.id)
            return False, answer[1], '钩子拦下', veto
        self.authorizations[call.id] = dict(source='execution-gate', decision='allowed', at=time.time(), scope='exact-call')
        return answer

    def reject(self, name, reason, source='model', call_id=None):
        self.invoke(name, {}, lambda: None, source=source, rejected=reason, call_id=call_id)

    def diagnostic(self, event, record):
        if self.emit:
            try:
                self.emit(event, **record)
            except Exception:
                pass  # Diagnostics must never alter execution facts.

    def invoke(self, name, args, operation, *, source='model', rejected='', cwd=None, call_id=None, authorization=None):
        from . import sandbox
        if self.control and not rejected and not self.job_control(name) and name not in self.box.mcp.tools:
            self.control.check()
        record = dict(call_id=call_id or self.call_id.get(), sandbox=sandbox.effective(), id=uuid.uuid4().hex, name=name, source=source,
                      cwd=str(cwd or self.box.cwd), args=args, started=time.time(), state='prepared')
        record['authorization'] = authorization or self.authorizations.pop(record['call_id'], 'caller-boundary; not a reusable grant')
        self.records.append(record)
        durable_op = None
        if self.durable and not rejected:
            spec = self.spec(name)
            if not self.job_control(name) and (spec is None or spec.effects == 'unknown/write' or source != 'model'):
                store, state = self.durable
                durable_op = store.prepare(state, record)
        op_token = self.active_operation.set(durable_op)
        self.diagnostic('execution_start', record)
        start = time.monotonic()
        try:
            if rejected:
                record.update(state='rejected', error=rejected)
                return None
            record['state'] = 'running'
            result = operation()
            record.update(exit_code=getattr(result, 'exit_code', getattr(result, 'code', None)),
                          truncated=getattr(result, 'truncated', False),
                          execution_started=getattr(result, 'execution_started', None),
                          stop_reason=getattr(result, 'stop_reason', ''),
                          evidence_error=getattr(result, 'evidence_error', ''))
            record['state'] = 'not_run' if getattr(result, 'execution_not_run', False) else 'unknown' if getattr(result, 'execution_unknown', False) else 'failed' if getattr(result, 'is_error', False) or getattr(result, 'ok', True) is False else 'completed'
            return result
        except KeyboardInterrupt:
            record['state'] = 'cancelled'
            raise
        except BaseException as exc:
            record.update(state='unknown', error=type(exc).__name__)
            raise
        finally:
            record.update(ended=time.time(), duration_ms=round((time.monotonic()-start)*1000))
            self.active_operation.reset(op_token)
            if durable_op is not None and durable_op.get('kind') != 'background-job':
                try:
                    store.finish(state, durable_op, record)
                except Exception:
                    record['state'] = 'unknown'
                    if name in self.box.mcp.tools:
                        try:
                            self.box.mcp.close()
                        except Exception as cleanup_error:
                            record['evidence_error'] = 'MCP cleanup failed: %s' % cleanup_error
                    try:
                        self.box.lsp.close()
                    except Exception:
                        pass  # Preserve the critical journal error after cleanup attempts.
                    raise
            if durable_op is not None and durable_op.get('kind') == 'background-job':
                record['state'] = durable_op['state']
            self.diagnostic('execution_end', record)

    def run(self, name, args):
        from .tools import ToolResult
        problem = self.problem(name, args)
        if problem:
            self.reject(name, problem)
            return ToolResult(problem, is_error=True, summary=problem, error_code='invalid_arguments')
        spec = self.spec(name)
        def operation():
            start = time.monotonic()
            try:
                result = self.box._run_raw(name, args)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                from .taskstate import PersistenceError
                if isinstance(exc, PersistenceError):
                    raise
                result = ToolResult('%s: %s' % (type(exc).__name__, exc), is_error=True,
                                    error_code='execution_error')
                result.execution_unknown = True
            if len(result.content) > spec.output_budget:
                result.content = result.content[:spec.output_budget] + '\n（输出已截断）'
                result.truncated = True
            result.duration_ms = round((time.monotonic()-start)*1000)
            result.source = 'mcp' if name in self.box.mcp.tools else 'builtin'
            if result.is_error and not result.error_code:
                result.error_code = 'tool_error'
            return result
        result = self.invoke(name, args, operation)
        if getattr(result, 'stop_reason', '') in ('cancelled', 'deadline_stopped', 'budget_stopped'):
            from .runcontrol import RunStopped
            raise RunStopped(result.stop_reason)
        return result
