# 框架演进设计草案（阶段 A，供 Astra 裁决）

日期：2026-11-15。源码基准：`d82d943e64dcf4129e5bc44f4798abff6949da83`，main，0.84.5。
本次交付仅为源码核查、基线与 B—E 具体设计，**没有实现 B—E，也没有验收整套能力收益**。
依据为完整任务书（见 `architecture-evolution-taskbook.md`）和当前源码；关联研究报告未在仓库、附件目录按 research 文件名及用户根目录的约定路径找到，未阅读任务书所列论文，不据此作研究收益断言。以下新增结构均为工程建议，不是已有实现。

## 1. 当前能力与缺口

| 实际路径与接缝 | 已有能力，应复用 | 后续缺口 |
|---|---|---|
| `feiyu/agent.py`：`send`、`_run_tools`、`_gate`、`_pre_tool`、`_reproduce_first`、`_fire` | 模式/权限/外部内容出网检查，基线复现，写后 verify，预算和压缩，工具配对补齐 | `verified_ok` 只有内存 True/False/None；基线一次/会话，未关联任务和工作区版本；职责集中 |
| `feiyu/tools.py`：`ToolResult`、`Toolbox.run`、bash/edit/write/job | 字符串、summary/detail、图片和展示路径；必填检查，写前读版本检查，Shell 状态、cwd、输出截断 | MCP 分支在内建必填检查之前；缺少统一类型验证和结构化执行元数据；Toolbox 本身不是权限入口 |
| `feiyu/providers.py` | Anthropic/OpenAI 分别维护原生 messages、工具结果、thinking、图像、用量和缓存标记，transcript/compact_to | agent/session/history 直接访问 messages；文本摘要不能代替原生协议或事实账本 |
| `feiyu/hooks.py`、`permissions.py`、`sandbox.py`、`net.py` | 项目 hooks 按内容信任；verify 独立信任；deny 优先；bash 前后台用 sandbox.wrap，探测实际 bwrap 能力 | hooks.run 直接 subprocess.run，仅共用 shell 与净化环境，未走 bash 沙箱/权限；自动命令需显式入口而非隐式特权 |
| `feiyu/session.py` | 多会话目录、随机后缀 ID、临时文件 + replace、0600、摘要卡片、旧格式读取 | 无 schema_version/task_id、验证记录和操作恢复日志；save 的异常被吞掉。注释称 legacy 只读，但 save 无 sid/legacy 仍写旧路径，迁移不能只信注释 |
| `feiyu/progress.py` | 工作区 hash、7 天时效、未完 todo 派生提示且声明不是当前指令 | 一工作区一份，MAX_TASK=200/MAX_ITEMS=20，写盘非原子且忽略错误；会话串覆盖、截断原要求 |
| `feiyu/history.py`、`files.py` | 仅改工具内容保持配对；Watcher 记录已读路径的 stat/hash、防覆盖 | Watcher 是读写新鲜度保护，不是全工作区指纹；相同 stat 快路不发现伪装同大小同时间内容变动，不能复用为验证证明 |
| `feiyu/verify.py` | 测试/构建报错摘要 digest | 没有执行记录、代码指纹、失效或持久化 |
| `feiyu/events.py`、`ui.py`、`serve.py` | UI 发结构化事件，stdio 桌面协议，确认回调与切工作区装配 | 全局 `_sink`，paused/capturing 也替换全局；运行事实依赖显示路径，嵌套和并发隔离不足 |
| `feiyu/subagent.py`、`jobs.py` | 四种本地只读工具，独立 backend/Toolbox、共享有锁 LSP，子用量回传；job 收集输出和杀进程组 | 子循环仅固定 12 轮，无父 deadline/cancel 参数；异常退出可能未回传用量；helper/reviewer/job 未统一预算；内存 job ID 不足以安全重启认领 |
| `feiyu/memory.py`、`dream.py` | 长期记忆与短期进度分离；Dream 来源逐字引用、base 指纹、apply 重检来源与写入结果 | 来源只含对话，不是执行证据；摘要/记忆转述需持续保留来源类别 |
| `feiyu/runtime.py` | 冻结 Linux 后端库和证书环境配置 | 保持原职责，绝不改成总运行时 |
| `tests/`、`evals/` | unittest 假 provider、临时仓库；builtin/medium/SWE/TBench 与 A/B/report | 缺少版本关联验证、崩溃窗口、任务隔离等针对性回归；已有跑分不是本次结果 |

### 0.84.5 已修边界

当前 HEAD 变更及 `tests/test_security_regressions.py`、`test_permissions.py`、`test_net.py` 表明：

- Shell 保留换行参与分段，合并续行，区分 FD 复制与文件重定向；撤回旧宽泛 `Bash(git status/log/diff/branch:*)`，结构化 git 工具有更窄的参数控制。仍是保守字符串规则，不是完整 Shell 语义安全证明。
- `hooks.allow_verify` 指纹包含规范来源路径、项目文本和命令，按 realpath 工作区记录独立信任；`/verify` setter 表示用户主动设置，项目 `verify:` 不因 auto 模式自动信任。CLI、serve 已安装 approve_verify，桌面启动/切工作区确认时序已修。
- `net.public_addresses/connect_public` 拒绝非公网和混合 DNS，建连重新校验并连数值地址，保留原 hostname 作 Host/TLS，公共抓取禁代理、校验重定向。不能把本地放行开关或自托管 Firecrawl 的远端行为说成同等网络隔离保证。
- 不把这些修复重列为“尚未开发”。B—E 必须保留相同或更强边界，并在实际入口回归。

## 2. 状态所有权与最小模块

保持 `Feiyu` 外部入口与 CLI/Electron 装配。只先增加两个小模块：`verification.py`（记录、指纹、当前有效性）与 `execution.py`（执行协调）；D 确有需要才增加 `task_state.py`。数据用 stdlib dataclass/enum，不引依赖或通用框架。

| 状态 | 唯一所有者 | 使用者及限制 |
|---|---|---|
| 原要求/修订、目标/约束/验收、task_id、运行状态/结果 | 每 session 的 TaskState | todo 是其任务视图；模型提议变更，不自行把验收提升为通过 |
| 调用关联、授权、开始/结束、未知副作用、取消 | 每 run 的执行协调器 | Toolbox 仅实现能力；授权规则仍在 permissions/hooks/sandbox 中 |
| 验证记录与当前有效性 | 每 task 的 VerificationLedger | `verified_ok` 兼容属性从账本派生，不另存真相 |
| backend 历史和协议 | provider 实现 | history 通过小接口编辑；账本独立于摘要和消息 |
| cwd、读版本、shell state、jobs | 每 Feiyu/Toolbox 实例 | 不共享可变 Shell 状态，不持久化秘密环境值 |
| 持久化/legacy 适配 | session 存储层 | progress/侧栏卡片都是派生缓存，坏了可重建 |
| 预算、deadline、取消令牌、event sink | 每 task/run 上下文 | 传给 helper、子 Agent、reviewer、job；不得用全局 sink |

运行状态拟为 idle/running/waiting_user/interrupted/budget_stopped/recovering；任务结果独立为 pending/complete/partial/unverified/blocked。没有测试的文档/问答可结束；代码任务也可带 unverified 结果结束，不能宣称当前已通过。预算停止不是任务完成。

## 3. B：验证记录、指纹与失效

`VerificationRecord` 最少保存 schema_version、verification_id、session_id/task_id/run_id、命令原文与来源类别/信任引用、实际 cwd/工作区、UTC 起止时间和单调耗时、exit_code（可空）、timed_out/cancelled、原始日志引用/摘要、baseline/post_change/manual 类别、前后 Fingerprint、执行结果及有效性原因。

将执行事实 `passed/failed/not_run/environment_blocked` 与有效性 `current/stale/unknown` 分开；面向用户可映射为通过/失败/未运行/已过期/环境受阻。超时、取消保存独立标志，不伪造普通测试失败；缺解释器、沙箱或进程启动失败有明确环境原因，不能仅凭输出猜“环境问题”。日志摘要继续用 verify.digest，日志缺失要显示证据不完整，记录不得只指向已删除临时文件。

指纹建议第一版默认保守的工作区范围：

1. 规范 root + 实际 cwd（含相对 Git root）、Git root/worktree 标识、HEAD、index 状态；无 Git 也必须可用。
2. 路径排序的内容摘要清单：所有 tracked（包括删改、暂存/未暂存）与非忽略 untracked；包含路径、文件类型、可执行位、软链目标。tracked 即使落在常用忽略目录也纳入。子模块记录 gitlink 与子工作区状态，无法检查则 unknown。
3. 纳入 verify 命令/来源文本、显式相关配置/锁文件、解释器路径与版本、依赖版本摘要、沙箱实际档位和批准的非秘密环境配置摘要。外部依赖/忽略文件无法完整自动发现；显式 scope 可补充，秘密值不读入/输出。
4. 扫描前后再次核查清单与元信息，文件读取前后检查 stat；竞态/不可读/目录变化不产出可靠指纹。不跟随软链逃逸，不读取 FIFO/设备。指纹是选定范围内证据，不证明动态依赖完备。

生命周期：执行前指纹 F0 + mutation epoch，执行后 F1。只有 exit=0、未取消/超时、F0=F1、期间 epoch 未变且扫描可靠时，才可记当前通过。验证自身格式化代码也算版本改变，需要针对新状态重跑。前后相等仍不能排除外部“改后恢复”的瞬时变化；没有文件系统快照时明确是尽力检测，不宣称原子一致性。已知写入发生后恢复相同内容也先失效。

内建编辑、undo、Shell（即使失败）、hooks、MCP、后台 job 在开始可能写入时递增 epoch 并立即失效；未知作用域一律按潜在写入。外部编辑/checkout 不靠这些通知：在展示/使用“当前通过”、结束任务、恢复会话前重新算指纹。Shell `cd` 改变验证 cwd、项目配置重载、依赖变化也失效。只读元数据不能豁免未知 MCP。

性能：平时只置 dirty，不每次读工具后扫描；验证开始/结束及消费结论时扫描。stat 缓存仅用于提示或快速拒绝，不能替代消费结论时内容核验。设置扫描文件数/字节/耗时上限，超限转 unknown/stale，允许显式缩窄范围并展示范围；不静默漏掉文件后宣称全仓库通过。大型忽略构建产物和仓外动态输入需显式声明，不能把 `IGNORE_DIRS` 当完整验证边界。

记录先接 `_reproduce_first` 和 `_fire` 中 verify 分支，再接手动验证/Shell 验证指定入口；普通命令不能仅因输出含“通过”自动获得验证身份。B 的记录通过 session 增量字段保存，D 再迁移到任务目录；旧 session 没记录就是 not_run，不推断历史助手陈述。

## 4. C：统一执行入口及安全迁移

当前调用图：

```text
CLI main（一次任务/pipe/TUI）或 Electron → feiyu --serve → Feiyu.send
  → backend.run_turn → _run_tools
    → _run_serial / _run_parallel → _pre_tool（可执行 hooks）→ _gate
      → [写前 snapshot + _reproduce_first → hooks.run]
      → Toolbox.run → builtin 或 MCP Registry.call
        → bash/_start_job → sandbox.wrap → subprocess / Jobs
  → finally _fill_missing → _after_tools → _fire → hooks.run
  → backend.add_tool_results → fold/compact；入口保存 session
子调查：_spawn → subagent.run → 独立 Toolbox.run（四工具 allowlist）
```

目标为同一执行协调函数，允许 `origin=model/hook/verify/job/subagent`，origin 不能由模型自行指定以获得特权。顺序为参数语法/required/类型检查 → 授权 → durable prepared → 隔离执行 → 归一结果 → 状态/验证更新 → 一个协议结果。模型调用的 PreToolUse 仍可在其权限询问前 veto，但 hook **自身**必须先过自身信任/执行检查并记录；它是嵌套操作，禁止再递归触发自身 hooks。不能用“先 hooks”绕过安全入口。

`ToolSpec` 在现有 schema 旁合并作用域、read/write/network、concurrency、retry_policy、输出预算；内建 schema 和名字不变。MCP annotations 仅为声明，未有本地信任/实际隔离证据的调用视为未知写入、串行，不能凭 readOnlyHint 豁免确认/验证失效。该收紧是有意行为变化，应独立小步提交和说明。

授权区分两件事：项目来源命令是否可信，与本次命令执行是否允许。项目 hooks/verify 保留内容指纹信任；auto 不授予项目来源信任，恢复不继承临时 allow_all。用户 `/verify` 原始命令有本次显式授权意图，但 deny、工作区/出网与隔离边界仍需检查。原先已信任自动命令是否每次再询问，用明确的 command/cwd/source 授权范围表示，不能合成无限制 Bash allow。

hooks 当前不沙箱；C 先以特征测试固化现状，再将其命令调度复用 sandbox.wrap/净化环境/进程组取消。需要仓外写的 hooks 可能因此受阻，显示边界原因，由用户显式选择范围，不能静默回退。禁止为了保持“行为相同”继续安全绕行。

只读整批并行、任何混合写整批串行继续保留。主线程做确认，worker 只执行；收尾按调用顺序配结果。`ToolResult` 追加可选 error_code/exit_code/duration_ms/truncated/artifacts/changed_paths/source，默认值兼容所有现有构造。changed_paths 只是已知路径，不证明无其他副作用；字符串、detail、image、shows 均保留。执行错误、拒绝、取消各产生一个调用结果；协调器以调用实例登记终态，finally 仅补未终结者，拒绝重复结果。诊断事件可多条，协议结果恰一条；不保证副作用恰一次。

Toolbox.run 保留兼容入口，明确它不单独赋予授权；产品入口逐个迁移后用调用路径测试证明 hooks/自动验证/job/MCP/子调查均进入协调器。任意 Shell 和 MCP 写入默认不自动重试；网络模型重试与工具副作用重试分别处理。

