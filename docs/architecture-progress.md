# 框架演进进度与交接

日期：2026-11-15。执行角色：设计执行代理（gpt-6.1-sol high），架构与验收负责人：Astra。
**当前 A 已由 Astra 审阅；B 已实现、待 Astra 审查；C—E 未实现、未验收。** B 的最终证据见本文末尾；前面的基线和设计描述保留其历史时点。B 勾选仅代表实现交付，不代表 Astra 已验收。F 不执行。

## 仓库与约定

- 实际项目 `/home/Feiyu/AI_Agent/feiyu-agent`；初始 `git status --short` 无输出，`git diff --stat` 无输出，分支 main。
- HEAD `d82d943e64dcf4129e5bc44f4798abff6949da83`。0.84.5，版本真源 `feiyu/__init__.py`，pyproject dynamic 读取；desktop/package.json 同为 0.84.5，HEAD 已同步其余桌面版本。
- 完整读取用户附件任务书，并原样复制 `architecture-evolution-taskbook.md`。已读 `/home/Feiyu/AGENTS.md`（界面参考、本次无 UI 改动），其余根/祖先无匹配 AGENTS；仓库未发现嵌套 AGENTS/CLAUDE，`docs/` 无附加约定。
- CLAUDE.md 按相关章节读取：结构/硬约定、测试/评测、上下文、权限、todo/plan、子调查、并行、中断/协议配对、trace、verify/hooks、memory、沙箱、Watcher、jobs、history；结合当前源码而非历史文字判断。旧章节的单会话/平台描述已落后于代码。
- 阶段 A 仅设计文档，由 Astra 决定不单独发版（并非用户原话），不改版本、不改 README，不提交/推送/发布，不引依赖，不启动子代理。
- 关联研究报告：仓库按 `*research*`、附件目录按 `*research*`、`/home/Feiyu/feiyu-agent-architecture-research-2026-11-15.md` 未找到；未广泛遍历用户私人目录。未阅读原论文，方案为源码核查后的工程判断。

## 环境证据

| 项目 | 本次结果 |
|---|---|
| `.venv/bin/python` | Python 3.14.10，GCC 16.2.1，解释器 `/home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python` |
| 依赖配置 | Python >=3.10；anthropic>=1.5、pillow>=9、prompt_toolkit>=3.0；可选 openai>=3.14 |
| 已安装包 metadata | anthropic 2.8.0，pillow 13.0.0，prompt_toolkit 3.0.53，openai 3.51.0 |
| metadata 探测阻碍 | 首次将 setuptools 一并查询抛 PackageNotFoundError；改为只查运行依赖成功。未安装/升级任何包 |
| 其他解释器 | `command -v python3.10` 无输出、exit 1；`.venv/bin/python3.10` 不存在。python3.11 可定位但未装环境/跑测试；Python 3.10 实际运行待补 |
| Node/npm | node v26.13.1，npm 12.2.2；desktop 要求 Node>=22 |
| bwrap | `sandbox.available()` 实际探测 True，真实沙箱用例执行（不是全部 skip） |
| CI 约定（只读配置，未触发） | `.github/workflows/desktop-linux.yml` Python 3.10/3.12/3.14；desktop npm test、backend build、build、smoke/verify-trust 与打包测试 |

版本查询精确命令：

```sh
.venv/bin/python -c 'import sys; print(sys.version); print(sys.executable)'
.venv/bin/python -c 'import importlib.metadata as m; print({p:m.version(p) for p in ("anthropic","pillow","prompt_toolkit","openai")})'
node --version
npm --version
command -v python3.10 python3.11 python3 node npm uv
```

## 测试证据及限制

Python 通过外置 runner 以 `subprocess.Popen(..., start_new_session=True)` 启动，240 秒限时，超时 TERM 后 5 秒再 KILL 整组。本次未触发超时。runner 使用显式环境白名单，在 import 前设 HOME/XDG，不继承任何模型密钥、代理、Shell 初始化或真实用户配置。不运行 evals/真实 provider 请求，不复制真实 models.json/history。

首次实际命令：

```sh
.venv/bin/python /tmp/feiyu-architecture-baseline/run.py
# runner 内 argv（cwd 为项目根）：
/home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest discover -s tests -t . -v
```

首次 env 精确键值：

```text
HOME=/tmp/feiyu-architecture-baseline/home
XDG_CONFIG_HOME=/tmp/feiyu-architecture-baseline/config
XDG_STATE_HOME=/tmp/feiyu-architecture-baseline/state
XDG_CACHE_HOME=/tmp/feiyu-architecture-baseline/cache
XDG_DATA_HOME=/tmp/feiyu-architecture-baseline/data
PATH=/usr/bin:/bin
LANG=C.UTF-8
SHELL=/bin/bash
PYTHONDONTWRITEBYTECODE=1
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL=/dev/null
```

结果：1572 tests / 46.328s（runner 46.72s），exit 1，failures=1，skipped=19。唯一失败：`tests.test_sandbox.TestConfinement.test_写工作区外被挡`，期望 Read-only file system，实际 No such file or directory。源码 `sandbox.wrap` 的 `--tmpfs /tmp` 遮住隔离 HOME，`tests/test_sandbox.py` 的用例假定 HOME 可见于只读根挂载；未发现越界写入，属于本次隔离环境布局与断言条件冲突，不据此认定产品回归。首次证据不删除。

重跑：外置 `/tmp/feiyu-architecture-baseline/run-var-tmp.py` 与首 runner 同逻辑，只将隔离 base 改为 `/var/tmp/feiyu-architecture-baseline`，每个目录 `mkdir(parents=True,exist_ok=True)`；env 上述 HOME/XDG 五项同步换为 `/var/tmp`，其他键和 argv、cwd、限时不变。精确启动命令：

```sh
.venv/bin/python /tmp/feiyu-architecture-baseline/run-var-tmp.py
```

重跑结果：1572 tests / 45.253s（runner 45.55s），exit 0，OK (skipped=19)，实际通过 1553 项、无失败。未修改生产代码或测试断言。测试期间仅新增/编辑这次 docs 文档；没有新的代码指纹机制，不能据此称 B 的失效策略已验证。

19 个跳过的覆盖缺口：SWE-bench hard 缓存 6，pyright/LSP 10，历史 TBench 基线 1，harbor 题面缓存 1，Windows/Git Bash 运行 1。它们不是通过，没有下载数据集或安装 LSP 来消除 skip。

桌面基线（cwd `desktop/`），两条均 exit 0：

```sh
env -i HOME=/tmp/feiyu-architecture-baseline/home XDG_CONFIG_HOME=/tmp/feiyu-architecture-baseline/config XDG_STATE_HOME=/tmp/feiyu-architecture-baseline/state XDG_CACHE_HOME=/tmp/feiyu-architecture-baseline/cache PATH=/usr/bin:/bin LANG=C.UTF-8 npm test
env -i HOME=/tmp/feiyu-architecture-baseline/home XDG_CONFIG_HOME=/tmp/feiyu-architecture-baseline/config XDG_STATE_HOME=/tmp/feiyu-architecture-baseline/state XDG_CACHE_HOME=/tmp/feiyu-architecture-baseline/cache PATH=/usr/bin:/bin LANG=C.UTF-8 npm run build
```

Node 9/9，通过，0 skipped，约 343ms；build 成功。未改桌面产品，此次未启动 Electron/真实 UI 集成、backend 打包或发行构建，不能将 HEAD 提交说明中的既往集成通过当作本次运行。Python 3.10、本机以外平台与真实模型收益均未验证。

## 设计交接要点

详见 `architecture-evolution.md` 第 1 节全部核心路径核查，第 2—6 节所有权/调用图/数据与迁移，第 7 节小步计划/必要回归和待授权评测模板。当前 0.84.5 的权限分段、项目 verify 独立信任和 DNS/连接检查已实现，不能重复开发或弱化。

建议先 B（记录与保守指纹），再 C 的机械提取与安全收紧分别实施，再 D 任务 journal/恢复，最后 E 历史接口和事件隔离。不要先重构 runtime.py 或统一 provider 消息格式。Astra 待裁决：默认指纹范围/扫描预算、hooks 沙箱及 MCP readOnlyHint 收紧兼容行为、task sidecar 单 writer/持久化失败策略、多轮 task 归属规则。无需因研究报告缺失停止源码设计。

付费评测未运行。现有 `evals.run._isolate` 会从调用环境配置目录复制模型清单，并设置 FEIYU_TRUST_OUTSIDE=1；后续必须先准备隔离评测配置，标明其与产品默认策略差异。题目/保留集和四组对照在设计第 7 节，命令模板未执行，收益不可验收。

## 任务书逐项跟踪（全部待 Astra 验收）

以下保留原任务条目。A 已采集证据不代表已由主代理验收；B 的接受决定和 C 的实现证据见本文末尾；勾选仅表示实现，D/E 仍未实施。
### A. 核对现状，建立基线

- [x] 保存当前 HEAD、工作区差异摘要、版本、解释器和依赖环境，避免输出密钥。
- [x] 核对本任务书所指能力是否已实现或已修正，已完成部分复用，不重复开发。
- [x] 运行适用的现有检查，区分产品失败、已有失败和环境受限。
- [x] 在 `docs/` 建立简短设计记录，写明状态所有权、兼容方式、模块边界、必要取舍和迁移顺序。
- [x] 建立实施检查表，后续阶段完成时更新结果与证据。

验收：有可复查的基线和设计记录，能解释为什么需要后续每项改动。读取现有 benchmark 结果可以辅助定位，不得冒充本次运行。

### B. 验证记录与失效——第一批实现

- [x] 基于已有复现、verify 和 hooks，增加机器可读的验证记录。
- [x] 至少保存：验证 ID、任务 ID、命令、cwd、开始/结束时间、退出码、超时/取消、日志引用、代码状态标识、基线/修改后类别。
- [x] 验证状态区分：通过、失败、未运行、已过期、环境受阻。
- [x] 文件修改后让旧验证结论失效，包括编辑工具、Shell、MCP 或外部修改等相关路径。无法准确追踪时，保守失效或在使用结论前重新核验。
- [x] 不单独用 Git HEAD 表示代码状态；必须考虑未提交及未跟踪文件、验证相关配置和工作目录变化。
- [x] 对大仓库控制指纹计算开销；记录失效策略及其覆盖边界，不能声称完整掌握动态依赖。
- [x] 保存并恢复验证记录；恢复时重新检查工作区状态，不能直接沿用旧“通过”。
- [x] 结束代码任务时，展示验证范围和未验证原因。无自动测试的任务可以结束，但不能宣称已验证。
- [x] 闲聊、只读问答等无需代码验收的任务保持自然结束。

必要回归：验证通过后再修改、验证期间发生修改、命令失败/超时/取消、原有失败基线、会话恢复后文件变化、状态未知。验证期间版本变化时不得标记为最新状态通过。

验收：验证结论能追到真实执行和对应代码状态；后续改动不会继续显示“当前已通过”。

### C. 统一工具执行入口（实现勾选，待 Astra 验收）

- [x] 从现有 `_gate()`、`_pre_tool()`、串并行执行和 `Toolbox.run()` 提取最小执行器，保留兼容入口。
- [x] 统一顺序：参数检查 → 授权 → 执行前记录 → 隔离执行 → 结果归一化 → 状态更新。
- [x] hooks、自动 verify、后台命令和 MCP 的相关执行路径纳入一致的权限与信任规则；避免自动命令形成绕行入口。
- [x] 收拢工具元信息：schema、作用范围、读写/网络性质、并发类别、重试语义、输出预算。保留现有安全默认值。
- [x] 元信息是调度依据，不能代替执行隔离。MCP 自报只读不能自动取得信任。
- [x] 在现有 `ToolResult` 上渐进增加可选机器字段：错误码、退出码、耗时、截断、产物引用、修改路径和来源类别。
- [x] 保留字符串内容、图片、摘要与详情的现有兼容，不让前端处理内部实现细节。
- [x] 保持只读并行、混合写入保守串行；没有资源隔离证据时不扩大并行范围。
- [x] 所有工具调用，包括错误、中断和拒绝，都有且只有一个协议结果与其配对。

必要回归：串并行等价性、拒绝不执行、确认范围、参数错误、副作用不被自动重试、输出截断、图片传递、后台命令、取消及调用结果配对。

验收：相同行为没有因提取而改变；所有适用入口确实复用检查，测试不能只覆盖新增包装函数。

### D. 任务状态与恢复

- [ ] 在 session/progress 基础上增加 `schema_version`、`session_id`、`task_id` 和明确工作区标识。
- [ ] 保存用户原始要求与后续修订引用、目标、约束、验收项、待办、预算消耗和验证引用。
- [ ] 区分运行状态与任务结果：等待用户/中断/预算停止等，不混同于完成/部分完成/无法验证。
- [ ] 任务状态按会话/任务隔离；同工作区多个会话互不覆盖。工作区进度如继续保留，应是明确选定任务的视图。
- [ ] 副作用执行前保存准备状态，完成后保存结果；崩溃窗口中的操作标为“结果未知”。
- [ ] 恢复时先核对当前文件、Git、进程或可查询外部状态；未知操作不能盲目重跑。
- [ ] 调用 ID 仅用于关联。对任意 Shell 和外部写入，不宣称能实现恰好一次执行。
- [ ] 关键持久化失败应显式处理；不得套用诊断日志“失败全部忽略”的语义。
- [ ] 保留旧会话可读；新格式按需迁移或读取适配，不批量重写真实用户历史。
- [ ] 统一父任务总预算、截止时间和取消传播，覆盖 helper、子 Agent、reviewer 与后台任务；安全处理仍需收尾的进程。

必要回归：写前、写后记录前崩溃；重启后状态变化；取消传播；预算累计；损坏快照；旧格式读取；同工作区多会话；恢复不会扩大授权。

验收：可解释地恢复到安全边界，不重复未知副作用，不丢未完成验收项，不跨会话串进度。

### E. 上下文与前端边界整理

- [ ] 上下文分清稳定规则、项目事实、任务状态、近期证据和按需历史。
- [ ] 压缩后用程序核对目标/约束引用、未完成验收项、未配对调用、未知操作及运行中 job。
- [ ] 摘要引用验证记录，不能把助手声称的结果升级为执行事实。
- [ ] 保留缓存意识，不因每轮更新状态而频繁改写稳定前缀；对不同 provider 的行为分别验证。
- [ ] 小步封装 provider 历史访问，保留工具配对、多模态和协议必需内容，不进行有损消息转换。
- [ ] 从关键执行链路开始，让运行层产出结构化事件，CLI/Desktop 分别渲染；保留已有协议兼容。
- [ ] 事件 sink 按运行/会话隔离，避免全局 sink 在并发和嵌套执行中串流。
- [ ] 来源类别经过摘要、子 Agent 和记忆转述后仍保留，不能自动提升为用户指令。
- [ ] 保留现有 Dreaming 来源、指纹和应用前校验；当前纯对话来源不能充当测试通过证据。

必要回归：强制压缩后继续任务、约束保持、切换模型、图片与工具历史、两个会话事件隔离、终端/桌面状态一致、来源标记保留。

验收：压缩和更换前端不改变运行事实；保留已有交互能力；不要求本阶段重写全部 UI。


## 任务书完成条件（未验收）

- [ ] A—E 所需功能完成，或逐项列出具体阻碍、已完成内容和可执行下一步。
- [ ] 源码实现与设计记录一致，兼容入口和旧数据读取得到验证。
- [ ] 适用回归、构建和集成检查完成；环境受限项单列，不能算通过。
- [ ] 记录真实模型评测结果，或明确待运行配置及费用授权缺口。
- [ ] 按仓库约定同步版本和必要的中英文文档，不夹带无关格式化改动。
- [ ] 提供变更摘要、验证证据、剩余限制、迁移和回退方式；不得把用户原有改动冒充本次实现。
- [ ] 保存交接记录：当前阶段、完成清单、相关文件、精确测试命令及结果、尚未解决的问题。

## A 条目证据映射与后续接手

| A 条目 | 本次已有证据 | 状态 |
|---|---|---|
| HEAD/差异/版本/环境 | 本文仓库/环境段；基线时生产代码零差异 | 待验收 |
| 实际能力核对 | 设计第 1 节全路径表及 0.84.5 安全边界 | 待验收 |
| 适用现有检查 | 本文精确命令、首次环境失败/重跑、跳过与未运行范围 | 待验收 |
| 设计记录 | architecture-evolution.md，第 2—8 节 | 草案，待 Astra 裁决 |
| 实施检查表 | 本文逐项清单与设计第 7 节执行顺序 | 待验收 |

本次交付仅三个 docs Markdown 文件；不把生产实现、3.10 实测或真实模型收益写为完成。原始 Python 日志/runner/result 在 `/tmp/feiyu-architecture-baseline/` 与 `/var/tmp/feiyu-architecture-baseline/`，为本机临时证据、非长期归档保证；精确结果已写本文以便交接，日志不入库。接手时先核对 HEAD/差异，阅读 Astra 裁决，再从 B1 开始，不自动提交这些草案。

## 最终差异检查

`git rev-parse HEAD` 仍为 d82d943e64dcf4129e5bc44f4798abff6949da83；`git diff --stat`、`git diff --cached --stat` 无输出，生产代码/测试/依赖/版本均零修改。`git status --short` 仅三个 `?? docs/architecture-*.md`；文档尚未 stage。`git diff --check` exit 0（未跟踪文件另行检查行尾空格）。任务书副本与原附件 SHA-256 一致：a1dc663b3f7fdf40a20c2270006e65e0f33ff531361235f2820233f24b25c778。

## Astra 审阅交接

已核对基线 result.json 和关键 verify 源码接缝。采用设计第 9 节决定，进入 B。上文“待验收/请求裁决”为 A 初始提交历史，以本节和设计第 9 节为准。Python 3.10、桌面集成、真实模型收益仍未验证。

## B 实现交接（2026-11-15，0.85.0）

本节覆盖上文 A 时期“B 待实现”的历史描述。执行者为 6.1 Sol High；下一步交 Astra 审查，未启动子代理，未开始 C—E，未提交/推送/发布。初始三个未跟踪文档保留，任务书副本不改。

文件摘要：新增 `feiyu/verification.py`（有界双读内容指纹、账本、消费/恢复失效）；agent 接复现和自动 verify；Toolbox 接潜在写入通知；hooks.Outcome 增量元数据及私有持久日志；session 增量字段和兼容旧格式；CLI/serve 的沙箱设置失效；ui 只增加事实尾注渲染；新增实际入口回归 `tests/test_verification.py`，更新一条旧模拟结果断言；版本真源和桌面 package/lock、Cargo/lock、tauri 均 0.85.0，中英 README 同步。

旧 `test_全绿也要说一声` 只 mock 一个 code=0 Outcome，没有日志。新语义下应是执行退出码 0、证据不完整，不能断言当前全绿；改为明确断言这个边界，真实持久日志和正常通过由新增入口测试覆盖。早期全量出现该唯一失败，未修改产品去迎合旧布尔语义。早期取消测试出现未关闭 stdin ResourceWarning，已修复；所有中间失败都不作为最终通过证据。

测试隔离 runner：`/var/tmp/feiyu-stage-b/run-final.py`。白名单环境与 A 的 var-tmp runner 同型，HOME/XDG_CONFIG/STATE/CACHE/DATA 分别为 `/var/tmp/feiyu-stage-b/{home,config,state,cache,data}`；PATH=/usr/bin:/bin，LANG=C.UTF-8，SHELL=/bin/bash，PYTHONDONTWRITEBYTECODE=1，GIT_CONFIG_NOSYSTEM=1，GIT_CONFIG_GLOBAL=/dev/null。不继承 API key、代理或真实配置/历史。每个子进程独立进程组，240 秒上限，超时杀组；未运行付费 eval/provider 请求。

Python 3.10 定位命令 `uv python find 3.10 --no-python-downloads` 找到 `/home/Feiyu/.local/share/uv/python/cpython-3.10-linux-x86_64-gnu/bin/python3.10`（3.10.20）。以它创建 `/var/tmp/feiyu-stage-b/py310`，离线依赖解析因兼容 Pillow 缓存缺失失败；随后只在该独立 venv 安装声明依赖及可选 openai，成功，未改全局环境。3.10 Pillow 12.3.0、3.14 Pillow 13.0.0；不能声称两套依赖完全一致。pyte 0.8.2 只装在临时 venv 用于渲染夹具。

回退检查不 stash 当前工作区：`git archive HEAD` 导出到 `/var/tmp/feiyu-stage-b/rollback`，只复制新增 verification 模块与测试，让测试可导入而真实 agent/tool/hooks 接缝仍为 HEAD。隔离运行 `python -m unittest tests.test_verification -v`：20 tests，errors=17，exit 1（缺少接线/账本的 AttributeError 等），3 项纯扫描/聊天边界通过，证明入口覆盖能发现回退，不把预期失败算产品通过。

桌面：在 desktop cwd、同一白名单 HOME/XDG 下 `npm test`：9/9，0 skipped，330.959177ms，exit 0；`npm run build` exit 0。日志 `/var/tmp/feiyu-stage-b/desktop-{test,build}.log`。未运行 Electron 实机 smoke/verify-trust、backend payload、发行打包及非 Linux 平台；当前改动未声称这些通过。

TUI：复制 dev/ui_drive.py 到临时目录，只把夹具 workspace 改到 `/var/tmp/feiyu-stage-b/ui-workspace`，保留仓库 ui_runner；临时 Python3.10/pyte、白名单环境，FEIYU_UI_STATE=/var/tmp/feiyu-stage-b/ui-state，80 列 swiss。夹具 60 秒 timeout，只生成 welcome/mention/timeout，未完成发送/编辑流程，不能当作新尾注视觉验收。截图及 screens.txt 留在 `/var/tmp/feiyu-stage-b/ui-shots`；不改仓库夹具来掩盖限制。

新增尾注的直接渲染补充：`/var/tmp/feiyu-stage-b/render-status.py` 使用实际 `ui.verification_status` + `ui.notice`、pyte 80×20 屏幕和仓库 render 函数，渲染 passed/stale 与未运行两种状态到 `status-80.png`，断言关键状态存在，exit 0；已查看图像，范围、原因、日志长路径换行可读，无越界。它不替代上述尚未完成的完整交互夹具。

补充实现边界：旧/未来/损坏账本恢复会先清除当前对象的旧证据；不让同一 agent 对象切换旧会话时继承“通过”。`/undo` 控制入口在执行前保守失效；只读 Git 查询不触发代码任务尾注。超时/取消/启动受阻没有普通命令退出码时，记录 exit_code=null，而 Outcome 保留兼容哨兵；绝不把 -1 伪作真实测试退出码。

B 逐项实现映射（均待 Astra 验收，不代表审查已通过）：

| B 要求 | 实现/证据 |
|---|---|
| 机器记录与真实执行 | Ledger + 复现/自动 verify 真实 hooks 入口；22 项新回归 |
| ID/任务/命令/cwd/时间/退出/取消超时/日志/前后状态/类别 | verification record schema_version=1，session 增量字段 |
| 执行事实与有效性分开 | execution=passed/failed/not_run/environment_blocked；validity=current/stale/unknown |
| 编辑/Shell/MCP/hooks/后台/外部变更失效 | Toolbox 写前 epoch、控制入口失效、双内容扫描、消费重核、开始/结束运行中 Jobs 检查 |
| 非 HEAD 唯一标识与配置/cwd | Git index/未提交/未跟踪内容与删除、Git config、运行配置/Python metadata/Shell cwd |
| 有界性能与覆盖限制 | 20k/256MiB/5s 双读、inventory/config 限额；不可靠即 unknown，动态依赖边界明确 |
| 保存/恢复 | session 兼容增量；旧/损坏清旧证据、恢复 stale 并重核、不自动重跑未知副作用 |
| 代码结束展示范围与原因 | ui 尾注经 note 事件兼容 CLI/serve，未运行不能声称通过 |
| 闲聊/只读自然结束 | 待交代代码活动跨中断/预算/保存恢复保留，成功显示尾注后消费；纯聊天和只读 Git 边界回归 |

风险与尚未验证：日志无自动清理；扫描预算为保守默认而非性能承诺；所有软链、子模块、子目录 workspace、工作区内状态目录会阻止 current；忽略依赖/动态环境/外部服务和外部瞬时写后恢复无法完整掌握；Windows 取消进程树未实机验证；crash journal/关键任务状态持久化、完整任务生命周期属于 D 尚未实现；安全统一/沙箱迁移属于 C 尚未实现。完整交互渲染超时与 Electron/打包未运行范围如上，真实模型评测未运行，不声称收益。

回退：未自动提交，生产改动可按本次文件 diff 单独撤回；旧 session 字段继续可读，多余验证字段被旧代码忽略；保留原始三份 docs 草稿。不要用全仓库 reset/clean 删除用户现有文件。下一步由 Astra 审阅本节、设计第 10 节、verification.py、agent/hooks/tools/session 接缝及新增测试，决定 B 是否验收；审查前不推进 C—E。

### B 最终测试证据

cwd 均为 `/home/Feiyu/AI_Agent/feiyu-agent`（桌面命令除外）。两个完整套件在最后的退出码/恢复/undo/只读 Git 修正后运行：

```sh
.venv/bin/python /var/tmp/feiyu-stage-b/run-complete.py
# 子进程：.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python /var/tmp/feiyu-stage-b/run-complete.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

| 解释器 | unittest 结果 | runner 耗时 | 退出码 | 证据 |
|---|---|---|---|---|
| Python 3.14.10 | 1594 tests / 56.065s，OK，skipped=19，实际通过1575 | 56.440143796s | 0 | `/var/tmp/feiyu-stage-b/complete-314.log`、`complete-314-result.json` |
| Python 3.10.20 | 1594 tests / 57.914s，OK，skipped=19，实际通过1575 | 58.249198621s | 0 | `/var/tmp/feiyu-stage-b/complete-310.log`、`complete-310-result.json` |

之后只校正“未运行”的尾注原因，区分未配置、未信任、尚未触发，不再把已配置但未触发误报为未授权。针对此最终小改动复核实际入口和兼容路径：

```sh
.venv/bin/python /var/tmp/feiyu-stage-b/run-targeted-final.py /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest tests.test_verification tests.test_agent.TestVerifyLoop tests.test_agent.TestReproduceFirst tests.test_cli tests.test_serve tests.test_hooks tests.test_session
```

261 tests / 16.807s，OK，0 skipped，exit 0（runner 17.082158615s）；证据 `footer-final-310.log` 和 `footer-final-310-result.json`，文件后缀来自 runner 模板，**实际解释器为命令中的 3.14**，不要据文件名误认成3.10。22 项新回归已包含在两次全量和该261项中。19项全量 skip 的数据集/LSP/Windows 等外部前提未消除，未把 skip 算通过。此处不借用先前失败或中间通过运行代替最终证据。

`git diff --check` exit 0；HEAD 仍为 `d82d943e64dcf4129e5bc44f4798abff6949da83`。任务书副本 SHA-256 仍为 `a1dc663b3f7fdf40a20c2270006e65e0f33ff531361235f2820233f24b25c778`。新日志/runner 是本机 `/var/tmp` 证据，不承诺长期归档，不入库。B 的实现勾选与测试证据已就绪，Astra 审查结论仍未取得。


## B 独立审查七项修复交接（2026-11-15）

状态：Astra 已决定 B 暂不验收；本轮完成修复并提交证据供复审，**不自行宣称 B 验收通过**。C—E 继续暂停，整体任务未结束。保留初始全部未提交变更，未提交/推送/发布、未启动子代理、未付费模型、未触碰真实密钥或历史。未发布版本继续统一 0.85.0，无额外 bump。设计修订见 architecture-evolution.md 第 11 节。

新增 `tests/test_verification_review.py` 共 11 项，与原 22 项共同运行；并非仅重跑旧测试。七项对应：

| 审查项 | 实现 | 实际回归证据（新文件内 test_ 后缀） |
|---|---|---|
| 1 P1 Git 执行配置 | _git 明确禁 fsmonitor/hooks；固定命令审计 | git_executable_configuration_marker：普通真实 ls-files 先产生 marker，指纹扫描不产生 |
| 2 P1 文件读取竞态 | 安全 fd 父路径遍历 + 非阻塞不跟链打开 + fstat/身份重核 | fifo_symlink_and_parent_replacement_in_bounded_real_process：3 个真实子进程分别注入 FIFO、外部软链、父目录改名后替换外部软链；8秒硬上限，外部 inode 的 os.read 哨兵，均 unknown 且不越界读取 |
| 3 P2 会话隔离 | reset 新 task/清账本和基线、消费核归属 | cli_clear_actual_main_loop；new_session_bot_clear_and_owner_checks（serve new_session、serve /clear、CLI _bot off）；model_switch_retains_task_and_ledger |
| 4 P2 中断续接 | pending 标记成功展示后消费、session 保存恢复 | write_interrupt_save_resume_summary_then_chat：真实写工具→模型中断→session save/load/restore→仅总结→有尾注→再闲聊无尾注；budget_stop_retains_pending_until_completion |
| 5 P2 LSP 潜在写入 | symbol 失效 + Pool 活动通知 + Toolbox 保守 unknown | real_lsp_process_write_restore_and_live_server：本地真实 JSON-RPC 子进程写后恢复原文并存活，epoch 增、旧通过失效、后续 verify unknown |
| 6 P2 ignore 来源 | info/exclude/default ignore/.gitignore 摘要；外部 excludes/include 保守 unknown | ignore_sources_even_when_inventory_unchanged：仅改 info/exclude 注释指纹改变；真实 Git core.excludesFile、include.path 指向外部文件，变更前后都 unknown |
| 7 P2 执行与证据错误分离 | evidence_error 保留真实 code/execution，unknown 提示已执行日志缺失 | fsync_failure_keeps_execution_and_exit_code：true 实际执行后 fsync 注入失败仍 passed/exit=0；large_output_and_real_descendant_timeout_cancel：2MB 输出、真实 sleep/touch 后代，超时和取消后等待 2.1秒不出现晚写 marker |

测试命令（cwd 仓库根，以下 runner 是本机临时证据，不保证长期归档）：

```sh
.venv/bin/python /var/tmp/feiyu-stage-b/run-review.py .venv/bin/python -m unittest tests.test_verification_review tests.test_verification -v
.venv/bin/python /var/tmp/feiyu-stage-b/run-review.py
.venv/bin/python /var/tmp/feiyu-stage-b/run-review.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

33 项定向通过，8.943s，0 skipped；保留日志 review-targeted.log。两套最终全量包含全部新增测试：

| 解释器 | unittest 结果 | runner 耗时 | exit | 证据目录 /var/tmp/feiyu-stage-b/ |
|---|---|---|---|---|
| Python 3.14.10 | 1605 tests / 54.267s，OK，skipped=19，实际通过1586 | 54.646s | 0 | review-314.log、review-314-result.json |
| Python 3.10.20（沿用 py310） | 1605 tests / 63.731s，OK，skipped=19，实际通过1586 | 64.067s | 0 | review-310.log、review-310-result.json |

runner 使用白名单环境，与前节 HOME/XDG /var/tmp/feiyu-stage-b 隔离相同，Git 全局 /dev/null、禁系统配置，不继承 API key/代理。全量开始后没有再改产品源码或测试。新回归初稿因复用非子类 setUp 的 super() 失败，已改独立 setUp；早期结果不作为通过证据。前期复用旧 runner 曾覆写 complete-310 日志（解释器后缀判断不可靠）；旧 1594 数量仍保留在历史文字，但该旧路径不再作原始证据，本轮以正确按解释器路径分名的 review-* 为准。

