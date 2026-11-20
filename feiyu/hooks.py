"""钩子：在固定的几个时机跑外部命令，不改代码就能加规矩

配置写 `hooks.json`，全局一份（~/.config/feiyu/）加项目一份（工作区的 .feiyu/），
两边都会跑 匹配用的是权限规则那套语法，不另发明一种：

    {
      "PreToolUse":  [{"matcher": "Bash(git push:*)", "command": "scripts/guard.sh"}],
      "PostToolUse": [{"matcher": "Write|Update",     "command": "npm test"}],
      "UserPromptSubmit": [{"command": "git status --short"}],
      "Stop": [{"command": "notify-send 干完了"}]
    }

约定跟 Claude Code 一致：**退出码 0 放行，非 0 拦下**，stderr 回给模型 
钩子从 stdin 收一份 JSON（事件、工具名、参数、工作区），要什么自己解析 

## 项目钩子必须先经用户同意

工作区里的 hooks.json 是从仓库带下来的，直接跑等于「clone 一个仓库就执行任意代码」 
所以第一次见到（以及内容变了之后）要用户点头，同意过的记在
~/.config/feiyu/trusted-hooks.json 里，按内容 hash 认 非交互场景一律不跑 
"""

import hashlib
import json
import os
import subprocess
import tempfile
import signal

from . import files
from . import sandbox

EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop")

_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "feiyu"
)
GLOBAL = os.path.join(_DIR, "hooks.json")
TRUST = os.path.join(_DIR, "trusted-hooks.json")
VERIFY_TRUST = os.path.join(_DIR, "trusted-verify.json")
PROJECT = os.path.join(".feiyu", "hooks.json")

DEFAULT_TIMEOUT = 60
MAX_OUTPUT = 4000      # 回给模型的输出截多长


class Hook:
    def __init__(self, event: str, spec: dict, source: str):
        self.event = event
        self.matcher = str(spec.get("matcher") or "*")
        self.command = str(spec.get("command") or "")
        self.timeout = int(spec.get("timeout") or DEFAULT_TIMEOUT)
        self.source = source      # 给 /hooks 显示这条是哪来的

    def __repr__(self):
        return "Hook(%s, %s, %r)" % (self.event, self.matcher, self.command)


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _collect(raw: dict, source: str) -> list[Hook]:
    out = []
    for event in EVENTS:
        for spec in raw.get(event) or []:
            if isinstance(spec, dict) and spec.get("command"):
                out.append(Hook(event, spec, source))
    return out