## 5. D：任务持久化、恢复与未知副作用

工作区标识使用 canonical root + Git common-dir/worktree（无 Git 用 root）；旧 hash 目录通过适配查找，不擅自移动历史。session_id 继续复用现有生成器，task_id 新建且多轮修订显式关联；每次 send 不能无条件丢掉前一目标。TaskState 保存原要求/后续修订的消息引用及摘要、约束、验收、todo、用量/预算及验证引用；引用不能只指向会被 compact 删除的列表下标，原要求另存受保护快照。

拟存储在 `sessions/<workspace>/<sid>/tasks/<tid>/` 的版本化快照、操作 journal 和验证日志（或兼容 sidecar；最终路径由 Astra 确认）。现有 `<sid>.json` 保持侧栏读取入口，含新字段与 sidecar 引用。原子 tempfile→flush/fsync→replace，必要时 fsync 目录，文件 0600/目录 0700；同任务单 writer，第二进程只读或冲突报错，禁止依赖 last-writer-wins。不要提前引入数据库。

副作用协议：

- 授权完成后，准备记录（operation_id、父调用、工具/参数摘要、cwd、范围、授权引用）必须持久化成功，才启动副作用。日志只保存必要且脱敏参数，不保存 Shell 环境密钥。
- durable prepared 后尚未启动、或执行完成但 finished 未写入就崩溃，都按 **结果未知** 恢复；PID/调用 ID 不是幂等证明。成功终态保存结果与日志后再更新快照，journal 序号允许重放重建。
- 写前记录失败：阻止新副作用，显式报告持久化受阻，可继续只读调查。执行后记录失败：内存也标 unknown、停止新增副作用并报告已有可能影响；不能照 trace 的“全吞异常”处理。
- 恢复先校验 schema/校验和/序号及当前工作区与指纹；重查文件 diff、进程启动身份或可查询外部结果。不能只凭 PID 存活杀进程（防 PID 复用）。无法查询的外部写入保留 unknown，提示人工核对，绝不盲重跑。
- 预算累计包含 helper、compact、review、子调查、重试和失败尝试；费用未知保留 priced=false，不能算免费。父取消/deadline 传递全部分支，已执行任务须收集结果/杀进程组并写收尾；合作取消无法瞬间停止所有外部服务须明示。

progress 改为 task 状态派生的工作区选中任务视图，双会话不覆盖真相；旧 progress 只作不可信、可能过期的恢复建议，不自动赋给新任务。旧 session 只读适配，首次显式继续时创建新版本 sidecar，不批量改写。损坏/未来版本保留原件、报恢复受阻，不能以空状态覆盖；验证恢复后先 stale/unknown，重新指纹核验后才使用。恢复授权按当前规则重新判定，不扩大旧 mode 或临时确认范围。

兼容与回退：先写可选字段、保留旧消息/工具接口与版本读取测试；不要把新真相仅写旧进度字段。旧版本能忽略新字段但不理解 sidecar，降级时只允许只读历史，禁止带 unknown 操作继续执行。提供导出说明和隔离夹具，绝不自动删 sidecar。阶段 A 无发版；实现阶段再遵循版本同步、中英 README 与迁移说明约定。

## 6. E：上下文与前端

稳定前缀为系统规则、可信项目上下文/工具 schema；易变 TaskState/验收/验证引用放后部任务块，近期执行证据与按需历史分开。不要每轮重建稳定前缀降低缓存。保留 provider 原生协议，逐步封装 `iter_tool_results/replace_tool_content/export_session/restore_session` 等确有调用方的小接口，不创建统一有损消息模型。

压缩前从程序状态提取必须保留项：原目标/修订引用、约束、未完成验收、unknown 操作、运行 job、未配对调用与最新验证 ID/有效性。先处理调用配对再摘要；压缩后程序比较这些引用，不完整则补回结构化块或拒绝替换历史，不能让模型自评完整性。助手说“测试通过”是 assistant_claim，工具执行/验证记录才是 execution_evidence；摘要、子报告、memory/Dream 都保留 source kind 与引用，转述不提升为用户指令或验证证明。

事件由执行/任务层产出 session_id/task_id/run_id/operation_id/seq + 结构化事实，UI/serve 负责终端或桌面显示。先迁移执行开始/结束、验证失效、任务停止/恢复，再处理其余显示。兼容现有 kind/payload 适配，只能有一个事件生产者，避免运行层和 ui 双发。sink 显式注入 run 上下文；并行线程显式携带，不依赖 ContextVar 自动传播。展示 sink 失败可以降级，持久化 ledger 失败不可以。

## 7. B—E 小步实施与验收设计

| 步骤 | 最小变更/顺序 | 必要的实际入口回归 |
|---|---|---|
| B1 | record 与指纹纯函数，接基线/写后 verify | 未提交/未跟踪/删文件/配置/cwd/同 stat 内容变化，无 Git、扫描受阻 |
| B2 | 失效通知 + 消费时重核，session 增量保存 | 通过后编辑、undo、Shell/MCP/外部修改；验证中变动、格式化；失败/超时/取消、原有红基线、恢复后变更、unknown |
| B3 | 结束任务展示验证范围和原因 | 代码无测试可 unverified 结束；闲聊自然结束；过期记录不能显示当前绿 |
| C1 | 固化串并行行为，提取执行协调，兼容入口 | 拒绝不执行、参数错不启动 hook、副作用不重试、一调用一结果、图片/截断保持 |
| C2 | hooks/verify/job/MCP 路径统一并收紧信任 | 源内容变化重问、auto 不越权、deny/出网/沙箱生效、背景取消、MCP 自报只读不能升级信任 |
| D1 | 版本化 TaskState、会话任务隔离和旧读取 | 多会话同仓库、长原要求不截断、旧 legacy 写路径特征、损坏/未来版本、磁盘失败 |
| D2 | prepared/finished、恢复与预算取消 | 写前/启动前/写后记结果前 kill，PID 复用、外部未知不重试、预算累计、子/helper/job 取消和收尾 |
| E1 | 历史小接口与压缩核验 | 强制压缩后目标/约束/unknown/job 保留，未配对处理、换模型、图像/thinking/工具结果完整 |
| E2 | 运行事件隔离与兼容渲染 | 双会话/嵌套/线程不串 sink，CLI/Desktop 同事实、无双发、来源跨转述保持 |

每步使用现有 unittest 和 FakeBackend/临时 Git、隔离 HOME/XDG；崩溃用可控子进程故障注入。Python 3.10 必须实际运行，不以 AST 或 3.14 通过替代。桌面路径变化后运行 npm test、build 与真实桌面 smoke/verify-trust，不能用本次纯文档的构建替代后续验证。

评测准备（未运行、未授权费用）：复用 `evals.run` 的 --model/--repeat/--suite/--out/--save/--compare，四组对照为原基线/执行提取、旧/新验证、旧/新压缩、旧/新恢复。先增加确定性可复现边界题及独立判据（B—E 实现任务），再跑模型收益；题目名称尚未注册，不能提供看似可用的虚构 --only 名称。

授权后在两份明确 revision 的源码环境分别运行以下模板；配置目录必须是人工准备的隔离评测配置，不能直接让 `_isolate` 从真实用户目录复制密钥：

```sh
HOME="$EVAL_HOME" XDG_CONFIG_HOME="$EVAL_CONFIG" XDG_STATE_HOME="$EVAL_STATE" \
  .venv/bin/python -m evals.run --model "$FIXED_MODEL_ALIAS" --mode auto \
  --suite builtin --repeat 5 --out "$EVAL_STATE/baseline.jsonl" --save architecture-baseline
# 候选版本、相同题目/模型/环境/预算及共享的隔离基线结果位置
HOME="$EVAL_HOME" XDG_CONFIG_HOME="$EVAL_CONFIG" XDG_STATE_HOME="$EVAL_STATE" \
  .venv/bin/python -m evals.run --model "$FIXED_MODEL_ALIAS" --mode auto \
  --suite builtin --repeat 5 --out "$EVAL_STATE/candidate.jsonl" --compare architecture-baseline
```

记录 revision/dirty 指纹、固定模型实际版本与 provider、配置/任务集/判题版本、seed（若支持）、预算和沙箱、成功数/样本数、成本/token、耗时、人工介入、环境失败、预算停止与不确定性。现有 evals._isolate 会设置 FEIYU_TRUST_OUTSIDE=1，不能据其结果证明产品默认出网安全；安全对照需独立保持默认策略。开发题/保留题分离，最终判据不可由被测 Agent 修改。重复 5 次只是待授权起点，不是统计充分性承诺。尚无真实模型收益证据。

## 8. 请求 Astra 裁决

1. 接受保守工作区内容指纹为 B 默认（扫描超限不显示当前通过），还是指定更窄的显式验收范围？建议先保守，性能测量后再优化。
2. 接受 C 中 hooks 沙箱统一与 MCP readOnlyHint 收紧作为明确兼容行为变化？建议与机械提取分两个可独立回归的小步。
3. 接受 D 的 session JSON + task sidecar/journal 单 writer 方案及关键写盘失败阻止新副作用？建议采用，避免此时引入数据库。
4. 确认多轮 task 的继续/替换边界及 UI 的最小选择方式；建议默认继续未完任务，明确新任务时新建 ID，避免每条消息都重置验收。

这些是设计审阅事项，不是本次文档工作阻碍。B—E 未获实现/验收结论，F 不在范围内。

## 9. Astra 设计决定（2026-11-15）

阶段 A 的源码核查和基线证据已审阅，可进入 B；未运行范围继续保留，不代表整套能力验收。

- B 默认使用保守内容指纹：Git tracked + 非忽略 untracked，无 Git 使用有界目录扫描；明确排除输出日志/状态目录，不能把任意源码当作输出排除。初始上限建议 20,000 文件、256 MiB、5 秒，可配置；超限、不可靠读取、未覆盖子模块或外部软链依赖均标 unknown，不静默得到当前通过。这些是工程起点，需测量，不是性能保证。
- 指纹至少覆盖命令、cwd、相关配置和实际内容；不为依赖摘要执行任意项目命令。环境与动态依赖覆盖不足明确展示。验证开始/结束重核及消费时重核必需；已知写入 epoch 独立于内容摘要。B 不等待 C 才处理 Shell/MCP/后台写入失效。
- C 接受 hooks 沙箱和 MCP 自报只读信任收紧，分别与机械提取验证。项目来源信任不能替代命令 deny/授权；不得静默取消沙箱。
- D 采用现有 session JSON + task sidecar/journal，单 writer，关键持久化失败阻止新副作用；未知结果不盲目重试。先保持最小实现，不引数据库。
- 多轮默认继续当前未结束任务；明确的新任务通过控制层动作创建 ID，不靠模型猜测并删除旧验收。已结束任务后的新请求新建任务；修订保留完整原要求和稳定引用。UI 的具体入口在 D 按现有交互选择最小兼容方案。
- B 先以稳定 session/task ID 和 session 增量字段接通记录，D 再扩展任务生命周期。先完成 B、审阅真实调用路径，再推进 C—E。

## 10. B 实现交接（0.85.0，待 Astra 审查）

实现限于 B，未提取 C 执行器、未引入 D 任务 journal/生命周期、未整理 E provider/events。`verification.py` 的 Ledger 独立保存执行事实与有效性；`agent._reproduce_first` 和 `_fire` 的 verify 分支记录真实 hooks 调用。旧 ToolResult 不变，hooks.Outcome 仅增加可选字段。session 增量保存 schema、稳定 session/task ID 与账本，旧 session 无记录不从对话猜通过。恢复记录一律 stale，重核后仍要求重新运行，比设计允许的自动恢复更保守。B 的 task ID 暂随会话继续；明确新任务的完整控制层生命周期留给 D。

指纹：Git tracked + 非忽略 untracked，纳入 HEAD/index、Git 目录身份/config 摘要、路径/类型/可执行位及真实内容；无仓库扫描目录。两次读取内容并复核清单和元信息，不能仅靠 stat/HEAD。默认 20,000 文件、每遍 256 MiB、5 秒，可通过 fingerprint 的参数调整；Git inventory 单次输出上限 8 MiB，Git config 单文件上限 1 MiB。命令、来源文本、实际验证 cwd、Shell cwd、Python 路径/版本、四个运行依赖 metadata 版本、hooks 配置、当前沙箱配置及实际 verify 不沙箱的旧行为参与摘要。PATH/LANG/LC_ALL 为批准的非秘密环境项，不扫描密钥环境。子模块、所有软链、特殊文件、读取竞态/失败/超限均 unknown；Git 仓库的子目录作为 workspace 也保守 unknown，不误声称扫描整个仓库。

状态和日志放在工作区外；如果 XDG_STATE_HOME 导致 session/log 目录落在工作区内，直接 unknown 并要求移动配置，不能以任意源码排除表掩盖问题。未排除 tracked 的忽略目录。忽略产物/依赖、仓外动态输入和外部服务不完整覆盖。两次内容观测不是原子快照，不能发现所有外部“改后恢复”的瞬时行为。已知写入另有 epoch，即使内容恢复也失效。

Toolbox.run 对 Shell、所有 MCP（含自报只读）、编辑及未知作用的工具在执行前通知失效；普通 hooks、配置重载、/verify、CLI/serve 的 /sandbox 设置和 Shell reset 也失效。后台 Jobs 在验证开始或结束仍运行时不能 current；消费结论再次扫描内容和持久日志。Shell 命令不会仅因输出文本像测试而被认作验证；明确验证入口仍为原有 /verify 配置和自动复现/写后调用链。