回归敏感性检查不 stash/reset 工作区：复制当前 feiyu/tests 到 /var/tmp/feiyu-stage-b/review-mutation，用 mutate-review.py 在副本撤掉七类保护，cwd 必须为该副本，使用真实解释器运行 `-m unittest tests.test_verification_review -v`。11 tests / 14.234s，failures=9/errors=1、exit=1（符合预期）；FIFO 子进程触发8秒上限，marker、旧task、丢尾注、LSP epoch、相同ignore摘要、丢退出码等断言均抓到回退。结果 review-mutation.log/result.json。此为定向撤销修复的敏感性证明，不冒充完整历史版本回放。曾误从主仓库 cwd 运行同一副本检查命令，未作为回退证据；最终 result 的 cwd 已核对为副本。

桌面 cwd=desktop，在 run-review-extra.py 的同一白名单环境下执行 npm test、npm run build、npm run test:desktop。Node 9/9、0 skipped，runner 0.516s；build exit0、0.215s；集成 exit1、0.616s，Electron 启动明确报 Missing X server or $DISPLAY / platform failed to initialize。smoke 未进入产品流程，后续 verify-trust 未执行，不能计通过；本机无 Xvfb。已有 backend payload 为既往生成文件，本轮未重打包或据其声称验证当前源码。日志 review-desktop-{test,build,integration}.log 与 result.json。

尾注补充：review-render-status.py 经 Python3.10/实际 ui.verification_status + ui.notice 和 pyte 渲染 fsync 缺日志的 passed/unknown 与未运行状态；exit0，review-status-80.png/txt，已查看80列图像，中文原因及日志换行可读。这不替代前节未完成的完整TUI交互或桌面集成。

剩余限制：非 POSIX 缺安全 fd 原语时是 unknown，Windows/macOS 未实机验证；所有软链依赖、子模块、超扫描预算仍保守 unknown；include/includeIf/core.excludesFile 配置使验证失去 current（即使实际来源无害），需要后续安全来源图支持才能收窄。LSP 一旦尝试运行，本 Toolbox 保持 unknown，需新 Toolbox 恢复能力，未宣称写隔离。外部瞬时写后恢复、硬链接/挂载别名、外部服务和忽略依赖没有原子快照/完整动态追踪保证。日志无自动清理；崩溃窗口与任务 journal 仍属 D。19项外部条件 skip 继续保留，完整 TUI/桌面集成、跨平台、发行打包、真实模型收益均未覆盖。

下一步仅交 Astra 逐项复审上述实现与证据；由其决定 B 验收和 C—E 恢复推进，不自动发布。

## Astra B 复审决定与 C 启动

已逐项复查七项修复的源码接缝，并核对 Python3.14/3.10 全量 result.json。主代理独立重跑 `.venv/bin/python /var/tmp/feiyu-stage-b/run-review.py .venv/bin/python -m unittest tests.test_verification_review tests.test_verification -v`，exit 0，runner 9.090 秒，33 项通过；`git diff --check` 通过。

B 核心记录、失效、恢复与七项缺陷修复接受，允许进入 C。此结论不将 Electron 集成、完整 TUI、跨平台/打包或真实模型收益标为通过，最终整体交付仍须列出这些缺口。Windows 安全扫描降级 unknown、LSP 活动后保守 unknown、外部 include/excludes 保守 unknown 均是当前明确限制。未提交/发布。

C 按设计拆成机械入口提取与安全收紧两步实施，保留 B 回归。执行顺序是参数检查、授权、执行前记录、隔离执行、结果归一、状态更新；D 再提供关键 durable journal。C 的临时执行记录不得宣称已具备崩溃恢复保证。

## C 实现交接（2026-11-15，0.86.0，待 Astra 审阅）

仅实施 C，未启动子代理、未付费评测、未提交/推送/发布。HEAD 仍为 d82d943e64dcf4129e5bc44f4798abff6949da83；全部既有 A/B 修改保留。C 实现勾选不代表自行验收，由 Astra 审阅决定；D/E 未勾选。初始设计和早期暂停说明是历史状态，以 B 复审决定及本节为当前状态。

源码分工与兼容行为详见 architecture-evolution.md 第 12 节。新增 execution.py（ToolSpec/Executor）、tests/test_execution.py；修改 agent/tools/hooks/subagent/sandbox 实际调用路径；七处版本同步 0.86.0，中英 README 同步纠正旧 hook 沙箱及 MCP 只读免确认说明。既有 tests/test_agent.py、test_verification.py 的 hook 替身补充隔离参数；MCP 夹具提供真实 schema；test_ask.py 与 test_mcp.py 对应明确的安全兼容变化修改断言。没有通过删除 B 测试消除失败。

13 项新增测试均通过 FakeBackend / 实际产品调用路径，不打真实模型 API：

| C 要求 | tests/test_execution.py 中的 test_ 后缀 |
|---|---|
| 参数错先拒绝，不运行串/并行 hook 或工具 | invalid_parameters_do_not_start_hooks_serial_and_parallel |
| deny 优先、不执行模型命令或其 hook、协议配对 | denied_model_does_not_start_hook_or_tool |
| 用户主动 verify 仍受 deny，来源信任不等于命令授权 | hook_deny_wins_even_for_explicit_verify |
| trusted hook 复用 sandbox.wrap/workspace/offline，禁止递归 | hook_uses_sandbox_and_offline_without_recursive_hook |
| auto 不绕过项目 verify 来源确认 | project_verify_source_not_bypassed_by_auto |
| MCP schema 校验、readOnlyHint 不授信任/只读特权/并行 | mcp_hint_still_guarded_and_serial_and_validated |
| 输出预算截断保留图片，失败副作用只尝试一次 | image_budget_record_and_no_retry |
| 模型 origin 字段不授特权 | model_origin_field_cannot_bypass_deny |
| 真后台 sleep 启动和取消，执行开始/结果记录 | background_start_cancel_actual_path |
| 只读调查实际循环执行 deny 并配对 | readonly_investigation_respects_deny |
| hook remember 只缓存完整来源/命令/cwd，换命令和新会话须重审 | hook_exact_approval_is_not_broad_allow |
| 模型执行中断，剩余调用配对，取消记录，无后续写 | cancelled_model_call_is_paired_and_recorded |
| barrier 证明真实只读并发，多图传入 provider user 图片块，混写主线程串行 | true_reads_parallel_mixed_writes_serial |

原 B 33 项及既有 agent、MCP、jobs、hooks、subagent、协议、版本同步测试包含在两版全量内。参数错误处理从 handler 容错改为 schema 前置拒绝，旧 ask_user 非数组用例因此更新为错误且不问用户。开发中的失败（hook 替身签名、缺 MCP schema、错误断言图片应在 tool.content 而非 OpenAI user 图块、未捕获预期 KeyboardInterrupt）均已修正，不作为通过证据。

验证 cwd 为仓库根；runner `/var/tmp/feiyu-stage-c/run-full.py` 使用白名单 PATH/LANG/SHELL、隔离 HOME/XDG 至 `/var/tmp/feiyu-stage-c/{home,config,state,cache,data}`，禁 Git 系统配置、全局配置 `/dev/null`，不继承密钥或代理。命令：

```sh
.venv/bin/python /var/tmp/feiyu-stage-c/run-full.py .venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python /var/tmp/feiyu-stage-c/run-full.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
.venv/bin/python /var/tmp/feiyu-stage-c/run-desktop.py
```

最终结果见下表；本机 /var/tmp 日志与 runner 不承诺长期归档，不入库。中间运行曾重复使用日志名，最终以最终 full-*.log/result.json 为准，不能据中间 targeted-* 失败日志判断最终结果。

| 检查 | 最终结果 | runner 耗时 | 证据（/var/tmp/feiyu-stage-c/） |
|---|---|---|---|
| Python 3.14.10 全量 | 1618 tests / 54.851s，OK，skipped=19，实际通过1599，exit0 | 55.2214s | full-314.log、full-314-result.json |
| Python 3.10.20 全量 | 1618 tests / 63.184s，OK，skipped=19，实际通过1599，exit0 | 63.5475s | full-310.log、full-310-result.json |
| 最后加强后的 C 13项，3.14 | 13 tests / 0.180s，OK，0 skipped，exit0 | 0.3655s | targeted-314.log、targeted-314-result.json |
| 最后加强后的 C 13项，3.10 | 13 tests / 0.172s，OK，0 skipped，exit0 | 0.3654s | targeted-310.log、targeted-310-result.json |
| desktop npm test | 9/9，0 skipped，exit0 | 0.5520s | desktop-test.log、desktop-test-result.json |
| desktop npm run build | exit0 | 0.1756s | desktop-build.log、desktop-build-result.json |
| git diff --check | exit0 | — | 本次直接运行 |

全量最后的产品改动为 reset 清空精确命令授权缓存，防止新会话沿用临时授权；两版全量均覆盖。全量之后仅加强同一测试文件的两处断言：trusted-project hook 同样受 deny；取消通过模型 job kill 工具代替直接 Job.kill。加强后的13项分别在两版解释器再次通过，产品源码未再变化。上表定向 unittest 耗时以日志实际值为准，runner 包括进程启动。

补充定向命令：

```sh
.venv/bin/python /var/tmp/feiyu-stage-c/run-targeted.py .venv/bin/python -m unittest tests.test_execution -v
.venv/bin/python /var/tmp/feiyu-stage-c/run-targeted.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_execution -v
```

回退敏感性使用 `/var/tmp/feiyu-stage-c/mutation.py`，复制 feiyu/tests 至 mutation 子目录，不 stash/reset 或覆盖主工作区。分别撤掉 prepare 参数前置校验、hooks sandbox.wrap 和 MCP hint 不信任三处保护；`-m unittest tests.test_execution -v` 13 tests，failures=2/errors=1、exit1，预期抓到参数错启动 hook、hook 绕过沙箱和 MCP 免确认回归。见 mutation.log、mutation-result.json；不是历史完整版本对照，也不是性能收益评测。

边界与未验证项：

- fresh 进程读取本轮隔离配置时 sandbox.effective 为 off（已关闭），can_cut_net=false（sandbox.json 证据）。新测试以 spy 验证受信 hook 实际进入 sandbox.wrap 且传入 workspace/offline；已有 sandbox 单测覆盖规则构造，不能据此声称本机已验证真实 bwrap 内核隔离。产品按有效配置工作，保留已有显式 off/exec wrapper 行为，不合成安全保证。
- C 未改前端流程；Node/build 已跑。Electron 集成沿用 B 已记录 Missing X server or $DISPLAY / platform failed to initialize 的环境限制，本轮未重复无效启动，不能计通过。完整 TUI、Windows/macOS、发行打包未运行。
- 保留19项数据集/LSP/Windows等外部前提 skip；B 的软链/扫描预算/LSP/外部配置 unknown、非原子快照边界不变。执行记录为进程内列表及可关闭的诊断 Trace，参数在日志中按原约定截短；没有 critical durable journal、崩溃窗口恢复保证或 exactly-once。来源和命令缓存不保存进 session。
- 命令被显式关闭的 sandbox 放行时仍不具备隔离；hooks 需要仓外写可能受阻，用户应明确配置所需边界。MCP 服务本身的外部副作用不受本地 bash 沙箱隔离，始终保守授权和串行。
- 未进行付费模型评测，不宣称成功率、成本或能力收益提高；D/E 未推进。

交 Astra：请审阅实际入口是否均经过参数/授权/执行记录/隔离与归一，尤其项目来源确认、hook 精确命令授权、MCP hint 收紧、只读调查 deny，以及 C 诊断记录与 D durable journal 的界限。全部变更仍在工作区，未提交、推送或发布。

## Astra C 审查修复与验证过程

独立审查发现四项问题，Astra 直接修复：MCP 联合类型/布尔子 schema 及校验异常归一；前置命令后的硬性权限/模式/出网重检（串行在复现之后、并行在全部 hooks 之后）；yes 不缓存；拒绝 verify 为 not_run/exit_code=null 并保留 rejected 原因。实现说明见设计第13节。新增真实入口回归包含串并行真实 hook 修改权限、单次授权、MCP schema、拒绝记录、新出网边界。

第一轮定向 execution/schema 43项通过；全量1623项两版解释器均仅失败1项：必填参数错误文案与既有兼容断言不同，已恢复原文案。随后改用两套全新且彼此独立的 HOME/XDG（/var/tmp/feiyu-stage-c-review-314 和 -310），发现旧 ProjectVerifyTests 三个用例把 marker 写到工作区外，默认真实沙箱正确阻止，造成2 error/1 failure；不是来源授权失效。改为工作区内 marker，使来源信任测试不依赖禁用隔离，并新增真实 bwrap hook 工作区内可写/外部不可写回归。未通过关闭产品沙箱迎合旧测试。

先前 C 全量配置 sandbox=off 已在交接中注明；此次补充发现说明不能以那轮测试证明默认配置全部通过。前次日志名被 runner 后续覆盖，因此失败事实在此明确保留，不冒用中间运行作最终证据。最终全量仍在运行，后续填写结果。

### Astra C 最终检查与进入 D

最终源码/测试未再修改后，两版全量均 exit0，1624项，skipped=19，实际通过1605；runner耗时3.14为54.556秒、3.10为65.453秒。命令分别为：

```sh
.venv/bin/python /var/tmp/feiyu-stage-c/run-review-314.py .venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python /var/tmp/feiyu-stage-c/run-review-310.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

精确日志/result位于 `/var/tmp/feiyu-stage-c-review-314/full-314.log`、`full-314-result.json` 和 `/var/tmp/feiyu-stage-c-review-310/full-310.log`、`full-310-result.json`。使用彼此独立HOME/XDG，新真实sandbox测试在bwrap可用时运行，未增加skip。修复后 `git diff --check` 通过。

Astra接受C核心实现及四项审查修复，允许进入D；完整桌面、跨平台、打包、真实模型收益仍保留未验证，不将其计通过。未提交/发布，版本0.86.0。

## D 实施中交接：0.87.0，未完成、未验收

本轮作为 6.1 Sol High 实现子代理独立工作，没有启动任何子代理，未提交/推送/发布，E/F 未推进。HEAD 仍 d82d943。保留 A/B/C 所有未提交改动，包括 Astra 第13节四项修复与真实 bwrap hook 回归。版本元数据统一 0.87.0，中英 README 同步；没有引入依赖。

实现范围：新增 `feiyu/taskstate.py`、`tests/test_taskstate.py`，修改 agent/session/execution/progress 及 CLI/serve/UI 命令接缝。具体语义与迁移回退见设计第14节。不能将此批视为 D1 或 D2 已验收，更不能将全部 D 打勾。

本批已实现：

- 完整请求和稳定修订 UUID、独立 TaskState v1、运行状态与结果分离；连续 send 保留未完成任务与 acceptance，模型收尾不自动完成任务。
- `/task new`、`/task complete` 控制层入口（CLI/serve），显式完成后下一请求新 ID；unknown 时拒绝切换/完成。
- session + checksum/sequence task sidecar 原子 journal 快照；0600/private_dir、flush/fsync/replace/目录 fsync；POSIX 会话生命周期单 writer，线程 RLock。
- legacy/no-ID 保存改为新 ID，不覆盖旧位置；旧读取适配不批量迁移；关键异常不吞；损坏/未来 sidecar/session 显式报错并保留原件，恢复失败阻止覆盖。
- CLI/serve 的 send 与工具批次实际保存 session；副作用执行器接入 durable prepared/finished。写前失败不启动、finished 失败内存 unknown 并阻止后续，prepared 重启为 unknown，不盲重放；journal 不保存原始命令参数/环境，参数仅哈希。
- progress 仅使用当前 TaskState 派生视图，CLI 收尾不再覆盖共享旧 progress 文件。旧 progress 仍为非权威建议。

必须继续的 D 项：

1. D1：完整 Git common-dir/worktree 身份、结构化约束/验收录入、真正的任务预算字段语义、task 原请求/事实恢复进模型上下文、取消/异常最终 session 保存，以及多进程入口/旧格式更全面的重启回归。当前约束/验收只是保留字段，不能解释为空需求。
2. D2：恢复时逐操作核对当前文件/Git、可靠进程启动身份和可查询外部结果；提供明确解决 unknown 的控制入口。目前只禁止未知操作自动重放，没有安全解决流程。
3. D2：后台 job durable 生命周期（启动结束不等于 job 完成）、恢复查询及安全收尾；reset/新 session 对未知旧任务的提示/约束。
4. D2：统一父任务预算/持久化截止/取消，包括 helper、compact、reviewer、子调查与 background jobs；失败尝试和异常用量累计。现有 budget/time-budget 仍是旧语义，sidecar 记录的是 session 累计费用，不是已完成的父任务预算。
5. D2：授权范围/授权事实引用；关键写失败、未知外部结果、重启文件变化、PID 复用、取消传播与预算累计等完整故障矩阵。不能把本批8个新增测试替代这些要求。

定向首次267项（taskstate/session/agent/execution）通过；新增测试包含长原请求与修订、checksum/未来格式保留、同 session writer 冲突/不同 session 隔离、写前失败无副作用、写后 finished 失败 unknown 并阻止重跑、真实子进程 prepared 后/写后退出、任务延续与显式新建、legacy 原件保留。子进程使用 /var/tmp 独立目录、完整 HOME/XDG 隔离、subprocess 硬超时15秒；不触真实模型/密钥历史。

全量使用本轮新 runner `/var/tmp/feiyu-stage-d/run.py`，继承 C 审查的最小环境并改为 D 独立目录，不复制旧配置，不设置 sandbox=off；每个 D_RUN 独立 HOME/XDG，runner 对整套测试240秒硬超时。第一轮3.14共1632项，仅图片测试错误1项、19skip（仍假定 legacy 保存位置），已修夹具路径且保留“不落盘base64”的原断言；第一轮3.10结果及最终结果见下。期间补了 writer 已关闭拒写、损坏恢复后禁止覆盖、session写失败阻止副作用、取消保守unknown和操作序号校验，再用两套全新目录跑最终全量。

桌面：`cd desktop && npm test`，9 tests/9 pass/0 skip，exit0；`cd desktop && npm run build` exit0。一次误在仓库根运行 npm run build，ENOENT（无package.json），随后在正确desktop目录重跑通过。未运行 Electron/TUI 可视集成、跨平台、打包或付费模型评测，不能计通过。

### D 本批最终验证与 Astra 交接

最终产品源码/测试确定后，两套独立新状态目录全量均 exit0，1632项，skipped=19，实际通过1613（比 C 新增8项）。未通过 config off 隐藏沙箱差异，C 的真实 bwrap 回归包含在本轮全量中。

```sh
D_RUN=full-314-final .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=full-310-final .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

3.14 unittest耗时78.643秒、runner78.977秒；3.10 unittest79.501秒、runner79.828秒。证据分别在 `/var/tmp/feiyu-stage-d/full-314-final/full-314.log`、`full-314-result.json` 和 `/var/tmp/feiyu-stage-d/full-310-final/full-310.log`、`full-310-result.json`。首次3.10同样1632项，图片旧路径错误1项、19skip，81.858秒；失败日志保留在 full-310-1，未覆写作通过记录。最后只补文档，没有再改产品源码/测试；`git diff --check` exit0。

资源交接：本轮实现资源未覆盖任务书全部 D 条件，D1 仍有上列缺口，D2 仅完成 journal 的最初安全接缝；**D 未完成，禁止验收为完成**。后续先补 D1 结构化验收与身份/恢复接缝，再继续 D2 操作核对、后台生命周期与共享预算取消；不可推进 E/F。本轮无真实模型收益证据。

交 Astra 审阅：请优先审查 sidecar 原子 journal 的实际 CLI/serve 接入、关键写失败的阻断、legacy 旧数据保护及 TaskState 生命周期；把上述缺口作为继续实施要求，不将全量通过等同 D 需求满足。代码仍全部未提交；本轮没有启动子代理、也没有自行作架构验收。

## D1 / D2 unknown 续作交接（2026-11-16，未发布0.87.0，待 Astra 审阅）

作为实现代理核对后继续；HEAD d82d943，保留所有既有A/B/C/D未提交改动。未启动子代理、未切模型、未调用付费模型、未操作真实密钥/历史、未提交/推送/发布。没有把上次usage中断后未做的工作记为完成。

本批实现见设计第15节：安全Git common-dir/worktree身份及旧摘要兼容；TaskStore摘要+修订防陈旧覆盖；内层数据校验；约束/验收控制录入、稳定ID/原请求引用、Ledger绑定及重新核验；完整任务事实回到系统上下文；取消/异常最终task/session；reset/new/current-delete的unknown保护；新任务清除旧Executor绑定、独立hook按需建立journal；恢复逐unknown文件/Git观察与显式人工依据入口；精确授权事实引用；LSP从并行只读名单移出并纳入持久记录；诊断失败不改变事实、未知执行异常为unknown、关键写失败穿透ToolResult及复现钩子。

unknown解除为resolved/acknowledged-unknown，保留原未知执行和人工依据，不伪造成completed或无外部影响证明、不授予重跑权限。缺失文件/相同hash/PID不作外部无副作用证据；不根据PID操作恢复进程。任意外部可查询结果目前须用户通过已有只读渠道核对并记录来源，未实现通用可信结果适配器。原请求及用户核对文本原样保存，不能输入秘密；操作记录只保留必要路径、摘要和范围，不持久化原始命令/环境。

阶段边界：本轮不做父预算/统一截止/取消传播或后台job完整生命周期，不推进E/F；LSP请求finished不意味着服务停止，仍维持B活动后验证unknown。D整体仍未完成，D1和此批D2实现须由Astra审查，不能用单测通过替代架构验收。旧身份没有inode历史，兼容读取不能补造当时的身份保证。没有exactly-once或通用外部真实性保证。

验证过程（失败保留，不冒充通过）：

- resume-target-1：267项，1 failure/25 errors；发现缺失workspace测试夹具、未知异常新语义、缺失LSP标志默认值和旧验收预期。修复夹具/断言并保持安全收紧。target-2曾因夹具重复mkdir留下5 errors，随后修正。
- resume-full-314-1：1632项，仅旧并行名单symbol断言失败，19skip。未隔离LSP改为串行并持久记录，更新名单断言。
- resume-full-{314,310}-final：1643项，两版均1 failure/2 errors、19skip；cost=None误拒、删除会话替身缺保护入口、旧验收状态断言。修复后v2两版全量通过，但之后增加独立hook按需journal及新任务绑定回归，故v2不作为最终源码证据。
- 独立新状态resume-hooks-target：60项2 failures，原两个启动异常测试假定直接shell，但默认bwrap开启。局部选择直接shell路径测试取消/缺shell分支，未关闭产品或全量沙箱；真实bwrap回归保留。resume-isolated-target-final随后61项通过，5.892s，0skip。
- resume-full-{314,310}-v3：1644项，两版各1 error/19skip；原B全局os.fsync注入同时打中D关键journal，命令正确未启动。将B故障注入限定hooks模块日志用os代理，保留原execution/exit_code/unknown/evidence_error断言；D关键持久化故障断言不删除。

最终源码/测试确定后新状态v4结果下补。所有run目录都使用本轮runner白名单环境，各自全新HOME/XDG，不复制旧配置、不设置sandbox=off。tests/test_execution真实bwrap工作区内可写/外部不可写回归保留在全量。新增回归实际进入CLI _run_turn、serve handle_prompt、task控制、真实验证hook与session restore；旧真实子进程崩溃前/写后恢复、writer冲突、legacy/未来格式原件保护继续保留。未将外部条件skip计作通过。

桌面在desktop目录运行npm test（9/9，0skip）及npm run build均exit0。未重试已知缺DISPLAY的Electron集成；TUI可视集成、跨平台、打包、真实模型收益未验证。git diff --check在最终交接前再核对。

### 本次续作最终验证与交 Astra

最后产品变更为独立hook按需建立TaskStore与新任务解除旧Executor绑定；最后测试变更为B日志fsync注入限定在hooks模块。此后只更新文档，最终两版全量均exit0：

| 环境 | unittest结果 | runner秒 | 日志/结果目录 |
|---|---|---|---|
| Python3.14 | 1644项，83.785s，19skip，实际通过1625 | 84.1153 | `/var/tmp/feiyu-stage-d/resume-full-314-v4/`，full-314.log / full-314-result.json |
| Python3.10 | 1644项，85.662s，19skip，实际通过1625 | 85.9804 | `/var/tmp/feiyu-stage-d/resume-full-310-v4/`，full-310.log / full-310-result.json |

```sh
D_RUN=resume-full-314-v4 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=resume-full-310-v4 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

两套env/result记录证明HOME/XDG彼此独立且新建，不继承sandbox=off。额外独立真实bwrap入口回归1项、0skip、0.055s、exit0，日志 `/var/tmp/feiyu-stage-d/resume-real-bwrap-final/full-314.log`；白名单runner耗时0.2147秒。独立定向61项exit0包含新20项taskstate测试，未用全量测试内部配置顺序掩盖默认隔离差异。Node 9/9、build与最终git diff --check通过。完整桌面/TUI、跨平台、打包、付费收益均未验证。

交 Astra：请审核设计第15节与实际agent/execution/taskstate/CLI/serve接缝，尤其陈旧save、内层校验、unknown人工声明不扩大授权、LSP异步边界、prepare/finish失败以及内部hook启动前的journal。D1此批实现待审，D2仅unknown安全恢复/人工核对闭环待审；不能验收D整体，父预算/取消与后台完整生命周期必须下一批继续。没有启动Astra子代理，本实现交接供既有审查方接手，不冒称已通过架构审查。版本仍未发布0.87.0，所有改动未提交。

## D 中期审查修复中

独立审查发现P1独立hook新任务journal未被session指针引用、P2 local_path缺少包含性校验、P2最终checkpoint异常跳过退出清理。D保持未完成。Astra已直接修后两项：内层schema与observe双重拒绝绝对/父级/非规范/异常类型路径并确认包含性；_finish使用finally逐项清理LSP/MCP/shell/jobs，保留原checkpoint异常，单项清理失败不阻止其余清理。

新增2项针对回归；`D_RUN=astra-review-path-cleanup .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_taskstate -v`：22项，1.302s，exit0；日志 `/var/tmp/feiyu-stage-d/astra-review-path-cleanup/full-314.log`。diff检查通过。尚未在本轮重跑全量；P1活动任务指针与未决journal恢复交执行代理继续，需涵盖这两项修复跑全量。不以该定向通过验收D。

## D 中期 P1 实现交接（2026-11-16，未发布 0.87.0，未验收）

本轮实施代理直接执行，无子代理。先核对祖先 AGENTS、三份架构文档末尾及 `/var/tmp/feiyu-d-review/repro.py`、`evidence.txt`，并核对 CLAUDE 相关约定。保留原有 A/B/C/D 未提交文件、Astra `local_path` schema/observe 包含性和 `_finish` finally 保留原异常修复，没有改动 schema.py，也未替换 `_finish` 的实现及其两项回归。

实现范围：`taskstate.py` 加版本/身份/校验和保护的 durable active 指针、同 session 全 journal 验证与未决集合；`agent.py` 在 new/send/独立 hook 前激活，恢复先于模型选择，支持 pending/select，所有任务的未知操作共同阻断；`session.py` 发现没有模型消息/backend/session JSON 的 journal 恢复入口；CLI complete 补 session 级 guard。具体崩溃窗口见设计第16节。未对用户历史批量改写，未提交/推送/发布，未触真实密钥或付费模型。

新增6项 P1 回归，原22项 taskstate（含两P2）保留，总28项：

- `test_isolated_hook_crashes_restart_via_session_and_serve`：两套白名单 HOME/XDG，各用独立真实子进程。在 old 场景先 FakeBackend send、真实 CLI `_task('new')`，在 empty 场景完全无 backend/消息/session JSON；实际 hooks.run 命令 `printf effect >> marker` 后、finish 前 `os._exit(73)`。另一个全新子进程经真实 session listing/load 默认恢复发现、Server.open_session/agent.restore 恢复；断言旧 JSON 确实还引用 old task、恢复选中 new task、operation=unknown、marker 恰为一次 effect、new_task 拒绝。每进程25秒硬超时，无自动重放。恢复子进程仅将 use_model 选择替为已有 FakeBackend，session/serve/restore/journal及真实命令不替换；没有把完整交互CLI或stdio服务主循环称为端到端覆盖。
- `test_pointer_failure_prevents_hook_even_without_backend`：只向 active.json 原子写注入 PersistenceError，sidecar 本身可写，断言 hooks.run 未调用、marker 不存在，剩余空 sidecar 仍能通过 session.load 发现。
- `test_pointer_corruption_future_missing_and_escape_preserve_originals`：损坏 JSON、未来版本、重新计算正确 checksum 但 task ID 越界/引用缺失均拒绝且原件不变；缺失 active 兼容加载。
- `test_multiple_pending_selection_does_not_bypass_guard_or_rewrite_history`：构造两个旧 prepared，restore 不自动改写未选中的 journal；pending 列出两项，select/complete/new 均不能解除未决阻断；逐个用户 resolve 后方可解除，resolution 明确 no replay authorization。
- `test_recovery_validates_all_journals_before_rewriting_and_missing_pointer_blocks`：缺 active、选中旧无操作任务时，孤立 prepared 仍阻断；任何同 session journal 损坏使 restore 失败，全部 sidecar 原始字节保留且 guard 继续阻断。
- `test_session_directory_symlink_is_not_followed`：session 目录软链拒绝，没有在外部目录产生锁或 journal。

失败记录（保留原日志）：`p1-target-v1/full-314.log` 177项1失败，原回归要求 new_task 后 durable=None，已按新行为改为确认绑定新 TaskState；`p1-target-v2` 181项通过。`p1-target-final` 183项1失败，新测试误要求选中的恢复任务也完全不写 checkpoint，修为检查未选中历史不改写；`p1-target-final-v2/full-314.log` 183项、19.404s、0skip、exit0。没有屏蔽失败或删P2回归。

最终代码（包括 recover 关键I/O异常转 PersistenceError/blocked）后的全量，两个目录均首次新建，各自独立 HOME/XDG，runner 白名单不继承密钥/真实配置；原 runner `/var/tmp/feiyu-stage-d/run.py` 的240秒进程组超时未触发：

- Python **3.14.10**：1652项，81.388s，19skip，实际通过1633，exit0；runner81.6986s。证据 `/var/tmp/feiyu-stage-d/p1-active-final2-314/full-314.log` 和 `full-314-result.json`。
- Python **3.10.20**（`/var/tmp/feiyu-stage-b/py310/bin/python`）：1652项，92.279s，19skip，实际通过1633，exit0；runner92.5849s。证据 `/var/tmp/feiyu-stage-d/p1-active-final2-310/full-310.log` 和 `full-310-result.json`。

```sh
D_RUN=p1-active-final2-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=p1-active-final2-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

此前 `p1-active-final-314` / `p1-active-final-310` 两版1652项也通过；最后为 recover 的异常保护补强使用上述 final2 全新目录再次跑完，不拿早于最终代码的结果充最终证据。19项skip沿用原有缓存/LSP/Windows缺口，不能算通过。