def digest(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return ""


def _trusted() -> dict:
    return _read(TRUST)


def allow_verify(workspace, source: str, text: str, command: str, approve=None) -> bool:
    fingerprint = hashlib.sha256(json.dumps([source, text, command],
                                            ensure_ascii=False).encode()).hexdigest()
    data = _read(VERIFY_TRUST)
    key = os.path.realpath(workspace)
    if data.get(key) == fingerprint:
        return True
    if approve is None or not approve(source, command):
        return False
    data[key] = fingerprint
    temporary = None
    try:
        files.private_dir(os.path.dirname(VERIFY_TRUST))
        fd, temporary = tempfile.mkstemp(prefix=".verify-trust-", dir=os.path.dirname(VERIFY_TRUST))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(temporary, VERIFY_TRUST)
    except OSError:
        pass
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return True


def trust(workspace, fingerprint: str) -> None:
    data = _trusted()
    data[str(workspace)] = fingerprint
    try:
        files.private_dir(_DIR)
        fd = os.open(TRUST, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def project_state(workspace) -> tuple[str, str, str]:
    """返回 (项目 hooks 路径, 内容指纹, 状态) 状态是 none / trusted / unknown """
    path = os.path.join(str(workspace), PROJECT)
    if not os.path.isfile(path):
        return path, "", "none"
    fingerprint = digest(path)
    known = _trusted().get(str(workspace))
    return path, fingerprint, "trusted" if known == fingerprint else "unknown"


def load(workspace, *, approve=None) -> tuple[list[Hook], str]:
    """全局的直接用；项目的要先经用户同意

    approve 是 (路径, 条数) -> bool，交互层塞进来 没给就当作不同意
    返回 (钩子列表, 给人看的一句话；没什么可说的时候是空串)
    """
    found = _collect(_read(GLOBAL), "全局")
    path, fingerprint, state = project_state(workspace)
    if state == "none":
        return found, ""

    project = _collect(_read(path), "项目")
    if not project:
        return found, ""
    if state == "trusted":
        return found + project, ""

    # 仓库里带下来的命令，跑之前必须让用户看一眼
    if approve is None or not approve(path, len(project)):
        return found, "项目钩子未启用（%s 里有 %d 条，没有同意就不会跑）" % (PROJECT, len(project))
    trust(workspace, fingerprint)
    return found + project, "已信任 %s 的 %d 条项目钩子" % (PROJECT, len(project))


def matches(hook: Hook, tool: str, subject: str) -> bool:
    """matcher 用权限规则那套语法，`|` 分隔多条，裸工具名当成 Name(*) """
    from . import permissions

    if hook.matcher.strip() in ("*", ""):
        return True
    for part in hook.matcher.split("|"):
        part = part.strip()
        if not part:
            continue
        if "(" not in part:
            part = "%s(*)" % part
        if permissions.matches(part, tool, subject):
            return True
    return False


def pick(all_hooks: list[Hook], event: str, tool: str = "", subject: str = "") -> list[Hook]:
    if event in ("UserPromptSubmit", "Stop"):
        return [h for h in all_hooks if h.event == event]
    return [h for h in all_hooks if h.event == event and matches(h, tool, subject)]


class Outcome:
    def __init__(self, hook: Hook, code: int, output: str, *, timed_out=False,
                 cancelled=False, environment_error="", evidence_error="", rejected="", log="", log_sha256="",
                 execution_started=False, stop_reason=""):
        self.execution_started = execution_started
        self.stop_reason = stop_reason
        self.rejected = rejected
        self.timed_out = timed_out
        self.cancelled = cancelled
        self.environment_error = environment_error
        self.evidence_error = evidence_error
        self.log = log
        self.log_sha256 = log_sha256
        self.hook = hook
        self.code = code
        self.output = output[:MAX_OUTPUT]

    @property
    def execution_unknown(self):
        return self.execution_started and bool(self.cancelled or self.timed_out or self.evidence_error)

    @property
    def ok(self) -> bool:
        return self.code == 0 and not (self.timed_out or self.cancelled or self.environment_error or self.evidence_error)


def run(hook: Hook, payload: dict, cwd, *, offline=False, control=None) -> Outcome:
    """跑一条钩子 钩子自己炸了不能把 agent 带崩，所以异常都转成非 0 """
    from .processwait import run as wait_process
    from .tools import _child_env, offline_safe, pinned
    from . import permissions
    if permissions.verdict("bash", {"command": hook.command}) == "deny":
        return Outcome(hook, -1, "被权限规则拒绝", rejected="被权限规则拒绝")

    from .verification import storage

    command = pinned(hook.command) if offline and not sandbox.can_cut_net() and offline_safe(hook.command) else hook.command
    code, timed_out, cancelled, error = -1, False, False, ""
    output, log, digest = "", "", ""
    evidence_error = ""
    proc = None
    try:
        folder = storage()
        files.private_dir(str(folder))
        fd, log = tempfile.mkstemp(prefix="hook-", suffix=".log", dir=str(folder))
        # File-backed streams keep verbose commands out of memory and retain stderr
        # even when the compatible successful Outcome.output only shows stdout.
        with os.fdopen(fd, "wb") as durable, tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            try:
                proc = wait_process(
                    (sandbox.wrap(command, workspace=cwd, cwd=cwd, offline=offline)
                     or [sandbox.SHELL, "-c", command]), cwd=str(cwd),
                    stdout=stdout, stderr=stderr, env=_child_env(),
                    payload=json.dumps(payload, ensure_ascii=False, default=str).encode(),
                    timeout=hook.timeout, control=control)
                code = proc.code
                timed_out = proc.reason in ('timeout', 'deadline_stopped')
                cancelled = bool(proc.reason) and not timed_out
                evidence_error = proc.error
                if timed_out or cancelled:
                    output = ("钩子超过 %d 秒还没结束" % hook.timeout if timed_out else "钩子已取消")
            except OSError as exc:
                error = str(exc)
                output = "钩子跑不起来：%s" % exc
            h = hashlib.sha256()
            for label, stream in ((b"stdout\n", stdout), (b"\nstderr\n", stderr)):
                durable.write(label)
                h.update(label)
                stream.seek(0)
                while chunk := stream.read(65536):
                    durable.write(chunk)
                    h.update(chunk)
            durable.flush()
            os.fsync(durable.fileno())
            digest = h.hexdigest()
            if not output:
                stdout.seek(0)
                stderr.seek(0)
                a = stdout.read(MAX_OUTPUT * 4).decode("utf-8", "replace")
                b = stderr.read(MAX_OUTPUT * 4).decode("utf-8", "replace")
                output = ((b + ("\n" + a if a else "")) if code else a).strip()
    except OSError as exc:
        log, digest = "", ""
        if proc is None:
            error = "persistent log unavailable: %s" % exc
            output = "钩子跑不起来：%s" % error
        else:
            evidence_error = "persistent log unavailable: %s" % exc
            output = "命令已执行（退出码 %s），持久日志缺失：%s" % (code, evidence_error)
    return Outcome(hook, code, output, timed_out=timed_out, cancelled=cancelled,
                   environment_error=error, evidence_error=evidence_error, log=log, log_sha256=digest,
                   execution_started=proc is not None, stop_reason=proc.reason if proc else "")