hooks 用文件流承接输出，完整 stdout/stderr 在结束/超时/取消后写入 0600 日志并 fsync，返回给模型的文本继续截断且成功时不混入 stderr。日志创建失败不启动命令，事后写盘失败保留真实执行结果和退出码，evidence_error 独立记录、validity=unknown；不重试副作用。取消在记录后传播 KeyboardInterrupt；POSIX 超时/取消杀进程组，Windows 路径尚未实机验证。记录时间为 UTC epoch 秒和 monotonic 耗时。日志目录无自动清理，需用户管理；进程崩溃中尚未完成的记录持久化窗口仍属于 D，B 不宣称 crash journal 或恰好一次。

用户可见代码任务尾注由 ui.verification_status 渲染范围、执行事实、有效性、未验证原因与日志；后续纯聊天不重复该尾注。模型的最终自然语言不能覆盖账本事实。现有项目 verify 独立信任与权限规则未放宽，hooks/verify 不沙箱的既有行为明确保留，统一授权/隔离属于 C，未提前标为完成。阶段 B 的准确测试证据及未运行范围见 architecture-progress.md 末尾。


## 11. B 独立审查修复（2026-11-15，仍为未发布 0.85.0）

Astra 对 B 暂不验收，C—E 暂停。七项均作为实质缺陷修复，未判定误报；本节修订第 10 节旧描述，回归及限制见进度末节。

1. Git 查询明确 `-c core.fsmonitor=false`，同时禁用 hooksPath 和 untrackedCache。审计仅调用 rev-parse、ls-files、config 的固定参数：不调用 checkout/add/diff、网络传输或子模块递归，不存在对应 clean/smudge/process filter、textconv/external diff、SSH/gitProxy 执行路径；输出重定向到临时文件，不触发交互 pager。`--no-optional-locks` 仅是避免可选锁，绝不是禁执行配置。真实 Git marker 先证明普通 ls-files 会运行 monitor，再证明指纹不会。
2. 工作区内容、Git 元文件、ignore 来源及消费时日志读取统一使用从 `/` 起的 dir_fd 逐层遍历，目录 O_DIRECTORY/O_NOFOLLOW，末端 O_NOFOLLOW/O_NONBLOCK；读取前 fstat 必须常规文件，读取后比较身份/类型/大小/纳秒时间，再重新安全打开路径核对身份，检测父目录替换。目录枚举使用 fd，无软链跟随；FIFO 不阻塞。缺 POSIX 原语的运行平台保守 unknown（包括 Windows），不声称可移植安全。两次内容读取仍不是文件系统原子快照，无法发现所有外部写后恢复、挂载或硬链接别名变化。
3. reset 清账本、新 task_id、清待交代标记和复现基线；CLI /clear、/bot 与 serve 新会话复用该入口。使用记录时核对 session_id/task_id，跨归属记录不参与结论。use_model 保持现有会话/账本语义，不调用 reset。完整任务生命周期仍属于 D。
4. `_code_task` 现在表示尚未展示验证尾注的活动，而非每轮消息的活动。写入后中断/预算停止保留；session 增量 `verification_pending` 保存恢复；在成功输出尾注之后清除，后续闲聊不重复。
5. symbol 不再豁免潜在写入；Pool.get 的活动回调覆盖实际 LSP 启动及复用路径。服务器没有写隔离，可能存活并异步写入，因此一旦尝试调用 LSP，本 Toolbox 后续验证保守 unknown，即使服务器已关闭也不自动恢复 current（需新 Toolbox）。真实 JSON-RPC 子进程写入再恢复内容，仍触发 epoch；不得把语义工具名称当只读证明。此处是 B 失效修复，不代表完成 C 的执行隔离。
6. 摘要纳入 git-dir/common-dir 的 config/config.worktree/info/exclude、默认 XDG git/ignore、清单涉及和 Git 能枚举到的忽略 .gitignore 来源；每来源安全有界读取，Git 输出上限 8MiB、单来源 1MiB、来源数量与总时限受限。不输出配置值。无 includes 的有效配置列表只取摘要；检测到任意 include/includeIf 或 core.excludesFile（含全局/系统配置）即 unknown，避免声称已覆盖任意外部配置图。即使 include 条件未生效也保守受阻，属于明确兼容收紧。ignore 注释变化但清单相同也会失效。外部动态依赖本身仍不完整覆盖。
7. Outcome 增加 evidence_error；日志创建/进程启动失败保留 environment_error，执行完成后的 fsync/写盘失败不改真实退出码和 passed/failed 执行事实，但 validity=unknown，提示“命令已执行，持久日志缺失”。超时/取消维持独立标志及 null 普通退出码，不盲目重试。真实大输出及后代进程测试覆盖 POSIX 杀组，Windows 尚未实机验证。

## 12. C 实现交接（0.86.0，待 Astra 审阅）

先提取 `execution.py`，让 `Toolbox.run` 委托到 Executor，保留原 handler 于 `_run_raw`；模型串/并行入口共用 `prepare`，校验和授权后再调用 `_pre_tool`，通过 `dispatch` 关联协议 call ID。Feiyu、_gate、_pre_tool、Toolbox.run 外部入口保留。随后收紧 hook 沙箱和 MCP 信任。未引入依赖，未改 provider 的多模态协议。

- ToolSpec 统一 schema、scope、effects、network、concurrency、retry、output_budget。并行由此元信息选择；MCP 的 schema 用于校验，其 readOnlyHint 不授信任、不进入并行列表。内建原有只读批次并行；混合写入整批串行。没有自动重试。
- ToolResult 增加可选 error_code/exit_code/duration_ms/truncated/artifacts/modified_paths/source；文本、image、summary/detail/shows 保留。产物与修改路径无可靠信息时为空，不从文本猜测。Shell 提供真实退出码；归一层提供耗时/来源/输出上限，截断保留图片。
- Executor 在副作用前写内存记录并发送 execution_start 诊断日志，结束/错误/中断发送 execution_end；含独立执行 ID、模型 call_id、来源、参数、实际 cwd、沙箱实际配置、时间和状态。Trace 按原约定缩短参数、可禁用、失败不阻断。这里不提供关键 durable journal、崩溃恢复或 exactly-once 保证；这些仍在 D。
- 自动命令经 `_execute_hook` 检查命令与模式、deny、项目 verify 来源、出网及命令授权。项目 hooks 的来源确认继续由 hooks.load 的内容指纹负责，auto 不跳过来源确认。用户主动 /verify 作为该条命令授权仍受 deny/模式/出网边界约束。hook 命令确认的 always/remember 仅缓存来源+完整命令+根 cwd，不调用 add_allow，不生成前缀授权；出网确认不缓存。
- hooks.run 的子进程复用 sandbox.wrap、净化环境和 POSIX 进程组取消；与 bash 同样受有效 sandbox/off/strict/exec wrapper 配置约束。不可断网时仅 offline_safe 命令使用 pinned 路径；其余由出网授权拦截。来源信任不代表宿主机权限。verification_sandbox 记录实际 effective 值，取消和日志错误继续沿用 B 语义。
- 模型输入不接受内部来源参数；origin 等额外模型字段不会授予权限。PreToolUse 可 veto 模型调用，其自身命令先检查且不触发递归 hooks。后台启动由 bash 入口检查，job 管理复用原取消实现。只读调查保留四工具 allowlist，实际运行前校验参数并执行 deny；取消时 finally 补齐协议结果。

兼容变化：类型错误现在在执行前拒绝（例如 ask_user.options 非数组），不再在 handler 里静默修正；MCP 只读声明不再豁免 default 确认或 readonly/plan 写入禁令；自动 hook 可能因 deny、模式、沙箱或出网受阻。需要仓外写的 hook 应由用户调整明确配置，不静默放宽沙箱。

保留 B 指纹、LSP unknown、持久日志、会话清理和中断 pending 修复。D/E 未实施。跨平台、完整桌面/TUI 集成、发行打包和真实模型收益仍待验证。具体测试证据及限制见进度文件末尾。

## 13. C 审查修复

Astra 修正四项独立复现问题：schema 支持联合类型与布尔子 schema，并将校验异常归一为工具参数错误；前置 hooks/复现结束后、dispatch 之前重检硬性 deny、模式和新出现的出网边界，并在并行批次所有 hook 完成后统一重检；hook 的 yes 仅对当前调用有效，只有 always/remember 缓存精确命令授权；拒绝 verify 保存 rejected 原因、not_run 和 null 退出码。

重检复用当前调用既有确认，不重复询问未变化的出网授权；它不是针对任意外部并发策略修改的原子事务。保留沙箱隔离，后续 D 的持久化不应替代执行前授权。最小 schema 校验仍非完整 JSON Schema 实现，不宣称支持所有组合关键词。

## 14. D 实现中交接（0.87.0，未完成，待 Astra 审查）

本节记录实现事实，不是 D 验收结论。A/B/C 及第13节修复保留。新增 `taskstate.py`：TaskState v1 使用现有 session/task ID，工作区身份绑定 canonical root 和根 `.git` 标记；完整请求及修订以 UUID 引用独立保存。目标、约束、验收、todo、预算、验证引用均有独立字段，但目前只有原请求目标、todo、现有累计用量及验证引用自动同步；**约束/验收的结构化录入与完整生命周期仍未实现**。不能把空字段解释成没有约束或已经验收。

实际 CLI/serve `send` 路径建立 sidecar，原请求加入消息后、工具批次后保存 session；工具执行前更新 sidecar。模型收尾只将运行状态改为 waiting_user，结果保持 unfinished。`/task new` 显式切换任务；`/task complete` 是用户控制层明确结束操作，验证记录独立，绝不产生测试通过证据；下一请求新建 ID。unknown/prepared 时不允许通过此命令切换或完成。普通连续 send 保持 task ID 和现有 acceptance 字段；压缩不触碰 sidecar 原请求。`progress.selected` 仅从选定 TaskState 派生内存视图，CLI 收尾不再覆写工作区共享 progress 文件；旧 progress 仍只是原有过期建议。

路径为 `sessions/<原workspace-hash>/<sid>.json` 和 `<sid>/<tid>.task.json`。sidecar 内含按 sequence 排序的操作快照和 SHA-256 校验，采用原子替换的完整 journal 快照，不是 append-only 日志。session 写入 v1/workspace/task_ref。`writer.lock` 通过 POSIX flock 持有到会话释放，线程内用 RLock；同 session 第二 writer 显式失败，不同 session 隔离。无可靠锁的平台目前拒绝安全写入，未做 Windows 兼容锁。关键写入均 tempfile(0600)、flush/fsync、replace、目录 fsync；目录复用 private_dir。派生 card 仍允许失败。新任务会话不自动 prune，避免删除唯一恢复入口，磁盘保留策略待补。

无 ID 或 legacy 保存分配新 session，不写旧位置。旧 session 在显式继续时将已保存 user-role 文本适配到 sidecar；不能从旧格式还原当初已丢失/压缩的原请求，也不能区分旧附加文本的完整来源。损坏/未来版本显式读取或覆盖会报 PersistenceError，保留原件；listing 仍略过不可读条目，显式按 ID 可看到错误。任务读写校验版本、checksum、sequence 和身份；恢复不恢复临时命令授权，也不从历史提升到 auto 模式。恢复侧盘失败后禁止 send/save，需核对原件或显式 reset。

执行器保留 C 参数/授权/前置命令后重检。已绑定任务的写/未知工具及 hook/verify 在 operation 前 durable prepared，完成后 durable finished；原始参数和环境不入关键 journal，仅记录参数摘要哈希、来源、工具、cwd、关联 ID、序号、时间及退出码。prepared 写失败不启动；finished 写失败标 unknown 并阻止新增副作用；取消中的副作用也保守 unknown。恢复 prepared 为 unknown，不自动执行。诊断 emit 不承担这些写入。任意 Shell/MCP 不具备 exactly-once 保证。

**D2 尚缺的必要工作，禁止据此验收 D：**

- 当前工作区标识尚未完整纳入 Git common-dir/worktree 身份图；恢复只验证身份、journal 完整性并沿用 B 的验证指纹重核，未建立文件/Git diff、可靠进程启动身份或外部结果的操作级核对与用户解决 unknown 的控制入口。当前安全边界是阻止未知副作用重放，尚不能完成核对后续跑。
- 后台 job 目前只记录启动调用结束，不能把它当后台工作完成；job 的 durable 生命周期、重启查询、退出后收尾和硬故障注入尚缺。新 session/reset 对未知任务的全局提示/约束也尚缺。
- 父任务预算、持久化截止和取消控制器尚缺。sidecar 保存的是现有 session 累计计数，不能称任务独立预算；helper/compact/reviewer/子调查失败用量以及取消传播仍需统一，不能宣称这些已归父预算。现有单 send 时间预算未改变，不承诺外部服务瞬时停止。
- 授权引用目前只有来源/调用关联，尚未持久化具体范围与授权事实；D 恢复不能用 journal 扩大现有权限。约束/验收录入、恢复时向模型提供权威任务事实、取消/异常最终 session checkpoint 与长请求完整重启回归仍需补齐。

迁移：仅操作隔离夹具，没有扫描或批量重写用户历史。显式 legacy 续接会新增 sidecar 和 session ID，旧文件保留。回退前先停止当前进程，完整备份整个 session 目录（含 sidecar）；旧版仅可读取导出的历史，不允许带 unknown 降级执行。不可只拷贝 `<sid>.json` 丢掉 sidecar。不要 stash/reset A/B/C 工作区；本轮新模块、接缝和测试需按差异逐项回退并恢复全部版本元数据。0.87.0 为未发布开发版本。

## 15. D1 / D2 unknown 续作（0.87.0，待 Astra 审阅）

本节覆盖第14节对应缺口；D整体仍未完成。父任务共享预算、取消传播和后台job完整生命周期明确推迟下一批，不推进E/F。