桌面现有依赖下 `cd desktop && npm test && npm run build` exit0，Node9/9、0skip，build成功；未做桌面交互、完整TUI、跨平台或发行打包。最终 `git diff --check` 通过。无新依赖，未改出0.87.0。

限制及下一批：扫描只覆盖显式恢复的同 session，不提供全局跨 session 未决任务约束；任一历史journal损坏保守阻断，需人工保留备份后处理，没有自动修复/批量重写。缺 active 不声称确定最后活动任务，须用户选核对。选择/resolve 无操作执行证明、无新增重跑授权，不提供 exactly-once 或真实断电证明；外部结果与恶意目录并发置换仍无完整保证。父预算/截止/取消传播及后台job完整持久生命周期仍必须下一批继续，不推进E/F。本轮只交P1实现与验证给Astra，不自行验收D。

### Astra P1 复查及 D 剩余工作启动

已核对 activate 在 prepared/实际副作用前持久化、recover 先验证同session全部journal并维护未决集合、恢复入口早于模型选择、journal-only入口。主代理独立重跑 `D_RUN=astra-p1-recheck .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_taskstate -v`：28项、2.513s、0skip、exit0；日志 `/var/tmp/feiyu-stage-d/astra-p1-recheck/full-314.log`。diff检查通过。接受此次P1修复，D整体仍未完成。

下一批完成父预算/截止/取消和后台job/LSP生命周期：启动不等于完成、未知进程不凭PID操作、恢复不增加费用额度或授权。保留现有unknown及全部审查修复，最后对D整体验收。

## D 父模型请求账本续作交接（2026-11-16，部分实现，未发布0.87.0）

本轮按实施子代理执行，HEAD d82d943，未启动子代理、未调用 Astra/付费模型，未提交/推送/发布，未触真实密钥/历史，保留既有 A/B/C/D 及 Astra P1/P2 修复。本轮实现资源仅覆盖父模型请求账本和操作准入；**用户要求的 D 剩余整体未完成，不能交付为 D 完成**。E/F 未推进。交既有 Astra 审阅此部分及继续实施，不冒称已通过独立审查。

新增 runcontrol.py 与 test_runcontrol.py，agent/execution/providers/subagent/serve 接缝及旧测试适配，设计第17节详述。实际入口含 send、helper、compact、reviewer、子调查失败回调、Executor prepare/dispatch/invoke；预算费用已与 session 旧累计分离，未知总额 null + known_cost 下界，不将未报 usage 猜零。请求前待决写盘、finally 计已知用量；真实独立进程在待决 attempt 内 os._exit(73)，新进程恢复仍 pending/有限预算阻断、不增加额度，15秒硬超时、独立白名单 HOME/XDG。deadline 是持久 epoch + 存活进程 monotonic，显式下一 user send 只恢复取消事件。持久化异常从 helper/compact/reviewer 穿透。

测试中发现并修正的失败（日志保留）：

- control-target-1/2：持久取消挡住下一 user send，以及旧 taskstate 测试直接在取消后执行新写入；新增断言先拒绝，再经显式续聊做原 unknown 回归。
- control-target-3：290项，4 failure/1 error；旧有限预算测试预置 session cost、未知价格让预算放行的旧语义、极短deadline认为必执行一次、子调查 fake 签名不支持 control。改为实际请求增加费用、未知价格阻断，保留配对断言。
- control-new-1：6项1 failure，helper 吞关键持久化异常，已修；new-2 六项通过。
- control-target-4：296项2 failure；mock Toolbox.run 跳过内层准入检查，新增 dispatch/prepare 检查；未知价格断言改为对应真实未知原因。
- control-full-314-1/-2：serve 测试借用的 Box 无 agent，interrupt 在 fail_all 前抛异常；保留真实 Feiyu cancel，对无 agent 夹具兼容。-2 为1658项1 failure/19skip（104.014秒）；不作为通过。
- control-new-3：9项1 error，patch 了函数内部 import 的错误位置，改为 providers.build_backend。control-new-final 10项通过，0skip，0.954秒。
- control-full-{314,310}-final：两版1661项通过/19skip，97.150/107.128秒，但最后新增 legacy 适配测试及修正旧 session 总额不混任务账本，故不作为最终源码证据。最终 frozen 两版新状态结果随后填入。

D任务书逐项复核（既有实现未冒充本轮新增）：

| D要求 | 当前状态与证据 |
|---|---|
| schema/session/task/workspace | 已有 taskstate/session + Astra P1 28项保留；本批只扩 budget control_version 校验 |
| 原请求/修订/约束/验收/todo/验证/预算 | 既有结构化要求保留；新模型账本10项入口回归，SDK内部重试/部分 usage 尚不完整 |
| 运行状态与任务结果分离 | budget_stopped/deadline_stopped/interrupted 不改 unfinished；新回归覆盖预算停止 |
| 同workspace多session隔离 | 既有 TaskStore/active 测试保留，全量复跑；本批控制对象绑定 state，不引入全局账本 |
| 副作用前后与unknown | 既有 C/D journal保留；新增模型请求pending崩溃回归；异步job/LSP仍缺口 |
| 恢复观察/不盲重跑 | 既有reconcile/resolve及P1保留；新模型pending阻断有限预算；无进程可靠身份适配 |
| 调用ID只关联/不承诺exactly-once | 保持；本轮没有根据模型请求ID重试副作用 |
| 关键写失败 | 新模型请求写前失败不调用；finally保存穿透；所有process清理矩阵尚待补全 |
| 旧格式读取 | 旧budget总额存legacy字段、任务总额未知；未来control版本拒读；不批量改历史 |
| 父预算/截止/取消覆盖全部分支 | **部分**：模型请求共享账本及Executor准入；进程等待、background/LSP生命周期和完整取消未做完 |

明确下一步（不可省略后宣称完成）：

1. 完成 SDK内部重试/Anthropic流中断已知部分用量与未知余额；session未知费用跨任务恢复；运行中预算配置收紧。
2. 父取消/硬截止穿透前台Shell、hooks、MCP、LSP锁/读等待、ThreadPool、后台job；关键checkpoint失败时仍逐项清理并持久化真实终态。同步SDK没有可用立即取消能力时须继续诚实报告等待，不用daemon请求线程伪造完成。
3. job启动只记录running，独立结束/取消关联持久日志；真实启动前/写后finished前崩溃测试；Linux boot ID + /proc starttime可靠身份，PID复用不查询为原进程、不误杀；日志缺失保守unknown，非支持平台unknown。
4. LSP服务从请求完成分离：启动/存活/退出记录、初始化失败清理、父退出杀进程组；重启不明服务保守unknown并提供明确人工处理入口。
5. 补全用户指定真实进程故障矩阵与入口取消链，重新跑双Python/Node/build，交Astra整体验收。当前10项不替代该矩阵。

迁移/回退限制见设计第17节：仅所选任务按需扩展，旧 writer 会覆盖新账本，回退需备份并避免继续旧写入；不能reset/clean未提交工作区。未验证桌面交互/TUI、跨平台、打包、真实断电或付费模型收益。

### 本批冻结源码验证及交接

源码最后变更为 legacy budget 不把旧 session 总额计作新任务费用、恢复 pending 请求总额为null；最后新增 legacy适配回归。此后只改文档。独立新 HOME/XDG、不复制旧配置、不设置sandbox=off，整套240秒硬超时：

```sh
D_RUN=control-frozen-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=control-frozen-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

| 版本 | 结果 | unittest秒 / runner秒 | 证据 |
|---|---|---|---|
| 3.14 | exit0，1662项，19skip，实际通过1643 | 91.148 / 91.4903 | `/var/tmp/feiyu-stage-d/control-frozen-314/full-314.log`、`full-314-result.json` |
| 3.10 | exit0，1662项，19skip，实际通过1643 | 93.088 / 93.4007 | `/var/tmp/feiyu-stage-d/control-frozen-310/full-310.log`、`full-310-result.json` |

相对上批P1的1652项新增10项，不把19skip计通过。包含既有默认真实bwrap回归；不能据此声称新增了job/LSP真实进程矩阵。`desktop/` 内 npm test 9/9、0skip，npm run build exit0；最终git diff --check exit0。版本仍0.87.0。没有调用独立Astra，供既有审查方接手本批差异；D整体禁止验收完成。

## D 后台 job 生命周期实现交接（2026-11-16，0.87.0 未发布，待 Astra 审阅）

本批只覆盖后台 job，未改 provider 计费实现和通用 LSP/MCP/Shell 等待取消。HEAD 仍 d82d943，保留先前全部 A/B/C/D 未提交修改；没有提交、推送、发布、付费评测、真实密钥/历史访问、启动子代理或推进 E/F。D 整体仍未完成，本实现不自行验收。

采用设计第18节协议，新增 jobrunner.py，复用 TaskStore/Executor/Jobs。旧 PID-only Job 路径移除，包括 standalone Toolbox 的 background 也先建立 journal；agent 则绑定现有 task/runcontrol。命令/环境仅经私有 pipe 交付，持久记录保留参数摘要与授权关联。监管进程 READY 后持久 running/身份再放行，不再把后台启动记成 completed。监管者 WNOWAIT 固定 child PID，在回收前 KILL 受控组（含正常退出时留下的后代），wait 得真实状态，fsync 日志、收据与目录；父记录持久终态及 output_ref。恢复只读观察身份/产物后更新 journal，不用消失的 PID 或 supervisor exit 推定成功。

Linux 身份为 boot ID + /proc starttime，取消先开 pidfd、再比较身份、最后通过 fd 发 TERM 给监管者；监管者负责自身 child 组清理。Python3.10 本机构建缺少 os/signal 的 pidfd API，使用标准库 ctypes 调 libc 同名 API，无 syscall 数字猜测、无新依赖；准入也实际探测 kernel pidfd/零信号支持。非支持平台拒绝新 job，恢复身份不确定保持 unknown，不按 PID 发信号。此协议不控制主动 setsid 逃逸的后代；supervisor 自身若被外部 SIGKILL、产物损坏或日志缺失，可能仍需人工处理，不声称成功或无副作用。

running/prepared/unknown 均纳入同 session pending 与 active/new/reset 保护；所有已验证 journal 的 job 恢复进 Jobs，即使旧 session/task_ref 落后仍能 pending/select 找到。人工 resolve 拒绝仍存活的 job；非存活 unknown 的用户声明仍不是成功、无副作用证明或重跑授权。job list/status/output/kill 不增加任意写能力，绕开新增副作用 journal 准入以允许已有 job 收尾；同名 MCP 工具不享此例外，仍保留写保护。wait 循环检查 runcontrol；父 cancel 显式清理当前 task jobs，持久 deadline 交给独立监管者执行（epoch + 活进程 monotonic），重启不续期。关键 task checkpoint/terminal save 失败仍尝试所有受控清理并保留原错误与 unknown。

新增 tests/test_job_lifecycle.py：14项，真实子进程，各用独立 HOME/XDG 与18秒硬timeout，包含 prepared、spawn后记录前、running写后放行前、真实输出/receipt后终态journal保存前 os._exit 崩溃；running→failed/输出；父取消/API/wait/后代不晚写；deadline；缺日志/缺receipt；running保存失败不放行；终态和checkpoint写失败仍清理；identity mismatch 不发 signal；旧session落后指针恢复pending/select、running拒resolve及unknown状态合法kill。已有短命令/输出/进程组测试改走同一真实持久路径，不使用单测壳替代生命周期。

发现并修复的失败（不当作通过证据）：
- jobs-target-2/-3：旧测试同时起多 job 触发新 pending 保护；旧 proc.stdout 内存输出断言过期；取消在监管者 handler 安装前到达导致无收据。新增 READY 握手，测试改为真实持久输出/明确保护语义。
- jobs-lifecycle-1/-2/-3：spawn 故障注入误拦指纹辅助进程，改为仅拦 jobrunner；缺日志时存活监管者不能令操作恢复 running；无法确认终态的 kill 不得声称已成功结束。四窗口和unknown断言已修正。
- jobs-full-314-1：1675项，1failure/1error/19skip：旧执行诊断期待后台启动 completed、旧验证测试试图在 running job 时启动写钩子。改为 running→真实cancelled 及写保护断言。
- jobs-full-310-1：1675项，14failure/24error/19skip，根因为该3.10构建没有stdlib pidfd接口；增加 libc 命名 API 包装及实际可用性探测后，jobs-310-target-2：77项通过，0skip，17.205秒。
- jobs-lifecycle-5：新增旧session/保存失败/API取消等后13项通过，0skip，7.856秒；随后补第14项checkpoint清理及精确终态保存前崩溃注入，最终证据以下方冻结源码两版全量为准。

Node：独立新 HOME/XDG、不复制配置，`npm --prefix desktop test` 9/9、0skip、exit0；`npm --prefix desktop run build` exit0。证据 `/var/tmp/feiyu-stage-d/jobs-node-{test,build}/full-314.log` 和 result.json。无 UI 改动，不声称 Electron/TUI 实机验收、跨平台或发布打包通过。

Astra 审阅重点：pidfd校验/发信号竞态与libc兼容；WNOWAIT与组清理/真实wait状态；gate四窗口和finished失败unknown；恢复只观察不signal/重放；同session pending/select/resolve 和旧活动指针；合法job控制不旁路其他写保护；关键存储失败清理。日志无自动保留/容量限制，默认bwrap原回归保留。

下一批仍必须处理：通用 Shell/hooks、MCP、LSP 锁/读/初始化/退出等待取消与持久服务生命周期；SDK等待限制；provider内部retry/Anthropic fallback逐attempt与流中断partial usage、未知费用跨任务展示、运行中预算/配置收紧；全局跨session未决任务约束和恶意目录并发置换也未提供。本批不替这些缺口验收 D，不推进 E/F。

### 本批最终冻结源码全量证据

最后源码变更为 pidfd kernel/零信号探测，最后测试变更为在真实 output/receipt 已 durable、terminal journal save 之前准确 os._exit(74)。其后仅改文档。最终两版分别用全新 HOME/XDG（未复制旧配置、未设置 sandbox=off），240秒硬timeout运行：

```sh
D_RUN=jobs-frozen2-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=jobs-frozen2-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

Python3.14：exit0，1676项，19skip，实际通过1657；unittest 114.590秒 / runner 114.941秒。证据 `/var/tmp/feiyu-stage-d/jobs-frozen2-314/full-314.log`、`full-314-result.json`。

Python3.10：exit0，1676项，19skip，实际通过1657；unittest 115.826秒 / runner 116.145秒。证据 `/var/tmp/feiyu-stage-d/jobs-frozen2-310/full-310.log`、`full-310-result.json`。

相对上批1662项新增14项，19skip不计通过；默认bwrap原回归保留。早先 jobs-final / jobs-frozen 全量也通过但源码/崩溃注入随后收紧，不代替这组最终证据。Node 9/9、build exit0如上；最终 diff --check 通过，未残留 jobrunner 进程。HEAD d82d943，0.87.0未发布，所有改动保持未提交。以上仅实施验证，供 Astra 审阅本批，不是 D 整体验收。

## Astra 后台产物两项P2修复

独立审查复现日志替换仍completed、产物目录软链导致job output返回外部内容。Astra直接修复监管收据长度/摘要绑定，以及refresh/take统一安全打开、内容/类型/路径校验；unknown输出不再返回原文。新增两个真实子进程回归，包含写后替换→当前与重启unknown、目录软链→实际Toolbox.run输出不含外部fixture。

`D_RUN=astra-job-evidence-target .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_job_lifecycle tests.test_jobs tests.test_runcontrol -v`：49项、14.061s、0skip、exit0。日志在同名/var/tmp/feiyu-stage-d目录。diff检查通过；双版本全量运行中，后续记录最终结果。D整体未完成。


### Astra 修复后最终验证与裁决

两版独立全新 HOME/XDG 全量完成：Python 3.14 共1678项、19skip、exit0，unittest101.465秒；Python 3.10 共1678项、19skip、exit0，118.980秒。实际各通过1659项。命令分别为 `D_RUN=astra-job-evidence-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .` 和 `D_RUN=astra-job-evidence-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .`。完整日志和result.json保存在各D_RUN对应的 `/var/tmp/feiyu-stage-d/` 子目录。最终 `git diff --check` 通过。

Astra裁决：本次两项P2已修复并有真实进程回归；后台产物这一批可继续进入后续实现。此结论不等于D整体验收；前台等待取消、MCP/LSP生命周期、provider逐attempt与partial usage等缺口仍保留。维持0.87.0未发布、全部改动未提交；下一批先补前台Shell/hooks等待取消和清理。

## D 前台 Shell/hooks 实施交接（2026-11-16，未发布0.87.0，待 Astra 审阅）

实施子代理仅收到本brief，已读适用AGENTS/CLAUDE及任务书、设计、进度最新章节；HEAD仍d82d943，既有全部未提交修改保留。本批没有提交/推送/发布、启动子代理、调用付费模型或读取真实密钥历史，未推进E/F。用户要求版本保留0.87.0优先于CLAUDE通常bump规则。交Astra审阅，本批程序验证不等于D验收。

设计见第20节。新增processwait.py，为前台Shell与hooks共享短周期父控制检查和WNOWAIT→killpg→wait清理；不改jobs/jobrunner的收据/安全产物协议。修改tools/hooks/agent/execution/taskstate/verification接缝，保留权限、sandbox、journal、验证失效。独立hooks可显式传control；agent全部自动hook入口传当前父control。Shell先持久执行事实再抛RunStopped，verify先记unknown与真实exit_code再传播。正常退出也清理组内遗留后代；日志失败和终态保存失败均不冒充not_run。

新增 tests.test_foreground_lifecycle 9项，每个真实子用例使用全新白名单 HOME/XDG、合成workspace、18秒硬timeout，覆盖：父API取消Shell、重建control不延长deadline、Shell超时与正常exit7遗留后代、standalone hook取消/deadline、真实Pre/Post/verify入口取消、hook超时/正常退出后代、终态持久化失败仍清理并保留exit事实、prepare失败/父启动前取消/权限拒绝不执行、hook日志fsync失败保留exit7但证据unknown。检查后代PID消失/僵尸（不可继续执行）、晚写marker未出现；临时fixture退出前关闭store/LSP/jobs。显式本地合成进程测试patch sandbox.wrap为None，不读取或写真实配置；全量继续跑既有默认bwrap真实回归，未设置全局sandbox=off。旧verification测试改用真实Timer父取消，避免原communicate mock因实现改变而空转；保留大输出与真实后代检查，unknown后明确fixture人工resolve，不绕过产品未决保护。

失败尝试全部保留日志，不算通过：
- foreground-target-1：334项、6failure/1error，24.719秒。旧Shell超时文案兼容断言、删除shell状态后bwrap源缺失、communicate注入点过时、旧not_run/空exit断言及未知操作阻断下一次验证。恢复原超时提示、重建缺失状态文件，更新真实取消/unknown断言，按合成fixture明确resolve后再做第二次验证。日志失败正常退出仍保留passed/failed执行事实，证据独立unknown，保留原回归。
- foreground-new-1：41项、3failure，19.365秒。新夹具deadline两次取time微差、verify来源未授权、晚写发生在timeout之前；改同一origin、普通hook来源和晚写时序。
- foreground-target-2：358项、1failure，46.589秒。恢复control绑定新TaskState但Executor.durable还持旧对象，触发陈旧修订拒绝；修为完整绑定恢复state，未削弱陈旧写保护。
- foreground-new-final-314：9项、0skip、13.732秒、exit0；runner13.866秒；result.json已检查。随后冻结源码，最终定向/全量见下。

所有命令使用 `/var/tmp/feiyu-stage-d/run.py`，D_RUN均首次新建目录。runner仅继承白名单环境，240秒总进程组timeout；wrapper自身exit0不作为测试成功，以下均读取full-{314,310}-result.json及unittest末尾。没有付费模型收益或桌面交互验收声明。

```sh
D_RUN=foreground-target-final-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_foreground_lifecycle tests.test_tools tests.test_hooks tests.test_execution tests.test_verification tests.test_verification_review tests.test_runcontrol tests.test_job_lifecycle -q
D_RUN=foreground-target-final-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_foreground_lifecycle tests.test_tools tests.test_hooks tests.test_execution tests.test_verification tests.test_verification_review tests.test_runcontrol tests.test_job_lifecycle -q
D_RUN=foreground-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=foreground-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

无桌面源码变动，本批未重新跑Node/build或TUI。后续边界保留SDK/MCP/LSP、provider费用、前台父死亡无独立监管、逃逸进程与非Linux未实测；详细限制见设计20节。Astra需审阅进程组回收顺序、停止后真实exit与unknown分离、关键存储异常传播及既有授权/验证保护。

### 本批最终冻结源码验证

源码在上述最终定向/全量开始前冻结，之后仅补文档；以下已逐一读取result.json的内部exit_code=0及完整日志末尾：

| D_RUN | Python | unittest结果 | unittest秒 / runner秒 |
|---|---|---|---|
| foreground-target-final-314 | 3.14 | 359项、0skip、通过359 | 49.034 / 49.2541 |
| foreground-target-final-310 | 3.10 | 359项、0skip、通过359 | 50.063 / 50.2489 |
| foreground-full-314 | 3.14 | 1687项、19skip、实际通过1668 | 116.197 / 116.5214 |
| foreground-full-310 | 3.10 | 1687项、19skip、实际通过1668 | 126.602 / 126.9033 |

证据为 `/var/tmp/feiyu-stage-d/<D_RUN>/full-314.log` + `full-314-result.json`（3.14），或 `full-310.log` + `full-310-result.json`（3.10）；精确命令如上。相对1678基线新增9项，19skip不计通过，原有Astra日志替换/目录软链P2回归仍通过。240秒外层timeout未触发；全部新增子用例18秒上限未触发。最终 `git diff --check` exit0；检查进程列表无本批jobrunner、sleep30、晚写fixture遗留运行进程（僵尸不具有执行能力，非本进程子孙由系统init回收）。版本仍0.87.0、HEAD仍d82d943，全部保持未提交。上述结果是实施验证，提交给Astra审阅，不自行宣布D验收。


## Astra 前台中断两项P1修复（2026-11-16）

独立报告 `/var/tmp/feiyu-foreground-review-sol/REVIEW.md` 确认启动交接和重复中断清理两个P1。Astra直接修复processwait，设计见第21节；新增一个unittest含六个隔离真实入口子用例，保留既有九项生命周期回归。未提交/发布，版本仍0.87.0。

首次 `astra-fg-signal-target` 失败：新trace夹具错误命中前置指纹扫描的Git子进程，尚未到达目标processwait；修为严格限定Popen调用者为processwait._run。失败日志保留，不计通过。`D_RUN=astra-fg-signal-target2 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_foreground_lifecycle -q` 内部exit0，10项通过，runner19.687秒。随后加强夹具为“兜底清理之前确认产品已reap”，最终双版本全量见后续记录。


### 修复最终全量与撤销保护验证

Python 314: Ran 1688 tests in 131.069s

OK (skipped=19); 内部exit_code=0，runner=131.429秒。

Python 310: Ran 1688 tests in 139.979s

OK (skipped=19); 内部exit_code=0，runner=140.320秒。

精确命令：`D_RUN=astra-fg-signal-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .`；3.10为 `D_RUN=astra-fg-signal-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .`。完整日志和result位于各D_RUN对应目录；各1688项中19skip，实际通过1669。

隔离副本 `/var/tmp/feiyu-sigint-negative-a0uqkzfu` 仅撤销SIGINT锁存保护，运行新增单测，六子用例全部在真实SIGINT处失败（内部exit1），证明回归能捕获缺陷；当前仓库未回退。证据 `/var/tmp/feiyu-stage-d/astra-fg-signal-negative/full-314.log`。副本用例finally杀组wait兜底。3.10全量出现一条subprocess ResourceWarning，未造成测试失败；独立复核需核对是否与本修复有关。最终diff检查通过；D不验收，交独立复核两项P1。


## Astra 前台中断复核裁决与D续作

已阅读 `/var/tmp/feiyu-fg-rereview-sol/REVIEW-resumed.md`：原两项P1关闭。独立双版本探针覆盖启动交接、运行中首次取消、killpg前/wait前及实际_wait内重复SIGINT、工作线程取消；产品先回收，真实退出7保留为7，journal停止后unknown，verify记录和原handler恢复均正确。前台Shell/hooks这一批通过限定范围审查，不构成D整体验收。

3.10历史ResourceWarning仍未归属：44项定向、184项重复和原序前610项均未复现，不能据此宣称彻底排除泄漏，保留非阻断观察；若再次出现应保存创建栈与即时进程状态。续作优先LSP等待取消、初始化失败清理和持久服务生命周期；MCP/SDK/provider等其余缺口继续保留。版本0.87.0未发布、所有改动未提交。

## D LSP 等待与持久服务实施交接（2026-11-16，待 Astra 独立审阅）

HEAD d82d943，版本仍未发布0.87.0。保留全部既有A/B/C/D未提交修改；未提交/推送/发布，未启动子代理、调用付费模型、读取真实用户密钥历史，E/F未推进。适用上级AGENTS、CLAUDE、任务书、设计及进度已读；先写设计22节，再实现。processwait SIGINT锁存/WNOWAIT顺序、jobrunner输出摘要/安全路径协议及共享PipeReader/MCP源码均未修改。历史3.10 ResourceWarning仍不归属本批。

实现范围：Client/Pool 取消/有界锁与非阻塞发送/读取/初始化/直接关闭；Linux受控进程组和未reap直属进程身份；独立 prepared→serving 服务记录；异常服务unknown、正常关闭lifecycle_only completed；恢复只观察不重放/重启/向历史PID发信号；在线服务不阻断所有副作用；task select/切换/cancel及关键保存失败清理。细节及非Linux拒绝、父硬死亡/setsid/内核阻塞等边界见设计22/22.1。

新增 `tests.test_lsp_lifecycle` 最初20项，最终增至21项。每项在新HOME/XDG白名单子进程运行（合成server/workspace，无用户配置），15秒硬timeout和双层finally兜底；服务器创建真实后代。覆盖初始化无响应/错误、Pool和Client锁占用、输出无响应、stdin背压、父取消、重建RunControl保留持久deadline、退出0/7及组内后代清理、空闲取消、正常连续Toolbox symbol入口、初始化时Pool.close、service prepare/身份保存/ready保存/工具终态保存失败、恢复观察与stale identity不发信号、多任务pending/resolve以及真实task select关闭旧服务。产品清理断言在fixture兜底之前运行；pipes closed/直属进程reaped和后代无执行能力均检查。正常服务验证失效沿用并复验 `tests.test_verification_review.ReviewEntrances.test_real_lsp_process_write_restore_and_live_server`。

失败尝试与改进：
- lsp-target-first：55项、10skip、2error、内部exit1、3.688秒。旧TestClose用object.__new__跳过所有生命周期初始化，另一条用poll假对象及旧Client lambda；会导致夹具自行启动的sleep30未被该失败夹具回收（已自然退出）。替换为真实构造/关闭/显式重建Client测试，不在产品增加绕过安全身份的兼容分支。该夹具ResourceWarning与历史3.10警告不混同。
- lsp-real-first：18项、1failure、内部exit1、7.432秒。监视线程取消先关闭stdin，发送端BrokenPipe未保留父取消原因；清理后重新检查父control修复。
- lsp-target-second：92项、10skip、内部exit0、13.351秒（runner13.5643），初步验证，非最终冻结证据。
- lsp-new-strengthened：19项、0skip、内部exit0、7.623秒；lsp-new-final-314：19项、0skip、内部exit0、7.633秒；lsp-task-select：20项、0skip、内部exit0、7.771秒。后续加强持久deadline重建并冻结源码后跑最终全量。
- negative首次在隔离副本使用相对.venv路径，shell exit127未启动runner；未算负对照结果。修正为绝对解释器后，lsp-negative-cancel-fixed 在 `/var/tmp/feiyu-lsp-negative-rxm4hodj` 仅撤销Client父control检查（含异常后的检查），取消用例内部exit1、1项失败、3.376秒，报 parent stop became ordinary error；证明捕获取消退化。未stash/回退工作区。

所有正式验证使用 `/var/tmp/feiyu-stage-d/run.py`，每次唯一D_RUN、新建HOME/XDG、白名单env及240秒进程组兜底；以result.json内部exit_code及unittest末尾为准。精确命令与最终结果续记下方；早期 lsp-full-* 在增加task select接缝回归前启动，不替代冻结源码最终证据。

### LSP 补充冻结与失败夹具说明

最终为21项新增用例：额外加入空闲服务关键保存失败；TaskStore.critical_write遇PersistenceError也必须blocked，监视线程可收尾空闲服务。加强对初始化失败前尚未来得及写pids的服务器Popen对象检查，确保在fixture fallback之前已reap并关管道。

lsp-frozen2-target-314/310两次各76项、10skip、19failure，内部exit1（12.309/11.742秒）：加强Popen捕获时误将工作区指纹扫描的Git子进程也当成服务器，stdin为None引发夹具AttributeError；产品未据此判失败。限制捕获精确匹配合成服务器argv后，lsp-capture-fix-target 21项、0skip、7.970秒、内部exit0。随后将pids文件未写出时的对象清理断言也移到兜底前，再跑最终两版定向及全量。所有中间失败全量日志保留，不作为通过证据；最终D_RUN是lsp-final-*。

最终回归不触及桌面源码，未重复Node/build/TUI。保留默认sandbox的原回归；合成LSP进程未经写隔离，验证仍保守失效。Astra重点：服务准入prepare与symbol操作关联、serving与pending的区别及恢复降为unknown、多任务选择先关闭旧服务、父cancel/deadline/critical save失败的空闲和请求中清理、未reap直属child进程组安全、初始化交接及协议锁并发关闭、保存失败不冒充成功、恢复不信号/重放。不可中断内核/setsid逃逸、父硬死亡无独立监管及非Linux拒绝是明确限制；本批不等于D整体验收。


### LSP 最终冻结结果（已检查内部result及日志末尾）

```sh
D_RUN=lsp-final-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_lsp_lifecycle tests.test_taskstate tests.test_runcontrol tests.test_lsp -q
D_RUN=lsp-final-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_lsp_lifecycle tests.test_taskstate tests.test_runcontrol tests.test_lsp -q
D_RUN=lsp-final-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=lsp-final-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

| D_RUN | 项数/skip/实际通过 | unittest秒 / runner秒 | 内部exit_code |
|---|---|---|---|
| lsp-final-target-314 | 76 / 10 / 66 | 12.383 / 12.5496 | 0 |
| lsp-final-target-310 | 76 / 10 / 66 | 11.338 / 11.4460 | 0 |
| lsp-final-full-314 | 1709 / 19 / 1690 | 135.124 / 135.4614 | 0 |
| lsp-final-full-310 | 1709 / 19 / 1690 | 136.914 / 137.2003 | 0 |

最终两份全量日志均未出现ResourceWarning；不能据此排除历史未归属警告。相对1688项基线新增21项；19skip不计通过。240秒runner/15秒子夹具上限均未触发。最终源码全量覆盖原前台SIGINT、后台job日志hash/安全路径、MCP既有用例及真实symbol验证失效用例。

证据 `/var/tmp/feiyu-stage-d/<D_RUN>/full-{314,310}.log` 和 `full-{314,310}-result.json`。所有已完成本批runner（包括失败尝试）的精确命令和内部结果汇总在 [lsp-command-results.md](/var/tmp/feiyu-stage-d/lsp-command-results.md)。负对照的cwd为 `/var/tmp/feiyu-lsp-negative-rxm4hodj`，其余为工作区。