- 新工作区身份使用 `v2:` 摘要，包含工作区、Git dir、common-dir 的路径/dev/inode。直接安全读取 `.git` / `commondir`，不运行 Git 或加载配置；拒绝软链/特殊文件/超长链接。子目录向上寻找 Git 工作区。旧摘要只读兼容，不能补造旧格式从未存过的 inode 证据。
- TaskStore 不再 `load()` 后无条件覆盖；已加载摘要与持久修订号共同检查，拒绝未加载 writer、磁盘变化和同 writer 的陈旧对象。保存时校验内层请求/来源/引用、要求、待办、预算和操作序号/身份。未知价格仍为 null，不归零。关键 I/O 异常提升 PersistenceError 并阻止新增副作用。
- `/task {JSON}` 是 CLI/serve 控制入口，不作为模型工具提供。`{"action":"show"}` 返回完整任务及原始请求 ID；`{"action":"add","kind":"constraints或acceptance","text":"要求","request_id":"原请求ID"}` 生成稳定要求 ID，保存 user-control 来源。旧无ID要求保持历史未绑定状态，不自动认定验收通过。
- `{"action":"bind","acceptance_id":"要求ID","verification_id":"验证ID"}` 只接受当前会话/任务 Ledger 中实际存在的记录。`{"action":"check"}` 重新检查当前文件/配置及日志。只有最后一条非baseline、passed/current且归属正确的记录可令绑定项 verified；恢复后仍 stale，必须重跑。每次 checkpoint 重新评估验收，模型完成文本没有验收权。`/task complete` 有未核验验收项时拒绝。
- 完整任务事实（请求、来源、约束、验收、操作及验证引用）重新进入系统上下文；不依赖摘要或旧 progress。verification_refs 修正为 Ledger 实际 verification_id。完整原请求按用户原文保存；不要在请求或人工核对说明中输入秘密。
- send 的 finally 同时保存 task/session；取消和异常仍保留协议配对及运行状态。reset/new/open/current-delete 在清除状态前拒绝 unknown、恢复受阻或关键存储失败。新任务解除旧 Executor 绑定；授权后的独立 hook（含 /verify）按需建立新 journal，不能写回旧任务。
- symbol 不再属于并行只读集：未隔离 LSP 的启动/查询经过 durable prepared/finished。LSP 服务可能继续异步写，B的保守 unknown 验证限制保留；请求 finished 不表示 LSP 服务退出。后台job同样尚无完整持久生命周期，本批不声称恢复后可安全杀进程。
- durable prepared 保存精确调用参数摘要、授权来源/决定/范围引用（不可复用）、安全范围内的本地目标路径及执行前观察；不保存原命令/环境/输出。模型调用经过 gate，hook 记录 hook-gate 的当前规则和模式；直接内部调用只标 caller-boundary，不能冒充用户授权。恢复不会恢复临时确认缓存。
- 恢复逐 unknown 操作重新观察本地目标（安全读取摘要/缺失/unknown）及 B 文件/Git 指纹，持久保存观察。`{"action":"reconcile"}` 可再次核对。观察失败保守 unknown；缺文件、相同hash和PID均不能证明外部副作用未发生，既不自动重跑也不凭PID杀进程。
- `{"action":"resolve","operation_id":"操作ID","acknowledgement":"用户人工核对的依据与剩余不确定性（勿含秘密）"}` 保存当前观察和人工声明，将操作转 resolved（acknowledged-unknown）。这不是 completed、外部无副作用证明或重新执行授权；禁止传入伪造 state/evidence/grant 字段。可查询的外部结果需要用户通过现有只读查询渠道核对并在声明中引用；本批没有为任意Shell/MCP建立通用可信外部结果查询适配器。
- Executor 诊断回调失败不改变事实；未捕获执行异常为 unknown，普通工具错误结果仍为 failed。Toolbox 内层和 Executor 不把 PersistenceError 包装为普通 ToolResult，复现钩子也不得吞关键写失败。finished 写失败使内存 unknown 并阻止继续。

仍需 Astra 重点审查：旧身份兼容强度、所有控制/内部调用的持久化覆盖、人工声明解除阻断的语义、LSP/job异步副作用与下一批生命周期的边界。没有 exactly-once、外部状态原子快照、通用外部结果真实性或父任务总预算保证。

## 16. D 中期 P1 活动指针修复（0.87.0，待审）

针对 `/var/tmp/feiyu-d-review/repro.py` 的旧 session → `/task new` → 独立 hook 写入 → finished 前退出窗口，增加 `<sid>/active.json`。这是独立于模型消息和 backend 的关键记录，包含版本、session/task/workspace 身份和 SHA-256；复用 0600 tempfile、文件 fsync、replace、目录 fsync。`new_task` 立即建立空 sidecar 并激活；独立 hook 和执行器 prepare 在副作用前再次确保活动指针 durable，不依赖可能直接返回的 `session.save`。

顺序固定为 sidecar → active → prepared → 副作用 → finished，session 对话 checkpoint 可落后。sidecar 前退出没有可执行记录；sidecar 后、active 前退出可由同 session 扫描发现，尚无本次副作用；active 后、prepared 前退出恢复空任务；prepared 后无论是否已启动，均恢复 unknown；副作用后、finished 前退出同样 unknown；finished 已 durable 而 session 未更新时，恢复以 active 所指 sidecar 为准。active/prepare 写失败均不启动副作用，包含 replace 后目录 fsync 失败这一不确定持久化窗口。未知结果不自动重试。

恢复先安全读取 active，再验证同 session 的全部 `*.task.json`，全部验证完才对选中任务做 reconcile checkpoint。active 损坏、未来版本、身份不符、非法 task ID、引用缺失任务均失败，原件保留，恢复错误禁止继续或切换。active 缺失兼容前版本/激活前崩溃：选 session task_ref，若没有则确定性选择一个已有任务，同时加载所有未决 journal；这不证明它是最后活动任务。session task_ref 指向缺失 journal 也失败。旧 session 指针落后不能隐藏新 journal，其他任务中的 prepared 在内存视为 unknown，持续阻断新增副作用、reset、new 和 complete，不能通过选择已完成任务绕过。

`/task {"action":"pending"}` 返回 selected/pending/tasks；`/task {"action":"select","task_id":"…"}` 仅在该 session 已验证任务中选择核对目标，更新活动指针，清临时命令授权，不执行操作、不解除其他任务阻断。随后沿用 show/reconcile/resolve；resolve 仍是用户承认未知的声明，不是执行证明、成功/无副作用证明或重跑授权。未选中的历史 sidecar 不自动改写；只扫描明确恢复的 session，不批量迁移用户历史。选择任务与恢复仍不提供外部结果的可信适配器。

没有 session JSON 或任何模型消息/backend 的 hook，session listing/load 可从 journal 目录生成只读恢复入口；restore 在模型选择之前绑定并核对 journal，journal-only 恢复不要求模型。没有伪造 user/assistant 消息。task ID 受原 ID allowlist 限制，读取用安全有界无软链打开；session journal 目录/锁文件拒绝软链，指针不能指定仓外路径。现有 writer 锁继续生效。新任务保留旧验收，恢复 todo 以选中 sidecar 为准。

限制：扫描同 session 全部 journal，有损坏历史也会保守阻断；无自动修复/删除、保留期限和全局跨 session 未决任务约束。受 POSIX 安全打开/flock 约束，未验证 Windows、恶意目录并发置换或真实断电。硬退出回归验证进程崩溃，不等价于存储设备断电保证。预算/截止/取消统一与后台完整生命周期仍须下一批继续，不推进 E/F，不据此验收 D。Astra 已修的 local_path 和 `_finish` 两项 P2 原样保留，版本不升出未发布 0.87.0。

## 17. D 父模型请求账本续作（0.87.0，部分实现，待 Astra 审阅）

本批没有完成 D。新增 `runcontrol.py`，不替换 B 验证、C Executor 或第16节 active/pending 恢复。

- TaskState.budget 的 `control_version=1` 区分新的任务账本与旧 session 累计字段。新任务从实际请求增量累计 tokens/known_cost；cost 为未知时保留 null，known_cost 只是已知费用下界。旧 budget 原值保存在 legacy_session_cost/tokens，不冒充任务费用，未知任务总量阻止有限费用预算继续消费。session 的旧累计显示接口继续保留；它没有升级为完整供应商账单。
- main、网页 helper、compact、reviewer、finish_json、子调查共用 RunControl。请求前增加 attempts/pending_attempts 并关键保存，finally 记录后端实际累计增量（包括抛异常后已有用量）。usage_reports 区分供应商明确报告零与未报告；未报告不猜零。重启 pending request 的费用总量为未知。有限预算在未知用量时保守停止，不自行豁免费用；没有自动补额入口。
- RunControl 用任务级锁串行准入模型请求，不预估请求费用。一个已经准入的请求仍可能超过剩余额度；没有 token 价格上界预留保证。成本上限只在首次控制绑定/恢复时取原记录与当前配置中较小的非零值；运行中改配置的即时收紧尚未统一，禁止宣称全部预算配置路径已完成。
- 绝对 epoch deadline 与首次请求/独立 hook 时间绑定并保存；恢复不延长，存活进程另用 monotonic 上限防墙钟倒退。重启仍依赖系统墙钟，未实现可信时钟。新 user send 可清除该次取消事件，但不能清除预算、未知用量或截止记录。Executor prepare/dispatch/invoke 均检查，重试等待可中断；主请求返回的工具列表仍在 finally 配对。
- serve interrupt 先标记共享事件，再沿用 interrupt_main 与确认卡唤醒。并行主线程收到中断时先传播事件/取消尚未启动 future，再等待已启动分支收尾。**同步 SDK 请求没有改为不可停止的后台线程，也没有承诺立即取消**；SDK 阻塞、锁等待、ThreadPool join 仍可能延迟返回。当前仅新操作准入/受控 retry wait 有截止检查，不能声称进程等待期间硬截止已经实现。
- 子调查通过 finally 回调用量，失败也计入 session 的外部模型计数；reviewer 同样加入 session 外部计数。OpenAI 流在 finally 结算已经收到的最后一份 usage，异常后不丢已有完整报告。

尚未实现而必须继续：SDK 内部重试/Anthropic fallback 的逐 attempt 与流中断部分 usage 收集；session 未知费用跨所有任务/恢复的完整展示；所有进程等待中的父取消/截止；后台 job durable running/ended/log 与崩溃窗口；Linux boot ID + /proc starttime 身份及 PID 复用故障注入；LSP 异步服务 journal、父取消和初始化失败清理；关键持久化失败后所有分支仍清理的完整矩阵。这些不是测试 skip，也不是已完成功能。

迁移/回退：仅在所选任务按需扩展 budget，不批量写用户历史，维持 schema_version=1 的可选 budget 扩展并严格校验 control_version/counters。未来 control_version 拒读并保留原件。回退前备份隔离 session/journal，旧实现会把任务费用覆盖成 session 累计，**不得用旧写入器继续写新账本并声称额度可靠**。保留全部 A/B/C/D 既有改动，按本节差异回退，不能 reset/clean。未发布版本仍0.87.0，E/F未推进。

## 18. D 后台 job 最小协议（0.87.0，实现交接，待 Astra 审阅）

协议沿用 TaskStore/Executor/Jobs：prepared → 创建私有产物目录 → 启动未放行监管进程 → 持久 running + boot ID/starttime/session/task/operation → 通过私有 stdin pipe 放行。prepared/启动前/启动后记录前崩溃均不重放；pipe EOF 在放行前禁止执行。running 保存之后、放行之前退出仍可能 unknown，不能据此推定未发生副作用。

Linux 监管进程取得真正 child wait status，WNOWAIT 保持组长未回收，先清理其受控进程组，再 wait、fsync output、原子 receipt + 目录 fsync。父进程观测 receipt 才保存 completed/failed/cancelled；日志缺失或 finished 保存失败为 unknown。父退出、写后 finished 前崩溃不丢独立 receipt。命令/环境经 pipe 传递，不写 journal；日志含原始输出，位于私有 session 目录。

身份使用 Linux boot ID + /proc starttime；取消先 pidfd_open，再比较身份，再 pidfd_send_signal 给监管者，监管者仅杀自己尚未 reap 的 child 组。不将 PID 查询与 killpg 组合冒充原子操作。非支持平台拒绝新 job；无法核验的恢复 job 为 unknown，不发 signal。受控进程组不包含自行 setsid/逃逸的后代；不声称可以控制恶意逃逸进程。

恢复只观测进程身份、日志和收据，不启动、重放或主动 signal。终态不依赖 supervisor 的退出码（它可能不是本进程的子进程），也不把 /proc 消失当成功。所有同 session journal 中的 job 都可经 Jobs 查找；running 纳入 pending 与切换保护，用户不能将真实存活 job 人工 resolve。job list/status/output/kill 是已有 job 的控制边界，不新增任意写授权；wait 路径循环检查父取消/截止并收尾。父任务持久 deadline 也交给监管者独立执行。

本批不推进 E/F、不完成 D：通用 Shell/hooks/MCP/LSP/SDK 等待取消、provider 内部 retry/partial usage、运行中配置收紧仍留下一批。最终测试与具体已知限制记录于进度末尾。

本机 Python3.10 缺少 os/signal pidfd 包装时，以标准库 ctypes 调 libc 的 pidfd_open/pidfd_send_signal，同样先开fd后校验；没有架构 syscall 常量或 PID-only 降级。启动前实际探测 kernel pidfd 与零信号支持。父观测终态时再次 fsync output/产物目录，避免在监管者 replace 与目录 fsync 间抢先把终态写入 journal。finished 写失败在该进程内锁存 unknown，重新打开后才能重新核对独立收据。