补充中间结果：lsp-frozen-full-314/310分别1708项、19skip、内部exit0、146.103/146.750秒；lsp-frozen2-full-314/310分别1709项、19skip、内部exit0、146.814/145.190秒。后者运行期间夹具修改，故只作中间结果，最终证据以lsp-final-*为准；不将当时两个定向失败归为产品失败。

迁移/回退按设计22.1：新增serving旧版本不可读，回退先关闭服务、退出writer并备份journal，仅撤销本批源码差量，不动A/B/C/D其他修改，不按旧PID盲杀、不把unknown改成功。最终git diff --check通过；检查无本批合成server/runner遗留运行进程。HEAD仍d82d943、版本仍0.87.0，全部未提交。交Astra独立审阅，不自行验收D；剩余MCP/SDK/provider及D其他缺口继续保留，E/F未启动。


## Astra 续作状态：LSP审查受阻，推进独立计费工作

LSP独立审查委派被平台以possible cybersecurity risk中止，未形成审查结论；不重试或转换执行渠道来绕过限制，LSP与D整体验收继续未完成。当前推进与该审查独立的provider重试/流中断用量及父预算记账实现，测试使用离线合成SDK响应，不调用真实模型。保留全部修改和未发布0.87.0。

## D 独立 SDK 用量与父预算实施交接（2026-11-16，待 Astra 审阅）

先写设计23节，再实现；保留全部既有未提交修改，HEAD d82d943、未发布0.87.0不变。未提交/推送/发布、未启动子代理、未调用真实/付费模型或读取用户真实密钥历史。LSP独立审查被平台中止仍未验收，本批没有执行、接管、重试审查，也未修改 LSP/进程生命周期；E/F未推进。普通全量 unittest 保留既有生命周期回归，不能替代受阻独立审查。

本批差量：providers.py 的显式 SDK 单次尝试与 retry/fallback、累计 usage 合并/异常流保留；runcontrol.py 的父准入/尝试记录/关键失败阻断/动态收紧；agent.py 的控制器创建锁、限制刷新及未知费用展示；session.py 的 unknown_cost 可选持久字段；taskstate.py 只扩展预算尝试记录校验；新增 test_sdk_accounting.py 最终17项。旧 test_providers 的529测试由“无fallback仅一次调用”改为显式 retry 总调用 RETRIES+1；旧 test_subagent 保留子费用断言，同时要求缺主 usage 的会话总额未知。未改 README/桌面/版本号，相关原有修改保留。

新增离线用例使用 Fake SDK create/stream/response，走实际 provider 方法与 Feiyu 的主 send/helper/compact/review/subagent 接缝；覆盖 retry成功/失败及有限预算未知阻断retry、两种cache fallback、异常流、仅输入/无usage/空usage、重复/累计usage、Anthropic cache与输入partial保留、双零和未知价格、首次并行helper共享父控制、恢复不补额度、SDK等待期间收紧及不放宽、动态deadline沿原起点、pending/结束保存失败阻断后续调用、跨任务和完整/journal-only恢复未知费用、同步调用返回后的取消及两种SDK构造 max_retries=0。旧RunControl十项继续覆盖主/helper/compact/reviewer/失败child、pending真实子进程崩溃恢复；其SDK完整性边界由新增测试补足，不以旧Fake计数冒充原生usage证据。

测试全部通过 `/var/tmp/feiyu-stage-d/run.py`：D_RUN唯一，新HOME/XDG、白名单env，240秒进程组timeout；检查内部result.exit_code及日志结尾，不看wrapper shell退出码。两版SDK实际均为 anthropic2.8.0/openai3.51.0；本机源码核对见设计23，Python3.10真实运行。无新依赖。

失败尝试（完整精确命令/结果另见下方命令汇总）：
- usage-first-314：81项、8failure/1error，8.532秒、内部exit1。FakeBackend继承Billing但覆盖请求方法，初版错误跳过旧counter；还误指定不存在的tests.test_cache。修为有SDK client的后端才绑定原生尝试；529断言调整显式retry，未放宽产品预算。
- usage-sdk-first：21项、2failure/18error、1.952秒、exit1。新增budget嵌套记录尚未扩展旧数字校验；测试模块直接import TestCase也导致重复发现旧十项。修字段校验和模块import；随后修 pending 写失败时尚未初始化event造成异常覆盖。
- usage-sdk-second：21项、1error、2.821秒、exit1。新测试没有聊天历史，session.save按原行为跳过，load得到journal stub；修测试建立合成历史。
- usage-target-third：146项、23error、10.853秒、exit1。旧Agentish会话适配器没有cost属性；用backend价格状态作兼容默认值，保留原接口。
- usage-final-full-314：1724项、1failure/1error、19skip、149.726秒、exit1。旧subagent金额断言未区分无主usage；另未修改的job missing-log/resolve用例出现resolved断言失败。usage-final-full-310：1724项、1error、19skip、157.954秒、exit1，仅同一旧subagent金额断言。两版同时全量及两版定向运行存在资源竞争，但不能据此认定job根因；不改生命周期代码。
- usage-subagent-job-recheck：25项、1failure、1.302秒、exit1。job独立复跑通过；临时给旧subagent测试增加parent known_cost>=.05断言错误，因为FakeSub在构造时预填历史成本、请求没有增量。去除该错误断言，保留子费用与总费用未知，实际SDK增量由新五入口用例验证。最终重新冻结后验证如下，早期通过不替代最终证据。

负对照：副本 `/var/tmp/feiyu-usage-negative-ggtkgten` 仅复制当前feiyu/tests，在副本撤去Anthropic事件usage捕获及tighten；`usage-negative-314` 两项均按预期失败（tokens0!=18、limit1!=0.000001），内部exit1，unittest0.130秒/runner0.3645秒。没有stash或回退用户工作区。命令：

```sh
# cwd=/var/tmp/feiyu-usage-negative-ggtkgten
D_RUN=usage-negative-314 /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python /var/tmp/feiyu-stage-d/run.py /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest tests.test_sdk_accounting.SDKAccounting.test_anthropic_partial_cumulative_preserves_input_and_cache tests.test_sdk_accounting.SDKAccounting.test_limit_changes_inside_sdk_wait_apply_to_next_admission -q
```

迁移、同步SDK不可即时取消、一次请求可能超支、重试策略与供应商账单边界见设计23.1。D仍未验收；Astra需独立审阅尝试边界、未知费用粘滞、累计去重、准入持久化/失败锁存、并发和恢复/收紧，不把本批回归当独立审查完成。MCP等其余D缺口和受阻LSP审查继续保留，真实模型能力/成本收益未验证。

### 最终复核补充与再次冻结

usage-refrozen-target-314/310 各408项通过（39.198/38.100秒，runner39.6245/38.3901秒），usage-refrozen-full-314/310 各1724项、19skip通过（152.958/141.564秒，runner153.4456/141.9688秒）；两份全量无前述job失败。该job偶发失败仍未归属，不宣称彻底排除。随后源码复核发现本批tighten在cost变更时重算monotonic deadline，系统时钟回拨可能延长进程内截止；修为min(原monotonic截止,新候选)。新增一项回归，最终总计16项新增SDK测试、全量1725项。3.10 refrozen全量在该修复期间运行，故以上均作为中间证据，最终以usage-clock-*为准。

clock负对照在 `/var/tmp/feiyu-usage-clock-negative-3009hn4e` 副本只撤去min保护，`usage-clock-negative-314` 一项如期失败（截止延长约1000秒），unittest0.077秒、runner0.3146秒、内部exit1。命令（cwd该副本）：

```sh
D_RUN=usage-clock-negative-314 /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python /var/tmp/feiyu-stage-d/run.py /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest tests.test_sdk_accounting.SDKAccounting.test_cost_tightening_does_not_extend_monotonic_deadline_after_clock_rollback -q
```

补充独立恢复探针 `/var/tmp/feiyu-stage-d/usage_restore_probe.py`：实际Feiyu.send产生无usage请求→new_task→关闭writer→journal-only restore→全新priced=True/cost=0后端，断言总费用仍None。白名单runner下 `usage-restore-probe-314/310` 两版均内部exit0，runner0.2647/0.2145秒；不将无backend时cost天然None当成恢复覆盖证据。精确命令：

```sh
D_RUN=usage-restore-probe-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python /var/tmp/feiyu-stage-d/usage_restore_probe.py
D_RUN=usage-restore-probe-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python /var/tmp/feiyu-stage-d/usage_restore_probe.py
```

最终冻结后定向命令与两版全量命令：

```sh
D_RUN=usage-clock-fix-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_sdk_accounting tests.test_runcontrol tests.test_providers tests.test_ask tests.test_session tests.test_taskstate tests.test_agent tests.test_parallel tests.test_subagent -q
D_RUN=usage-clock-fix-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_sdk_accounting tests.test_runcontrol tests.test_providers tests.test_ask tests.test_session tests.test_taskstate tests.test_agent tests.test_parallel tests.test_subagent -q
D_RUN=usage-clock-final-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=usage-clock-final-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
```

### 协议EOF完整性最终补充

usage-clock-fix-target-314/310各409项通过（44.457/45.846秒）；usage-clock-final-full-314/310各1725项、19skip通过（精确runner/result见命令汇总）。随后复核实际SDK发现Anthropic.get_final_message仅检查已有snapshot；正常EOF也可能缺协议结束事件。收紧完整性判断：OpenAI需finish_reason、Anthropic需message_stop，加正常返回和输入/输出字段齐全。缺结束标志保留usage但为partial。新增OpenAI表驱动EOF子用例及Anthropic完整/不完整对照一项，最终17项新增、全量1726项。此后冻结源码，只补文档；usage-terminal-*为最终证据，所有更早轮次作中间验证，不冒充最终。

第三组负对照：`/var/tmp/feiyu-usage-terminal-negative-p2s5krwt` 副本仅撤去协议终止条件，`usage-terminal-negative-314` 两项分别捕获OpenAI与Anthropic静默EOF被误标complete，内部exit1、runner0.4646秒；完整日志和精确命令见命令汇总，cwd为该副本。没有回退工作区。

最终协议冻结精确命令（cwd仓库，新D_RUN）：

```sh
D_RUN=usage-terminal-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_sdk_accounting tests.test_runcontrol tests.test_providers tests.test_ask tests.test_session tests.test_taskstate tests.test_agent tests.test_parallel tests.test_subagent -q
D_RUN=usage-terminal-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_sdk_accounting tests.test_runcontrol tests.test_providers tests.test_ask tests.test_session tests.test_taskstate tests.test_agent tests.test_parallel tests.test_subagent -q
D_RUN=usage-terminal-final-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=usage-terminal-final-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
# cwd=/var/tmp/feiyu-usage-terminal-negative-p2s5krwt
D_RUN=usage-terminal-negative-314 /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python /var/tmp/feiyu-stage-d/run.py /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest tests.test_sdk_accounting.SDKAccounting.test_partial_input_missing_and_duplicate_usage tests.test_sdk_accounting.SDKAccounting.test_anthropic_eof_without_message_stop_is_partial_even_with_usage -q
```

### 最终协议冻结结果（已核对内部result与日志）

| D_RUN | 项数 / skip / 实际通过 | unittest秒 / runner秒 | 内部exit_code |
|---|---|---|---|
| usage-terminal-target-314 | 410 / 0 / 410 | 45.130 / 45.5587 | 0 |
| usage-terminal-target-310 | 410 / 0 / 410 | 46.512 / 46.8073 | 0 |
| usage-terminal-final-full-314 | 1726 / 19 / 1707 | 148.793 / 149.2761 | 0 |
| usage-terminal-final-full-310 | 1726 / 19 / 1707 | 157.095 / 157.5191 | 0 |

相对1709项实施基线新增17项，19skip不算通过；最终全量各实际通过1707项。最终四份日志没有ResourceWarning；不能据此排除历史未归属警告或首轮job resolve偶发失败。runner 240秒上限均未触发。全部最终测试开始前源码冻结，其后仅补文档。

完整精确命令（含所有失败/中间轮次及三组负对照）和内部结果见 [usage-command-results.md](/var/tmp/feiyu-stage-d/usage-command-results.md)。各运行证据为 `/var/tmp/feiyu-stage-d/<D_RUN>/full-{314,310}.log` 与 `full-{314,310}-result.json`；恢复探针脚本与隔离副本路径如上。`git diff --check`及新增/未跟踪实现文件空白检查通过。无桌面修改，未重复Node/build/TUI，未做付费模型收益或账单对账。

最终交接：HEAD d82d943，0.87.0未发布，全部原有及本批改动保持未提交。设计23/23.1包含状态所有权、兼容/迁移/回退、SDK等待限制与Astra重点。保留未知费用人工对账/恢复策略、MCP等其余D工作与受阻LSP独立审查；不重试该审查，不自行验收D，不推进E/F。


## Astra SDK记账审查裁决

已阅读 `/var/tmp/feiyu-sdk-review-20261116/report.md`。独立9项离线探针加既有17项，两版各26项内部exit0；覆盖pending/retry/fallback、累计去重和缓存差价、流close/中断下界、并行ContextVar、持久化失败、恢复与收紧。未发现确定缺陷，SDK记账本批通过限定范围审查，不等于真实账单对账或D整体验收。同步SDK静默等待、单次可超支、额外非token费用及原job偶发观察保留。接续MCP请求等待与连接收尾；受阻LSP独立审查保持未完成，不重试或接管。

## D 普通 MCP 请求可靠性实施（2026-11-16，待 Astra 审阅）

先写设计24，再实施与补24.1。保留HEAD d82d943及全部既有未提交改动、未发布0.87.0。未提交/推送/发布、未启动子代理、未用真实模型/付费调用、未读取真实配置或密钥；LSP实现未改，未执行/接管/重试受阻审查，SDK已审实现及RunControl不变，E/F未推进。

本批源码：mcp.py的请求级timeout/父控制检查、可取消锁等待、POSIX非阻塞管道写、短读等待、HTTP短命I/O进程与有界回收、失效连接不复用、初始化显式控制及串行所有权；Toolbox映射started/known/stop_reason为结果事实；Executor让MCP请求准入拒绝可落not_run，并保留关键写错误优先级；TaskState读取新增not_run；agent.load_mcp仅增加现有父控制传递。tests/test_mcp.py将原DELETE断言改为明确本地失效不等待远端DELETE；原有权限/readonly hint测试保留。新增test_mcp_lifecycle.py共18项，部分表驱动两种传输/失败阶段，使用全新HOME/XDG子夹具，18秒进程组timeout，stdio/server及loopback fixture有finally收尾。覆盖实际Toolbox/持久journal/Agent配对，不以内部helper测试代替执行事实。

运行均用唯一D_RUN及 `/var/tmp/feiyu-stage-d/run.py`，白名单env、新HOME/XDG、240秒进程组timeout。以内部result.exit_code和日志末尾判定。失败/中间结果：
- mcp-initial-314：31项，1failure（旧DELETE断言），10.713秒，内部exit1。关闭不等待服务端DELETE为本次明确兼容变更，更新断言。
- mcp-target-first-314：44项，5failure，21.226秒，内部exit1。HTTP新用例漏必填text，在schema层被拒绝，导致没有操作记录/发送信号；另Agent新用例没有捕获按契约向上传播的RunStopped。修夹具，不放宽schema或父取消。
- mcp-target-second-314：44项，1failure，16.873秒，内部exit1。剩余Agent异常捕获问题，修为断言RunStopped并检查恰好一个协议结果。
- mcp-target-third-314：104项通过，26.300秒，内部exit0。
- mcp-frozen-target-314/310：各106项通过，28.151/26.061秒，内部exit0。随后复核避免HTTP worker二次环境变量展开，并在原连续HTTP测试补字面量`${...}`断言。
- mcp-final-target-314/310：各106项通过，29.651/27.099秒，内部exit0。复核又加强finished关键写失败与cleanup同时失败时保留PersistenceError的回归；因此此前已启动mcp-final-full-*仅作中间验证，不替代最后冻结全量。

隔离负对照：`/var/tmp/feiyu-mcp-negative-ogmeb1g_`只复制feiyu/tests，单独撤去Toolbox的execution_unknown标记。mcp-negative-314两项如期失败（unknown变failed），1.376秒，runner1.6187秒，内部exit1。最终源码再次复制到 `/var/tmp/feiyu-mcp-final-negative-xhck49f4`，同一单点变异与同两项测试，D_RUN=mcp-final-negative-314；不stash、不回退工作区。精确命令和结果汇总见下方命令记录。

限制/迁移详见设计24.1：HTTP取消只能停止本地等待，服务端动作无法撤销；session不发DELETE，可能保留到过期。stdio及HTTP worker的有界管道实现限POSIX；冻结版HTTP明确拒绝，需源码Python运行，未补打包入口/未跑桌面构建。请求等待50ms检查不是硬实时承诺，进程TERM/KILL收尾最多两段2秒，OS不可中断调用/父硬死亡无独立监管仍保守unknown。旧reader不认识not_run，降级需停止服务/关闭writer、备份journal并只读历史。新实现无自动重连/重发。D仍未验收，Astra需审阅设计列出的边界，尤其发送事实、关键保存、worker回收、兼容缺口与迟到响应，不将本批回归当成独立审查结论。

再次冻结补充：mcp-refrozen-target-314/310各106项、0skip通过，unittest27.950/25.805秒，runner28.1486/25.9417秒，内部exit0。最终副本负对照mcp-final-negative-314两项如期失败，unittest1.382秒、runner1.6187秒、内部exit1；只撤unknown标记，不改生产工作区。

中间全量mcp-final-full-314/310各1744项、19skip、内部exit0，unittest168.318/157.859秒；因运行期间补了保存/cleanup双故障保护与夹具，不作为最终冻结证据。3.10中间全量出现一条subprocess ResourceWarning（PID647793）；检查时该PID已退出，未归属，不宣称已排除。最后全量以mcp-refrozen-full-*为准。

### MCP 最终冻结证据

```sh
D_RUN=mcp-refrozen-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_mcp_lifecycle tests.test_mcp tests.test_execution tests.test_runcontrol tests.test_taskstate -q
D_RUN=mcp-refrozen-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_mcp_lifecycle tests.test_mcp tests.test_execution tests.test_runcontrol tests.test_taskstate -q
D_RUN=mcp-refrozen-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t .
D_RUN=mcp-refrozen-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t .
# cwd=/var/tmp/feiyu-mcp-final-negative-xhck49f4
D_RUN=mcp-final-negative-314 /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python /var/tmp/feiyu-stage-d/run.py /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest tests.test_mcp_lifecycle.MCP.test_timeout_late_stdio_response_cannot_be_reused tests.test_mcp_lifecycle.MCP.test_http_missing_response_is_bounded -q
```

| D_RUN | 项数 / skip / 实际通过 | unittest秒 / runner秒 | 内部exit_code |
|---|---|---|---|
| mcp-refrozen-target-314 | 106 / 0 / 106 | 27.950 / 28.1486 | 0 |
| mcp-refrozen-target-310 | 106 / 0 / 106 | 25.805 / 25.9417 | 0 |
| mcp-refrozen-full-314 | 1744 / 19 / 1725 | 161.521 / 162.0427 | 0 |
| mcp-refrozen-full-310 | 1744 / 19 / 1725 | 168.613 / 169.0011 | 0 |

相对1726项基线新增18项，19skip不计通过；源码在最终四次运行前冻结，其后仅补文档。最终四份日志均无ResourceWarning，不能据此宣称中间全量那条警告已归属/修复。18秒子夹具及240秒runner上限均未触发。检查无本批合成stdio server/HTTP I/O worker遗留运行进程。git diff --check及本批未跟踪实现/测试文件尾空白检查通过。

所有失败/中间/最终轮次的精确命令、cwd、内部结果汇总：[mcp-command-results.md](/var/tmp/feiyu-stage-d/mcp-command-results.md)。原始日志与result位于 `/var/tmp/feiyu-stage-d/<D_RUN>/full-{314,310}.log` 及 `full-{314,310}-result.json`。未重复Node/build/TUI，不声称冻结版/非POSIX或真实远端服务通过验证。

交接：HEAD d82d943，版本0.87.0不变，保留全部既有修改并保持未提交。设计24/24.1已列状态所有权、兼容/回退、明确限制及Astra审查重点；本批待独立审阅，不自行验收D。SDK记账通过限定审查的结论不变，LSP受阻审查保持未完成，不重试/接管，E/F未推进。


## Astra MCP审查裁决与P2直接修复

已读 `/var/tmp/feiyu-mcp-review-20261116/report.md`。本批暂不可验收：P1冻结/Windows兼容回归必须补齐，不能以文档声明替代原产品能力；两P2为HTTP close未回收在途worker、清理异常覆盖原PersistenceError。

Astra直接修复两P2：HTTP传输以独立锁管理活动worker所有权，close先标关闭并清空状态、回收worker；结果导入与close串行，关闭后不能恢复session/inbox。初始化、request、notify及worker finally使用原错误优先清理，secondary保存到cleanup_errors，保留PersistenceError及取消原因。新增真实loopback在途close与stdio持久化/取消双故障回归；没有修改LSP或重试受阻审查。

`D_RUN=astra-mcp-p2-target .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_mcp_lifecycle tests.test_mcp -q`：51项通过、23.404秒、内部exit0。随后补充RequestFailure保留secondary诊断字段，3.10及后续完整兼容批次测试覆盖最终源码。本轮不以此宣称MCP验收；后续打包兼容修复必须保留上述回归并最终双版全量。

3.10最终定向 `D_RUN=astra-mcp-p2-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_mcp_lifecycle tests.test_mcp -q`：51项通过，内部exit0，runner21.293秒，证据同名D_RUN目录。diff检查通过。

## D MCP P1 兼容实现交审（2026-11-16，未验收）

按Astra报告补齐冻结入口、Windows管道适配及正常关闭有界DELETE；保留两项P2与原回归。先读约束、设计24/24.1/24.2、最新进度及审查报告。生产变更仅feiyu/mcp.py、feiyu/mcp_windows.py、__main__顶部worker分流及desktop backend入口/构建检查；未改LSP/SDK。设计/迁移/IPC取舍/平台范围与审查重点见24.3，旧24/24.1的功能禁用记录由该节替代。

冻结worker使用同一可执行文件，源码用本解释器-m feiyu；业务初始化前分流，URL/headers/session/请求均走stdin。Windows PeekNamedPipe读探测与CancelSynchronousIo写取消、限时join替代POSIX门禁；并非只删除判断。独立HTTP worker所有权、关闭后结果检查及原错误优先机制保留。正常空闲close通过独立0.5秒预算worker DELETE；异常/取消/在途close不追加网络等待。release_confirmed/release_error记录释放是否确认；DELETE不撤销POST。

最终证据（内部result.exit_code均0；skip不计通过）：

| D_RUN | 项数 / skip / 实际通过 | unittest秒 / runner秒 |
|---|---|---|
| mcp-p1-final-target-314 | 112 / 1 / 111 | 34.232 / 34.4257 |
| mcp-p1-final-target-310 | 112 / 1 / 111 | 30.930 / 31.0600 |
| mcp-p1-final-full-314 | 1750 / 20 / 1730 | 173.172 / 173.6872 |
| mcp-p1-final-full-310 | 1750 / 20 / 1730 | 162.469 / 162.8950 |

mcp-p1-final-build复用既有desktop/build/python-build（Python3.14.10、PyInstaller6.22.3），不pip安装、不引新依赖；--paths指当前源码、--collect-all feiyu，构建到 `/var/tmp/feiyu-mcp-p1-final-build/{payload,work}`，spec同目录，runner22.992秒。未覆盖desktop/build、用户安装或发布产物。实际ELF位于 `/var/tmp/feiyu-mcp-p1-final-build/payload/feiyu-backend/feiyu-backend`。

mcp-p1-final-frozen-parent-check（runner3.576秒）覆盖真实冻结worker初始化/工具调用/正常DELETE/在途取消与回收，敏感headers不进argv、字面量不二次展开，PATH=/no-external-python；另实际生产冻结--serve父入口（无sys.frozen/命令mock）加载HTTP配置、初始化/list/session/退出DELETE通过。工具/取消probe为源码父驱动真实冻结worker，不冒充GUI或模型对话。mcp-p1-final-backend-check（2.469秒）既有冻结OpenAI/Anthropic无请求初始化、host bash子进程及loopback HTTPS自定义CA检查通过。mcp-p1-desktop-all：9项Node测试通过（0.365秒）；py310-syntax解析新增Windows模块与打包入口/检查脚本通过。仅改backend入口及打包检查，无renderer修改，不重复前端build/TUI/完整安装器发布。源码追踪desktop/electron/agent.mjs:8与get.sh:160共用backend可执行入口；未实际运行get.sh安装。

新增兼容测试包括源码协议/取消、DELETE无响应有界失败且明确未确认、无原异常cleanup失败；Windows背压取消/回收测试在Linux跳过，不能作为Windows通过证据。现有51项MCP/P2回归保留并通过最终两版套件。隔离负对照 `/var/tmp/feiyu-mcp-p1-negative-20261116` 移除源码worker入口，mcp-p1-negative-entry-b 1项如期失败（内部exit1、0.9669秒），未stash用户改动。

失败与限制：target-314-b新增probe漏传RunControl构造参数，1失败；修正后通过。中间128项包含import测试类导致重复收集，最终改成模块引用，精确计数用112项。首个冻结父检查误断言status含工具名，改为按boot事件验证注册；生产实现未因此更改。首个负对照shell相对解释器不存在exit127、无runner结果，随后绝对路径重跑如期失败。完整精确命令、cwd、每轮成功/失败及result/log路径见 [mcp-p1-command-results.md](/var/tmp/feiyu-stage-d/mcp-p1-command-results.md)。

3.14最终全量出现一条subprocess ResourceWarning（PID677065），收尾时已退出，无本批HTTP worker/合成stdio server遗留；该警告未归属，不宣称已排除。3.10最终全量无该警告。所有runner均未触发240秒硬timeout。Windows实机/Windows冻结/NSIS/macOS均未验证；Windows CancelSynchronousIo竞态、权限与taskkill失败的子树收尾仍需实机确认。不宣称P1全平台已关闭；本批交Astra审阅，不自行验收D。HEAD d82d943、未发布0.87.0及全部既有未提交改动保留；无提交/推送/发布、子代理、真实模型/付费调用、真实配置/密钥读取；不推进E/F，不接管或重试受阻LSP审查。


## Astra MCP复核中断续接：响应导入后关闭

前次复核因额度中断，但 `/var/tmp/feiyu-mcp-rereview-20261116/report.md` 已落盘：Linux冻结HTTP原禁用可按已测范围关闭，Windows仍缺实机；原错误覆盖P2可按已测范围关闭；HTTP close仍有响应已导入inbox但未消费时等待原超时的P2。Astra直接修复：请求响应循环读取前后检查closed，保留父控制异常优先；HTTP gone返回关闭状态，inbox读取与close同步；DELETE是否空闲使用完整Server请求锁状态，不仅看worker是否存在。新增真实loopback事件屏障回归，断言关闭后0.5秒内结束、started unknown、不复活session且不发DELETE。两版定向证据续记。

当前源码已改变，旧 `/var/tmp/feiyu-mcp-p1-final-build/` ELF对应此前实现，不得称其包含本次响应循环修复。后续冻结检查需重新构建或明确区分既有兼容证据和最新源码修复证据。未提交/发布，版本仍0.87.0，LSP受阻审查未重试，D未验收。

`D_RUN=astra-mcp-import-close-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_mcp_lifecycle tests.test_mcp -q`：Ran 52 tests in 25.001s

OK；内部exit0，证据同名D_RUN目录。

`D_RUN=astra-mcp-import-close-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_mcp_lifecycle tests.test_mcp -q`：Ran 52 tests in 22.332s

OK；内部exit0，证据同名D_RUN目录。


## Astra MCP续核裁决

已读 `/var/tmp/feiyu-mcp-close-review-20261116/report.md`：原HTTP close及响应导入后未消费窗口P2、原PersistenceError覆盖P2在已测Linux范围关闭；冻结HTTP兼容P1在Linux源码/新实际ELF范围关闭，Windows实机/冻结/NSIS证据仍缺，不能全平台关闭。两版各52项定向、18个独立交错、10项smoke通过。新ELF位于该审查目录build/payload，已核对当前源码provenance；旧ELF不作为本次小修证据。正常DELETE与异常/取消优先均有独立证据。本批不等于D总体验收。

下一步对照原任务书整理D验收矩阵，保留LSP审查受平台限制、Windows未实测、同步SDK静默等待及历史未归属ResourceWarning等限制。不得以“已实现”或“测试通过”代替独立审阅，不为填齐清单无限扩大范围。所有改动仍未提交，0.87.0未发布。


## D 验收矩阵文档交接（2026-11-16，仅文档，待 Astra 裁定）

新增 [D验收矩阵与E接续计划](architecture-d-acceptance.md)，逐条映射原D十项及九组必要回归的实现入口、现有测试、独立证据和限定状态，并给出最小剩余工作及E原九项接续顺序；不改原任务书勾选，不宣布D通过，不实施E/F。

最新裁决沿用：SDK独立记账审查通过限定离线范围；前台Shell/hooks两P1关闭；MCP最新独立复核在Linux源码及新实际ELF范围关闭兼容P1及两P2，Windows实机/冻结/NSIS仍缺。LSP已有实施测试，但独立审查被平台中止，继续未验收；本次没有执行、接管、重试或另换渠道绕过。最后双版全量1750项/20skip（实际1730通过）早于最后MCP响应导入后close小修；小修后各52项定向、18个独立交错、10项smoke与新ELF通过，不能称最终全量已重跑。历史ResourceWarning仍未归属。

文档按原要求保留两个具体实现缺口供Astra裁定/后续最小实施：TaskState结果只支持unfinished/completed，部分完成/无法验证尚无明确任务结果表达；后台job仅接收启动时deadline，存活父运行中收紧限制尚无持续同步路径（无job.wait场景）。同步SDK静默等待的即时取消/总时限仍是能力限制，不因记账已审而称D10全部满足。以上为普通入口与原文的文档核对，未进行新故障或安全审查，不对受限LSP形成替代结论。矩阵同时明确不新增跨session全局互锁、通用外部查询适配器、exactly-once等非原硬要求。

本次只新增矩阵并追加本节；无测试执行、子代理、真实模型/付费调用、生产代码/tests/版本改动或提交发布。HEAD保持d82d943、0.87.0未发布，全部既有未提交修改保留。最终文件内容/路径核查记录随交付说明；本节不覆盖前文历史时点。

## D3 明确任务结果实施交审（2026-11-16，未验收）

本批仅补 D3，先落设计第25节再实现。TaskState.result 增加 partial/unverifiable，保持 unfinished/completed；CLI/serve 共用 `/task {"action":"result","result":"partial|unverifiable|unfinished|completed","reason":"人工依据（勿含秘密）"}`。partial/unverifiable 必须人工说明，不自动从模型文本、等待、中断、预算或deadline推断。result_details 保存 user-control 来源、请求ID、时间、验收状态与验证引用快照，快照不写回Ledger；人工声明不制造passed事实。继续原任务清回unfinished并保留验收/引用；completed仍经已有事实验收及同session未决门禁，证据失效/恢复核验可撤回unfinished。旧 `/task complete` 保留，旧unfinished/completed无details可读，不补造来源、不批量迁移。