## 19. 后台产物审查修复

监管者在收据中绑定 output_size/output_sha256；恢复及消费完成日志时通过逐级安全fd打开、普通文件校验、长度/摘要/读前后身份核验。旧无摘要收据、缺失/替换/截断日志或扫描超限保守unknown；真实退出码的历史事实不因此被改写为另一个退出码，但当前完成证据不能继续作为完整证据使用。摘要只检测产物变化，不抵御同UID同时篡改收据与产物。

job output 对unknown不返回内容；运行中允许安全读取有界尾部，终态在同fd核对摘要后读取，拒绝祖先软链/异常类型/路径替换。完整日志核验复用256MiB/5秒预算，超限unknown，不声称任意大小日志能即时校验。

## 20. D 前台 Shell / hooks 等待传播（0.87.0，实施交接，待 Astra 审阅）

本批仅补前台 Shell 与独立/PreToolUse/PostToolUse/verify hooks；保留第18/19节 job 协议及两项P2真实回归，不泛化到 SDK/MCP/LSP/provider，不推进 E/F，不代表 D 整体验收。

新增 processwait.py，复用 RunControl.check 和 jobrunner 的 WNOWAIT 顺序，而不将前台伪装成后台 job：启动前再次检查父准入，运行中每20ms检查同一控制对象（持久 epoch + 活进程 monotonic deadline、父取消、预算停止）；stdin/stdout/stderr 使用文件，既不阻塞在 communicate/input pipe，也不因后代持有输出管道而无限等待 EOF。Shell 的权限/沙箱/offline/环境/shell状态逻辑仍在原入口，hooks 的来源授权、独立日志和验证失效仍在原入口。已删除 shell 状态文件时重建新的0600临时文件，避免 bwrap 挂载缺失源失败。

POSIX 使用 start_new_session；waitid(WNOWAIT) 观察真正子进程退出且保持组长未回收，再 SIGKILL 原进程组、wait 取得真实退出码。正常退出也清理遗留后代，并保留组长原退出码（如7），不把 KILL 后代冒充组长被杀。无 WNOWAIT 的 POSIX 启动前拒绝，不降级为 poll 后再按可复用 PID 杀组。没有引入新依赖或持久进程身份适配器；前台从不根据恢复记录 PID 发信号。

执行事实分为 execution_started、exit_code、stop_reason、evidence_error：已启动后超时/取消/截止的结果与 journal 为 unknown，并保存实际 wait 退出码；Shell 在 Executor 保存这些事实后才向父层传播 RunStopped，hook 在完成独立日志与验证记录后传播。TaskStore.finish 写失败继续保留内存中的真实退出事实且锁存unknown，错误不能被普通工具错误吞掉；进程清理先于终态保存，保存失败不会跳过清理。启动前持久 prepare 失败与父准入拒绝不调用命令；权限拒绝的 standalone hook 明确 rejected、execution_started=false。没有从 unknown 自动重放或扩大授权。

验证取消/超时不再标 not_run：execution=unknown，validity=unknown，保留真实exit_code和停止原因，不能授予pass；导入旧验证记录仍可读，并接受新unknown执行值，恢复继续标历史失效。已正常退出后日志fsync失败则保留 passed/failed 与真实退出码这一执行事实，但 evidence_error/validity=unknown，Executor/journal=unknown、Outcome.ok=false，不将日志失败误报启动失败。not_run留给明确拒绝；启动环境失败为environment_blocked。

迁移为现有 schema_version=1 的可选操作事实字段，不批量改写历史；回退需备份session/journal，旧writer不会保留新增停止字段。不能 reset/clean 此未提交工作区。版本按本批用户明确要求保持0.87.0（优先于CLAUDE的通常bump规则）。

边界：20ms是检查周期，不是硬实时承诺；Popen/沙箱准备/临时文件及日志fsync等阻塞OS调用、内核不可中断I/O仍可能延迟。SIGKILL不能回滚已发生副作用；主动setsid逃逸后代不在受控组内。前台没有独立监管收据，父进程被SIGKILL/os._exit或机器断电时仍按prepared/unknown恢复，不能承诺自动清理或成功，也不能重放。Windows沿用直接子进程kill能力，未提供Job Object树清理保证；非Linux平台未实测。超大hook日志的最终复制/摘要仍同步且未加容量治理，Shell输出为有界临时读取、不是独立持久输出收据。SDK/MCP/LSP等待/服务生命周期、provider逐attempt/partial usage和运行中配置收紧仍留后续。最终命令、失败尝试和结果见进度第“D 前台 Shell/hooks”节。

本批冻结源码证据：Python3.14/3.10定向各359项、0skip、exit0；全量各1687项、19skip、实际各通过1668、exit0（116.197/126.602秒）。唯一D_RUN分别foreground-target-final-{314,310}和foreground-full-{314,310}，均经既有run.py新HOME/XDG隔离，内部result.json已核实；完整命令和失败记录见进度对应节。最终git diff --check通过，无受控fixture运行进程遗留；没有重跑桌面Node/build（无桌面改动）。这些只是程序证据，等待Astra独立审阅，不构成D总体验收。


## 21. Astra 前台中断窗口修复

独立审查确认两项P1：Popen返回后进入try之前的SIGINT，以及finally清理中的第二次SIGINT，均可跳过杀组和回收。processwait现将Popen纳入try/finally，在主线程创建子进程前安装临时SIGINT锁存处理器，直到进程组清理和wait结束才恢复原处理器。真实信号只标记取消，等待器返回实际退出码和cancelled，既有Shell/verify入口持久化unknown事实后传播RunStopped。工作线程不注册信号处理器，仍使用共享RunControl取消；Python信号在主线程处理。保持先killpg后wait，不重试向已回收PID发信号。

新增入口回归在Popen.__init__返回（调用方尚未赋值）、killpg前、wait前注入真实SIGINT，Shell与verify各跑三种情况。断言产品已回收子进程（先于夹具兜底清理）、同组后代不能晚写、journal有started/真实exit/取消原因、verify有unknown记录，以及原信号处理器已恢复。此保护针对processwait拥有子进程期间；不宣称对任意Python异步异常、父SIGKILL或此范围外的连续中断提供原子持久化保证。D其余缺口不变。

## 22. D LSP 持久服务与有界等待（实施设计，待独立审阅）

单次 symbol 的 journal 仍是副作用操作，不能把语言服务器视为纯读取或隔离执行。新增 `lsp-service` 操作记录：spawn 前 prepared 持久化；直属进程身份（Linux boot/starttime）保存后为 serving，服务初始化完成仅更新 service_status=ready，不代表任务或 symbol 成功。在线 serving 不进入 pending；恢复时所有 serving/prepared 转 unknown，仅观察，不重放、不启动、不对旧 PID 发信号；服务失踪也不是成功。unknown 复用 pending/select/resolve，仍存活同身份服务不得人工 resolve。正常关闭保存 completed + service_status=stopped，含义只限受控进程生命周期已终止。故障关闭记 unknown，保留人工核对要求。

Pool 绑定 Toolbox 当前 Executor 的 control/durable/active_operation；服务 prepare 允许当前已准入 symbol 操作，禁止其他未决操作。服务归启动时任务所有，任务切换先关闭服务，避免跨任务持有旧 deadline。父取消、deadline、关键持久化 blocked 和服务器退出由监视线程短周期发现并收尾；关键保存失败先回收，再传播，不能依赖诊断 sink。

仅在 Linux 且具有 waitid/WNOWAIT 时启用受控 LSP；不承诺跨平台。持有 Popen 直属 child，禁止 poll/reap 直到 killpg，SIGINT 启动交接和清理复用 processwait 的锁存。所有锁获取、非阻塞 os.write、协议读取与 warmup 每 50ms 检查父控制，共享单次绝对 timeout；关闭不等协议 shutdown、不取请求锁，直接杀组并有界 wait/关管道。共享 PipeReader 不修改，MCP 行为保留。普通异常/取消后终止服务，防止半包/迟到回复被复用。协议头/体设大小边界，持续噪音也检查 deadline。

边界：进程组不包含主动 setsid 逃逸后代；父进程硬死亡后没有独立 LSP supervisor，恢复只观察并需用户核对/外部清理；内核不可中断睡眠可能使 kill 后有界 wait 失败，此时记 unknown，不宣称完全回收。旧 reader 和工具接口继续支持，TaskState schema 1 新增可选操作 kind/state，旧版本不能读取 serving，回退前必须关闭服务并保留 journal 原件。不扩展 MCP/SDK/provider，D 不自行验收。

### 22.1 最终接缝与兼容说明

实现使用独立 service operation，`parent_operation_id`/call_id/原准入 authorization 关联 symbol 操作，不存明文 argv。process 身份复用 jobs.identity，当前 owner 清理依赖直属 child 未 reap 的 WNOWAIT 保证；恢复只用 boot/starttime 观察，不使用 killpg/pidfd_signal。`serving` 仅允许 lsp-service，其他 kind 不能借此绕过 pending。TaskStore.load 把 serving 转 unknown；reconcile/resolve 沿用显式人工 acknowledgement，仍活同身份者拒绝 resolve，失踪/身份不同也只允许确认未知，不会推导成功。

Pool 缓存按完整 argv，关闭事件先中止正在构造的 Client，再至多3秒等待所有权交接；Client 的 kill 后 wait 上限2秒。close 不取协议锁；协议操作使用绝对 timeout，锁/写/读均50ms轮询父控制；取消造成的 BrokenPipe/关闭fd异常在清理后再次检查父控制，保留 RunStopped 原因。监视线程覆盖无请求时的取消/deadline/服务退出/存储 blocked。`/task select`、常规任务切换及 agent.cancel/checkpoint 失败清理 LSP，cancel 的 LSP 错误不阻止既有 jobs 清理。Executor 终态保存失败先尝试关闭服务，再保留原关键错误。

正常明确关闭保存 completed/lifecycle_only 只表示服务进程已收尾；异常退出、请求失败、取消过程中断操作仍为 unknown。healthy serving 既不 pending，也不当作 symbol 结果；现有验证 mutation callback 和 `_unisolated_lsp` 保守失效一直保留。服务失败后的缓存会显式要求核对，只有服务 resolved 或明确 Pool.close 后才允许后续显式新调用重新启动；恢复从不自动创建 Pool Client。独立无 durable Pool 仍可在关闭死 Client 后按显式 get 重建。

操作有界不等于能给内核文件系统调用设硬实时限额：spawn、fsync、关键 journal 文件读取和线程调度仍取决于 OS；不可中断内核睡眠或第三方主动逃逸进程组无法承诺回收。Pool 关闭等待超时明确报 cleanup unknown，保留关闭事件阻止新准入。未提供跨平台降级为旧的不受控启动。

迁移：schema_version 仍1，旧记录不改写，新增 serving 枚举与可选 kind；旧程序无法读 serving，不能直接覆盖新 journal。回退先正常关闭当前服务、退出 writer，备份完整 session 目录，核对未知服务/操作；仅回退本批源码差量（保留 A/B/C/D 其他修改），不要批量重写真实历史或把 unknown 改 completed。不能仅按旧 PID 做回退清理。版本保持0.87.0未发布。

## 23. D 独立 SDK 尝试记账设计（实施中，待 Astra 审阅）

不执行或重试受阻的 LSP 独立审查，不改 LSP/进程生命周期，不推进 E/F。保持 0.87.0。

- providers 的单次 ask / streaming attempt 是计账边界；SDK max_retries=0，适配器显式有界重试，缓存 fallback 是另一次尝试。RunControl 通过上下文绑定父任务，外层兼容非 Billing 后端的旧计数接口，避免双计。
- 每次发送前保存 pending；结束后保存完整/部分/未知、token 与已知金额下界。流 usage 按累计字段合并，不逐事件相加；只有输入或中断的 usage 为部分，缺 usage 或价格为未知，均不作为零费用。部分数字仍计入下界。未知状态粘滞保存在父预算与会话展示中。
- 父锁串行准入及持久记账，覆盖主请求/helper/reviewer/compact/subagent。关键保存失败将控制器与 store 标为 blocked，后续调用必须失败；恢复保留 pending/未知与旧额度。动态限制只收紧，下一次请求前刷新，时间限制沿原起点计算。
- 同步 SDK 无安全即时取消能力：不另起后台线程；事件、调用返回和重试等待处检查取消/截止。网络等待受 SDK socket timeout 约束，不能承诺总时限硬中止。
- 本机核对 anthropic 2.8.0 / openai 3.51.0；_base_client 的 max_retries=0 关闭重试；Anthropic streaming/_messages.py 明确 message_delta usage 是累计值、遗漏字段保留 message_start 值。只读本机包源码，无真实请求/密钥读取。无新依赖，Python 3.10。

### 23.1 已实现接缝、格式与限制

`RunControl.attempt` 对带 SDK client 的 Billing backend 绑定 ContextVar；单次 provider `ask`/`_turn` 内再准入，兼容无 SDK client 的旧 Fake/custom counter backend。主请求、helper、compact、reviewer 仍走 `_model_call`，subagent 仍使用父 attempt 绑定，不改外部签名。父控制器创建由 agent 锁串行化；所有实际请求持父 RLock 到结束，防止并行 helper 使用同一笔剩余额度。重试在已见流事件后不执行；Anthropic 与 OpenAI cache fallback 在单次尝试之外，单独记 pending。默认显式至多4次重试，退避0.5/1/2/4秒；不再由 SDK 内部重试。有限额度遇首个未知失败后保守阻断 retry/fallback，不能假定失败请求免费。

budget 增加可选 `attempt_records`、`partial_attempts`、`started_at`：每行 sequence/model/started_at/state，终态含 usage_status、tokens、known_cost、price_known、usage 数字快照、outcome、finished_at；不记录提示或密钥。完整 usage 与已知价格是两个维度，`known_cost` 永远仅下界，`cost=None` 表示总额未知。旧计数适配器保留 delta 兼容；它没有原生协议完整性信息，不能视为 SDK 集成证据。跨失败/未知后成功不会冲掉旧未知；SDK 报告的显式双零与未提供字段不同。累计字段取非递减快照，输入/输出分别判断，Anthropic cache 与 message_delta 遗漏字段保留，不相加重复事件。

运行中限制通过 limit_source 在检查/准入时刷新，cost/time 仅取更严格值；起点在首次控制器创建时固定（已有原始请求时采用请求起点），恢复不补额度或延长 deadline。请求允许一次超支；不预测服务端未来费用。pending crash 保持 pending 计数及未知总额；不自动重发或以新额度替代。关键写前/写后失败均锁存 control/store.blocked，当前进程后续请求拒绝，即使故障注入仅抛异常、未设置 store 状态。正常持久文件损坏继续沿既有 fail-closed 读取。

backend.priced 对缺失/部分 usage 也粘滞为 False；agent 捕获未知费用，session 新增可选 `unknown_cost`。恢复不只依赖 session 快照：同 session 已恢复的全部 task budgets（含旧任务/pending）参与 cost 展示，因此 journal-only 恢复和任务切换不会让未知费用变成0。不同 session 仍隔离。旧会话无新字段可读，不批量改写历史。

格式兼容：TaskState schema_version/control_version 仍1，新增 budget 嵌套列表有显式读取校验；新代码读旧数字预算，旧代码不能读取新 attempt_records，失败关闭而非静默丢账。session 的 unknown_cost 为可选字段。回退前退出 writer，备份完整 session+journal，仅回退本批差量；保留新 journal 原件，不删除 pending/未知或重置累计金额。需用新读取器核对账本后再决定兼容导出，本批没有自动降级迁移。

SDK能力边界：两版环境均 anthropic 2.8.0/openai 3.51.0（本地实际包）。同步 create、stream enter/next 与 close 仍由 SDK/网络驱动；父取消在流事件/返回/退避处被发现，网络静默可能等到 FEIYU_STREAM_TIMEOUT（默认600秒，相邻读取超时，非总请求时限）。持父锁的同步请求也会延迟其他线程的准入/配置保存；不启动不可停止的后台线程，不宣称实时可取消。显式重试采用上述本地退避，未完整复制 SDK Retry-After/jitter/exception cause-chain 策略。服务端未提供/非标准 usage、内置 server tool 等额外费用无法推断；本账本是接收到的 token 及配置价格核算，不保证与供应商账单完全一致。没有真实模型收益或计费对账验收。

Astra重点：实际 SDK max_retries=0、两种 fallback 的尝试边界、异常流 usage 下界与完整性、累计去重、父锁与 ContextVar/旧适配器边界、关键保存异常锁存、恢复不补预算、动态收紧不放宽、跨任务/journal-only 未知费用展示及格式降级边界。LSP独立审查仍受阻未验收，本批未执行/接管/重试；D整体不验收，MCP等其他缺口仍待后续，E/F未启动。

23.1补充：同一进程收紧限制时，monotonic_deadline 也只取更早值，防止系统wall clock回拨叠加cost收紧反而延长等待；没有将跨重启monotonic读数当持久时间（恢复仍依据原绝对deadline与系统wall clock）。新增离线时钟回拨回归和隔离副本负对照。同步SDK静默等待限制依旧，不增加取消线程。

23.1协议终止补充：正常迭代EOF本身不是完整性证据。OpenAI要求观察到finish_reason，Anthropic要求message_stop；缺终止事件即便已有input/output数字仍为partial，只计下界。Anthropic本机get_final_message仅assert快照非空，不能替代message_stop。输入/输出字段齐全、协议结束且本次方法正常返回才标完整；异常、close失败或仅输入仍为未知总额。非流式ask以正常响应与两项字段为准。新增两种静默EOF合成回归；不以后台线程改造等待。

## 24. D 普通 MCP 最小设计（实施前，0.87.0）

范围仅 mcp.py 与 Toolbox 控制/执行事实接缝；不改 LSP/SDK，不推进 E/F。一次请求自准入起持有同一个 monotonic timeout，锁等待、发送、接收、反向请求共用；每50ms检查显式父RunControl（含持久deadline及动态收紧），初始化和分页亦传递。等待锁尚未发送为not_run，不关闭另一请求拥有的连接；发送后异常/停止使连接永久失效，丢弃迟到响应且禁止自动重连/重发。完整匹配JSON-RPC结果才是完成证据。

stdio在POSIX使用非阻塞写和短读等待，无后台写线程；不支持可停止管道写的平台明确拒绝启动。HTTP保留urllib协议解析，在每次POST的短命Python I/O进程执行；父进程通过有界管道轮询、到期终止并wait回收，覆盖DNS/headers/body/SSE慢流，不能用不可停止线程冒充取消。HTTP关闭仅本地失效，不额外等待DELETE；服务端session可能保留到其自身过期，已收到POST的远端动作无法撤销。启动OS调用/不可中断内核I/O不提供硬实时保证，终止收尾有限wait，失败须显式报错。

Toolbox把父控制显式传入Registry；MCP异常携带发送边界与停止原因，转ToolResult后先记账再传播RunStopped。进入transport.send即保守视为可能已发出（含部分写、HTTP worker启动窗口）；无结果则unknown，不宣称执行成功或未执行。发送前拒绝为execution_started=false/not_run。关键写失败继续上抛并阻止后续调用。权限/readonly hint不变。测试使用合成stdio及loopback HTTP，实际Toolbox入口验证事实、journal和配对；新HOME/XDG、唯一D_RUN、硬timeout、两版Python。D待Astra独立审查。

### 24.1 实施边界、兼容与审查重点

实现保留Registry.call原有(text, failed)接口；Toolbox用facts=True取得RequestFailure中的started/known/stop_reason。匹配JSON-RPC error是已知失败；异常或无匹配响应是unknown。正常响应也写execution_started=true；发送前停止/失效连接/锁超时写not_run，随后才向上层传播父停止。Executor仅对MCP将最初控制检查移入已prepared的请求准入，使Toolbox直接入口取消亦可记录not_run；既有Agent授权、prepare/dispatch检查不变，不扩大权限。TaskState只增加not_run枚举的读取支持，RunControl及已审SDK实现未改。finished保存失败时关闭MCP，收尾异常仅附于内存evidence_error，不遮蔽原始关键保存错误；持久化失败不伪造成功。

Registry启动改为调用者拥有的串行启动，不再遗留超时daemon启动线程。初始化、通知、每页list各有20秒本地上限，list至多50页；父持久deadline优先，未设置父deadline时多服务器/分页总时长可累计，不承诺全Registry固定20秒。每次HTTP POST启动短命源码Python，stdin传已展开的url/headers及请求，argv不含凭证；避免二次环境变量展开。正文/headers/DNS的阻塞均局限于可回收worker，父每50ms轮询。stdio/worker采用POSIX非阻塞写；其他平台明确拒绝，未假装支持Windows可取消写。冻结版sys.executable不能执行Python -c，HTTP明确拒绝并提示源码运行；本批未补冻结入口，也未做桌面构建验证，这是现有HTTP能力的明确兼容限制，后续应在独立打包适配任务补齐。

关闭不发DELETE，HTTP远端session可能保留到服务端过期；本地取消不证明远端未收到、未执行或已撤销。stdio/worker关闭先SIGTERM、2秒后SIGKILL、再wait最多2秒；仍未回收显式报错，不以daemon线程冒充完成。Popen/JSON序列化/文件系统关键写/不可中断内核调用不是硬实时可取消点。父进程硬死亡时没有独立监管HTTP worker的收据，worker可能继续到其网络超时，DNS等仍可能阻塞；恢复仅prepared→unknown，不自动重放，不能承诺父硬死后立即终止远端或worker。

兼容/回退：新增not_run终态旧reader不认识，回退前停止服务器、关闭writer并备份sidecar/journal；旧版本只读历史，不用旧版本继续带新终态的任务，不改写unknown为成功。只撤本批差量，保留SDK、LSP等既有工作，不删除用户配置/历史。源码版本仍0.87.0。

Astra重点：发送边界的保守unknown与not_run准确性、锁等待者不得关闭拥有者、所有阶段共用请求timeout且父持久deadline优先、迟到响应与关闭后禁止复用、初始化交接/worker管道背压及回收、关键保存错误不被普通MCP错误/收尾异常吞掉、Toolbox/Agent一调用一结果、匹配协议error与未知响应的区别、HTTP远端不可撤销与冻结/非POSIX兼容限制。此设计/回归不替代独立审查或D验收；受阻LSP审查保持未完成，不接管、不重试；E/F未推进。


### 24.2 Astra审查修正

HTTP close与活动worker归属由独立同步保护，关闭时有界回收当前worker，关闭后禁止导入迟到session/inbox；不依赖整个请求锁。异常清理保留原PersistenceError或取消原因，次要清理错误附加诊断，正常路径无原异常则仍报告清理失败。冻结HTTP及非POSIX能力降级尚未接受为最终方案，需后续打包/传输适配补齐；正常显式退出的远端session best-effort释放也需恢复适当有界行为。

### 24.3 P1 兼容补齐设计与迁移（2026-11-16，待 Astra 审阅）

本节替代24/24.1中“冻结HTTP/非POSIX禁用”和“正常关闭不发DELETE”的最终方案；历史记录保留，不代表此前降级已获接受。保留24.2两项P2：独立_worker_lock/_worker/closed所有权与结果导入检查；_close_preserving保留PersistenceError/取消，secondary附cleanup_errors，正常无原异常仍报告cleanup失败。

内部HTTP入口为精确单参数 `--_mcp-http-worker`。源码 `python -m feiyu` 在__main__顶部、业务/SDK导入前分流；冻结 backend_entry 在runtime冻结环境配置之后、业务__main__导入之前分流。源码worker argv为本解释器 `-m feiyu --_mcp-http-worker`，冻结worker为同一sys.executable加该开关；请求、URL、已展开headers、session、协议版本、超时和DELETE标志全部经stdin单行JSON，不放argv，不二次展开。worker保留urllib重定向拒绝/JSON/SSE解析，只执行一个网络操作；父进程仍以原请求总预算检查、终止并wait回收。不需要外部Python或新依赖。内部入口不是服务监听器，也不读用户MCP配置。

非POSIX中的正式Windows路径使用独立 `mcp_windows.WindowsPipe`，不改共享pipe.py/LSP。评估：stdlib socketpair/loopback socket能select，但Windows普通stdio子进程的ReadFile不能直接消费Winsock SOCKET；增加桥进程/监听端点还须认证及管理桥和子树。multiprocessing Connection.send自身可阻塞，单独换IPC名称不能解决取消。overlapped named pipe可行，但需要额外管道创建/句柄继承协议。选择无新依赖的ctypes Win32适配现有匿名管道：PeekNamedPipe轮询可用字节后读取，无永久reader线程；writer线程只做os.write，调用者每50ms检查父控制/总预算，finally设置停止信号并以CancelSynchronousIo重复取消、限时join（2秒），覆盖检查与进入WriteFile的竞态。线程daemon标志不是回收证据，超过界限明确报未回收。Windows close先有界taskkill /T /F（2秒），再kill/wait，再取消并join writer，最后关句柄；taskkill不可用/失败的子树收尾能力仍需实机检查。POSIX保留非阻塞管道，无新增后台写线程。不宣称支持所有非POSIX操作系统。

正常空闲显式HTTP close先置closed/清空inbox和session，再经同样可回收worker在独立0.5秒网络预算内尝试DELETE，带session和协商版本；无重试。释放用临时transport，send finally拥有并回收worker，不递归DELETE。release_confirmed仅表示DELETE收到成功响应；release_error明确保留“远端session释放未确认”及原因。异常/取消期间或在途close只回收活动worker，不加网络请求、不拖住主错误，并保留释放未确认。DELETE不撤销之前的POST，也不证明服务端动作未发生；本地关闭/unknown语义不变。正常释放失败属于best-effort诊断，不替换已完成的调用结果。

迁移无需改mcp.json、外部Python或重装依赖；desktop打包脚本加入实际冻结MCP smoke，发布入口与get.sh shim均指向同一个backend_entry构建的可执行文件，故无需完整发布AppImage/deb/NSIS才可验证内部路由。回退仍须遵守24.1新not_run journal的兼容规则；只回退本批差量，不撤Astra的P2、SDK或其他未提交工作。版本仍0.87.0，HEAD d82d943。

已测平台仅本机Linux：3.14/3.10源码；用既有desktop/build/python-build依赖离线构建的Linux PyInstaller onedir真实二进制。冻结协议probe实际启动该ELF worker，覆盖初始化、工具、DELETE、取消及回收，PATH故意无外部Python；另生产 `--serve` 父入口加载loopback HTTP配置，未经sys.frozen/worker argv mock，验证初始化/工具列表/session与正常退出DELETE。工具调用/取消probe由源码父驱动真实冻结worker（明确替换父的worker命令），不冒充整段GUI对话/模型调用；生产父入口另有无mock检查。Windows源码/冻结实机不可用，真实管道背压用例已加入但Linux跳过；Win32 API运行效果、取消竞态、子树终止和NSIS均未验证。未跑macOS，未访问真实外部MCP/模型/密钥，不宣称远端动作撤销。Popen/OS不可中断调用和父硬死亡的既有限制继续保留。