本批文件：feiyu/taskstate.py、agent.py、__main__.py、serve.py、progress.py；新增tests/test_task_results.py；README中英同步；设计/进度/矩阵。现有 `/task` 文本/JSON note、完整context、progress.selected及serve.status可选task字段覆盖展示接缝，不改desktop renderer/布局/框架或桌面文件，故本批未跑Node/build/TUI布局检查。未动后台父限制同步（下一批）、LSP/SDK/MCP进程逻辑；全量中的普通既有测试不是执行/接管受阻LSP独立审查。E/F未推进。

最终源码冻结后双版离线验证，内部 result.exit_code 全为0（skip不计通过）：

| D_RUN | 项数 / skip / 实际通过 | unittest秒 / runner秒 |
|---|---|---|
| d3-final-target-314 | 214 / 0 / 214 | 22.453 / 22.6987 |
| d3-final-target-310 | 214 / 0 / 214 | 22.305 / 22.5000 |
| d3-final-full-314 | 1759 / 20 / 1739 | 176.884 / 177.3899 |
| d3-final-full-310 | 1759 / 20 / 1739 | 166.674 / 167.0715 |

精确命令（cwd `/home/Feiyu/AI_Agent/feiyu-agent`）：

```sh
D_RUN=d3-final-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_task_results tests.test_taskstate tests.test_runcontrol tests.test_session tests.test_serve tests.test_progress -q
D_RUN=d3-final-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_task_results tests.test_taskstate tests.test_runcontrol tests.test_session tests.test_serve tests.test_progress -q
D_RUN=d3-final-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t . -q
D_RUN=d3-final-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t . -q
```

各轮由唯一D_RUN建立新HOME/XDG（不继承环境，白名单含PATH/LANG/SHELL/PYTHONDONTWRITEBYTECODE及禁用用户Git配置），FakeBackend、合成工作区/既有本地夹具，无真实模型/付费请求、真实外部服务或用户配置密钥读取。8项新增用例覆盖部分验收verified/unverified、无法验证的人工声明、CLI中断/等待/预算及截止停止不升级结果、继续工作后结果更新、session保存恢复、旧checksummed result读取且不写原件、completed恢复保守核验、unknown仍阻断且不获重放授权、伪造字段及关键写失败。总数1759减本批8项为既有1751；原1750全量早于MCP新增1项，不能沿用为本批最终全量。

全部命令、cwd、失败与结果链接：[d3-command-results.md](/var/tmp/feiyu-stage-d/d3-command-results.md)；机器摘要：[d3-summary.json](/var/tmp/feiyu-stage-d/d3-summary.json)；源码/测试SHA256：[d3-source-sha256.json](/var/tmp/feiyu-stage-d/d3-source-sha256.json)。日志/result保存在 `/var/tmp/feiyu-stage-d/<D_RUN>/full-{314,310}.log` 和 `full-{314,310}-result.json`。检查了内部exit_code，未依赖runner外层退出0。四次最终运行无ResourceWarning，不能据此排除历史未归属观察；未触发240秒硬timeout。

失败如实保留：首轮d3-target-314共212项，1失败1错误，新夹具遗漏verify配置且误用serve事件字段event；第二轮d3-target-314-b共212项，1错误，协议实际字段kind而非type。修正夹具后d3-probe-314新增8项通过；未放宽生产验收条件。负对照独立副本 `/var/tmp/feiyu-d3-negative-20261116` 仅复制源码/tests并移除revise清回unfinished的两行，`d3-negative-314` 1项如期失败（内部exit1、0.370秒，runner0.6662秒），准确报partial != unfinished；没有stash/reset/覆盖用户原改动。

迁移/限制：schema1仅扩展可选details与result枚举；旧记录可读，新枚举不允许旧writer写回。降级先退出writer、备份完整session/journal，只读历史；不得删unknown、重置预算或伪造验证。partial/unverifiable是人工结果声明而非独立执行证明，说明勿含秘密；没有自动交付比例推导。Windows/macOS/真实供应商未验证，LSP受阻审查保持未完成，SDK静默等待及后台收紧缺口不变。临时证据目录需负责人归档。

Astra审阅入口：设计第25/25.1节 → tests/test_task_results.py八项 → 命令索引/源码指纹 → 矩阵D3与第5节。重点检查人工结果和Ledger事实边界、继续/恢复撤回语义、unknown门禁不受结果影响及旧格式只读兼容。本批只记录D3实施完成待审，不自行验收D或勾任务书。HEAD d82d943、未发布0.87.0保持；所有既有未提交改动保留，无子代理、提交/推送/发布。


## Astra D3 select P2修复与裁决

独立报告 `/var/tmp/feiyu-d3-independent-20261116/REVIEW.md` 确认select未checkpoint导致失效completed展示及旧任务progress视图。Astra在选中任务绑定完成后、刷新提示前复用_task_checkpoint；新增两项serve入口回归。原独立探针原有两失败在修复后双版均通过，P2关闭，D3按本批范围通过；D整体不验收。

`D_RUN=astra-d3-select-314`，命令 `.venv/bin/python -m unittest tests.test_task_results tests.test_taskstate tests.test_session tests.test_serve tests.test_progress -q` 经既有run.py白名单新HOME/XDG隔离：Ran 206 tests in 14.185s

OK；内部exit0，runner14.461秒。

`D_RUN=astra-d3-select-310`，命令 `/var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_task_results tests.test_taskstate tests.test_session tests.test_serve tests.test_progress -q` 经既有run.py白名单新HOME/XDG隔离：Ran 206 tests in 22.047s

OK；内部exit0，runner22.254秒。

`D_RUN=astra-d3-independent-fix-314`，命令 `.venv/bin/python /var/tmp/feiyu-d3-independent-20261116/probe.py` 经既有run.py白名单新HOME/XDG隔离：Ran 14 tests in 3.747s

OK；内部exit0，runner3.925秒。

`D_RUN=astra-d3-independent-fix-310`，命令 `/var/tmp/feiyu-stage-b/py310/bin/python /var/tmp/feiyu-d3-independent-20261116/probe.py` 经既有run.py白名单新HOME/XDG隔离：Ran 14 tests in 3.798s

OK；内部exit0，runner3.924秒。

未重复全量，上一1759项全量早于本次一行修复和两项新增回归，最终后续冻结全量需覆盖。diff检查通过，0.87.0未发布，全部改动未提交。后台限制动态同步下一批继续，SDK/LSP/Windows限制保留。


## D 最后明确缺口：后台运行中父限制同步（2026-11-16，实施待 Astra 审阅）

先写设计第26节再实施；仅普通本地任务预算控制，未开启新安全审查。保留D3 select绑定后的checkpoint及两项test_task_results；HEAD d82d943、未发布0.87.0、所有既有未提交修改保留，无子代理/提交/推送/发布，无真实模型/付费/外部服务/真实配置密钥，无E/F与受限LSP独立审查动作。

RunControl新增后台有效限制快照：独立短锁单调锁存最严费用/时间/双时钟截止，父请求锁只尝试非阻塞取得；拿不到仍检查预算并通知job，后续tighten合并锁存值，防止放宽补额。pending尝试本身不停止已有job，已知到限或unknown遇有限预算停止。原启动门禁管道保留作小JSON控制通道，父写非阻塞；只发更早deadline/停止，不重复写全部journal。jobrunner沿用WNOWAIT、身份与进程组清理、输出摘要和独立收据；真实退出先于停止决策，冻结terminal_reason，后续取消不改原exit。动态原因deadline_stopped/budget_stopped/cancelled；保存失败persistence_error并保留原异常与unknown，status/take/wait/kill/父check显式报错。启动旧deadline的reason=deadline兼容。

父已死只承诺最后传入监管者管道的deadline，EOF不扩额、不假装实时读父配置；恢复仍只观察，不重放、不新开控制monitor、不绕过pending/resolve。OS不可中断调用、逃逸setsid、同步SDK静默等待及真实供应商硬费用上限的既有限制均未消除。仅Linux；Windows/macOS未验。无schema/config迁移，reason为现有字符串扩展；降级先退出writer/job、备份完整session/journal，只撤本批差量，不清unknown/预算，不让旧writer覆盖新格式。

新增tests/test_job_limits.py九项：真实sleep/ready/标记后台任务，无job.wait收紧时间和费用、预算运行中到限/unknown有限值、显式取消、持父锁仍停止、收紧保存失败保留主异常并实际收尾、父死亡最后传递deadline、已完成真实exit7不被改写、pending不误停且锁释放后不补额。ready文件与持锁事件是同步点，断言收据/监管者退出/标记未发生均在finally kill_all兜底前；每个子场景私有HOME/XDG白名单、18秒硬timeout，顶层既有run.py为240秒硬timeout。

失败如实保留：首轮probe-314共50项，1失败，新增失败路径在锁存error后wait仍循环旧running，触发该子场景18秒timeout；产品在timeout前已产停止收据且监管者已退出（测试随后卡在wait）。修复wait显式抛原异常，monitor保存失败operation保守unknown，收尾reason=persistence_error。首轮还因直接导入Lifecycle被unittest重复发现16项；改为模块导入，未改旧测试。修复轮probe-314-b共34项全通过，之后新增pending/不补额第9项。相关target双版119项通过后，最后两行unknown/原因断言强化，再做final-target双版119项全通过；冻结全量只针对这版源码。

负对照在独立副本/var/tmp/feiyu-job-limit-negative-20261116，复制源码/tests并仅将runcontrol/jobs/jobrunner/tools替换为本批实施前快照；原工作区未stash/reset。no_wait_cost_tightening 1项如期失败，原因5秒内无产品收据（内部exit1），随后夹具finally才清理；证明捕获原缺口，不是以兜底清理算产品成功。

| D_RUN | 实际总数 | 内部exit | unittest秒 / runner秒 |
|---|---:|---:|---:|
| job-limit-probe-314 | 50 | 1 | 40.815 / 40.981447 |
| job-limit-probe-314-b | 34 | 0 | 13.533 / 13.713031 |
| job-limit-target-314 | 119 | 0 | 44.332 / 44.721248 |
| job-limit-target-310 | 119 | 0 | 43.907 / 44.220774 |
| job-limit-final-target-314 | 119 | 0 | 44.040 / 44.477501 |
| job-limit-final-target-310 | 119 | 0 | 42.968 / 43.262629 |
| job-limit-negative-314 | 1 | 1 | 5.304 / 5.578560 |

首轮冻结全量双版实际均1770项/20skip/1失败，实际1749通过，内部exit1；3.14 unittest183.384秒/runner183.906925秒，3.10 unittest171.658秒/runner172.098430秒。失败相同：旧LSP普通生命周期test_task_select以object.__new__(Feiyu)构造，缺verifications；D3已保留的select checkpoint读该字段而报AttributeError。未撤checkpoint或改LSP产品语义，仅在该夹具补两行真实空Ledger初始化。补齐后fixture-target双版11项（该普通回归+全部10项test_task_results）0skip/exit0，3.14 2.351/2.519961秒，3.10 2.461/2.571091秒。这不是受限LSP独立审查，不是接管/重试，也不声称LSP验收；首轮失败日志保留，不拿旧1759计数替代。

夹具修复后的第二轮全量（job-limit-final-full-{314,310}-b）均1770项/20skip/1750实际通过，内部exit0，runner分别179.847474/168.221873秒；这轮早于最后kill错误优先级小修，**不当最后冻结全量**。随后新增j.kill原异常同一性断言（未回退生产代码），job-limit-primary-negative-314 1项如期红灯，内部exit1、unittest0.259秒/runner0.414924秒，明确收到次要“job identity unknown; refused signal”而非主保存异常。修复kill在安全身份信号未命中后优先抛锁存原异常，两行差量，不放宽身份检查；这是保存失败交接路径修正，不是新安全审查。强化断言后job-limit-close-target双版各120项/0skip/exit0，3.14 unittest44.500秒/runner44.957816秒，3.10 unittest43.370秒/runner43.697986秒。

最后源码冻结后以job-limit-close-full-{314,310}执行全量，最终结果见下表；此前所有轮次与失败均保留。精确最终命令（同项目cwd）：

```sh
D_RUN=job-limit-close-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_job_limits tests.test_job_lifecycle tests.test_runcontrol tests.test_sdk_accounting tests.test_task_results tests.test_taskstate tests.test_execution tests.test_foreground_lifecycle tests.test_lsp_lifecycle.TestLifecycle.test_task_select -q
D_RUN=job-limit-close-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_job_limits tests.test_job_lifecycle tests.test_runcontrol tests.test_sdk_accounting tests.test_task_results tests.test_taskstate tests.test_execution tests.test_foreground_lifecycle tests.test_lsp_lifecycle.TestLifecycle.test_task_select -q
D_RUN=job-limit-close-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t . -q
D_RUN=job-limit-close-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t . -q
```

证据索引：[精确全部命令/结果/日志链接](/var/tmp/feiyu-stage-d/job-limit-command-results.md)、[机器摘要](/var/tmp/feiyu-stage-d/job-limit-summary.json)、[冻结Python源码/tests SHA256](/var/tmp/feiyu-stage-d/job-limit-source-sha256.json)、[仅本批四产品文件差量](/var/tmp/feiyu-stage-d/job-limit-implementation.diff)。工作区完整diff/status/文件指纹另存job-limit-final-workspace.diff、job-limit-final-status.txt、job-limit-workspace-sha256.json，供负责人归档；目录为本机临时证据，不是发布产物。D3原独立14项既有通过记录保留，本批没有借此重做独立审查。

Astra审阅重点：父RLock持有时monitor无等待/无锁反转；限制锁存与后续持久化不补额，pending不冒充unknown超支；父死EOF最后deadline而非不存在的实时父配置；自然exit与停止决策的顺序及真实exit不抹除；原保存异常在monitor/kill/后续check中优先、清理与独立收据不依赖失败journal；恢复观察/pending/resolve不因停止而获得重放授权。当前仅实施完成待审，SDK/LSP/Windows能力及审查限制继续保留，D整体不验收、不勾任务书，E/F未推进。

job-limit-close-full-310实际1770项/20skip/1750通过、exit0（unittest172.119秒/runner172.543147秒）；314同总数但1失败、实际1749通过、exit1（182.968/183.504640秒）。唯一失败是既有job启动deadline用例reason != deadline，日志没有打印收据完整值，不能据此断言实际是deadline_stopped还是cancelled。普通等待/monitor/监管者均可先观察到截止，新的动态deadline_stopped与原启动deadline理由发生竞争；SIGTERM亦可进入该窗口。监管者现将父传来的deadline_stopped归一到它当前deadline的来源（原启动=deadline，后续更早=deadline_stopped），并在已经到截止的停止决策上选择该来源，persistence_error仍优先，真实退出先观察与真实exit码均保留。未放宽/改掉原测试断言。修后reason-target双版120项/0skip/内部exit0，runner44.808259/43.603865秒；最终全量改用唯一job-limit-frozen-full-{314,310}，上列close/full历史结果不冒充此修正后的冻结证据。产品/测试SHA256已重冻结。

reason修正后的job-limit-frozen-full双版均1770项/20skip/1750实际通过、exit0，runner183.362265/171.697856秒；但运行中普通源码核对发现保留stdin控制管道后必须给子命令显式DEVNULL以延续旧EOF行为，故这两轮不作为该末次修正的最终冻结证据（可能混合加载，日志仍原样保留）。已补stdin=DEVNULL，既有九项中场景先read确认EOF再ready，未增加测试计数；stdin-target双版35项/0skip/exit0，runner13.852464/12.499427秒。最终唯一冻结全量改为job-limit-eof-final-full-{314,310}；无进一步产品/测试修改，SHA256以job-limit-source-sha256.json为准。没有撤回用户修改或用旧全量代替。

末次EOF冻结的实际命令（前面各命令保留为相应历史轮次）：

```sh
D_RUN=job-limit-stdin-target-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest tests.test_job_limits tests.test_job_lifecycle tests.test_runcontrol -q
D_RUN=job-limit-stdin-target-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_job_limits tests.test_job_lifecycle tests.test_runcontrol -q
D_RUN=job-limit-eof-final-full-314 .venv/bin/python /var/tmp/feiyu-stage-d/run.py .venv/bin/python -m unittest discover -s tests -t . -q
D_RUN=job-limit-eof-final-full-310 .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t . -q
```


### Astra 中断后证据核对（2026-11-16）

额度中断后直接核对末次 EOF 冻结结果：job-limit-eof-final-full-314 与 job-limit-eof-final-full-310 的内部 result.json 均 exit_code=0；日志各1770项、20 skip，即1750项实际通过。unittest耗时分别182.947/180.247秒，runner耗时183.437263/180.632507秒。当前109个Python源码及测试SHA256与job-limit-source-sha256.json全部一致，无差异。未重跑已完成全量，未改产品代码。上一实施线程失败不等于磁盘上的最终测试失败；本批实现进入独立复核，尚未验收。D整体、受阻LSP审查、Windows实机及同步SDK等待边界仍保留，未推进E/F。


### Astra 裁决：后台同步 R1 修复关闭（2026-11-16）
独立复核报告 /var/tmp/feiyu-job-limit-review-20261116/report.md 确认首次take导入终态保存失败时吞错P2。Astra在持job锁refresh之后再次检查error并抛同一原异常，保留前置检查；新增test_first_take_preserves_terminal_save_error，真实监管收据/退出7后由前台首次导入，保存失败保持unknown。未改副作用、恢复和预算语义。

- D_RUN=astra-job-take-fix-314；命令 `.venv/bin/python -m unittest tests.test_job_limits tests.test_job_lifecycle tests.test_runcontrol -q`（经既有run.py全新HOME/XDG隔离）；内部exit=0，runner=14.159556秒。定向36项通过。
- D_RUN=astra-job-take-fix-310；命令 `/var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_job_limits tests.test_job_lifecycle tests.test_runcontrol -q`（经既有run.py全新HOME/XDG隔离）；内部exit=0，runner=12.801563秒。定向36项通过。
- D_RUN=astra-job-take-probe-314；命令 `.venv/bin/python /var/tmp/feiyu-job-limit-review-20261116/review_probe.py`（经既有run.py全新HOME/XDG隔离）；内部exit=0，runner=1.418842秒。原独立5项探针全部通过。
- D_RUN=astra-job-take-probe-310；命令 `/var/tmp/feiyu-stage-b/py310/bin/python /var/tmp/feiyu-job-limit-review-20261116/review_probe.py`（经既有run.py全新HOME/XDG隔离）；内部exit=0，runner=1.367273秒。原独立5项探针全部通过。

R1在上述范围关闭，后台父限制同步本批可接受。此前1770/20skip全量早于本次两行修复及新增回归，不宣称是当前代码最终全量；本次只运行受影响定向与原独立探针。D仍未整体验收：同步SDK等待、受阻LSP独立审查、Windows实机等限制保留；E/F未推进，0.87.0及全部未提交修改保留。


## 恢复执行：D收口、E实施与任务书总验收（2026-11-17）

用户已授权按四步恢复：最后修复后的双版全量/桌面检查；处理D剩余验收条件；实施E；任务书逐条总验收。整个任务书完成前禁止提交，仍不推送或发布。先冻结当前源码补证据，不把此前1770项全量当末次take修复后的结果。SDK取消边界按原D10评估，不以说明代替实现；平台受阻LSP独立审查不重试、不换渠道。Windows没有实机证据则明确未验证。原任务书第7节允许逐项记录具体阻碍及可执行下一步，但不将阻碍记作测试通过或自行豁免验收。E和总验收仍待后续实施。

### 2026-11-17 首批 D 收口证据（测试角色交 Astra，非 D 验收）

本次在末次 `DurableJob.take` refresh 后原异常检查和 `test_first_take_preserves_terminal_save_error` 已存在的工作树执行。HEAD仍为`d82d943e64dcf4129e5bc44f4798abff6949da83`，0.87.0未发布，保留所有既有未提交修改；本次只追加进度/验收文档，未实施E、未修改产品或版本、未提交/推送/安装/发布、未付费调用、未启动子代理。未读取真实密钥/历史；受阻LSP独立审查未执行、接管、改写重试或换渠道，普通全量不替代该审查。

证据根目录：`/var/tmp/feiyu-d-close-20261117/`。`report.md`总报告，`commands.txt`精确命令，`results-summary.json`内部结果汇总，`source-snapshot.tar.gz`归档180个源码/测试/桌面/文档配置文件，`source-sha256.json`逐文件指纹；其中109个Python源码/测试见`python-source-sha256.json`，该清单文件SHA256为`895da88566b45d8de21b572e1581771cf3cb5d8f0b81e03934a841ae85f3c845`。测试后、追加本节前180文件指纹全部一致（`post-tests-fingerprint-check.json`）。起点HEAD/status/diff及两版SDK依赖指纹均已归档；文档追加属于此后差量，不改变本批产品/测试指纹。

所有D_RUN均为唯一全新目录，沿用`/var/tmp/feiyu-stage-d/run.py`白名单环境、独立HOME及四项XDG，不依赖外层runner退出0；已核对各目录内部`full-314-result.json`或`full-310-result.json`的exit_code及日志。

```sh
D_RUN=/var/tmp/feiyu-d-close-20261117/full-314-20261117-a .venv/bin/python /var/tmp/feiyu-stage-d/run.py /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python -m unittest discover -s tests -t . -q
D_RUN=/var/tmp/feiyu-d-close-20261117/full-310-20261117-a .venv/bin/python /var/tmp/feiyu-stage-d/run.py /var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t . -q
D_RUN=/var/tmp/feiyu-d-close-20261117/node-test .venv/bin/python /var/tmp/feiyu-stage-d/run.py /usr/bin/npm --prefix desktop test
D_RUN=/var/tmp/feiyu-d-close-20261117/node-build .venv/bin/python /var/tmp/feiyu-stage-d/run.py /usr/bin/npm --prefix desktop run build
.venv/bin/python /var/tmp/feiyu-d-close-20261117/desktop_checks.py
.venv/bin/python /var/tmp/feiyu-d-close-20261117/desktop_checks_xauth.py
```

- Python3.14.10：内部exit0，1771项/20skip/1751实际通过，unittest181.166秒，runner181.664330秒（以归档日志原文为准）。
- Python3.10.20：内部exit0，1771项/20skip/1751实际通过，unittest169.502秒，runner169.930096秒。
- Node26.13.1/npm12.2.2：`npm test` 9/9、0skip，内部exit0；`npm run build`内部exit0。Node结果沿用runner的full-314文件名，以内部command识别。
- 当前源码后端普通桌面集成：已有DISPLAY/套接字/Electron依赖，原夹具默认冻结后端为11月14日旧产物；仅在归档夹具副本改为当前`.venv/bin/feiyu`+显式PYTHONPATH、修正副本导入路径，全部断言保留，repo夹具未改。首轮隔离环境未传XAUTHORITY，smoke/verify-trust均exit1，保留X11 Authorization required日志。加入既有XAUTHORITY与DBUS会话路径（不读取cookie、不搭基础设施）后，两夹具内部exit0，分别7.334516/7.832990秒。覆盖真实Electron/当前Python、PTY/文件边界/工作区/表单/开场及verify信任拒绝批准持久化；不代表当前冻结包或Windows/NSIS通过。夹具关闭应用并清理临时状态，未触及已安装桌面。

本轮无普通Python回归失败；两版日志只有预期的不可写trace路径诊断，无ResourceWarning，后者不排除历史未归属观察。20skip不计通过。此前1770/20skip全量不再充当末次take修复后的全量证据。

SDK只读方案：`sdk-plan.md`列出providers.py ask/create、stream enter/next/close、父attempt RLock的具体调用位置。现有同步close不能证明按请求跨线程有界取消；更短受控timeout可缓解但非总deadline，不足以关闭原D10。建议每attempt可回收SDK worker、父保有账本和原生历史、取消/截止时有界终止并wait回收，补锁等待与动态收紧观察、IPC背压/冻结入口/usage完整性回归。工程估计中等改造（约2—4开发日加审阅，非承诺）；不以遗留线程冒充取消、不把未收到usage当零，远端生成和收费不能保证撤销。仅交方案，未实施、不降级原要求。

Windows：`windows-boundary.md`区分MCP已有实现缺真实管道/CancelSynchronousIo/taskkill/冻结worker/NSIS证据，与TaskStore安全writer（dir_fd/NOFOLLOW/fcntl）、受控LSP（Linux gate）、durable job身份/进程树的实现缺口。无Windows实机，不以Linux模拟算通过，不重开MCP Linux已关闭范围。下一步由Astra复核本批证据、落实原D10方案与Windows支持范围/实机条件；LSP受阻独立审查保持未完成。D整体不代签、原任务书不勾完成，E和总验收仍由主控后续推进。

### D10 同步 SDK worker 实施交接（2026-11-17，待 Astra 独立审查）

仅D10；HEAD仍d82d943/0.87.0未发布，全部原有改动和已修take P2保留，无子代理、提交/推送/发布、stash/reset、付费/真实provider或真实密钥/历史访问；未推进E/F，未执行/接管/重试受阻LSP独立审查。协议先写后实现，见设计§27/27.1及`/var/tmp/feiyu-d10-sdk-worker-20261117/protocol.md`。父唯一RunControl账本/原生历史，worker每attempt一次SDK调用，max_retries=0，独立有界IPC、取消后kill+wait+关闭管道，原停止/持久化错误优先；pending不是inflight已知超支。源码/frozen同exe、Fake/custom兼容保留。

本批具体产品文件：`feiyu/sdk_worker.py`、`sdk_windows.py`、`sdk_errors.py`、`providers.py`、`runcontrol.py`、`__main__.py`、`agent.py`（纯异常判据共享及结构化字段读取）；desktop两入口/构建脚本。新增`tests/test_sdk_worker.py`与`desktop/tests/check_sdk_backend.py`。README中英及设计同步，版本不另bump。

证据根`/var/tmp/feiyu-d10-sdk-worker-20261117/`：report.md列实现/局限/所有失败轮次，commands.txt精确命令，results-summary.json内部结果，source-snapshot.tar.gz冻结122文件及source-sha256.json（清单SHA256 `4fff3fd60399080e789cfd5f5f2064b4d3a56030232cbf5162653abcc5581018`），post-tests-fingerprint-check.json确认测试后122文件无差异；本节/验收追加在该检查之后，产品与测试无后续修改。环境JSON单列：源码两版anthropic2.8.0/openai3.51.0，既有冻结构建venv openai3.50.0，无pip/网络安装，冻结实测通过。

最终冻结后证据（外层runner0不当判据，均核对内部result和日志）：

- `final3-full-314`：内部exit0，1786项/20skip/1766实际通过，unittest210.349秒、runner210.867022秒。
- `final3-full-310`：内部exit0，1786项/20skip/1766实际通过，unittest209.201秒、runner209.641059秒。
- `frozen-target-314/310`：各108项，内部exit0，unittest41.595/50.732秒。此前含agent的定向各293项也exit0，但早于最终流中静默夹具修改，不替代本项。
- `final-node-test` 9/9、`final-node-build`、`final-freeze-build`、`final-frozen-backend-smoke`、`final-frozen-mcp-smoke`、`final-frozen-sdk-smoke`均内部exit0。既有构建venv离线PyInstaller，新产物在final-payload，不替换已安装程序。SDK smoke实际两SDK ask/stream及CLI父同exe success/cancel，PATH无外部Python；MCP为入口普通回归，不重开已关闭结论。
- `final-desktop/desktop-smoke-xauth`与`desktop-verify-trust-xauth`真实Electron+当前源码后端均exit0，7.285706/7.886744秒，沿用前批归档夹具副本适配、全部断言保留，隔离HOME/XDG及既有显示授权路径，不读取cookie。

命令均沿用`D_RUN=<上述证据子目录> .venv/bin/python /var/tmp/feiyu-stage-d/run.py <绝对解释器> -m unittest ...`，完整参数见commands.txt/内部JSON；desktop副本见final-desktop-checks.py。白名单环境、全新HOME/XDG、240秒硬超时与finally清理；产品回收断言在夹具清理前检查returncode、管道关闭、waitpid ECHILD。新增15项覆盖两SDK ask/stream建立静默、收到usage后流中静默取消、更早deadline、锁等待、请求IPC背压、早死、终态取消交错、持久化原错、usage下界、retry/cache fallback、图片/reasoning/原生thinking签名/tool分片/扩展字段及SIGINT交接。既有回归覆盖显式零、累计去重和pending恢复不补预算。

失败保留：worker-a用了不存在夹具方法；原生模型相等断言漏SDK可选默认None字段，导致早期定向及首轮1785全量失败，改为逐字段证明原值保留；一次命令误写不存在tests.test_overflow；负对照首次cwd未创建执行前失败。负对照仅独立副本禁用SDK轮询，终态交错断言真实失败（complete而非partial）；工作区从未撤改。full2双版1785/20skip虽通过但早于最后异常兼容修改，不当最终证据。所有轮次见report，无隐藏失败。最终全量只有预期不可写trace诊断，无本轮ResourceWarning；20skip不计通过。

限界/未完成验证明确交Astra：Windows独立pipe实现路径保留但无Windows/macOS实机；TaskStore/LSP/jobs既有Windows缺口不扩建。新矩阵尚未穷尽回收失败注入、持续非事件HTTP噪音、通过IPC的完整tool配对回调loopback脚本、真实SDK父硬死后恢复（已有账本崩溃测试是合成backend）。无独立SDK supervisor，父SIGKILL不保证worker/远端生成撤销。64MiB帧上限、Popen/序列化/用户回调及内核不可中断I/O不作50ms硬实时承诺。模型列表/custom client仍是旧路径，不声称获得worker取消。远端收费不撤销，单次可超额，未知usage不是零。

迁移无schema/config变化；回退先停请求/writer、备份完整session/journal，只撤D10差量，保留unknown/pending与全部既有改动，不重放、不补预算。交Astra具体代码/协议/证据和上述限制，等待独立审查，不自称D或原D10已验收完成。


## Astra D10审查修复（2026-11-17，待复核）

F1：Exchange清理完成后重新检查父控制，主异常不覆盖；request_attempt在成功报告前核对停止，停止时撤回本次新增历史并保留partial/unknown，移除成功报告之后的停止检查以明确接受顺序。F2：cleanup unknown禁止内部retry、Anthropic/OpenAI cache fallback、agent transient及overflow/rejected自动救援重发，原异常属性向上传递。新增双provider ask/stream清理窗口取消及双provider503/400清理失败回归。

- D_RUN=astra-sdk-fix-probe-314，命令 `.venv/bin/python /var/tmp/feiyu-d10-sdk-review-20261117/probe.py`；内部exit=0；原独立4项全部通过，runner 9.694087秒。

- D_RUN=astra-sdk-fix-probe-310，命令 `/var/tmp/feiyu-stage-b/py310/bin/python /var/tmp/feiyu-d10-sdk-review-20261117/probe.py`；内部exit=0；原独立4项全部通过，runner 12.706971秒。

- D_RUN=astra-sdk-fix-target-314，命令 `.venv/bin/python -m unittest tests.test_sdk_worker tests.test_sdk_accounting tests.test_providers tests.test_runcontrol tests.test_agent -q`；内部exit=0；相关285项全部通过，runner 67.771115秒。