Astra交审重点：真实冻结父路由与同exe再启动的环境；stdin敏感值与字面量不二次展开；Windows PeekNamedPipe唯一reader假设、CancelSynchronousIo权限/竞态/join及taskkill失败路径；正常释放的预算/诊断与主错误优先；关闭/响应交错不复活session；P2原有回归不退。Windows证据缺口待实机补齐，不据Linux测试自行宣布P1全平台关闭或D验收；不推进E/F，不接管/重试受阻LSP审查。


24.3续补：请求级closed检查覆盖响应已导入但尚未消费的关闭交错；读取前后均先检查父控制再检查关闭状态，已发送请求按unknown及时退出。HTTP inbox与close同锁访问，空闲DELETE须完整请求锁未占用，不只以worker已退出判断空闲。旧冻结产物不含该续补，最终产物验证应重建。

## 25. D3 明确任务结果（实施前最小设计，待 Astra 审阅）

仅扩展现有 TaskState 与 `/task` 控制，不触碰后台限制同步、LSP/SDK/MCP进程或 E/F。`run_state` 继续描述运行；`result` 增加 `partial`（用户声明已交付部分结果）、`unverifiable`（用户声明当前无法验证结果），保留 `unfinished`（未作结果结论/继续工作）、`completed`（显式结束且经现有事实验收门禁）。等待、中断、费用/时间停止、模型自由文本均不推导结果。

新增 `/task {"action":"result","result":"partial|unverifiable|unfinished|completed","reason":"人工说明，勿含秘密"}`，仅 CLI/serve 控制调用。partial/unverifiable 必须有说明；人工声明不设置验收 status、不制造验证 passed。所有新声明保存 `result_details`：user-control 来源、说明、请求引用、时间及当时验收状态/verification_refs 快照；其中 verified 来源仍只由 Ledger 核对，不因用户宣称而升级。没有自动部分完成推导，避免把验证数量当作交付比例。completed 复用原 complete 的 pending/unknown 与有效验收门禁，旧 `/task complete` 保留。

新请求继续 partial/unverifiable 时复用任务但结果回 unfinished；验收/验证引用保留。completed 继续既有下一请求新任务语义；checkpoint 核对后若验收失效则撤回 completed 至 unfinished。结果操作不改 run_state（旧 complete 保留 idle），不处理 unknown、不清授权缓存、不许可重放。

持久化仍走 checksummed sidecar/session 与关键写失败阻断。schema_version=1 可选字段默认空 details，旧 unfinished/completed 可读，不补造来源；恢复重新核验事实，旧值不等于新的事实证明。新枚举旧 writer 不理解，降级先退出 writer、备份完整 session/journal，只读历史，不删改 unknown 或批量迁移。实现后以隔离 HOME/XDG 白名单 runner、FakeBackend 和真实 CLI/serve/verify 入口检验，交 Astra 审阅而不自行验收 D。

### 25.1 已实现接缝与审阅入口

`TaskState.result_details` 可选字典经内层校验，partial/unverifiable 没有 user-control 说明/请求来源时拒读；旧 unfinished/completed 不补造历史声明。`revise` 在原任务继续时清空旧结果声明，不删除验收与验证引用。`Feiyu.task_control(result)` 复用 `_check_task_acceptance`/`_guard_task_switch`；completed 的既有空验收行为保留（没有验收项也不等于测试通过），其他结果不解除任何 pending。只有旧 `/task complete` 保持将 run_state 置 idle 的行为；JSON结果操作只改结果。关键写失败仍锁存 blocked，需重开核对。

`_task_checkpoint` 重新核对 completed 的事实，验收失效撤回 unfinished；恢复在加载 Ledger 后 checkpoint，journal-only 恢复也按无当前验证事实保守核验。`send` 在决定是否新建任务前先核验 completed，避免失效结果直接转新任务。partial/unverifiable 是历史人工结果声明；其中快照不是“当前验证通过”，恢复不会将快照导入 Ledger。没有自动交付比例或从自由文本升级的逻辑。

CLI `/task` 展示独立 run_state/result，JSON show 返回说明和依据；serve 继续用原 note 渲染 JSON，并在 status 增加可选 `task={task_id,run_state,result,result_details}`，旧客户端可忽略。`progress.selected` 含同样结果字段，完整 TaskState.context 已自然包含新字段。未修改桌面 renderer、UI框架或布局，未触碰 LSP/SDK/MCP进程、后台父限制同步或 E/F。

Astra 可从 `tests/test_task_results.py` 的8项入口回归开始：真实 verify/bind 形成 verified+unverified；partial声明/继续/重新验证/完成/日志失效；serve命令note/status与session恢复；等待/CLI中断/预算与截止停止；unknown仍阻断且授权不可复用；旧内层及checksummed sidecar读取保留原件；伪造声明/存储失败；completed恢复撤回。测试为FakeBackend/合成工作区离线事实，不是远端或真实模型证明。精确命令、所有失败轮次、负对照及双版最终结果见进度与命令索引。D3仅实施完成待审，D清单不勾选；LSP受阻独立审查保持未接管。

## 26. D 后台父限制同步（实施前最小设计）

仅普通本地任务预算控制。存活父的 DurableJob.monitor 每50ms取得 RunControl 的有效限制，复用 tighten 单调收紧及关键保存；请求持父锁时不等待该锁，按只读快照和 limit_source 的更严值检查费用/时间，不把在途 pending 本身当已超额。预算已到、unknown费用遇有限值、取消均停止。避免锁顺序反转：父控制检查在 job/store 锁之外。只在限制变化时经原私有启动管道传更早 deadline 或具体停止原因，不轮询重写journal。管道非阻塞、小消息；失败保留主错误并以既有身份信号收尾。

监管者接收后只收紧不放宽；父死亡/管道EOF后继续最后收到的deadline，不声称读取已死父配置。监管者先观察真实退出再应用停止，保留原退出码与终态；实际停止记录 deadline_stopped/budget_stopped/cancelled，启动旧deadline理由兼容既有deadline。沿用身份核对、WNOWAIT进程组回收、输出摘要及独立收据；无重放/新授权/resolve豁免。关键保存失败时即使不能写journal也收尾；monitor锁存原异常，控制后续检查及job交互显式抛出，收据仍可观察，不把停止当成功。

双解释器隔离合成真实sleep/标记任务，通过ready文件和事件明确同步，断言产品收尾发生于夹具兜底之前。覆盖无wait收紧费用/时间、已到/未知预算、取消、保存失败、父持锁、父死亡最后deadline、正常已完成不改写。仅Linux既有可靠身份范围；OS不可中断调用/逃逸setsid限制不变。无schema迁移；旧记录只读，降级先退出writer和job并备份完整journal，新收据reason是字符串扩展。Astra重点：无父锁阻塞、单调限制/EOF、错误优先与真实终态竞态、恢复pending/resolve不退。D待审，不推进E/F或接管LSP审查。

### 26.1 实施状态与边界（待 Astra 审阅）

已实现 RunControl.background_limits：独立短锁锁存最严费用/时长和双时钟deadline；父请求RLock只作非阻塞尝试，拿不到仍按快照停止/通知监管者；后续tighten合并锁存值，不因源配置放宽补额。在途pending本身不停止既有job；已知费用到限、unknown遇有限预算停止。正常idle不写journal，只有限制真正变化及operation状态变化才保存。

tools保留原私有stdin门禁并切非阻塞；DurableJob.notify仅发变化或停止，小JSON写失败保留异常、身份安全信号兜底。jobrunner按更早deadline接收，EOF不取消原监管；时间/费用停止的收据reason分别deadline_stopped/budget_stopped，显式cancel仍cancelled，保存失败以persistence_error收尾。已有启动deadline保留旧reason=deadline兼容。监管者每20ms观察退出与管道，父monitor每50ms检查；这不是OS硬实时承诺，也不改变SDK静默等待能力。

真实退出在应用停止之前观察，terminal_reason在该决策点冻结，后续信号不改写真实exit。持久化失败保留独立收据，内存operation保守unknown，monitor保留主异常至job.status/take/wait/kill及父check，不由清理次错替代；存储失败后的journal仍须重新打开核对。恢复只建立无control/proc的观察对象，不启动monitor/重放。父死只保留已写入监管管道的最后deadline，不提供父配置实时读取或费用账单硬上限。

迁移无新schema/配置；旧收据reason仍可读，新增reason为现有字符串字段。回退先关闭writer与job、备份完整session/journal，仅撤本批差量，不能用旧writer覆盖新结果/unknown，也不能删除预算事实。精确命令、失败轮次、负对照、最终源码指纹见进度末尾及job-limit命令索引。D3的select checkpoint与两项回归原样保留；版本0.87.0/HEAD d82d943，无提交发布，无E/F及LSP审查动作。

26.1末次兼容补充：保留控制管道后，实际子命令显式stdin=DEVNULL，保持旧启动管道关闭后的EOF，避免子命令与监管者竞争控制消息；合成场景以read先确认EOF再发ready。启动deadline的父通知归一到监管者已有来源，已到截止的决策保留deadline/动态deadline_stopped，持久化失败优先；真实退出观察仍最先。这只是原本地job协议/预算实施的兼容收口，不改SDK/LSP语义。

## 27. D10 同步 SDK worker 等待取消（2026-11-17 实施，待独立审查）

本节更新第23节的同步静默等待限制，仅实施D10，不宣称D完成，不推进E/F。协议先行记录在 `/var/tmp/feiyu-d10-sdk-worker-20261117/protocol.md`。每次ask/stream attempt新建独立worker；父RunControl仍是唯一准入/pending/usage账本，父provider保有原生历史、缓存策略、回调、retry/fallback。worker只有一次SDK调用，max_retries=0、不读用户模型配置、不写journal。Fake/替换client保留既有同步调用接口；真实内建client通过worker。模型列表查询不属于任务生成attempt，仍沿用原路径。

SDK IPC v1是独立于MCP的私有stdin/stdout协议：4字节网络序长度、UTF-8 JSON，每帧最大64MiB，超限显式失败而非截断。request携带provider、显式client配置和原生kwargs；event/result携带SDK模型的完整model_dump(json)，父端按固定SDK Message/RawMessageStreamEvent/ChatCompletion/ChatCompletionChunk重建，保留额外字段、thinking签名、工具分片与多模态。结果快照不替代协议结束；只有done说明worker正常关闭SDK。error仅传白名单连接/超时类别、status、x-should-retry及cache拒绝判据，不传异常原文、请求、响应正文或headers全集。密钥只在内存和私有stdin，不在argv、stderr或journal；worker stderr丢弃，故诊断细节有所减少。

父进程POSIX非阻塞管道每50ms检查停止、持久化blocked和更早deadline；发送背压、建立请求、静默read、流迭代与收尾均可停止。锁等待也按50ms观察；tighten先发布单调限制，不等活动请求持有的ledger锁，请求持有者轮询后保存。pending本身不触发inflight预算停止。接到停止即拒绝后续帧，kill+wait自身worker，再关闭管道；Popen交接和收尾延用通用SIGINT延迟保护，不改变MCP业务协议。回收失败在原异常sdk_cleanup_error中明确unknown，无原异常则抛WorkerError，不声称已本地完成。原停止/持久化异常优先，额外终态记账失败附accounting_error并锁存blocked。

收到结果usage即在父观察，故终态与取消交错仍保留下界；没有done/完整协议终止或异常时维持partial/unknown，不将未收到usage视为零，不重复相加累计usage。父硬死亡后持久pending恢复不重放；本实现没有独立SDK监管收据或父死亡远端撤销保证。本地kill不撤销远端生成/收费，不保证一次请求绝不超额。

源码精确 `python -m feiyu --_sdk-worker` 与冻结同exe `--_sdk-worker` 在业务导入前分流；desktop构建加入离线SDK smoke。没有新增运行依赖。每attempt新增Python/SDK导入成本，丧失跨attempt连接池复用。Windows有独立PeekNamedPipe reader和发送线程，仅用于管道写，取消时先kill/wait唯一reader再join发送线程；没有把SDK放到不可停止后台线程。Windows/macOS未实机验证，不将Linux证据泛化；不禁用既有Windows/frozen路径，也不扩建TaskStore/LSP/jobs既有Windows缺口。OS不可中断I/O、Popen/序列化和用户回调本身不属于50ms硬实时承诺。帧上限是新增明确容量边界。

迁移无schema或配置变更，版本保持未发布0.87.0/HEAD d82d943。回退须先停止请求、退出writer并备份session/journal；只撤本批SDK差量，保留所有既有工作及unknown费用事实，不用旧writer覆盖pending或重放。最终验证和具体未覆盖矩阵见进度及本批report；待Astra独立审查，不勾D完成，不接管或重试受阻LSP独立审查。

27.1异常兼容补充：上下文溢出判据和可学习窗口上限由纯模块` sdk_errors.py`共享正则，worker仅传布尔值与受原有范围约束的数字；agent保留原有压缩/窗口学习决策，不回传供应商错误正文。旧合成/custom异常仍沿用原匹配路径。收到停止时已观察usage保留下界，即使终态帧紧随其后也不得升格complete。


### D10 审查修正：取消接收点与清理失败（2026-11-17）

SDK Exchange成功收尾后再次核对父控制；存在主异常时保留主异常。request_attempt在method返回后、report成功赋值前核对停止；若停止则撤回本次追加的原生历史，保留usage下界和failed_or_interrupted。该检查是本地接受响应的顺序点，其后的取消归后续执行门禁；不再在成功report之后检查停止而制造returned与抛错冲突。清理unknown附在主异常时禁止provider内部retry、两类cache fallback和agent transient/overflow救援重发，原异常及元数据向上传递。相关双provider清理窗口及503/400清理失败回归已加入；真实tool分片取消采用原独立probe复验，待复核裁定。

## 28. E 首批：分层上下文与原生历史（2026-11-17，待审）