- D_RUN=astra-sdk-fix-target-310，命令 `/var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_sdk_worker tests.test_sdk_accounting tests.test_providers tests.test_runcontrol tests.test_agent -q`；内部exit=0；相关285项全部通过，runner 80.751602秒。

均经既有run.py全新HOME/XDG白名单执行；精确环境、内部result、日志保留于各目录。本次未重跑全量或重建冻结产物，先前1786全量及旧冻结二进制不当作修复后证据。设计补充已写入；D10/D未验收，受阻LSP/Windows等限制保留，未推进E/F。无提交推送发布。


## Astra裁决：D10 F1/F2关闭与E接续（2026-11-17）

已读 /var/tmp/feiyu-d10-sdk-fix-review-20261117/report.md。双版新增5项/16子情形及原独立2项通过；新隔离冻结SDK smoke通过，8个代码对象与当前源码匹配。接受本次限定范围关闭F1/F2：接受前停止撤销本次历史并保留partial/failed_or_interrupted，接受后由工具门禁停止且补配对；cleanup unknown不被retry/cache/agent救援隐藏。不是D10/D整体验收，也不宣称全平台或硬死亡清理通过。修复后全量仍待后续最终冻结验证。

原任务书第7节允许逐项记录阻碍及下一步；用户已授权推进E和总验收。现启动不依赖缺失Windows/LSP审查证据的E上下文/历史整理，不以E启动倒推D通过。Windows安全writer/LSP/jobs实现与MCP/SDK实机缺证据分开保留；受阻LSP审查不重试；SDK父硬死亡/平台等限制继续列入最终交付。整个任务书满足完成条件前不提交、不推送、不发布。


## Astra恢复核对：E首批额度中断后（2026-11-17）

已读原实施线程，确认无活动run。核对 /var/tmp/feiyu-stage-e-context-20261117 内部result与日志：final-target-314/310各403项、exit0；final-full-314为1794项/20skip、1774实际通过、exit0；未找到final-full-310证据。Node9/9、build、源码后端Electron smoke/trust内部exit0。116项source-sha256指纹与当前文件全部一致。initial-target/seam夹具失败及negative-prefix预期失败均保留，不冒充通过。E第1/4/5项已有实施但待独立审查，其余E项未完成。

恢复时查询原模型gpt-6.1-sol high，Codex provider返回canRunChildTask=false，原因“Codex app-server provider probe failed: workspace routing discovery failed.”，无法启动接续任务。本轮未换模型/渠道、未新启委派、未修改产品或重跑测试。服务恢复后从补Python3.10最终全量、完善交接及独立审查继续，不重写已落盘实施。任务仍未完成，不提交推送发布；D平台/受阻LSP限制保留。


### E首批独立只读审查交接（2026-11-17，待Astra裁决）

报告 `/var/tmp/feiyu-e-context-review-20261117/report.md`；精确命令、内部JSON/日志、指纹与探针均在同目录。HEAD d82d943/0.87.0保留；源码/测试116项指纹前后与实施清单全部一致。仅追加允许的证据文档，无产品/测试/版本修改，无子代理、提交推送发布、stash/reset、真实key/历史、付费/外部provider；未执行/接管/重试被平台拒绝的LSP独立审查。

发现R1 P2：`agent.py:606–616`的易变层只在_refresh_system时取快照；真实send→todo→下一轮run_turn中，TaskState已通过session checkpoint保存新todo，task层仍为首轮todos=[]。`stale_probe.py`双版各1项确定失败（内部exit1），稳定前缀及工具配对保持。主循环1439–1447/1538未刷新易变层；建议每轮主请求前更新task/evidence/recall并保留稳定rules/project字节，补实际入口回归。未自行修复或验收。

补3.10最终全量：唯一D_RUN=`/var/tmp/feiyu-e-context-review-20261117/full-310-a`，经原run.py新HOME/XDG白名单及240秒硬超时，内部exit0；1794/20skip/1774实际通过，unittest214.668秒/runner215.092582秒。命令解释器`/var/tmp/feiyu-stage-b/py310/bin/python -m unittest discover -s tests -t . -q`。既有final-full-314指纹匹配，核对内部exit0、1794/20skip/1774实际通过，未重复跑。

新E探针双版各4项内部exit0：实际provider请求cache拒绝fallback/关闭兼容、3MiB合成图片0600保存恢复及旧schema读取、两provider原生thinking/signature/reasoning/tool配对/扩展字段、同类模型切换、跨provider旧行为、来源标签和custom backend。首轮custom夹具漏model造成exit1，原脚本/失败保留，修夹具后全新目录通过，不冒充产品失败。D10原独立修复probe在当前源码双版各5项/16子情形内部exit0，接受前只撤本次历史、接受后配对及cleanup unknown禁重发保持。原285项不宣称本轮重跑。

普通全量通过不覆盖新发现R1；E2/3/6/7/8未实施、Dreaming未重构、真实模型收益未验证，D平台/父硬死/受阻LSP等限制不变；E/D/任务书不勾完成，交Astra修复及裁决。


## Astra E首批R1修复裁决（2026-11-17）

采纳独立报告 /var/tmp/feiyu-e-context-review-20261117/report.md 的R1。将易变层构建提取为_refresh_volatile_context，每个主run_turn前刷新TaskState/Ledger/recall，直接复用已建rules/project字节，不额外checkpoint或读写持久化。配置真实变动仍走完整_refresh_system。新增实际send→todo→下一轮回归，断言清单更新、前缀相同、人格仅构建一次及工具配对。修正session旧图片注释。

- D_RUN=astra-e-refresh-target-314；`.venv/bin/python -m unittest tests.test_context_layers tests.test_agent tests.test_session tests.test_providers -q`，经既有run.py全新HOME/XDG隔离，内部exit=0，runner=33.262972秒。日志/result保留在该目录。

- D_RUN=astra-e-refresh-target-310；`/var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_context_layers tests.test_agent tests.test_session tests.test_providers -q`，经既有run.py全新HOME/XDG隔离，内部exit=0，runner=34.620280秒。日志/result保留在该目录。

- D_RUN=astra-e-refresh-probe-314；`.venv/bin/python /var/tmp/feiyu-e-context-review-20261117/stale_probe.py`，经既有run.py全新HOME/XDG隔离，内部exit=0，runner=0.415201秒。日志/result保留在该目录。

- D_RUN=astra-e-refresh-probe-310；`/var/tmp/feiyu-stage-b/py310/bin/python /var/tmp/feiyu-e-context-review-20261117/stale_probe.py`，经既有run.py全新HOME/XDG隔离，内部exit=0，runner=0.364620秒。日志/result保留在该目录。

双版原独立stale_probe已通过，相关定向通过，diff检查通过。R1在上述范围关闭，E原第1/4/5项有限范围可接受；不宣称真实provider缓存收益、压缩核验或来源链完成。修复前双版1794/20skip全量仍是旧状态，本次不冒称最终全量。下一批实现压缩后的程序核对和验证引用。D平台/受阻LSP等限制保留；全部未提交修改和0.87.0保留，无推送发布。


## E2/3 压缩核验实施交接（2026-11-17，待 Astra 审阅）

HEAD仍d82d943/0.87.0；原有全部未提交修改保留，无提交推送发布、stash/reset、子代理、付费/真实provider/真实key历史。未执行、接管或重试平台拒绝的LSP独立审查，不自验收E/D/总任务书。先读原E/6/7、设计6/7/28及D10接受点和E矩阵/进度，协议先写后实现。差量仅compaction.py、agent.compact/import、Ledger.reference与共享_recheck、新15项测试、中英README和设计/进度/E矩阵。

显式/自动/overflow摘要入口统一候选事务；trim/shrink/fold仍仅工具文本处理。双原生配对拒绝闸；TaskState完整原请求/修订/目标/约束/验收/todo/操作/预算与job观察作程序真源，候选核对并补结构化事实。模型文字为assistant_claim，程序块为program_state；逐ID Ledger引用重核owner/指纹/config/epoch/日志，不从摘要创建execution evidence或提升stale/unknown。摘要attempt费用不撤销、不补预算。原生compact_to在独立副本构造候选，程序核对完整块和配对，停止检查、关键存盘后才替换。保留D10接受前撤本次历史及cleanup unknown禁重发语义。

自查补强atomic_json在replace后目录fsync失败窗口：先持久化原历史并同目录硬链接备份；候选保存失败原子恢复原文件。新增真实writer写候选后报错注入，证明磁盘/内存原历史保留。恢复rename本身被文件系统拒绝时保留副本及异常compaction_rollback路径，writer仍blocked待人工核对；不承诺任意存储故障/断电exactly-once。派生备份清理错误不推翻已接受事务。单agent串行历史writer，非新并发事务框架。

证据根`/var/tmp/feiyu-stage-e-compaction-20261117/`：report.md、protocol.md、commands.txt、内部JSON/日志、results-summary.json、最终183项source-sha256/source-snapshot及post-tests-fingerprint-check。唯一原run.py每次全新HOME/XDG白名单、240秒硬超时；均核对内部exit而非runner外层0。最终源码冻结后结果：

- `final-target-314-b`：内部exit0，395项全部通过，runner 87.859651秒。
- `final-target-310`：内部exit0，395项全部通过，runner 99.690271秒。
- `final-full-314`：内部exit0，1810项/20skip/1790实际通过，runner 214.638442秒。
- `final-full-310`：内部exit0，1810项/20skip/1790实际通过，runner 233.358707秒。
- `final-node-test`：内部exit0，runner 0.565055秒。
- `final-node-build`：内部exit0，runner 0.264376秒。
- `final-r1-probe-314`：内部exit0，runner 0.314649秒。
- `final-r1-probe-310`：内部exit0，runner 0.264870秒。
- `final-desktop/desktop-smoke-xauth`：内部exit0，7.184287秒。
- `final-desktop/desktop-verify-trust-xauth`：内部exit0，7.840838秒。

15项新增覆盖强制压缩续作、约束/未完成验收、Fake摘要谎称通过、missing/stale/foreign-owner验证引用、unknown/prepared/running操作及真实job+新agent会话恢复、双provider原生入口/配对拒绝、多模态失败保留、取消/模型/保存失败及replace后失败恢复。最终独立副本移除程序事实导致续作测试内部exit1，预期失败；工作区未撤改。R1原独立stale_probe双版通过。Node9/9/build及当前源码后端真实Electron smoke/trust通过，适配仅归档夹具副本、原断言保留、隔离HOME/XDG及既有显示授权路径，无替换已安装应用。

失败轮次全部保留：首轮遗漏session导入；合成操作夹具缺必填字段；运行job在原agent恢复触发现有切换保护及夹具cleanup顺序；恢复后system应刷新却被夹具要求逐字相同。各次具体计数见report。此前frozen双版1809/20skip虽通过但早于最后replace后回滚修复，不能充当最终结果。最终双版1810/20skip实际各1790通过，只有预期不可写trace诊断，无本轮ResourceWarning；skip不计通过。183项最终源码测试后无差异。

无schema/config迁移；整段摘要仍按既有明确策略删除早期图片/thinking/signature/reasoning原生消息，不冒充无损转换。普通保存恢复/工具瘦身保真，已经丢失的旧内容不能重建。回退先停请求/writer并备份完整session/journal，只撤本批差量，保留首批/R1/D10和既有全部修改；unknown不重放、预算不补。完整程序事实可能很大，不保证任意上下文都能压入窗口。

交Astra重点审阅接受/回滚顺序、来源块完整性与custom compact_to契约、Ledger逐ID消费有效性和归属、原请求/验收/预算保全、实际job/session恢复。E6结构化事件与E7 sink隔离、E8全链路来源和E9 Dreaming尚待后续；本批仅摘要source_kind/verification_refs接口。真实模型收益未验证；D平台/Windows及SDK父硬死、受阻LSP审查限制不变。不自行代签E/D/整任务书。


## Astra E2/3两项P2修复（2026-11-17，待复核）

compact普通摘要异常分支遇sdk_cleanup_error原样raise，禁止自动摘要后继续主模型；session.save按是否存在非system消息判断非空，解决Anthropic单user原历史未落盘导致hardlink失败。仍保留先持久原历史/备份/候选及原回滚顺序，没有吞FileNotFoundError后继续。新增两个实际send→auto摘要和首条Anthropic send→overflow→compact回归。

- D_RUN=astra-e23-probe-314；`.venv/bin/python /var/tmp/feiyu-e-compaction-review-20261117/probe.py`；内部exit=0，runner=1.919300秒；Ran 8 tests in 1.707s

OK

- D_RUN=astra-e23-probe-310；`/var/tmp/feiyu-stage-b/py310/bin/python /var/tmp/feiyu-e-compaction-review-20261117/probe.py`；内部exit=0，runner=1.869709秒；Ran 8 tests in 1.734s

OK

- D_RUN=astra-e23-target-314；`.venv/bin/python -m unittest tests.test_compaction tests.test_session tests.test_agent tests.test_verification tests.test_verification_review -q`；内部exit=0，runner=40.422918秒；Ran 290 tests in 40.218s

OK

- D_RUN=astra-e23-target-310；`/var/tmp/feiyu-stage-b/py310/bin/python -m unittest tests.test_compaction tests.test_session tests.test_agent tests.test_verification tests.test_verification_review -q`；内部exit=0，runner=41.474537秒；Ran 290 tests in 41.319s

OK

均沿用run.py全新HOME/XDG白名单；未重跑全量，旧1810/20skip全量早于本修复，不算当前最终证据。设计已同步，交独立复核后裁决；E6/7/8/9、D平台/父硬死/受阻LSP等限制保留。不提交推送发布，所有既有改动及0.87.0保持。


## Astra裁决：E2/3有限接受及E6/7接续（2026-11-18）

已核对 /var/tmp/feiyu-e23-fix-review-20261117/report.md：双版独立7项通过，183项指纹和工作区状态保持，原Astra双版8项反例及290项相关回归有效。关闭F1/F2；接受压缩事务、程序事实保全与Ledger引用本批已验证范围。清理unknown原样传播，单user原生历史先落盘再备份，候选失败原异常/预算/原历史保留。不是D/E整体验收；修复后全量尚待最终冻结验证，平台/硬死亡/受阻LSP限制不变。

下一批实施E原6/7：关键运行事件和session/run隔离sink，兼容CLI/Desktop并避免双发。E8/9来源链与Dreaming后续继续。任务书完成前不提交推送发布，0.87.0与全部未提交改动保留。


## E6/7 结构化运行事件及sink隔离交接（2026-11-18，待 Astra 独立审阅）

报告 `/var/tmp/feiyu-stage-e-events-20261118/report.md`，先行契约protocol.md，精确命令commands.txt、内部result/log及results-summary.json、160项源码指纹/快照与测试后核对均保留。HEAD d82d943/0.87.0及全部既有未提交修改保持；无子代理、提交推送发布、stash/reset、付费/真实provider/真实key历史访问，未执行接管重试受阻LSP独立审查。

运行层唯一生产Executor执行边界、Ledger显式/消费时验证失效、send持久准入后恢复及持久收尾后停止/run_end。Route显式绑定session/task/run/seq、关闭丢弃迟到事件；工具线程逐提交copy_context，子调查显式注入回调；原UI卡片kind/payload单生产者保留。CLI简短显示执行状态，Desktop更新原卡片pending文字，停止恢复/失效映射提示。frontend异常降级不吞TaskStore/会话关键异常。详见设计30及E实施矩阵，不实现E8/9。

最终frozen-target双版各479项通过，frozen-full双版各1820项/20skip/1800实际通过，内部exit0（3.14 runner216.349465秒、3.10 233.615133秒）。R1原探针双版各1项，E2/3原probe双版各8项，补充子调查/持久化失败probe双版各2项均exit0。Node10/10、build、当前源码后端真实Electron smoke/trust均exit0，隔离HOME/XDG及既有显示授权路径/归档夹具副本，无cookie读取或已安装应用替换。最终160项指纹无差异，diff检查通过。独立最终副本移除worker上下文传递确定内部exit1，seq断裂；未撤工作区。

失败全部保留：新测试缺FakeBackend、误用clear而非reset；旧helper fake_run未接受新增event_emit导致首轮扩大定向/全量各一个error，修替身保留原断言。旧final-*全量早于最终测试/呈现冻结，不冒充当前；最终仅frozen-*有效。桌面adapter首次缺证据父目录为启动前准备失败。3.14最终全量有一条subprocess ResourceWarning（另附tracemalloc提示），PID 1234430事后已不存在；未定位夹具触发，不宣称零警告。3.10全量和最终定向/桌面无该警告。

审阅重点：单生产者/旧卡片语义、运行关闭/线程传播、会话恢复身份、关键持久化与事件顺序、CLI worker呈现、旧客户端字段兼容。事件非可靠授权/journal真源；执行结束指调用返回，后台job终态仍看持久收据。无schema/依赖/版本迁移；回退先停writer并备份完整session/journal，仅撤本批差量，保留R1/E2/3/D10/全部继承修改、unknown和预算。E8全链路来源（摘要/子报告/memory）和E9 Dreaming集成未完成，真实模型收益未验证；D平台/Windows/SDK父硬死/受阻LSP审查限制保留。不代签D/E或总任务书，交Astra独立审阅。


## Astra裁决：E6/7有限接受与来源链接续（2026-11-18）

核对 /var/tmp/feiyu-e-events-review-20261118/report.md：双版各5项独立入口探针通过，14组最终frozen证据与160源码/归档指纹一致；有限范围未发现确定缺陷。接受关键执行事实和session/run隔离本批范围，不宣称可靠重放或同agent并发历史支持。ResourceWarning具体创建来源未定，既有事后PID退出不等于排除全部生命周期问题。D平台/SDK父硬死/受阻LSP/真实模型收益等限制保持。

接续原E8/9来源经摘要、子报告、记忆的保留，以及Dreaming原来源/指纹/应用前校验；不把已有source_kind字段当作全链路完成。全部任务书完成前不提交推送发布，0.87.0与所有既有改动保留。

## E8/9 来源转述实施交接（2026-11-18，待 Astra 独立审阅）

先追踪send/工具/辅助提炼/子调查/压缩/memory/Dreaming/session路径，协议先写 `/var/tmp/feiyu-stage-e-provenance-20261118/protocol.md`，再实现设计31及E矩阵。程序维护原ID/digest/source_kind/source_refs引用集合；生成文本一律claim，外部来源不因转述升级，旧数据unknown/legacy。remember兼容原tuple及旧Markdown读取，新JSON行包含来源；模型不能选择其类别。Dreaming保留原来源范围/quote/base/apply检查并增加来源、记忆metadata和候选指纹；纯对话不写Ledger、不自动验收。

新普通回归覆盖实际子调查外部文本→remember→两次压缩→恢复、同批文件读取→remember、web辅助提炼、来源字段自称无效、旧记忆unknown、Dreaming正常应用及周边来源变化/metadata变化/候选变动拒绝、reset。独立副本撤来源保留和来源指纹门禁均预期失败，未stash/reset工作区。早期失败保留：子报告JSON破坏字符串/长度接口（改程序属性+回注信封）；Agentish无root兼容（collect接受workspace）；新夹具漏self.root（修夹具）。最后自查补web辅助模型与同批工具返回即时登记，因此此前frozen-/final-不冒称最终源码；只final2-*匹配最终产品/测试指纹。

证据report.md、commands.txt、内部result/log、results-summary.json、source-sha256.json与source-snapshot.tar.gz均在上述目录。最终结果将据内部exit与日志追加；不看外层runner的0。无子代理、提交推送发布、stash/reset、真实provider/key/用户history/dream访问、版本bump或新依赖；HEAD d82d943/0.87.0和全部继承改动保留。未执行/接管/重试受阻LSP独立审查。交Astra重点审查来源登记时序、旧数据降级、并发引用合并、重复转述与Dreaming指纹/写回；不自行裁定E/D/总任务书，评测对照配置与总验收仍由主控后续安排。

### E8/9 最终冻结验证交接（待 Astra 独立审阅）

双版全量各1829项 / 20skip / 1809实际通过，内部exit0；3.14 runner216.859272秒，3.10 runner234.178922秒。双版定向各220项、原E2/3独立八项及R1各一项通过；Node10/10、build、当前源码Electron smoke/trust通过。最终两独立副本负对照各exit1（预期来源保留/来源指纹断言失败）。唯一最终轮次final2-*；137项产品/测试/README指纹与当前源码一致，支持文件指纹另存，git diff --check通过。精确命令/内部result/log、保留失败、指纹与审阅限界见 `/var/tmp/feiyu-stage-e-provenance-20261118/report.md`。最后双版全量无ResourceWarning，不据此排除此前未定来源问题。原限制与未提交0.87.0保持，不自行接受E/D/任务书。


## Astra裁决：E8/9有限接受与总交付准备（2026-11-18）

已核对 `/var/tmp/feiyu-e-provenance-review-20261118/report.md`：137项源码、15项支持文件与归档匹配，双版各5项独立实际入口探针、85项定向及2项D10回归内部exit0；有限范围未发现确定缺陷。接受来源依赖集合跨子报告/压缩/记忆/恢复保留及Dreaming应用前重核本批范围，不承诺逐句归因、语义真伪、绝对模型免疫或多writer记忆事务。旧v1候选不具有缺失的历史指纹，仍须当前来源/base/quote校验。

当前产品最终全量证据仍为E8/9 final2双版各1829项、20skip、1809实际通过，Node10/10、build和源码Electron smoke/trust通过。本轮仅记录裁决，不重复未变化产品的全量测试。E各批已分别有限接受；此结论不是D/E跨平台或整任务书总验收。D平台/SDK父硬死/受阻LSP独立审查、真实模型收益和既有ResourceWarning来源未定缺口继续保留。

下一步按任务书第6节补齐四组对照评测的可复现配置、命令和输出格式，仅离线验证，不调用付费或真实模型；随后逐项核对第7节交付条件、迁移回退与实际阻碍。整份任务书完成前不提交，HEAD d82d943、未发布0.87.0及全部既有改动保留。

## 第6节四组对照离线准备（2026-11-18，交 Astra 审阅，未代签）

先核对HEAD d82d943e64dcf4129e5bc44f4798abff6949da83、未发布0.87.0及全部既有修改；本轮开始无evals改动/评测报告目录。读适用约定、第6/7节、E接受记录及末尾裁决后实施，未启动子代理。证据 `/var/tmp/feiyu-evaluation-preparation-20261118/`，新增 `docs/architecture-evaluation.md`、`evals/architecture.py`、`architecture_cases.py`、精确JSON配置/结果schema及5项离线测试，同步中英文README。无产品运行代码变化，无stash/reset/bump/提交推送发布/工作区版本切换/真实provider或key/history/memory/dream访问，未接管或重试受阻LSP独立审查。

实际离线链路包含四组各开发/保留题、六次重复交替两臂的96条计划，真实临时夹具、未解答拒绝/参考答案通过/越界改动拒绝共288次检查，独立于agent提交测试的文件判据及事件计划；写出源码/任务/提示/判题/解释器/包版本锁、合成JSONL和聚合。聚合严格核对身份、重复、缺样本、模型/提示/源码/判据变更、混合真假数据、非有限/负费用；辅助和失败费用累计，unknown/incomplete不归零；分开六种失败、成功率分母、样本/独立题数、Wilson描述区间、耗时/人工介入。合成控制器观察不冒充真实压缩/恢复行为或模型收益。

唯一最终验证为commands-final.json的final轮：原D runner唯一D_RUN、全新HOME/XDG白名单、240秒硬超时。双版Python各50项/6skip/44实际通过；validate/dry-run/aggregate内部exit0；live拒绝内部exit2（预期，无provider调用），不能以外层0当通过。早期target双版亦通过但非最终冻结；首个dry-314将D_RUN与--out重用导致FileExistsError内部exit1，原日志/verify-failed-first.py/commands.json保留；新路径重跑通过。产品未变未重跑全量桌面；继承E8/9 final2证据不冒称本轮结果。

四组都是HEAD对完整未提交产品快照，含多阶段/系统提示差异，明确confounded_full_snapshot，无单特性旧版或因果隔离。尚未接通的真实运行适配：双源码只读装载、请求参数和原生提示精确锁、工具/预算总账、版本变更后验证观察、真实compact/restart/外部一次操作收据、独立UID/容器不可篡改控制器判题、失败重试全费用账单。live固定拒绝，后续命令及授权/专用凭证/精确版本环境锁前提写在评测文档；命令不冒充适配已完成。保留题公开且只有每组1道，不作总体收益推断；需冻结扩大题库后真实评测。

程序回归已验证，真实模型收益尚未验证。第7节本批补齐离线工具/说明/证据交接，不代表A–E总完成或D/E/整任务书验收；D平台/SDK父硬死/受阻LSP独立审查/既有ResourceWarning来源未定缺口继续保留，交Astra核对报告与实际待准备项。


## 2026-11-18 Astra review fixes / 审查修复（待独立复核）

R1–R5: new locks explicitly bind offline_synthetic / fixture_self_check; all real-labeled rows and live locks are rejected until a protected execution adapter exists. Lock validation now checks its schema, baseline object, nonempty source manifests, SHA formats, judge/source agreement, exact schedule and required environment descriptions. Baseline hashing reads the configured commit, not symbolic HEAD. These are structural and self-consistency checks, **not source authenticity attestation**; protected source-bundle verification and actual execution remain pending.

配置所有字段与精确类型均按显式契约检查。aggregate未传--config时仅使用归档lock中的配置；显式传入时必须完全相同。新锁需要模式/版本/基线字段，旧合成锁保留作历史证据但不自动补字段为有效新锁，应重新dry-run。不得通过手改模式将旧合成数据转为真实结果。

Result validation rejects boolean schema versions and invalid object/hash types; sums must remain finite and JSON output disallows NaN/Infinity. All sixteen planned cells now report planned/observed/missing counts even when empty; empty rates and total cost remain null. 没有改变真实live固定拒绝的状态，四组真实执行适配仍未完成。

双版定向各58项、6skip、52实际通过，内部exit0；证据 `/var/tmp/feiyu-eval-fix-20261118/target-314/`、`target-310/`。8项新增回归覆盖整包改标、损坏锁、配置字段/CLI冲突、类型、费用及时间溢出、空计划单元和固定基线读取。没有重跑未变化产品全量/桌面。程序回归已验证，真实模型收益尚未验证。未提交/推送/发布，未接管受阻LSP审查；D/E既有限定与平台/父硬死等缺口保持。


## Astra裁决：关闭评测R1–R5离线缺陷（2026-11-18）

核对 `/var/tmp/feiyu-eval-fix-review-20261118/report.md`：双版各58次独立CLI检查符合预期，定向各58项/6skip/52实际通过、内部exit0，234文件与工作区状态不变。关闭R1–R5及空计划单元消失的问题，仅限离线结构、自洽、类型和统计；不将输入自带hash解释为源包真实性证明。

下一批沿用已有四组夹具和结果契约，以离线假provider接通真实产品执行：固定基线与当前包的双源码装载/核验、实际验证变更/压缩/恢复事件、控制器判题边界和请求预算账单。保持合成标签及confounded_full_snapshot，不调用收费或真实远端模型；缺授权live继续拒绝。§6尚未完整交付，D/E和整任务书不据此自动验收。平台/SDK父硬死/受阻LSP独立审查/历史ResourceWarning限制保留；所有既有改动、HEAD d82d943、0.87.0保持，不提交推送发布。

## §6 离线产品执行接线（2026-11-18，交 Astra 独立审阅）

新增 architecture fake 子命令、父控制器/原生请求假传输/环境字节锁及定向边界测试；未修改产品运行代码。固定 baseline 与当前 package 快照分别物化、清单/字节核验，bwrap 实跑独立产品，捕获模块来源、环境、原生提示/工具/请求与父账单。真实 rename、VALUE 首验后外部改写/失效检查/最终重验、首写后原生 compact 续接、一次服务 accept 后断连杀进程/真实会话重启/unknown 重放拒绝均有可执行路径。恢复题安全拒绝后仍未完成，保持 agent_failure，不伪造完成。父账单覆盖 primary/auxiliary/failed 身份及零/unknown/缺账单/重试耗尽/30轮120秒3元2attempts边界，跨子进程恢复不重置。

程序回归已验证，真实模型收益尚未验证。证据协议、逐次失败、双 Python 独立结果和最终指纹见 `/var/tmp/feiyu-eval-execution-20261118/report.md`。小规模仅 development 接线，不执行96轮或公开 holdout，不作收益/因果推断。现有 aggregate 继续只认 fixture 锁；新的 synthetic_product_execution 收据与逐行 schema 输出单列，不开放真实结果。Live SDK/专用凭证/精确返回版本可用性、付费授权和有硬截止的 provider 回调仍需后续接入和审查；现有父 execute/transport/Ledger 接口已具体实现，live 继续 exit2。OS镜像可重建性、恶意host/controller证明不在本批保证内。

未启动子代理，未提交推送发布/stash/reset/bump/切换工作区，保留 HEAD d82d943、未发布0.87.0及继承修改。未访问真实keys/history/memory/dream，未接管重试受阻LSP。产品未变无需全量桌面；E8/9 final2只继承不冒称本批重跑。D平台/SDK父硬死/受阻LSP/历史ResourceWarning限制不变，不代签D/E/任务书。Astra须独立审阅此次执行适配与剩余范围。


## Astra F1读帧期限修复（2026-11-18，待独立复核）

父worker stdout改为非阻塞字节读取、自有换行缓冲；每次select/读取后及处理完整帧前检查同一观察deadline。半帧保持开启超期为budget_stop，半帧EOF明确environment_failure，帧大小上限8MiB。父回复改为非阻塞os.write和可写等待，同一期限控制背压，避免readline/flush无限等待。finally保留杀组和回收。没有改变已声明同步transport callback自身须实现deadline的live接线限制。

新增真实bwrap半帧保持/EOF回归和真实管道写背压回归。双Python各65项、6skip、59实际通过，内部exit0；两版fake各8条真实产品观察均跑完：executor/verification/compaction各双臂success，recovery双臂agent_failure，未将unknown阻断冒充任务完成。证据 `/var/tmp/feiyu-eval-frame-fix-20261118/` 的target-314/310、fake-314/310内部result和data-314/310。产品源码未变，不重跑产品全量或桌面；原final8仅为修复前证据。真实模型收益未验证，D/平台/SDK父硬死/受阻LSP/历史ResourceWarning限制保持。未提交发布。


## Astra裁决：评测F1关闭与§7总交付核对（2026-11-18）

已核对 `/var/tmp/feiyu-eval-frame-review-20261118/report.md`：双版65项/6skip/59实际通过，独立真实worker/pipe验证半帧deadline、分段帧、EOF、回复背压、8MiB上限及kill/reap/关闭。修复后两版各8产品观察与当前声明源码包一致。关闭F1，仅限离线fake父控制器读写帧；不覆盖同步live callback内部期限。

接受§6当前离线准备交付范围：四组配置/夹具/命令/结果契约、结构与统计校验、双源码实际装载及小规模假provider产品路径。真实运行仍缺受审live SDK callback、专用凭证及费用授权、固定远端版本确认、真实开发/保留任务多次试验与收益报告。恢复题agent_failure保持，未知阻断不冒充完成；整体快照对照不推导单特性因果收益。该有限接受不等于§6真实运行或D/E/总任务书验收。

接下来按任务书§7核对每项交付及证据、迁移回退、当前D/E状态和剩余阻碍，形成统一矩阵，避免历史待办与最新裁决混淆。平台/SDK父硬死/受阻LSP独立审查/历史ResourceWarning继续保留；任务书完成前不提交推送发布。HEAD d82d943、未发布0.87.0与全部既有修改保持。


## §7 总交付矩阵与证据核对（2026-11-18，交 Astra 最终裁定）

新增 [architecture-delivery.md](architecture-delivery.md)，按原A5/B9/C9/D10/E9共42条及§7七完成条件逐项列实现、裁决、证据和状态；D/E矩阵开头仅加最新索引，历史全部保留，原任务书未改勾选。区分已验收局部、已实现待证、具体未实现、外部受阻及不属本任务；不自行验收D/E或总任务书。

只读核对报告、内部result/log、源码/归档字节。产品最后全量仍为E8/9 final2：双版1829/20skip/1809实际通过，Node10/build及源码后端Electron smoke/trust；内部exit0。137项清单与其归档完全匹配；当前只有中英README两项不同，均为后续六行评测说明追加，其余135项及15项支持文件一致。差量与覆盖证据保存在 `/var/tmp/feiyu-delivery-audit-20261118/`，不是产品不匹配，无需新全量/桌面。

后续evals证据单列：最新F1修复双版65/6skip/59实际通过，QR独立同套和管道探针；fake每版8观察中executor/verification/compaction双臂success，recovery双臂agent_failure。60项HEAD/81项当前package与物化字节匹配。未相加冒充新全量/独立样本；恢复安全阻断未冒称任务完成。旧D10冻结SDK包早于E，不证明最终E打包；最终E源码Electron通过也不是发行冻结包通过。

§6离线配置/命令/输出及小规模产品路径按Astra限定接受；live仍exit2，callback自身期限/账单适配、专用凭证、费用授权、远端版本及真实多次评测缺失，程序回归已验证，真实模型收益尚未验证，整体快照混杂保留。Windows TaskStore/LSP/jobs缺实现与MCP/SDK缺实机证据分列；SDK父硬死亡保证、平台受阻LSP独立审查、历史ResourceWarning未关闭。没有执行/接管/重试或替代该LSP审查。

版本各处0.87.0一致，中英README新增段对应，但旧D/E当前状态文字仍需发布前窄范围同步；本批仅交付文档未改README。迁移/回退写明先停writer、备份完整session/journal/收据/日志/memory/dream、旧memory JSON writer不兼容、unknown和已花预算不可删除或补充。§7条件1/6/7已有逐项交接，2/3具限定源码证据，4具无授权离线边界证据；5版本已同步但README状态收口未完。支持范围/SDK父硬死/LSP审查/警告条件/最终产物与正式留存交Astra裁定，不自动豁免。

本批只新增交付文档、追加本节和D/E索引；审计目录保存初末文件指纹、内部命令结果/日志摘要、证据hash与报告，正式存储/保留期限仍需确定。A起始干净但累计工作全部未提交，不能把HEAD差量冒称本批；HEAD d82d943、未发布0.87.0及所有继承修改保留。无子代理、产品/evals/tests/版本变更、stash/reset、工作区切换、提交推送发布、付费或远端provider、真实keys/history/memory/dream访问。未重跑未变化产品全量或桌面，不代主控签字。

## §7 总交付续作收尾（2026-11-18，review 交 Astra）

先读既有交付矩阵与审计脚本/结果，未重新执行全量审计或桌面。续作起点239文件与原after.json完全一致；原审计51个result/log/报告SHA全匹配，原失败轮次所有产物原位保留。续作只向 `/var/tmp/feiyu-delivery-audit-20261118/resumed/` 写核验脚本、初末指纹、证据检查和最终report。重算两版60/81项源码/物化清单和5745/6183项依赖字节均无差量；QR 116项证据SHA匹配，版本7个读取值均0.87.0，git diff --check通过。

原42条与§7七条件矩阵无需重建。交付文档补充README中英对应行及最小修改范围（含verify旧沙箱说明与D/E历史待审文字），明确本批未改README、U8仍待主控实际收口/归档；补充journal/Ledger引用状态根外产物也须备份，缺失引用必须显式列出。D/E开头已有总矩阵索引足够，本次未重复追加或改写历史。续作实际仅改交付文档和本progress追加，文件SHA及允许范围核验见resumed/after.json和final-workspace-check.json。

继承证据仍分列：产品E8/9 final2双版各1829/20skip/1809、Node10/build/源码Electron；后续evals双版65/6skip/59及每版8产品观察（恢复双臂agent_failure），不相加、不宣称新运行。旧D10包不证明最终E包。§6离线准备与F1有限关闭已获Astra接受，live callback、授权/专用凭证与真实收益未完成；Windows三项缺实现和MCP/SDK缺实机、SDK父硬死、受阻LSP、历史Warning继续保留，不自动豁免功能，F不属任务。

文档交接收尾完成，最终裁定仍由Astra处理U1—U8：先收口README与正式证据留存，明确平台/SDK保证范围，逐项保留或安排已授权后续。无产品/evals/tests/版本/任务书修改，无子代理、付费或真实provider/keys/history/memory/dream访问，无stash/reset/工作区切换/提交推送发布；未执行、接管、重试或替代受阻LSP独立审查。HEAD d82d943和未发布0.87.0全部继承修改保留，不代签总验收。


## Astra README状态收口（2026-11-18）

已核对总矩阵续作报告并完成中英README窄范围同步：verify共用沙箱/命令权限，D durable journal已实现，取消/retry/动态预算局部审查，Linux job和D10 F1/F2限定关闭，E各批及来源/Dreaming有限接受。追加0.87.0平台边界，Windows缺实现与缺实机证据分开，最终E冻结包待证。diff --check通过；仅文档不重跑产品测试。原矩阵U8的README部分关闭，正式证据归档仍待完成；U7下一步当前Linux冻结包验证，其他U1—U6限制保持。不提交发布，不声明总验收。

## 当前Linux冻结backend与本地证据补证（2026-11-18，交Astra）

本轮报告 `/var/tmp/feiyu-final-package-20261118/report.md`，受控副本 `/home/Feiyu/AI_Agent/feiyu-agent-evidence/architecture-20261118/final-package/report.md`。当前239文件源码快照、54冻结代码对象匹配，实际exe SHA256 `d9ac629a4ce2708129ccb6abac918bdc9b742636d9c46e74a4a8643ee3a4e2ba`。新构建/版本/backend/MCP/SDK同exe均内部exit0；从实际产物PYZ加载运行既有E夹具41/41，非bootloader内单测；现有真实Electron smoke/trust指向新冻结backend各exit0，非发行安装包。初次marshal字节比较ui不一致的exit1及修订代码对象比较记录均保留，不改产品。

U7仅Linux frozen backend及上述入口证据可交关闭，Electron发行/安装包与跨平台仍缺；不发布。E89 final2产品清单无变化，仅README中英预期变化，双版1829/20skip/1809与eval65/6skip/59、各8观察分开继承，未重新跑全量。U8 README由Astra已关闭；用户授权0700本地目录已保存最小可复核集，历史2939文件49,268,527字节加本轮源码/产物/结果/日志，来源映射与SHA均存索引。本机保留至用户明确清理，不称永久或外部备份；未保存全部历史，archive-plan.json/excluded和not-archived-references.json逐项列排除及未覆盖引用，原件未删，完整历史要求不能因此签关闭。

本轮仅矩阵/progress事实更新，Astra刚追加README裁决保持。U1—U6、父硬死、受阻LSP独立审查、历史Warning及live收益限制不变；未执行/接管/重试/替代LSP审查，无真实provider或用户数据、付费、产品变更、子代理、提交推送发布/bump/安装替换。不代签D/E/总任务书。


## Astra当前交付裁定（2026-11-18）

核对 `/var/tmp/feiyu-final-package-20261118/report.md` 与留存核验结果：接受U7的当前Linux frozen backend限定证据，54代码对象匹配、backend/MCP/SDK同exe检查及开发Electron宿主smoke/trust通过；41项E检查为构建Python加载实际产物PYZ，不称bootloader内41项。Electron发行安装包及跨平台验证未完成，U7不整体关闭。

接受U8的README状态同步及最小本机留存范围：`/home/Feiyu/AI_Agent/feiyu-agent-evidence/architecture-20261118/`，0700，3453文件、197727809索引字节，留存核验报告all_hashes_verified=true。以RETENTION.md、archive-plan.json与not-archived-references.json为范围，不称完整历史归档、永久保存、外部备份或全部依赖可离线重建。本裁定晚于归档最终文档，应单独保留。

当前结论：A/B/C和E各批、D已审Linux局部及§6离线评测准备具有限交付证据；整份任务书尚不能宣称全部功能/平台验收通过。§7逐项阻碍交接路径已具文档，并不消除U1—U6及U7发行范围的未完成事实。Windows TaskStore/LSP/jobs缺实现，MCP/SDK原生平台证据缺失；LSP独立审查受阻；SDK父硬死无独立监管保证；历史ResourceWarning来源未定；live SDK评测适配与费用授权/真实收益缺失。F不纳入本任务，不为结束任务降低验收标准。

保留HEAD d82d943、未发布0.87.0及全部累计未提交修改，不提交推送发布。后续实施须按矩阵对应实际缺口推进；平台证据需相应环境，受阻LSP不得换渠道绕过，真实模型评测需费用授权。普通Linux测试通过不替代这些条件。


## 用户确认的范围与旧版问题记录

用户确认本次按Linux范围继续，Windows完整适配后续处理，不再作为本次Linux交付的阻碍；历史U1/U2跨平台未完成事实仍保留，不能称Windows已支持或已验证。Linux其余未决项不因此自动关闭。

用户报告：0.84.5 Windows桌面安装版存在部分文字乱码、对话内容不显示并报错，仍无Windows机器、日志或截图。2026-11-19用户新授权窄范围修复：已合成复现并修复serve标准流未约束UTF-8以及Protocol吞编码异常的代码缺口；双Python/Node及独立Linux冻结后端离线检查通过，待独立审查。现场根因及用户故障是否解决仍未确认，Windows原生验证待办；不扩展TaskStore/LSP/jobs适配。旧Linux发行包和正式归档早于本次源码修复，不含它；证据 /var/tmp/feiyu-windows-stdio-20261119/，详见本次进度条目。

## Linux U4 SDK父SIGKILL监管实施（2026-11-18本地 / 2026-11-19 UTC，交Astra）

按用户最新Linux范围自行实施，无子代理；先读任务书D/§6/7、§27及裁决，设计先存 `/var/tmp/feiyu-sdk-parent-lifecycle/20261119T052932Z/design.md`。新增sdk_lifecycle专用监管入口，fresh exec后fork一个SDK直接子进程，父独占pipe写端关闭后监管者kill/wait并记录本地事实。私有no-follow/uid/mode检查、128个flock槽、单槽4KiB及同token/pinned-fd核对；local_worker在已有pending记录中启动前保存。收据不是usage/远端撤销证明，恢复不消费它完成请求，未知继续阻断，不重放不补预算；原主异常/取消、F1历史接受点/F2清理unknown禁止retry不变。详见§27.2和本批report。

定向双Python各77项通过；新增真实隔离父SIGKILL覆盖spawn前、Popen交接中、请求已发静默、含usage的部分流、done后清理竞态，核对worker消失、监管者实际wait退出、收据与journal关联；收据损坏后两次独立恢复仍pending/unknown/原额度、请求数不增。槽位耗尽、失败收据、既有双SDK正常/取消/usage及异常优先回归通过。finally探针回收补强后仅重跑新增4项双版及冻结SDK夹具，不因fixture修订无理由重复全量。初版backpressure清理缺口和两轮探针夹具错误均保留log/result，没有隐藏失败。

新构建仅在本批临时目录，复用已装PyInstaller/依赖、不pip安装/联网/替换应用；55个产品/入口冻结代码对象匹配当前源码。新exe双SDK direct ask/stream、生产同exe正常/取消、父硬SIGKILL（PATH禁外部Python）通过。最终全量计数及内部exit见report/results-summary；本批不重跑无变化的桌面其他检查，不声称新Electron发行包通过。普通Linux、监管者存活且子可杀范围以外不保证，Windows后续。

旧 `/var/tmp/feiyu-final-package-20261118/` 和正式留存全部原位不改；旧“当前源码匹配”及旧全量不覆盖本批产品差量，旧E/桌面局部证据仅作历史，不冒充新增U4证据。本批源码/命令/完整日志/收据观察/指纹及限制在新唯一批次目录，后续再更新正式留存。HEAD d82d943、未发布0.87.0及全部继承修改保留，无stash/reset/bump/提交/推送/发布/安装、真实provider/keys/history/memory/dream、付费或受阻LSP独立审查动作。U4/D/总验收交主控，不自行关闭；live评测接口和最终Electron发行包后续。


续作核验（2026-11-19，交Astra新独立审查）：原摘要未包含后完成全量，已逐个核对内部result/log。3.14全量1854/20skip/1834实际通过、exit0；3.10原全量240秒超时为-9，保留失败，不算通过。本次仅补3.10缺失全套覆盖：66模块分两批，分别796/1skip和1058/19skip，均内部exit0，合计1854/20skip/1834实际通过，不称一次全量运行。77项双版、最终4项双版与冻结SDK硬死smoke已完成且源码匹配，未重复。3.14全量开始早于最后fixture finally修订，该差量由最终4项/冻结smoke单列覆盖。

报告 `/var/tmp/feiyu-sdk-parent-lifecycle/20261119T052932Z/report.md` 已补齐，权威命令/结果/指纹在其resumed/；根旧摘要保留为中途快照。续作首次脱离会话启动未产出result，保留日志，新目录附着运行完成。未改产品/tests/build/版本；仅本设计/progress/交付矩阵追加事实，中英README现有Linux实施待审说明已一致无需重复修改。当前无本批匹配SDK进程，97个历史日志PID均已不存在，未发清理信号。旧E89/final-package当前源码及冻结匹配声明只适用当时快照，旧归档不改、新证据后续留存。普通Linux监管者存活且直接子可杀范围不扩大；Windows后续、远端撤销不保证；unknown不重放不补预算。保留HEAD d82d943、未发布0.87.0及全部继承修改，不接管受阻LSP审查，不代签U4/D/总任务书。


## Astra U4 有限关闭裁定（2026-11-19）

核对实施报告 `/var/tmp/feiyu-sdk-parent-lifecycle/20261119T052932Z/report.md` 和独立审查 `/var/tmp/feiyu-sdk-parent-review-20261119/report.md`：接受普通Linux、监管者存活可调度、直接SDK子可杀且本地I/O正常范围内的父硬退出监管。并发启动交接/请求已发后父SIGKILL、启动前保存失败、收据异常、恢复不重放不补预算及既有F1/F2定向证据通过；实际冻结55代码对象匹配。监管者死亡探针保留原异常和cleanup unknown，不承诺该边界自动回收。

审查两次3.10夹具兼容失败及其精确身份清理记录保留，最终兼容探针通过，不算产品缺陷也不计作成功样本。3.14全量1854/20skip/1834通过；3.10以两批66模块同覆盖，原单次超时仍为未完成。既有same-exe硬死smoke为核验继承证据，不冒称新审查实测。README中英状态同步；本裁定仅改文档，不重跑产品测试。

本节更新此前U4待审状态，不关闭D或总任务书。远端取消/费用、监管者同时死亡、不可中断内核及逃逸后代不保证。Windows后续；受阻LSP、历史Warning、live适配/收益、最终Electron发行产物与新增证据归档继续分列。下一步验证当前Linux桌面发行产物并增量留存证据，不安装替换、不提交推送发布，版本仍为0.87.0。


## Linux Electron 发行产物 U7/U8 增量交接（2026-11-19，待 Astra 裁定）

证据 `/var/tmp/feiyu-linux-delivery-20261119/report.md`。从当前 HEAD d82d943 的未提交0.87.0源码副本重新构建 UI及实际 Electron45.3.1 linux-unpacked、deb/AppImage；复用现有工具/依赖与 U4 payload-final，不联网安装。当前55代码对象逐项匹配；包内完整205个backend文件与U4最终产物清单一致，app.asar内Electron源码/新dist共23项字节核对通过。deb/AppImage只解包，主程序/app.asar/backend共207项逐项相同，未验证安装行为。

新证据内部exit0：打包可执行文件的桌面smoke/verify-trust；实际app.asar/isPackaged中文三段流式+合成session保存/重开且仅一次loopback HTTP请求；包内backend初始化/本地TLS/MCP/双SDK same-exe及父硬退出smoke；Node10项。没有重跑无变化双版全量：继承U4 3.14的1854/20skip/1834，3.10两批66模块同覆盖1854/20skip/1834，原单次超时仍未完成。旧54对象final-package和E89指纹只适用原快照。当前U4有限关闭依据及范围以上节Astra裁定为准。

首轮准备脚本未保留软链接导致manifest断言失败，随后provenance/UI/build依赖不可见失败；修正临时准备脚本后成功。新增中文夹具三轮失败（Electron属性取值、GET余额请求、事件JSON未解析）及deb检查缺dpkg-deb失败均保留；最终夹具/现有ar+tar替代解包通过，无产品修补。构建器报告node-addon-api/scheduler依赖路径警告，现有产物smoke/PTY通过，不扩张为所有可选依赖验证。最终/proc exe扫描无本批进程，无按旧PID清理。

必要双语README仅同步U4有限裁定和本次Linux产物事实。本批源码、工具/依赖指纹、精确命令/内部结果/完整日志/全部失败轮、发行产物及U4实施/独立审查/当前裁定增量保存到 `/home/Feiyu/AI_Agent/feiyu-agent-evidence/architecture-20261119/`，根0700，逐文件SHA复核；范围/排除见该目录RETENTION.md、archive-plan.json和index.json。保留至用户明确清理，原件/旧归档不变；非全历史或外部备份，不包含全部依赖本体/OS重建镜像及合成HOME缓存。U7已有当前Linux发行内容和已测运行证据，安装/Windows/macOS仍缺；U8本次增量可复核集交主控裁定，不自行关闭整任务书。U1—U3/U5/U6保持，不接管受阻LSP，不付费/真实provider或用户数据，不提交推送发布/bump/安装替换。迁移/回退本批仅文档：撤回本次明确段落，保留累计实现与unknown账本；未操作真实用户状态。


## Astra Linux发行产物与留存裁定（2026-11-19）

核对 `/var/tmp/feiyu-linux-delivery-20261119/report.md`：接受U7当前Linux x64发行构建及已测打包应用入口，unpacked/deb/AppImage已生成，包内backend完整205文件与U4产物一致、55代码对象一致，asar 23项匹配。实际packaged应用smoke/trust、中文三段流式与合成会话重开、包内MCP/SDK离线入口通过。失败轮次保留；没有产品修复，不重复无变化全量。此接受不包含系统安装/卸载、菜单注册、FUSE运行、Ubuntu22.04或Chromium sandbox部署（测试使用--no-sandbox），不等于发布批准。

接受U8新增最小本机留存：`/home/Feiyu/AI_Agent/feiyu-agent-evidence/architecture-20261119/`，根0700，1226项指纹核验，范围以RETENTION/index/archive-plan为准；旧归档不变，保留至用户明确清理。非全历史/外部备份/完整离线依赖。此次主控裁定晚于该归档，应在下一批增量保存。

下一项推进U6真实评测程序适配，以本地假服务验证期限、逐attempt用量/费用与授权边界，不执行付费评测，不宣称真实收益。受阻LSP和历史Warning继续保留；Windows后续。D及整任务书仍未整体验收，HEAD/0.87.0及全部未提交修改保持，无提交推送发布。

## U6 OpenAI SDK离线最小批次（2026-11-19，实施交接，未验收）

本批只改evals/tests及必要双语文档，保留HEAD d82d943、未发布0.87.0及全部累计改动，产品/发行包未变。先写设计，再以eval-only SDK子进程接execute期限seam，禁止隐式SDK retry；父账本请求前预留unknown，正常/异常/取消均留attempt。同一观察期限覆盖静默、半帧和写背压，finally杀组/回收/关闭；不覆盖评测父进程同时死亡或远端撤销。复用双源码/原生OpenAI参数/实际工具、摘要和恢复路径，不借用当前产品替代baseline。固定价格usage估算与供应商invoice分开；partial usage下界留存，未知费用null并停止。`loopback`仅合成key+literal本地假HTTP，live在读配置前固定exit2。授权入口仅实现缺失/完整契约均拒绝的gate，正向授权/专用凭证读取/远端启用未实施。

双Python final3-target各76项/6skip/70实际通过、内部exit0；locked-loopback各8条，executor/verification/compaction双臂success，recovery双臂agent_failure，快照unknown阻断不冒充完成。前轮httpx与已装SDK httpx2不匹配失败保留；适配客户端声明接口后通过。实际保存失败的environment_failure及账本日志留存；副本SDK max_retries=1负对照预期红。精确命令、内部result/log、设计、冻结源码/结果hash及限制见 `/var/tmp/feiyu-eval-sdk-adapter-20261119/report.md`。没有无变化产品全量/桌面重跑；原U4/U7/U8证据范围不扩大。

完整协议见architecture-evaluation末节。剩余：Anthropic原生产品路径、正向授权/凭证契约验证、受审远端SDK与真实账单适配、供应商版本/endpoint确认、真实开发/保留任务重复运行与收益报告。全部仍synthetic/全快照混杂；旧synthetic整包改标拒绝不变。普通Linux范围U4、U7及U8既有有限接受保持；Windows后续，LSP独立审查仍受阻、历史Warning保持，未接管替代。无付费、真实用户状态、stash/reset/bump/提交推送发布/安装替换。交Astra新独立审查，不自行签U6/D/总任务书。


## Astra U6 R1/R2修复交审（2026-11-19）

R1：execute捕获取消类BaseException，保存requests/events/ledger失败快照后重新抛出原取消；写盘失败附controller_persistence_error并输出诊断，不置零成本。R2：HTTP响应流包装在SDK解析之前检查原始JSON/SSE usage严格整数（排除bool），有界8MiB缓冲；SDK本身和原生参数路径保留。新增实际SDK流/非流false/true用量停止准入、实际execute取消持久partial账本两项回归。

双Python最终各78项/6skip/72实际通过，内部exit0，证据 `/var/tmp/feiyu-eval-sdk-fix-20261119/suite314/` 和suite310。初版只查SDK对象字段仍失败，已改原始HTTP层；首次3.14命令误列不存在test_architecture_cases报import error，记录保留，最终命令为sdk/execution/architecture_evals/test_evals四模块。仅evals/tests和交接文档变更，不重跑产品桌面。未关闭R1/R2，交新独立复核；live仍拒绝、无真实收益，Anthropic/授权/账单等缺口保持。无提交发布或付费。


## Astra U6 R1关闭、R2 SSE分帧补修（2026-11-19）

核对 `/var/tmp/feiyu-eval-sdk-fix-review-20261119/report.md`，限定关闭R1：普通取消后requests/events/attempt/partial usage及null成本持久化，原异常对象与清理保持，写盘失败有附加异常和stderr诊断。R2原HTTP guard在CR-only或缺Content-Type时绕过，继续保持开放至新复核。

R2补修按请求stream模式选择原始校验，不再靠响应Content-Type；校验副本将CR/LF/CRLF按跨chunk状态分行，事件完整时先检查usage再交原始字节给SDK；正常流原字节不改，8MiB边界保留。实际SDK false/true回归扩为非流/LF/CR/CRLF/无头。双版四模块各78项/6skip/72通过；改编原审查探针每版29观察全部达到修复断言（不再排除CR/缺头），内部exit0，正常整数兼容；原R1保存失败断言也通过。3.14所有单切点/缓冲界限探针通过。日志中的本地服务BrokenPipe来自无效响应被客户端拒绝后断开，未抹日志。

证据 `/var/tmp/feiyu-eval-sdk-r2-sse-fix-20261119/`，各轮内部result带argv/env/exit和完整log，源快照及hash保存。未改产品/包/旧归档，不全量桌面重测，不提交发布或付费。下一步独立复核R2，不代签U6/D/总任务书。


## Astra U6 R2有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-sdk-sse-review-20261119/report.md`，接受R2在当前OpenAI SDK 3.51.0 eval-only loopback兼容层有限关闭。双版108条独立观察和3.14切点/上限探针通过：CR/LF/CRLF、缺头、跨chunk、多data行及DONE后不EOF，异常原始usage均在SDK转换前拒绝，成本null并停止准入；正常整数兼容。R1已关闭范围保持。当前修复双版78/6skip/72通过证据继承，不冒称新全量。

此结论不扩展到未来SDK/任意HTTP编码或通用SSE保证，不验收U6/D/任务书。下一批补Anthropic原生评测路径，仍只用合成本地服务；正向远端费用授权、专用凭据、真实账单/远端模型版本和收益未完成，live保持拒绝。产品包不变，无提交发布或付费。

## U6 Anthropic原生离线实施交接（2026-11-19，未验收）

新增`anthropic-loopback`：冻结HEAD/snapshot分别调用各自AnthropicBackend，保留原生system/messages/tools、tool_use/结果往返、nonstream辅助compact及session恢复。实际安装SDK 2.8.0只连literal loopback合成服务，禁隐式retry/代理/重定向。Messages SSE与OpenAI协议差异先记录于新证据design；共享有界HTTP分行但独立usage语义。累计输出、缓存输入和nested TTL明细不重复计费，bool等在SDK转换前拒绝，partial下界/完整费用null停准入；固定合成价格和真实invoice分开。父deadline/取消持久化及原异常优先沿用，未接管LSP审查。

证据 `/var/tmp/feiyu-eval-anthropic-20261119/`，精确命令/内部exit/log、失败轮次、负对照、冻结源码与产物指纹见report/commands/fingerprints。双Python最终五模块各86项、6skip、80通过，内部exit0；取消正常与controller保存失败均保留原异常。首轮产品观察因原生TextBlock无法RPC JSON序列化而失败，修正eval边界的SDK对象序列化后重跑；3.10中间轮因实现期间源码变更被源锁拒绝，保留失败日志。native采样配置最后改为null表示产品未显式指定，并重新生成锁；不伪称显式temperature=0。四组两臂执行与OpenAI保留观察的精确最终结果见报告。恢复仍agent_failure，不删除未知操作拒绝/基线重复请求事实。副本去掉raw guard，false被SDK转换成0并错误成功，负对照如期红，原件不stash。

R1/R2既有限定关闭不扩大；U4/U7/U8裁定保持。live在配置/凭据前exit2；正向远端授权、专用凭据/费用、真实账单/收益均未交付。全快照混杂、Windows后续、LSP受阻及历史Warning保持。仅evals/tests/必要双语文档改变，产品及Linux发行包、HEAD d82d943/0.87.0和继承修改保持；无安装替换/提交推送发布。交Astra独立审查，不自行验收U6/D/任务书。


## Astra Anthropic AR1终态修复交审（2026-11-19）

针对 `/var/tmp/feiyu-eval-anthropic-review-20261119/report.md` 的P2，父适配complete显式检查原生stream事件顺序：message_start未提前停止、message_delta含有效终态停止原因和output计数、随后message_stop；重复/逆序/缺失终态拒绝。SDK final snapshot/HTTP EOF/child done不再单独证明完成。非流Message校验独立保留；失败保留已观察usage下界、cost=null并阻止账本继续准入。原始HTTP usage校验与产品代码未改。

新增真实SDK正常/缺stop/缺delta/start提前完成回归。双版五模块各87项、6skip、81通过、内部exit0。原独立10模式探针改为缺stop和start提前完成也必须失败，双版各10观察全部符合断言。修复后两版各8个四组原生产品观察通过布线检查，前三组双臂success、恢复双臂agent_failure，未冒充恢复任务完成。证据 `/var/tmp/feiyu-eval-anthropic-fix-20261119/` 含source/hash、每轮argv/env/内部result/完整log与产品源锁；本轮无失败测试，故障注入stderr如实保留。

AR1仍待新的独立复核，不自行关闭U6/D/任务书。全部本地synthetic，无真实模型费用/收益，无产品包变化、提交推送发布，HEAD/0.87.0保持。Anthropic正向远端授权/专用凭据/真实账单仍未完成。


## Astra Anthropic AR1有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-anthropic-fix-review-20261119/report.md`，接受AR1在Anthropic2.8.0受控eval路径有限关闭：双版各27实际SDK观察和12父层断言通过，旧semantics负对照复现原缺陷；缺失/逆序/重复终态保持下界/null成本并停止准入，正常工具块/非流保持。原始guard/共享adapter/child未变。继承双版87/6skip/81通过及各8原生观察已核对，不称新重跑。

原审查指纹唯一不符为finalize314/full-314.log，源于指纹扫描后同一脚本继续打印日志；该自指生成限制和provenance首轮失败保留。其余旧条目匹配，修复源码、产品观察与新独立证据匹配；不宣称旧清单全部字节吻合，下一次归档排除运行中的自生成文件，结束后另核验。

U6两供应商原生离线最小路径具有限接受证据，但正向远端授权、专用凭据、真实账单/远端版本与收益仍未交付。下一批实现可离线审核的授权契约/预算与输入绑定，真实网络执行继续默认拒绝，未获费用授权不调用provider。未验收U6/D/总任务书，无提交推送发布，产品和Linux包保持。

## U6正向本地授权契约/离线预检（2026-11-19，实施交审）

先读适用约定、§6/7与最新AR1裁定，design先存 `/var/tmp/feiyu-eval-authorization-20261119/design.md`。新增eval-only严格计划/显式批准记录/观察输入匹配及template/preflight CLI；require_remote_contract可返回本地有效JSON收据，固定provider/HTTPS endpoint/模型及SDK版本、双源码/依赖/解释器/提示/任务/采样lock、run/time/费用/秒/物理请求cap与固定估算政策。未批准模板不默认批准或捏造批准者；异常类型/NaN/Infinity/到期/漂移/预算扩大拒绝。凭据文件只引用不解读。hash和caller-supplied record不能证明可信宿主、真实用户身份或本会话费用授权，预检不消费批准，不实现实际lock文件测量。

最终run.py fresh HOME/XDG白名单及240秒硬超时，唯一D_RUN：final314/final310各93测试、6skip、87实际通过，内部exit0，runner分别101.677850/121.977289秒。optimized双版各6项exit0；synthetic receipts/template/计划hash保存。副本仅删除observed绑定，双版各18失败子断言、内部exit1，证实检测输入漂移。首轮helper KeyError及3.10既有取消usage断言失败、首次负对照cwd未切副本（原实现正对照）全部保留；最终完整轮通过不冒称已证明取消时序失败成因。

原生产品接线按改动范围各选一版：native-openai314与native-anthropic310内部exit0，各8个双源码实际产品+合成本地HTTP观察，各6 success/2 recovery agent_failure；不把恢复unknown阻断当完成，不混synthetic/real。两版定向suite仍覆盖两原生SDK。未重跑产品全量/桌面/包。报告含精确内部命令/完整失败、最终源码/源锁、plan/receipt、非自指指纹及结束后另核验；不扫描仍写入的finalize日志冒充完整证明。