仅原E第1/4/5项；最小方案、实际调用者、provider请求形态、数据兼容/回退和余项见[实施矩阵](architecture-e-acceptance.md)。稳定rules/project与volatile task/evidence/recall分段，缓存断点只覆盖稳定段；任务变化不改变稳定段字节，模式/模型/项目配置等真实变更继续刷新。Ledger引用与assistant声称分开，不授予新权限。原生列表接口接通瘦身、compact替换、模型切换及会话保存恢复；新存盘保留图片和协议扩展字段，摘要仍走原transcript。没有统一有损消息模型，没有实现压缩前后程序核验、事件隔离或Dreaming重构，不自签E/D/总验收。D10接受前回滚与cleanup unknown禁retry/fallback/agent救援保留。


## 29. E2/3 压缩核验与验证引用（2026-11-17，待 Astra 审阅）

设计先行协议 `/var/tmp/feiyu-stage-e-compaction-20261117/protocol.md`，实际入口、事务接受点、来源边界、兼容和回退见[E实施矩阵](architecture-e-acceptance.md)“E2/3 压缩事务实施”。`feiyu/compaction.py`小模块复用TaskState/Ledger/native_history，不建立第二任务真源。所有重摘要路径在`agent.compact`捕获、核对、补可信事实，再经候选原子session保存接受；单纯工具输出折叠仍是原小接口。程序块完整性由程序检查，模型“完整/测试通过”只在assistant_claim字段；验证记录按ID消费并重核owner、代码与持久日志。已发生summary费用保留，unknown不可变passed；取消、模型或关键保存失败不留下半替换历史。遵守D10接受前回滚和cleanup unknown禁重试，不重构其语义。

摘要沿用整段历史被替换的明确有损策略，不借统一转换声称图片/推理保真；普通原生保存恢复仍保真。无schema/config迁移、依赖或版本变化。仅此块预留source_kind和verification_refs，E6/7、全链路来源和Dreaming未做；E/D及任务书总验收不代签。


### E2/3审查修正：摘要错误与首条原生历史（2026-11-17）

摘要模型异常带sdk_cleanup_error时必须原样传播，不能作为可忽略的普通摘要失败继续主模型请求。session.save的空历史判断改为无非system消息，而非messages长度<=1：Anthropic的system独立于messages，单user就是应持久化的原历史。压缩仍先保存原历史、再建立备份、再保存候选，不吞备份文件缺失后冒险继续。空历史/system-only仍跳过，实际非空对话从首条即可保存。原失败回滚、预算累计及接受顺序不变。

## 30. E6/7 运行事实和隔离路由（2026-11-18，交 Astra 审阅）

先行契约及证据 `/var/tmp/feiyu-stage-e-events-20261118/protocol.md`。events.Route显式持有sink、session_id/task_id/run_id、锁与seq；send的运行装饰器创建路由，准入TaskState后绑定最终归属，finally关闭。每次send新run；恢复继续同session/task，previous_state保留。关闭后旧上下文只会丢事件，不查询新run。运行外配置命令的失效通知有独立单事实run，归属来自agent自身；不借其他agent的当前route。install/clear只改当前ContextVar，paused/capturing用token退出恢复，保留斜杠命令最高note等级。无全局sink回退。

实际路径：CLI/serve主线程send→Executor；只读批量events.submit为每个worker单独copy_context，包含原route和取消/SDK上下文；子调查同步在该worker内，显式注入父execution回调。jobs monitor不生产本批UI事件，继续写自己的持久收据；余额线程直接回调serve状态快照、model_list和reader发送原有控制协议，不借事件sink或冒充执行事实。run关闭不等于取消后台job；本批execution_end指调用边界，job仍可能running，最终收据仍是真源。

唯一生产者：Executor的execution_start/end经agent桥接trace和前端；Ledger.invalidate与消费时_recheck失效产生verification_invalidated；send在checkpoint和session.save后产生task_stopped/run_end，准入checkpoint后产生task_resumed。source_kind与verification_refs仅为事实接缝，不实现E8来源链。记录operation_id与旧call_id关联。前端投递异常只在events边界降级，TaskStore/会话关键异常继续传播，保存失败不发送成功run_end；事件不能授权执行。

旧tool_start/result保留UI唯一生产者：它们表示确认前提案卡片和给人看的结果，非execution_start/end事实。新事实不生成第二套工具卡片。CLI runtime_event和Desktop handle映射停止/恢复/失效为提示，CLI简短显示执行边界，Desktop更新原工具卡片pending文字（不新增第二卡片），执行细节沿用既有工具呈现；旧客户端忽略新kind，旧字段和顺序不改，seq/归属为增量字段。其余ui文本/thinking/hook/plan仍走原入口，在run内带归属；不重写全部UI。

无schema/config/依赖/版本变化。回退先停请求和writer，备份session/journal，只撤本批events路由、事件桥接及呈现差量，不撤R1/E2/3/D10或既有修改；旧客户端可先继续使用。新客户端不依赖诊断事件重建任务，不保证投递可靠、跨进程事件重放或崩溃exactly-once。E8/9、D平台/SDK父硬死/受阻LSP审查限制保持，不自行验收D/E。

## 31. E8/9 来源转述（2026-11-18，实施交独立审阅）

最小契约先写 `/var/tmp/feiyu-stage-e-provenance-20261118/protocol.md`。`provenance.py`维护增量引用表（原ID、digest、source_kind、source_refs），与原生消息分开存session可选字段；不解析正文自称。send原始输入关联TaskState request ID为user_request；附加内容与工具结果external_data；子报告保持原字符串接口，用程序Report属性携带子工具引用，回注封装assistant_claim。子报告不增加写工具。新remember及Dreaming文本始终assistant_claim，引用保留原类别但不传递权限。旧会话无法确定来源的user-role消息为unknown；旧请求适配为unknown/legacy，既有历史不批量重写。正常保存、恢复、重复摘要均保持引用，摘要program_facts带程序表；model_summary仍claim。系统中的记忆改为JSON数据而非无来源笔记，模型仍可能受内容影响，不承诺语义上的完全隔离。

记忆沿用原路径、限额、删除/展示/tuple读取接口；新条目同文件JSON行含日期/文本/类别/引用，旧Markdown行读为unknown。新格式须用当前reader；回退前停writer、备份memory/session/journal/dream，再只撤本批差量，旧版只能读取备份/导出，不运行旧writer覆盖新记录。原memory写失败处理沿用，Dreaming仍读回核对。无版本、依赖、CLI/serve协议或UI改动。

Dreaming仍只选人/助手文字，不增加工具正文、图片输入；原用户首段过滤保持。会话中的已压缩摘要不因user-role变成用户授权。候选保留逐字引用、原base并增加memory来源/完整选中source/changes指纹，apply先核指纹再重新parse来源与限额、写后比较完整metadata。旧version1候选仍可读并重验引用，缺指纹不补造旧可信来源。对话“测试通过”可保留为带来源claim，不进入Ledger、不触发验收。execution_evidence不在来源表可写类别中；唯一执行证据消费仍是原Ledger.reference的ID、归属、指纹、日志重核，摘要里的历史passed不自动有效。

引用表是保守的上下文依赖集合，不声称逐句因果归因或授权凭证；ID有各自原作用域，摘要哈希不证明外部世界事实。授权、deny、沙箱、unknown/cleanup禁止重试、每轮volatile更新、D10接受点和压缩原生首user备份回滚不变。无F向量库/知识图谱/自动技能提炼/可写子代理。D平台/SDK父硬死/受阻LSP/真实模型收益限制保留。

### 27.2 Linux SDK父硬退出监管（2026-11-18本地 / 2026-11-19 UTC，实施交审）

本节替代§27的“父硬死亡无独立监管”Linux实现限制；不自行关闭U4/D或总验收。设计先记于 `/var/tmp/feiyu-sdk-parent-lifecycle/20261119T052932Z/design.md`。Linux Exchange现在启动同exe专用监管入口，监管者在全新exec、业务/SDK导入之前fork唯一SDK子进程；原私有stdin/stdout帧直接接SDK子进程，监管者不解析请求或usage。原始`--_sdk-worker`仍保留为直接协议入口，只有产品Exchange经过监管；Fake/custom接口不变。Windows/macOS保持旧路径，不扩大保证。

父独占写端的专用pipe通过pass_fds只交读端给监管者，SDK子进程关闭该读端；其他attempt不会继承写端。父SIGKILL无论发生在Popen交接、入口尚未运行、请求静默或结果收尾阶段，EOF均保持可观察；未spawn则没有SDK worker。监管者先waitpid观察自然退出，否则在EOF时SIGKILL自己尚未回收的直接子进程并waitpid，故信号目标不会因PID复用指向他人；每20ms观察，kill后的回收等待2秒，有界等待失败不写成功收据。监管者忽略SIGINT，存活父仍由RunControl取消并关闭pipe；父等待监管者3秒，失败时终止监管者且清理unknown，原主异常优先、禁止retry/cache fallback的政策不变。不能把“owner_pipe_closed”解释成父死或远端取消：正常清理也关闭同一pipe，wait_status才是实际子退出状态。

本地收据放在XDG_STATE_HOME/feiyu/sdk-lifecycle：逐层directory-fd/no-follow打开，末目录必须本uid/0700，槽文件必须本uid/0600/单硬链接普通文件。128个固定槽，每槽最多4096字节；flock从父预留跨exec交给监管者，活跃槽不覆盖，全部占用即拒绝启动。槽在释放后可复用，不是永久历史。token/槽/目录在已有pending attempt追加local_worker并先保存；收据仅有token、parent/supervisor/worker PID、source、state、wait_status、完成时间及本地原因，没有密钥/请求/响应/usage。父从已固定且锁定的fd读同token终态，SDK子进程不持有收据fd；可信范围是本用户私有存储和产品监管者，不防御同uid恶意篡改。写入truncate/write/fsync，读到中间态、损坏、丢失、复用或写入失败均不构成完成凭据；不承诺掉电原子持久化，也不把可复用路径当恢复授权。

普通Linux父进程单独SIGKILL、监管者存活可调度、直接SDK子进程可杀且本地I/O正常时，保证本地SDK子进程被终止并回收，有成功收据可核对。监管者退出后由存活父或OS init/subreaper回收；探针使用自身subreaper并断言实际waitpid成功，不依赖容器PID1行为。任意逃逸后代、内核不可中断、监管者同时死亡/被杀、系统掉电不在保证内。没有新增通用进程树框架或远端撤销承诺。SDK协议和父历史接受点保持§27.1/F1/F2；父死前尚未持久化的部分usage仍未知，绝不补造。

恢复完全不消费收据来结束请求：无父账本完成凭据仍pending/unknown，原额度/截止不补、不重放；本地reaped也不能证明远端已取消或免费。缺失收据同样保守。无schema/config/依赖/版本迁移，仅可选attempt字段和独立有界文件。回退先停止请求和writer、等待监管者退出，备份完整journal/session及仍需核对的槽；只撤本批差量，不用旧writer清除pending/unknown。已复用收据不可恢复为历史证明。此次产品差量使旧最终冻结包及源码全量证据不能代表当前字节，旧正式归档原位保留；新批结果见progress/report，后续再更新正式留存。


续作核验（2026-11-19，交Astra新独立审查）：原摘要未包含后完成全量，已逐个核对内部result/log。3.14全量1854/20skip/1834实际通过、exit0；3.10原全量240秒超时为-9，保留失败，不算通过。本次仅补3.10缺失全套覆盖：66模块分两批，分别796/1skip和1058/19skip，均内部exit0，合计1854/20skip/1834实际通过，不称一次全量运行。77项双版、最终4项双版与冻结SDK硬死smoke已完成且源码匹配，未重复。3.14全量开始早于最后fixture finally修订，该差量由最终4项/冻结smoke单列覆盖。

报告 `/var/tmp/feiyu-sdk-parent-lifecycle/20261119T052932Z/report.md` 已补齐，权威命令/结果/指纹在其resumed/；根旧摘要保留为中途快照。续作首次脱离会话启动未产出result，保留日志，新目录附着运行完成。未改产品/tests/build/版本；仅本设计/progress/交付矩阵追加事实，中英README现有Linux实施待审说明已一致无需重复修改。当前无本批匹配SDK进程，97个历史日志PID均已不存在，未发清理信号。旧E89/final-package当前源码及冻结匹配声明只适用当时快照，旧归档不改、新证据后续留存。普通Linux监管者存活且直接子可杀范围不扩大；Windows后续、远端撤销不保证；unknown不重放不补预算。保留HEAD d82d943、未发布0.87.0及全部继承修改，不接管受阻LSP审查，不代签U4/D/总任务书。

### U6 durable native loopback protocol (2026-11-19, implementation handoff)

The measured native product execution path now has an optional durable receipt view. One parent Controller owns reservation, accounting and absolute deadlines across observations, helpers and retries; legacy Ledger accounting is bypassed in this path. An observation starts durably before the worker, each physical SDK call reserves durably before dispatch, and real returned facts save before late-stop reporting. Actual native requests bind to measured arm/source and retain native SDK receipts; OpenAI raw SSE and Anthropic message_stop semantics are unchanged. Resume never replenishes or replays unknown/started work and failed resume poisons its handle.

中文：只接development/repeat=0小规模合成loopback，保留恢复题agent_failure、全快照混杂及尚缺完整schedule/holdout/repeats/严格聚合出口。两供应商原生SDK均受同一父预算；caller合成批准不等于本会话费用授权。真实credentials/HTTPS/账单/收益、恶意host和完整跨文件事务仍缺；live继续拒绝。协议/迁移回退详见architecture-evaluation末节，独立审查入口在 `/var/tmp/feiyu-eval-durable-sdk-20261119/report.md`。不验收U6/D/任务书，不改产品包/版本、不发布。