live保持配置/credential前exit2，两SDK仍只接受synthetic literal loopback。真实安全凭据摄取、HTTPS接通/供应商版本与费用核实、批准来源认证、single-run批准消费/重启持久预算和真实invoice对账仍未实现。后续由主控对最终具体计划取得用户费用批准，独立审查真实控制器；网络前原子消费run批准、逐attempt预留，重启保留已花/unknown与deadline，请求失败不假定免费，unknown阻断不补额。本次委派不是费用授权。交Astra独立审查，不代签U6/D/总任务书，真实模型收益尚未验证。

仅evals/tests及必要双语README/evaluation/delivery/progress事实改变；产品/包、HEAD d82d943/0.87.0和累计未提交修改保持，无stash/reset/bump/安装替换/提交推送发布、真实provider/凭据/keys/history/memory/dream、子代理或受阻LSP接管重试替代。U4/U7/U8限定裁定、Windows后续和历史Warning限制保持。完整证据 `/var/tmp/feiyu-eval-authorization-20261119/report.md`。


## Astra U6本地授权预检有限接受（2026-11-19）

核对 `/var/tmp/feiyu-eval-authorization-review-20261119/report.md`，接受本地契约语法/输入匹配/预算估算/未批准模板及预检收据限定范围。双版各5独立测试通过，删除observed绑定的副本负对照均预期失败；604旧指纹及30最终源码匹配，live/远端transport拒绝保持。不是批准来源认证、实际锁测量、用户费用授权或真实账单证明。

首轮3.10取消用例usage={}而预期8/2仍保留为未解释证据：1.5秒计时未与父层已观察事件同步，现有日志不足区分取消早于帧到达和已观察事实丢失。不据后续通过宣称根因修复，不无限重跑。后续若调整此夹具应增加可观测同步再作诊断，独立列明，不改变产品语义。

下一批补实际输入锁测量与测量预检，仍离线、不得读取真实凭据或发远端请求。单次批准消费/恢复预算及真实执行/账单/收益继续未完成。无提交发布或产品包变化，不验收U6/D/任务书。

## U6实际输入测量/测量预检（2026-11-19，实施交Astra，未验收）

新增eval-only `architecture_measurement prepare/measure/preflight`：真实freeze/verify_package双源码及Git基线内容，实际解释器/依赖文件manifest，完整config/schedule/开发保留任务/judge/tools/采样绑定；复用隔离worker hello/environment/origin握手，16次原生初始请求均在transport前停止。v2计划显式区分pre-send原生构造器system/task/tools/source锁与含任务UUID/时间/预算事实的actual full system/parameters逐request绑定；不声称未来完整prompt事前固定。v1 caller-only语法契约保持，测量预检仅v2、重新生成observed，不接受调用方manifest冒充测量。输出未批准模板false/null；测试中的批准全为synthetic，不是本会话费用许可。

最终定向回归双版各16项/0skip通过（内部结果final314-v2/final310-v2）；离线CLI两provider的prepare→未批准拒绝→合成批准重测、跨解释器拒绝及删除重测的隔离副本负对照结果见 `/var/tmp/feiyu-eval-measurement-20261119/report.md` 与commands-results。首轮错误把动态system当固定锁导致正向拒绝、CLI长路径recovery多余socket失败及修复前各轮均保留，未隐藏失败。仅测量模式省去不需要的recovery service/prepared额外RPC，正常SDK生命周期不扩展。

源码/依赖/config/schedule/judge/prompt构造器/采样漂移、假锁/旧v1/不同解释器、缺失输入/测量失败、到期/预算扩大拒绝覆盖。测量是本机字节绑定，不是恶意host/批准者身份证明；runtime明确限解释器文件/版本与purelib/platlib树，不是OS/完整stdlib镜像。live仍在配置/credential前拒绝，两远端transport仍拒绝；credential引用不解读。单次批准消费、恢复持久预算、真实凭据/远端版本价格/账单/收益仍未实现。原1.5秒取消usage{} vs8/2未解释失败保持，本批不重跑来冒充修复。

R1/R2/AR1与U4/U7/U8限定裁定保持，Windows后续、受阻LSP及历史Warning不变。HEAD d82d943/0.87.0、产品/Linux包/旧归档及全部继承修改保持；无子代理、真实provider/凭据/付费/用户数据、stash/reset/bump/安装覆盖/提交推送发布。不代签U6/D/整任务书，交Astra新独立审查。迁移无真实用户状态操作；回退仅撤回本批measurement文件/测试、窄eval协议扩展及追加说明，保留继承实现和证据。


## Astra U6测量优化模式修复交审（2026-11-19）

按 `/var/tmp/feiyu-eval-measurement-review-20261119/report.md` 的P2，在CLI、measure、preflight公共入口用不依赖assert的auth.need(__debug__)拒绝-O/-OO，先于输入读取/输出创建。新真实子进程回归覆盖三个CLI命令及两个导入入口；普通测量/授权/执行定向双版各17项、0skip、内部exit0。证据 `/var/tmp/feiyu-eval-measurement-fix-20261119/`，内部命令/env/结果/log、修复源码hash与快照均保留。未改产品包/版本，不提交发布或付费。本P2待新独立复核，不验收U6/D/任务书。继承的Anthropic无transport scripted恢复组合KeyError及定时取消未解释限制保留，不称本批修复。


## Astra 测量优化模式P2有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-measurement-fix-review-20261119/report.md`，关闭当前测量CLI/measure/preflight优化解释器绕过P2。双版各18条独立命令覆盖原非法删减配置、-O/-OO、缺输入优先拒绝、导入访问trap与正常非法配置拒绝，无测量/预检产物；当前源码双版17项普通路径证据已匹配。仅此入口范围，不扩为全产品assert保证。

U6实际输入测量/本地预检具有限接受证据；调用方批准来源并未认证，测量收据不赋予远端权限。下一项补一次性批准消费和运行预算持久化，验证仍只用临时合成记录/本地transport，不发真实请求。单次消费/重启保留额度/unknown不重放的控制器必须先完成并审查，实际费用授权另行取得。既有取消时序及scripted Anthropic恢复组合限制保留。无提交发布或产品包变化，不验收U6/D/整任务书。


## U6单次合成批准消费/持久预算（2026-11-19，实施交Astra，未验收）

设计先存 `/var/tmp/feiyu-eval-durable-budget-20261119/design.md`。新增独立eval-only Linux Controller API，create真实v2重测/严格预检后，在同一原子registry同时消费record并绑定run/plan/measurement；flock持有到派发/落盘，重复create及同批准新run拒绝，恢复只显式resume。每物理attempt先fsync预留，内置子进程fake调用后保存事实；重启不重置次数/已知估算/partial/unknown/原截止，pending转unknown阻断重放。全局预算跨观察/辅助/重试且只能收紧，原逐观察限制额外叠加；未知成本null，supplier invoice独立null。保存失败先阻断；执行后保存失败保留原异常、partial事实及persistence_error，不冒称未执行。预留耗尽截止则在派发前拒绝；replace后目录fsync失败也不允许再次消费。

最终源码双Python各25项（持久控制器/授权/测量/父Ledger），0skip、内部exit0，130.02/123.09秒。此前双版各46项含完整两SDK定向回归，0skip、内部exit0，209.99/221.64秒；之后只补durable派发前截止检查及其测试，两SDK模块未改，不冒称最终源码重跑46项。

真实临时子进程覆盖消费replace前/消费后、预留后与调用已发未落盘死亡、锁冲突/恢复unknown禁重放；失效批准/输入、预算扩大、跨boot、磁盘写/replace/fsync故障、已知失败/partial及原异常保留均有定向断言。最终双版副本负对照各两处删除预留/次数检查，均按预期exit1，外层核验器内部exit0。新HOME/XDG白名单、独立绝对D_RUN、原run.py硬240秒，核对内部result和log。初轮夹具tuple错误及测量中改源码导致漂移拒绝日志均保留，不混作最终通过。新报告/protocol/源码快照/hash/命令结果和新进程恢复实物均在证据目录，无自指manifest。

未接入产品观察调度/判题或远端transport；这是允许的独立API最小实际组合，不声称跑完完整schedule。批准/自带hash仅caller evidence，非真实用户费用授权/可信宿主/身份认证；同一持久registry是所有协作writer必须共享的本地边界，恶意同UID、删除回滚/另建副本registry、远端撤销不在范围。真实credentials/HTTPS/账单/收益继续未完成，估算cap不是供应商账单保证。保留1.5s取消usage{}vs8/2与无transport Anthropic scripted KeyError限制，不扩修、不重试受阻LSP审查。产品/U4/U7/U8/Linux包、HEAD d82d943/未发布0.87.0及累计修改保持；无子代理、真实keys/history/memory/dream读取、付费、stash/reset/bump/提交推送发布/安装替换。Windows后续。迁移回退保留完整registry和证据，不清unknown或复制旧ledger补额。交Astra独立审查，不自验U6/D/任务书。


## Astra durable R1/R2修复交审（2026-11-19）

按 `/var/tmp/feiyu-eval-durable-budget-review-20261119/report.md` 修复两P2。R1恢复任何校验/持久化异常即毒化句柄，后续invoke和resume拒绝，不能因捕获原异常继续派发。R2观察绝对截止从首条reserved_at推导，预留落盘后再次检查，physical timeout与调用后检查均取全局/观察截止较小值。超期前未派发仍保留reservation为unknown，不补额度；真实结果已返回则先保存事实再报告超期。

双版durable套件各9项通过（含实际create/preflight/恢复），随后新增的timeout传递及执行后事实保存回归双版各1项通过，内部exit均0；不能称套件运行时已含最后新增方法。无产品/SDK/包变更，不重跑不相关全量。证据 `/var/tmp/feiyu-eval-durable-fix-20261119/` 含精确argv/env/内部结果/log和源码快照。两P2待独立复核，不验收U6/D/任务书，不付费/提交发布。


## Astra durable R1/R2有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-durable-fix-review-20261119/report.md`，接受两P2在独立synthetic API限定关闭。真实公开测量/create后，双版恢复源/runtime/绑定/保存/中断等失败均毒化句柄；捕获后invoke/resume/tighten/create不能恢复派发。合法120秒观察限额下慢保存越界零派发并留unknown，真实子进程timeout取全局/观察较小值，实际结果后超期先保存事实再报停止。复核分轮夹具失败/修正记录保留，不称一次最终全套通过；3165指纹无变化。

本批独立控制器具有限接受证据，尚未两SDK/schedule持久接线。下一批将已审原生loopback评测接入同一持久run账本，跨观察/辅助/重试不重置预算。live/远端授权/专用凭据/HTTPS/真实账单收益继续未完成，不将本地合成批准解释为用户费用授权。无提交发布，不验收U6/D/任务书。

## U6 durable→原生SDK产品loopback交接（2026-11-19，实施未验收）

先读适用约定、任务书§6/7、evaluation和durable R1/R2有限关闭报告；协议先存新证据design.md。`architecture_durable.Controller.execute_loopback`验证已消费v2测量包/源/runtime/观察身份后启动真实冻结产品worker；新增DurableLedger视图绕开旧Ledger计费，主/辅助/重试物理SDK请求统一由父Controller预留、截止与保存结果。观察先持久化启动身份，整题不隐式重放；未知保留下界/null并全局阻断。实际原生request/system、来源arm/source及transport收据绑定，预留后再检截止/超期事实先保存/失败resume毒化保持。OpenAI原始SSE与Anthropic message_stop代码未改。

最终小规模产品链：OpenAI/3.14和Anthropic/3.10各1集成方法内部exit0，各8观察、36物理SDK请求，6 success/2 recovery agent_failure；真实prepare→create重测/consume→原生本地SDK→持久结果→新进程resume/拒绝整题重放。两SDK不称在每个解释器各跑完整产品链。定向双版5新增边界通过；后增同步实际SDK取消/timeout各1通过、保存崩溃证据再跑各1通过。原四模块3.14共39通过；3.10共39中38通过、继承Anthropic 1.5秒定时取消usage{}vs8/2再次失败，内部exit1，未重跑洗绿/未宣称根因修复。新增同步用例只证明已经observe的usage保存，不解释旧失败。双版删除reservation提交、删除全局次数检查两种内存副本负对照均预期exit1；live双版exit2，缺失config前拒绝。

失败保留：首轮抽取漏计价变量；外部脚本缺仓库sys.path；两初次产品链实际断言已通过但copytree复制Unix socket归档失败（内部exit1）；修正仅归档排除socket后在新目录重跑通过。测试文件运行期间新增方法导致旧Python traceback引用行文本漂移，原日志不修饰；最终源码单独快照。完整精确命令/env/内部exit/log、registry/测量包/原生收据、崩溃73/74与resume unknown、失败轮次及最终指纹见 `/var/tmp/feiyu-eval-durable-sdk-20261119/report.md`。

只支持development/repeat=0；完整96观察schedule/holdout/repeats、持久judge到严格aggregate行出口、未完成观察人工处置/跨文件事务未实现。registry为预算权威，不从controller.json补额。固定估算不证明远端token上界/真实账单，凭据摄取/HTTPS/真实远端/费用授权/收益均未实现；live继续拒绝，全部合成、本地HTTP、假key、runner隔离HOME/XDG。旧取消时序、无transport Anthropic scripted恢复组合、恶意同UID/registry回滚、父硬死SDK监管、Windows、受阻LSP和历史Warning限制保持。

交主控/Astra独立审查，不自行验收U6/D/任务书，不接管LSP、不启动子代理。仅evals/tests与相关设计/进度/矩阵文档改变，未操作真实凭据/用户历史/费用，HEAD d82d943/0.87.0/产品/Linux包及全部继承修改保持，无stash/reset/bump/安装/提交/推送/发布。回退只撤本批增量，保留完整registry/unknown与证据，不能删除或复制账本补额度。


## Astra：adapter 副本绑定修复待复核（2026-11-19）
独立审查发现实际 adapter 未绑定已消费快照。已补严格两文件清单/字节/普通文件及软链接检查：持久入口在 observation-start 前检查，共用执行入口在创建输出/启动 worker 前检查，测量结束再次检查。公共 create 后 worker/runtime 改动、缺失、软链接、额外文件均拒绝，账本不新增 reservation；恢复副本后真实本地 OpenAI 路径成功。
双 Python 定向各18项通过、内部exit0；首轮夹具失败完整保留。待新的独立复核，不自行关闭本条 P2，不验收 U6/D/任务书。Anthropic3.10 定时取消、完整schedule/live及原限制保持。证据：/var/tmp/feiyu-eval-adapter-fix-20261119/report.md。


## Astra：adapter R1 有限关闭（2026-11-19）
已核对独立复核 /var/tmp/feiyu-eval-adapter-fix-review-20261119/report.md：实际公共 create 路径在 OpenAI3.10、Anthropic3.14 分别覆盖15类拒绝、恢复正常副本、真实SDK负对照和测量结束重核，durable R1/R2定向未回归。接受仅限合作式本地执行前一致性，不提供恶意同UID并发置换防护，不代表双provider双版完整集成。原adapter P2按此范围关闭。
Anthropic3.10定时取消仍未决；下一批优先定位取消时序及已观察用量持久化边界，不能用同步探针通过替代根因解释。完整schedule/live及原平台/LSP/其他限制保留，不验收U6/D/整任务书，无提交发布。


## U6 取消时序实施交审（2026-11-19，历史失败仍未归属）

证据 `/var/tmp/feiyu-eval-cancel-timing-20261119/report.md`。原 Anthropic Python3.10 的 1.5 秒定时测试在原生子进程启动前开始计时，断言 8/2 缺少「父 observe 已记录用量」前提；历史失败日志只有最终 `{}`，没有 HTTP/child/父 observe 阶段时间，不能归属为启动慢、IPC延迟或已观察事实丢失。本轮确认测试语义缺陷并修测试，未确认产品缺陷，未改产品；历史轮继续未决，不能用新同步通过替代历史归因。

原已观察取消方法改为真实父 observe 完成后触发 SIGALRM，8/2、原异常 identity、unknown/null费用、保存失败与child回收断言保留/加强。另保留真实原生HTTP到达但服务端尚未发送首用量的提前取消用例，明确空用量仍为未知、费用null。新增两SDK持久矩阵覆盖上述两时点各自保存成功/真实atomic保存失败：保存成功保留已知lower bound；失败仅异常/内存保留已知事实，磁盘仍reserved，新解释器resume转unknown且不补额、不补造用量。

带时间戳探针对真实本地SDK/HTTP、child send、父observe/取消、registry保存及新进程resume建立事件链；server flush本身不等于父已观察。进程回收与父退出73/74的窄边界、两SDK原验证器与durable接线已做双3.14/3.10定向验证，精确分轮内部结果/源码指纹见报告；没有双provider双版全8观察重测或完整96 schedule。adapter R1有限关闭保持。live仍拒绝，未真实密钥/历史/远端/付费，未接管LSP，HEAD d82d943及未发布0.87.0/产品包/旧归档/继承改动保留，无提交推送发布安装改版本。交主控安排新的独立审查，不自行验收U6/D/整任务书。

本轮宽定向双版各40项中39通过、1旧OpenAI故障注入夹具被adapter一致性门禁拒绝；失败原样保留。随后仅修复该合成夹具的冻结worker/adapter/hash一致性并双版补测，结果见报告，不称最终40项整套重跑全绿。


## Astra：取消测试语义有限接受（2026-11-19）
已核对 /var/tmp/feiyu-eval-cancel-timing-review-20261119/report.md，接受同步前提修订、独立提前取消、两SDK受控四分支持久化/恢复证据和session-save合成夹具修正。独立双Python各4方法通过；取消后用量不更新的负对照被严格8/2断言捕获。未确认产品缺陷，本批未改产品。旧40项各1 error与后续单项补验分别保留，不宣称修后整套全绿。
历史Anthropic3.10失败仍未归属，不能由当前同步成功关闭历史原因，也不证明任意取消窗口。下一批补齐离线schedule/holdout/repeats与durable结果导出；live/真实账单及原限制保持，不验收U6/D/整任务书，不提交发布。


## U6 schedule/export 实施交接（2026-11-19，待主控独立审查）

已实现配置生成的完整arm/group/split/repeat调度、同一持久父账本跨批次/进程续接，以及从registry独立判题证据导出的v2结果与严格aggregate；保留旧schema/数值/防改标门禁，controller.json仅诊断。原始预算不补额，started/interrupted/unknown不重放；人工解除中断尚未实现。协议与短AF_UNIX路径要求见architecture-evaluation最新节。

实测严格分列：OpenAI/3.14 72/96评分、360请求，72 success，首个recovery因证据长路径AF_UNIX失败留1 interrupted/23未开始，后续仍exit2；不能宣称该全计划通过。Anthropic/3.10 96/96评分、432请求，72 success、24 recovery agent_failure；48观察后迁短measured路径沿用同一registry/plan/预算完成，batch-05退出状态未收集单列null，其余命令内部退出码见证据。另两provider/runtime组合未完整运行。全快照混杂/合成布线，不是live或模型收益。

双版五模块各39项、原生边界各5项、最终调度/导出各9项分别通过，精确源码时点不合并冒称单次全绿；导出真实registry审计各20类、优化模式/live拒绝、有效负对照见 /var/tmp/feiyu-eval-schedule-export-20261119/report.md。全部源漂移、长路径、测试异常类型与负对照探针失败保留。旧40项error/单项补验分别保留，历史Anthropic3.10定时失败仍未归属，adapter R1/durable R1/R2有限关闭不扩大。

只改eval/tests/相关docs，不动产品包/HEAD d82d943/0.87.0与累计修改，无真实凭据历史/远端付费、受阻LSP、提交推送发布安装改版本或子代理。不自验U6/D/整任务书。迁移回退必须保留完整registry及证据，不能清除中断或回滚预算；真实授权/凭据/HTTPS/账单/收益及人工处理仍缺。


## Astra：schedule/export 两项P2修复待独立复核（2026-11-19）
长路径在批量计划派发前及direct observation started前按物理路径字节数检查；socket bind/listen纳入finally关闭。完整SDK receipt增加类型、用量映射、请求摘要、模型/SDK/源码/runtime、费率与结算绑定，未知记录不升级。
双版最终schedule各12项、公共create各1项通过；真实旧72/96记录只读导出及每provider14类重算hash后receipt异常拒绝通过。初轮发现原严格浮点相等误拒正常Anthropic费用，加入极小舍入容差，失败保留。此前双版27项是最后修订前快照，未冒称最终全量。旧OpenAI中断run未解锁/重放，Anthropic batch05 exit仍null，历史取消未归属。证据 /var/tmp/feiyu-eval-schedule-fix-20261119/report.md；待新独立复核，不自验U6/D/任务书。


## Astra：receipt R2有限关闭；R1规范路径补修待复核（2026-11-19）
已核对 /var/tmp/feiyu-eval-schedule-fix-review-20261119/report.md：R2在合作式本地synthetic导出范围有限关闭，双版每provider27类故障拒绝及费用容差边界成立。未知/partial不升级，非真实供应商账单。
R1剩余pad/..缺口已补：check_service_path返回已校验的物理Path，共享execute将同一Path用于bind及sandbox挂载，去除原始路径重建。双版公共create含20层pad/..真实recovery回归、schedule/execution各共20项通过、内部exit0；recovery保留agent_failure/3请求/finished。待新独立复核，旧run无解锁重放。证据 /var/tmp/feiyu-eval-socket-canonical-fix-20261119/report.md；不验收U6/D/任务书。


## Astra：socket R1有限关闭与完整规模补证（2026-11-19）
已核对 /var/tmp/feiyu-eval-socket-canonical-review-20261119/report.md，R1在合作式Linux synthetic范围有限关闭。双Python新公共路径的20层pad/..均维持agent_failure/3请求/finished，预检-bind-挂载一致；独立负对照复现原错误，长物理路径、symlink、107/108及异常关闭边界通过。R2既有限关闭保持，不扩为U6/D/总验收。
下一批在固定源码、新独立计划与短物理路径补齐OpenAI完整96观察；旧72/96中断run不解锁不重放，Anthropic旧batch05 exit=null与历史取消未归属保持。不拼接新旧run为完整通过，不提交发布。


## U6 新独立 OpenAI3.14 完整计划补证（2026-11-19，交主控审阅）

证据 `/var/tmp/feiyu-eval-openai-completion-20261119/report.md`。固定当前源码，新独立run/record，短物理非symlink目录 `/var/tmp/foc19/m`，全96路径预检最长61字节；公共prepare→create实际重测/preflight/原子消费→24批新进程→registry export/严格aggregate，均取得真实内部exit0。96/96评分、96 finished：72 success、24 recovery agent_failure原判据保留；432物理请求（408 primary/24 auxiliary，全部attempt1、无实际retry），未知0。仅本地原生OpenAI SDK/Python3.14.10合成HTTP，不是远端或真实模型收益。

全局上限在prepare前固定1000请求/7200秒/1 CNY合成估算，逐观察30轮/120秒/3 CNY/2 attempts未变。23项定向审计通过：24批同plan/measurement/record/started/deadline/limits，entries前缀连续，累计费用单调、无补额；导出/局部重算hash后的judge/request/receipt篡改拒绝，已消费身份不能重用，三类增额拒绝。审计前后registry不变；live仍在配置/凭据前exit2。所有内部exit/完整日志和恢复失败、连续性全快照、源码/依赖/解释器前后指纹及完整执行包已保留，日志结束后散列。244工作区文件、6183依赖文件未漂移；测试结束后才追加本三文档。

旧OpenAI72评分＋1 interrupted/23未开始保持，未解锁/重放/回填，新run不填旧缺口。Anthropic3.10原96/96、432请求只读继承核对；不是当前源码重跑，更不是双provider双Python版全量。旧Anthropic batch05 exit=null、历史定时取消未归属、旧40项error及单项补验分列、受阻LSP和历史Warning继续保留。socket R1/receipt R2沿用有限关闭。

当前本地完整调度/holdout/repeats、同一持久预算、实际preflight/合成消费、权威judge导出/aggregate均已实现并有本批完整规模证据，不再列作缺实现。仍缺远端正向授权消费/批准来源认证与撤销、专用凭据摄取、受审HTTPS/live期限/取消/用量及供应商账单适配、真实版本/费率确认及授权后真实收益；本地合成消费不授远端权限。interrupted/unknown人工核对解除、generic eval父硬死监管、跨boot等加强边界未新增。仅证据缺口另列：当前源码Anthropic3.10完整96及OpenAI3.10/Anthropic3.14组合未重跑，真实收益/缓存收益/远端费用语义未实证。

下批可审本报告、audit.json、24批registry/连续性、export/aggregate及前后源码/依赖指纹，裁定是否接受本run完整规模证据；不需重建旧run或重跑无关产品/桌面。无真实凭据历史/远端请求/费用授权/付费，无子代理、版本/包/HEAD d82d943变更或提交推送发布安装。仅更新三文档真实状态，不代签U6/D/任务书。回退只撤本段与交付矩阵本次更新，完整保留新旧账本/测量包/证据，不回滚预算。


## Astra：完整离线证据接受与收尾范围裁定（2026-11-19）
核对 /var/tmp/feiyu-eval-openai-completion-review-20261119/report.md 后，有限接受新OpenAI/Python3.14本地synthetic完整96执行证据：72success/24recovery agent_failure、432请求、24批预算连续，非真实模型收益。旧Anthropic证据沿用既定版本范围，旧batch05 null及历史取消未归属均保留。
任务书§6明确无付费授权可交配置、命令、格式并说明真实收益未验证；§7允许逐项具体阻碍。因此本次收尾不增加远端批准平台、凭据摄取、HTTPS/live账单等新实现门槛，不推进F。进入最终回归核对、逐项交付矩阵与增量证据留存。LSP受阻审查等必须在最终结论显式列出；不得将限定交付说成所有验证通过或模型收益已验收。仍不提交/推送/发布。


## 最终收尾交接（2026-11-19，供主控审阅）

主控已有限接受新OpenAI3.14完整96本地合成规模证据；按§6无付费授权与§7逐项阻碍路径交付，不新增远端平台/凭据/HTTPS账单或加强边界，不推进F。最终主体矩阵、七项条件和最小命令见[交付文档](architecture-delivery.md)。

- Python 3.14.10: 1919项，1899实际通过，20 skip，0 failure/0 error；14批内部exit [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]，覆盖无漏项/无重复。
- Python 3.10.20: 1919项，1899实际通过，20 skip，0 failure/0 error；14批内部exit [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]，覆盖无漏项/无重复。

完整发现清单1919双版一致，预定14批各<=240秒、逐ID无漏项/重复；源码/测试/配置前后字节未变，精确argv/内部exit/skip及历史失败见 `/var/tmp/feiyu-final-handoff-20261119/`。Node/build/桌面按有效hash复用，不重打包。新正式0700留存 `/home/Feiyu/AI_Agent/feiyu-agent-evidence/architecture-final-20261119-171221`；范围/仅索引排除和最终hash核验见RETENTION/copy-index及最终report。受阻LSP、历史Warning/取消未归属、旧Anthropic batch05 null、Windows缺口/0.84.5乱码未复现、真实收益未验证继续保留。不代签总验收、不提交推送发布安装改版本。

## 主控最终裁定（2026-11-19）

接受本次任务书§7“完成或逐项列明具体阻碍”的Linux限定交付，及§6无付费授权下的离线评测交付。此为交付收尾，不是D整体、所有平台、全部独立审查或真实模型收益验收通过；LSP受阻与下表未决事项继续开放。F及新增远端评测平台不纳入本次。

主控已阅读最终报告与矩阵，并独立重核正式归档2145文件、当前171个源码/测试/配置文件，零hash差异。最终双Python各1919项分14批覆盖，1899通过、20skip、无失败；有效桌面证据按输入hash复用。所有累计修改保持未提交，0.87.0未发布；不因本限定裁定自动提交、推送或发布。

本裁定晚于最终归档封存，另存补充裁定副本，不改写原归档及其SHA清单。


## 2026-11-19 Windows serve UTF-8 窄范围修复（实施完成，待独立审查）

新授权后确认的代码缺口：严格cp936输出中文不是Node所需UTF-8；emoji/罕见字触发UnicodeEncodeError，被Protocol.send的ValueError分支吞掉导致整条丢失；cp1252输入可能得到合法JSON但内容已乱码。它们是合成复现事实，不是Windows用户现场根因定论，不假定PyInstaller的实际编码行为。

runtime.configure_serve_stdio重配现有TextIOWrapper：stdin/stdout=UTF-8 strict，stderr=UTF-8 backslashreplace以保留无法直接表示的诊断；不替换协议坏字符。共用main在精确--serve解析前配置（排除--后的位置参数），解析后覆盖argparse缩写；serve直接调用也配置。普通终端不调用；SDK/MCP私有二进制worker早路由不变；StringIO/None保留。Protocol不再吞UnicodeError，关闭流仍容错。Electron readline原本正确，逐字节拆块通过，未改Node产品代码。

证据 `/var/tmp/feiyu-windows-stdio-20261119/` 含复现/原send负对照、精确argv/内部exit、日志、源码hash及report。Python3.14.10/3.10.20各125项、1skip（124通过），Node15/15、另3.10传输5/5、npm build均exit0。负对照四入口/编码组失败、独立readline拆块通过，内部exit1已保留。Node入口夹具在真实main解析后拦截为实际Protocol echo，未冒称完整业务；另真实CLI双Python及Linux新冻结后端（各cp936/cp1252）隔离配置通过paths中文/emoji/罕见字输入→实际Protocol输出，无模型请求。冻结在证据目录独立构建，不替换原归档/用户应用，不代表Windows冻结或NSIS验证。

HEAD d82d943及0.87.0不改，全部累计未提交修改保留；无提交/推送/发布/安装、远端模型或付费调用、真实密钥历史读取、子代理或受阻LSP接管。产品源码已经变化，既有Linux包/正式归档只对应修复前快照，不得复用旧包无变化声明。本批不代签总验收；Windows原生方法、限制及文件清单见证据report。


## Windows stdio：request异常清理补修待复核（2026-11-19）
独立审查发现新传播的UnicodeError会在Protocol.request的try外逃离，遗留_waiting。已将send移入现有try/finally；新增write/flush失败均保留原异常且_waiting为空的回归。双Python serve/stdio各106项通过、0skip、内部exit0，未重跑无关全量。
措辞限定：直接Protocol.send不吞UnicodeError；既有events._deliver仍是best-effort并吞投递异常，本次未改，不保证所有非法Unicode事件都向用户报告。正常合法中文/emoji走UTF8保真。Windows现场未确认；先前新Linux冻结实验包尚未包含这次request清理补修，不能当作最新源码包。未提交发布、未改版本。证据 /var/tmp/feiyu-windows-stdio-waiter-fix-20261119/。


## Astra：Windows stdio源码修复有限接受（2026-11-19）
已核对 /var/tmp/feiyu-windows-stdio-waiter-review-20261119/report.md：request异常清理P2有限关闭。双Python原失败回归、各9项独立边界及各106项serve/stdio均通过，所测等待项清空、无死锁、原异常保留。结合前轮已审UTF-8入口/Node/负对照证据，接受本次源码编码缺口修复；不确诊或验收Windows0.84.5现场故障。
后续需要Windows原生构建与管道/GUI验证；当前旧发行包及先前Linux冻结实验包均不含最终request补修。events._deliver仍为best-effort，非法surrogate投递可能被吞，不宣称所有投递异常可见。本次不改Windows TaskStore/LSP/jobs范围、不提交推送发布安装改版本，所有累计修改保留。
