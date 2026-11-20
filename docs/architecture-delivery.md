# 架构演进最终交付矩阵（主控限定交付裁定）

2026-11-19；HEAD `d82d943e64dcf4129e5bc44f4798abff6949da83`；未发布 **0.87.0**。

**本次是原任务书§7带明确阻碍的Linux限定交付，不是所有功能/平台/独立审查/模型收益全部通过，主控已按下述范围接受交付。** 主控已有限接受新OpenAI3.14完整96本地合成证据；§6无付费授权下交配置、命令、格式并明确真实收益未验证。不得将远端批准平台、凭据摄取、HTTPS/live账单、恶意同UID、跨boot或通用eval父硬死等额外加强变成本批门槛；不推进F。

## 主控最终裁定（2026-11-19）

接受本次任务书§7“完成或逐项列明具体阻碍”的Linux限定交付，及§6无付费授权下的离线评测交付。此为交付收尾，不是D整体、所有平台、全部独立审查或真实模型收益验收通过；LSP受阻与下表未决事项继续开放。F及新增远端评测平台不纳入本次。

主控已阅读最终报告与矩阵，并独立重核正式归档2145文件、当前171个源码/测试/配置文件，零hash差异。最终双Python各1919项分14批覆盖，1899通过、20skip、无失败；有效桌面证据按输入hash复用。所有累计修改保持未提交，0.87.0未发布；不因本限定裁定自动提交、推送或发布。

本裁定晚于最终归档封存，另存补充裁定副本，不改写原归档及其SHA清单。

## 交付变化与证据归属

累计A—E复用原Feiyu/Toolbox/provider/session接口：版本验证Ledger、统一Executor、TaskState/journal、父预算/取消与Linux生命周期、SDK worker/监管者、上下文/压缩/事件/来源引用。eval独立增加四组对照、测量绑定、持久预算、完整调度和权威判题导出。当前工作树全部累计改动未提交，不能称本收尾批实现；本批只同步交付文档及中英README过时描述、最终回归和留存，没有改源码/测试/配置/版本、提交推送发布安装或操作真实用户数据。

证据代号：A0/B0/C0见progress原阶段；D0见D历史矩阵及局部裁决；SDK/E1/E23/E67/E89见progress对应独立审查；P为2026-11-18双版1829/20skip旧全量，Q/QR为旧eval定向。**FNL为本轮最终冻结回归**，不能将P或分散旧定向替代FNL。下表“已验收范围”仅沿用主控明确局部接受，继承Linux/合作式本机/合成输入限制；“待证/受阻”不是通过，“不属本任务”不是新门槛。逐条原要求保留如下。

## 原 A—E 逐项矩阵

编号顺序严格对应原任务书各条；必要回归另在各阶段末列出。文件路径均相对仓库根。

| 原要求 | 实现文件/入口 | 最新裁决、实际证据及明确状态 |
|---|---|---|
| A1 保存 HEAD/差异/版本/环境 | `docs/architecture-progress.md`、设计；A0 环境及 result | **已验收范围**：Astra 设计§9接受基线；A 起始干净、0.84.5，当前 HEAD 不变/0.87.0，不能混写时间点。 |
| A2 核对既有能力、复用 | 设计§1—8，原 `agent/tools/providers/session` 调用图 | **已验收范围**：A0；不是从零新增既有 verify/hooks/subagent/Dream。 |
| A3 适用现有检查并分类 | A0 result/log、progress 基线失败记录 | **已验收范围**：环境冲突与产品失败分开；后续实际 3.10 及桌面补证看 P，不倒写为 A 时已测。 |
| A4 简短设计/所有权/兼容/取舍/迁移 | `docs/architecture-evolution.md`§1—9及后续实施章节 | **已验收范围**：Astra 方案决定；设计中的旧计划以明确后续章节更新。 |
| A5 实施检查表与证据 | progress、D/E 矩阵、本文 | **已验收范围**：A 基线检查表；本次统一索引已交付，**最终裁定待 Astra**，不勾原任务书。 |
| B1 机器可读验证 | `verification.py` Ledger；`agent._reproduce_first/_fire`、`hooks.py` | **已验收范围**：B0 核心与修复，P 的 verification/agent/hooks 测试；不是文本“通过”。 |
| B2 完整记录字段 | `verification.py` record、`hooks.Outcome`、`session.py` | **已验收范围**：B0/P；ID/task/命令/cwd/时间/exit/timeout/cancel/log/前后状态/类别，未执行 exit=null。 |
| B3 通过/失败/未跑/过期/受阻 | Ledger execution 与 validity 分离、`ui.py` | **已验收范围**：B0/P；unknown 不归通过。 |
| B4 各写入路径失效 | `tools.py` 写前 epoch、Ledger invalidate/recheck，`agent.py` undo/MCP/job/LSP 接缝 | **已验收范围**：B0/P；消费时重核覆盖外部写；**边界**：外部瞬时改后复原/动态依赖不作全知承诺。 |
| B5 dirty/untracked/config/cwd 状态 | `verification.fingerprint`/workspace 扫描 | **已验收范围**：B0/P，Q verification 实际变更后 snapshot stale_rejected；非仅 HEAD。 |
| B6 有界指纹成本/边界 | `verification.py` 限额和安全读取 | **已验收范围**：B0，20k文件/256MiB/5秒默认，有界扫描失败为 unknown；性能提升**待证**，不是无限仓库完整依赖保证。 |
| B7 保存恢复并重核 | `session.py`、`agent.restore`、Ledger restore/reference | **已验收范围**：B0/E23/P；恢复 stale/unknown，不从旧对话补造执行事实。 |
| B8 代码结束展示范围/未验证原因 | `agent.py` 验证尾注、`ui.verification_status`、serve note | **已验收范围**：B0 直接渲染/实际入口及 P；旧完整 TUI 夹具曾超时，P Electron smoke 不能冒充该旧交互流程重跑。 |
| B9 闲聊/只读自然结束 | `agent.py` 代码活动标记/尾注消费 | **已验收范围**：B0/P 对应行为测试。 |
| C1 最小执行器/兼容入口 | `execution.py` Executor、`agent.py` 串并行、`Toolbox.run` | **已验收范围**：C0 核心；P actual agent/execution，不仅包装函数。 |
| C2 参数→授权→前记→隔离→结果→更新 | Executor.invoke、taskstate、tools/hooks | **已验收范围**：C0/D0/P；D 持久 journal 补足 C 早期诊断列表。 |
| C3 hooks/verify/job/MCP 信任一致 | `agent.py` command authorization、`hooks.py`、tools/MCP | **已验收范围**：C0/P；项目来源信任不代替 deny/单次授权，前置 hook 后重核；非 Linux D 限制另列。 |
| C4 工具元信息 | `execution.ToolSpec`、`tools.py` schema/spec | **已验收范围**：C0/P；范围/网络/并发/重试/预算收拢，名称参数兼容。 |
| C5 元信息不替代隔离/MCP自报不授信 | Executor 调度、`sandbox.py`、MCP spec | **已验收范围**：C0/P；只读 hint 仍保守授权串行；外部 MCP 服务不受本地 bash 沙箱包围。 |
| C6 ToolResult 机器可选字段 | `tools.ToolResult`、execution normalize | **已验收范围**：C0/P；error/exit/duration/truncation/artifacts/paths/source 是增量，路径表不是无其他副作用证明。 |
| C7 字符串/图片/摘要详情兼容 | tools/providers/ui/serve | **已验收范围**：C0/P，E1 native history；P 源码 Electron；当前Linux发行入口已限定接受 U7。 |
| C8 只读并行/混合写串行 | `agent._run_tools/_run_parallel`、subagent allowlist | **已验收范围**：C0/P；未扩大写并发。 |
| C9 所有调用恰一个协议结果 | executor 终态/`agent._fill_missing`、providers 配对 | **已验收范围**：C0/SDK/E23/P；拒绝/异常/取消补结果，协议配对不等于副作用恰一次。 |
| D1 schema/session/task/workspace身份 | `taskstate.py`、session/progress/agent restore | **已验收范围**：D0 身份/worktree/common-dir/single-writer；**具体未实现**：Windows 安全 writer，见 U1。 |
| D2 原请求/修订/目标/约束/验收/todo/预算/引用 | TaskState、`agent.task_control/_task_checkpoint` | **已验收范围**：D0/P；保存完整要求稳定引用，模型不能自封验收。 |
| D3 运行状态与结果分开 | TaskState result_details、CLI/serve task status | **已验收范围**：Astra D3关闭；`tests/test_task_results.py`、P；partial/unverifiable 为人工声明，不能解除 pending。 |
| D4 会话任务隔离/progress视图 | TaskStore、session、`progress.selected`、active/pending | **已验收范围**：D0 active P1关闭、P；不同session不覆盖，同session单writer；不承诺共享文件跨会话全局事务。 |
| D5 写前准备/写后结果/崩溃unknown | Executor/TaskStore、jobrunner/jobs、processwait、MCP/LSP | **已验收范围**：基础/前台/job/Linux MCP D0及P；**已实现待证+外部受阻**：LSP 独立审查 U3；SDK 父硬死亡普通Linux限定已关闭 U4；Windows U1。 |
| D6 恢复重核/未知不重跑 | TaskStore.recover/observe/resolve、agent.restore、jobs.identity | **已验收范围**：D0/P/Q 的真实重启阻断；LSP 只有既有实施证据**待审且受阻**。无法查询外部状态保留 unknown，人工 acknowledgement 不证明成功。 |
| D7 ID仅关联、不保证恰一次 | TaskStore.prepare/resolve、MCP request、SDK cleanup guard | **已验收范围**：D0/SDK/P；Q snapshot service只接收1次、head2次，但恢复均失败，非恰一次一般保证。远端撤销/通用幂等服务**不属本任务**。 |
| D8 关键存储失败显式阻断/收尾 | taskstate critical_write、RunControl、Executor、processwait/jobs/MCP/SDK | **已验收范围**：D0/SDK/P；保留主异常/unknown；LSP 独立清理审查**待证/受阻**，历史警告 U5 未关闭。 |
| D9 旧会话可读/按需适配 | session.load/save/journal_stub、TaskState.read、agent.restore | **已验收范围**：D0/E1/E89/P；旧原件保留，不批量迁移；新字段/记忆 JSON 不支持旧 writer 安全双向写，见迁移。 |
| D10 父总预算/截止/取消/helper/子调查/reviewer/job | runcontrol、providers.request_attempt、sdk_worker/windows/errors、processwait、jobs/jobrunner、MCP/LSP | **已验收范围**：D0各局部、后台父限制修复及 SDK F1/F2；P仍保留回归。**已实现待证**：Windows MCP/SDK实机 U2，SDK父硬死普通Linux限定见 U4；**具体未实现**：Windows TaskStore/LSP/jobs U1；**外部受阻**：LSP U3；D整体未验收。 |
| E1 五层上下文 | context.py、agent._refresh_system/_refresh_volatile_context | **已验收范围**：E1 R1关闭，每轮请求前更新易变层，P。 |
| E2 压缩后程序核验必须事实 | compaction.py、agent.compact、TaskState/jobs | **已验收范围**：E23 F1/F2关闭、P、Q真实compact；配对/目标/约束/验收/unknown/job保全，不让模型自评完整。 |
| E3 摘要引用Ledger，claim不升级 | compaction.facts、Ledger.reference、agent/session | **已验收范围**：E23/E89/P；owner/指纹/日志重核，旧passed不等于current。 |
| E4 缓存意识/不同provider | ContextLayers、providers.Billing.set_context/原生请求 | **已验收范围**：E1 双provider离线请求/fallback；**已实现待证**：真实缓存命中/费用收益 U6。 |
| E5 原生历史小接口、图片配对 | native_history.py、providers、session、agent | **已验收范围**：E1/P，图片/thinking/signature/reasoning/扩展字段普通存盘恢复；跨provider保留原不转历史行为。整段摘要仍有损，不可重建已删图片。 |
| E6 运行事实/CLI Desktop渲染/旧协议 | execution/verification/agent/events/ui/serve、desktop/ui/app.js | **已验收范围**：E67/P Node10及源码Electron；事件投递best effort，非journal授权真源；当前Linux发行入口已限定接受 U7。 |
| E7 sink按session/run隔离 | events.Route/ContextVar、submit逐worker copy_context、subagent回调 | **已验收范围**：E67/P；seq单run，关闭丢迟到，不承诺同agent并发历史或跨进程可靠重放。 |
| E8 摘要/子报告/记忆来源保留 | provenance.py、agent/tools/subagent/compaction/memory/session | **已验收范围**：E89/P；引用为保守依赖集合，文本为claim，旧unknown/legacy；非逐句归因或语义免疫。 |
| E9 Dream原来源/指纹/apply检查 | dream.py、memory.Item、provenance | **已验收范围**：E89/P；完整source/metadata/候选指纹重核；旧v1无历史指纹不补造，纯对话不写Ledger。多writer memory事务**不属本任务**。 |

必要回归映射：B 的改后/运行中变更、失败/超时/取消/原红基线/恢复/unknown 在 `test_verification*`；C 的拒绝/参数/串并行/权限范围/截断/图片/配对在 `test_execution/test_parallel/test_images/test_security_regressions`。D 写前/写后崩溃、多session、损坏/旧格式、预算取消在 `test_taskstate/test_runcontrol/test_job_lifecycle/test_foreground_lifecycle/test_sdk_* /test_mcp_*`；LSP `test_lsp_lifecycle` 只有实施回归，不能替代 U3。E 强制压缩续接/约束/换模型/原生图片配对/双session事件/前端/来源见 `test_compaction/test_context_layers/test_event_routing/test_provenance` 与 Desktop runtime-events。FNL 是当前源码全部发现测试的最终分批回归，覆盖新增 eval 测试；P保留历史时点。实际 skip 仍是 skip。

## 最终正确性及复用证据

证据 `/var/tmp/feiyu-final-handoff-20261119/`：先用标准unittest discover生成两版相同的完整ID清单（1919），再按预记录plan.json分14批loadTestsFromNames执行；每批全新HOME/XDG、无真实凭据环境、假provider/loopback、独立240秒保险。精确argv/env/内部exit在每批result.json，逐ID结果与skip原因在*-tests.json。命令入口为 `.venv/bin/python /var/tmp/feiyu-final-handoff-20261119/run.py prepare` 与 `run.py run`，须使用全新证据目录；普通单进程入口仍为 `python -m unittest discover -s tests -t .`。

- Python 3.14.10: 1919项，1899实际通过，20 skip，0 failure/0 error；14批内部exit [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]，覆盖无漏项/无重复。
- Python 3.10.20: 1919项，1899实际通过，20 skip，0 failure/0 error；14批内部exit [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]，覆盖无漏项/无重复。

source-before/after.json逐文件相同，source清单摘要与workspace初末差量见最终report。没有测试中修改文件、夹具修复或失败刷绿；历史失败不因本轮通过而归零。CLI live拒绝、配置validate及版本检查另见对应目录内部result，拒绝exit2是预期，非程序正确性通过数。

reuse.json：与既有Linux发行源清单240项比较，最终228项一致；12差异为8文档、3 eval、1 eval测试（文档更新前为230/10，见reuse-before-docs.json）。全部feiyu/desktop产品输入未变；450发行文件、205 backend、7962 Node依赖逐项hash匹配。沿用已接受Node10/build、packaged smoke/trust、合成中文流式/会话重开，不重复运行/重打包。`pyproject.toml`仅packages=["feiyu"]；desktop/scripts/build_backend.py仅collect-all feiyu且入口不导入evals；已有code-provenance 55对象对应产品。因此新增eval不在Linux产品包范围，不将新eval覆盖冒充包内验证。deb/AppImage只核对内容，不声称安装/卸载/FUSE/Ubuntu/Chromium sandbox部署通过。

## §6 离线交付与最小入口

`python -m evals.architecture validate --config evals/architecture.json`；`python -m evals.architecture dry-run --config evals/architecture.json --out <全新绝对目录>`输出格式夹具；`python -m evals.architecture fake --out <全新绝对目录>`为冻结双源码实际产品假provider接线。原生SDK用`loopback`/`anthropic-loopback`。完整持久协议入口为`python -m evals.architecture_measurement prepare`和`python -m evals.architecture_schedule create/batch/export/aggregate`，参数/短物理路径要求见[评测协议](architecture-evaluation.md)，不能重用已消费身份或将示例当费用授权。`live --config ... --out ...`固定在配置/凭据前exit2。

主控接受的完整新OpenAI3.14：96 finished/96评分、72success/24recovery agent_failure、432请求、24批预算连续；完整执行包与独立审计留存，不重跑。旧OpenAI72+1interrupted/23未开始不解锁；旧Anthropic3.10 96/432只属旧源码证据，batch05内部exit=null保留。当前其他provider/runtime组合未全跑是覆盖缺口，不是无证据产品失败。全快照混杂、公开holdout与相关repeat不能推导单特性因果收益。**程序回归证据见上，真实模型/缓存/成本收益尚未验证，能力收益未验收。** 真实运行需另有明确费用授权与受审适配，不在本批实现远端平台。

## 兼容、迁移与回退操作

Python最低3.10；本机3.10.20/3.14.10实际运行通过，各环境分开。CLI/Electron/serve工具旧名称参数、字符串/图片/summary/detail及旧事件kind/payload保留；旧客户端忽略增量字段。Anthropic/OpenAI原生历史分别保留；custom/Fake路径与内建SDK worker保证不同。Linux是当前验证范围；一般README中历史Windows CI支持说明不能证明本次D/E。macOS无本批实机/发行包验证。Windows三项缺实现与MCP/SDK缺实机证据见 U1/U2。

迁移只在将来经授权的用户数据维护中操作，本批未读写这些真实目录：

1. 先停止活动请求，正常关闭CLI/serve/Desktop和受控job/LSP/MCP，确认无writer；无法核实的进程/操作保留unknown，不按旧PID盲杀。若存在关键写失败，先保留原件再处理，不开旧writer覆盖。
2. 记录当前源码清单、工作区canonical root/Git worktree身份、所用HOME/XDG。备份**整个** `${XDG_STATE_HOME:-$HOME/.local/state}/feiyu` 到应用不会扫描的独立目录（权限0700），例如在已停止writer后 `cp -a -- "$STATE_ROOT/feiyu" "$BACKUP_ROOT/feiyu"`；STATE_ROOT/BACKUP_ROOT须由操作者设置为实际绝对目录且目标不存在。保留sessions的会话JSON、cards、active指针、全部task sidecar/journal/验证日志/job输出收据，以及memory/dream/progress；自定义状态根同样全备份。不能只复制会话JSON。为完整备份生成SHA清单，并将版本/路径/权限/时间记录在备份旁。
3. 用**备份副本**在新隔离 HOME/XDG和同一工作区身份条件下演练当前reader恢复（不要伪造worktree身份）。`/task {"action":"pending"}`、`/task {"action":"select","task_id":"实际ID"}`、`/task {"action":"show"}`检查所有未决项、预算、约束和验证引用。恢复先观察文件/Git/进程/收据；验证需重核，unknown不能盲重放。`resolve`只能由用户在核对真实依据后明确声明，不代表重跑授权。未来/损坏记录保留并阻断，不以空状态覆盖。
4. 旧会话按需读取/显式续接建立新ID/sidecar，不批量重写。旧已丢图片或压缩原文不能补造；新普通保存保留多模态，整段摘要仍有损。schema_version仍1不等于旧writer兼容全部字段/枚举。
5. 回退前再次停止所有writer并备份**当前完整状态**。本收尾批仅文档，回退只撤本批文档差量；累计产品回退须另按明确差量逐项审查，不执行全仓reset/stash或整份覆盖，保留其他批修改。旧程序仅只读历史/专用导出副本；它不理解新JSON记忆行，旧session writer还可能丢图片/新字段，禁止在新状态根继续写。保留unknown、pending、已花费用、partial/unknown账单和截止，不通过删除journal/重置预算“恢复可运行”。需要旧版继续写时先实现并验证明确降级转换，当前未提供。

完整备份还须按 journal/Ledger 的引用清单保留产物与日志：若自定义输出或产物在上述状态根外，单独备份并记录原绝对路径、相对映射、权限及SHA；已缺失的引用明确列缺失，不能把只备份状态根说成所有产物齐备。工作区文件/源码也按对应内容清单独立保留；memory、dream候选及其来源session必须在同一备份时点。以上为未来维护步骤，本次没有读取或迁移真实用户数据。

## 未决事项、完成内容与可执行下一步

| ID | 当前状态 | 最小下一步/条件 |
|---|---|---|
| U1 Windows TaskStore/LSP/jobs | 具体缺跨平台实现；本次Linux范围外 | 后续Windows任务实现安全writer、身份/树监管并做真实崩溃恢复，不把Linux测试当Windows通过。 |
| U2 Windows MCP/SDK，macOS | 实机/冻结安装证据缺失 | 有相应原生环境后验证；本轮不安装、不操作用户应用。 |
| U3 LSP独立审查 | 已实施但审查受平台机制阻碍，未关闭 | 仅在平台允许且负责人安排时恢复原独立审查；本轮不重试、不绕过，既有回归不替代。 |
| U4 SDK父硬死 | 普通Linux范围有限关闭 | 仅监管者存活可调度、直接子可杀、本地I/O正常；不保证同时死亡、不可中断内核、逃逸后代或远端撤费。Windows后续。 |
| U5 历史Warning/取消 | 历史ResourceWarning来源、Anthropic3.10定时取消失败未归属，仍待证 | 保存完整原失败；后续自然复现时有界采栈与回收证据交负责人。本轮成功不证明历史原因消失，不无限重跑。 |
| U6 真实收益 | §6无付费授权的离线配置/格式/本地合成规模有限接受；真实收益未验证 | 未来获得具体授权后单开受审live适配与真实评测；远端身份/凭据/HTTPS/账单等不追加为本次门槛。 |
| U7 Linux发行 | 已接受现有x64构建及已测入口；本轮hash复用有效 | 安装/卸载/菜单/FUSE/Ubuntu/Chromium sandbox部署未测；声明这些范围前另补证，不等于发布授权。 |
| U8 文档及留存 | 本轮主体表/README确切旧状态已同步，新增0700归档已建并最终核验 | 按RETENTION保留至用户明确清理，非完整历史/异地备份；总验收由主控。 |
| Windows0.84.5乱码/对话报错 | serve编码缺口已合成复现并修复，待审查；现场根因未确认 | 双Python/Node及Linux冻结离线检查通过，仍需Windows原生验证；旧安装包不含修复。 |
| 额外加强/F | 不属本批 | 不新增远端批准平台、恶意同UID/跨boot/通用eval硬死等门槛；unknown人工解除未提供，继续阻断重放。 |

## §7 七项交付核对（供主控裁定）

| 条件 | 本次状态与证据 | 保留边界 |
|---|---|---|
| 1 A—E完成或逐项阻碍/内容/下一步 | 完成逐项映射；A/B/C及E各批、D Linux局部限定接受 | U1—U6具体阻碍及下一步如上，D未整体验收，不把列明阻碍当全部通过。 |
| 2 源码设计一致/兼容与旧读 | 完成Linux已测入口回归，FNL/设计后续章节对应 | LSP独立受阻、非Linux及安全降级写缺口保留；非无损双向迁移。 |
| 3 回归/构建/集成 | FNL双版完整发现分批覆盖；Node/build/发行有效hash复用 | 实际skip/历史失败/受阻不算通过，未测安装与平台保留。 |
| 4 真实评测或配置授权缺口 | 按§6限定完成离线交付；新OpenAI96合成已接受 | 无费用授权，真实模型收益未验证，不验收能力收益。 |
| 5 版本/中英文必要文档 | 完成版本一致性核对；README中英仅更新过时eval断言 | 0.87.0/HEAD不变，全部累计未提交修改保留，不发布。 |
| 6 摘要/证据/限制/迁移回退/归属 | 完成，本页与最终report、源码差量/留存索引 | 未操作真实用户数据；不能把累计实现归本批。 |
| 7 阶段/清单/文件/命令结果/未决 | 完成可读交接及新的本机正式留存 | 供主控审阅，不代签总验收，不称全验证/收益通过。 |

## 正式本机留存

新增 `/home/Feiyu/AI_Agent/feiyu-agent-evidence/architecture-final-20261119-171221`，根0700；旧architecture-20261118和architecture-20261119未覆盖/清理且初末hash核验。包含最终源码/测试/配置/任务书与交付文档、回归精确日志/内部exit/发现与覆盖清单、重要eval实施/独立审查索引、新96完整执行包/原始registry与审计。copy-index.json逐文件标明复制与仅索引，排除特殊socket和无谓中间测量副本；SHA256.json和外部核验回执排除自指，日志结束后生成验证。保留至用户明确清理，不称完整历史、异地备份或全依赖可离线重建。迁移回退保留完整registry、unknown与原预算，不删除账本补额。

## 历史交接与裁决（以下按原时点保留，当前状态以上表为准）

## 续作核验收尾（2026-11-18，交 Astra）

续作证据仅写 `/var/tmp/feiyu-delivery-audit-20261118/resumed/`，原失败轮次的全部产物保留。续作起点239个工作区文件与原 `after.json` 逐字节一致；原审计51个证据result/log/报告SHA全部匹配。复用原审计逻辑，仅重算当前字节与清单、两版物化包/依赖（3.10为5745项、3.14为6183项）、QR的116项证据SHA、版本与diff检查；没有执行产品测试、桌面或独立LSP审查。P的README两项预期差量保持，产品覆盖无缺项/差量，Q两版60/81项源码包及物化字节仍匹配。

矩阵42条及§7七条件已经具备交接内容；本次只补README精确待改清单和状态根外产物备份要求，最终文件SHA及允许范围检查见 resumed 的 `after.json`、`final-workspace-check.json`、`report.md`。这是文档交接收尾完成，不是U1—U8关闭或Astra总验收。主控下一步先按上表收口README，确定平台/SDK保证边界与正式证据留存，再依据U1—U8逐项裁定；不以记录阻碍自动豁免原功能，不扩大到U9/F。


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

用户报告：0.84.5 Windows桌面安装版存在部分文字乱码、对话内容不显示并报错，仍无Windows机器、日志或截图。2026-11-19用户新授权窄范围修复：已合成复现并修复serve标准流未约束UTF-8以及Protocol吞编码异常的代码缺口；双Python/Node及独立Linux冻结后端离线检查通过，源码修复及request异常清理已获有限接受。现场根因及用户故障是否解决仍未确认，Windows原生验证待办；不扩展TaskStore/LSP/jobs适配。旧Linux发行包和正式归档早于本次源码修复，不含它；证据 /var/tmp/feiyu-windows-stdio-20261119/，详见本次进度条目。

## Linux U4 实施交接（2026-11-18本地，未验收）

用户已指定本次Linux，Windows后续；不处理待复现的0.84.5 Windows桌面问题。本批§27.2专用监管和本地收据实现不等于U4/D关闭。源码双版定向77项各通过；新冻结同exe双SDK协议/正常/取消及父SIGKILL通过，55代码对象匹配。全量及具体失败记录以 `/var/tmp/feiyu-sdk-parent-lifecycle/20261119T052932Z/report.md` 为准。旧final-package及正式归档不覆盖，旧冻结产物不包含U4新增代码，其当前源码匹配结论仅对当时快照成立；本批新产物只补SDK范围，不继承为新Electron发行包证明。后续再更新正式留存。

恢复不把本地收据当usage或完成授权；pending/unknown、额度/截止与重放阻断保持。无schema/版本变更；回退先停writer/请求/监管者、备份完整journal/session和未复用槽，再只撤本批。限制、独立审查重点与精确命令见本批report。live适配、最终Electron发行包、受阻LSP及原历史warning状态不因此关闭；未接管或替代LSP审查。


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

## U6 SDK最小批次交接（2026-11-19，待Astra独立审查）

新增OpenAI原生SDK可注入transport及CLI loopback：父控制器实际生成双源码四组产品路径观察、请求/model/endpoint/SDK/source指纹和逐物理attempt账本，统一deadline含SDK静默/半帧/IPC背压/取消清理。全快照混杂与recovery双臂agent_failure保持；全部合成，不报告真实收益。完整usage×固定合成价格仅作估算，供应商invoice始终未知；partial下界/失败/辅助请求保留，不补预算。未知费用停止，SDK自动retry禁用，父retry记录逐次收费或unknown。

双Python final3-target各76项/6skip/70实际通过、内部exit0；locked-loopback各8真实产品观察；副本负对照预期失败、真实保存失败账本及首轮SDK兼容失败均保留。证据 `/var/tmp/feiyu-eval-sdk-adapter-20261119/report.md`。无产品/发行包变更，因此不重跑无变化产品全量/桌面；U4/U7/U8已有限接受范围不扩大，旧产物未过期。

live仍在读配置/凭证前exit2；仅literal本地HTTP和合成key，禁代理/跳转。远端契约仅拒绝入口，正向授权验证/专用凭证/真实费用授权/账单核对尚缺；Anthropic原生路径和真实多次能力收益实验待后续。评测父硬退出不继承产品U4保证；Windows、受阻LSP及历史Warning保留。HEAD d82d943、未发布0.87.0及累计修改保持，未stash/reset/bump/安装替换/提交推送发布。交Astra独立审查，不自行关闭U6、D或整任务书。

## U6 Anthropic原生离线批次（2026-11-19，交Astra独立审查）

新增`python -m evals.architecture anthropic-loopback --out <全新绝对目录>`，使用实际Anthropic SDK、本地合成HTTP和各自冻结源码的原生请求构造，接通四组stream/nonstream、工具结果、compact和恢复。增量/累计/cache usage独立处理，未知费用null停准入，估算不是invoice；取消账本持久化及写盘失败原异常优先保留。双Python定向各86项/6skip/80通过，内部exit0；完整执行锁、额外SDK探针、OpenAI回归、失败轮次、精确命令/指纹/回退见 `/var/tmp/feiyu-eval-anthropic-20261119/report.md` 和[评测文档](architecture-evaluation.md)。恢复agent_failure、全快照混杂保持，不宣称真实模型收益。

Live、正向远端费用授权/凭据/账单仍未交付；live读取配置/真实凭证前拒绝。仅evals/tests和必要双语说明，不改变产品/Linux包/0.87.0/HEAD，不stash/reset/bump/安装替换/提交推送发布。U4/U7/U8既有限定裁定和Windows/LSP/Warning限制保持。下一步Astra独立审查；U6/D/整任务书不在本次自行验收。

## U6本地授权契约增量（2026-11-19，实施待独立审查）

继两原生SDK受控eval路径R1/R2/AR1有限关闭，本批仅增加严格计划/显式批准记录/观察输入绑定、未批准模板和机器可读本地预检收据。详见evaluation末节及 `/var/tmp/feiyu-eval-authorization-20261119/report.md`。`require_remote_contract`可接受有效本地契约，不能据此称用户已授权；live仍在配置/凭据前exit2，两原生transport/child仍仅synthetic loopback。真实模型收益尚未验证。

U6剩余不是单纯测试：实际冻结输入测量与批准来源核验、由主控取得具体用户费用批准、单run批准消费/重启持久预算、专用credential安全摄取、真实HTTPS路径、远端版本确认、真实费用/账单对账和重复真实评测仍未交付。本地预检不消费批准、不读专用credential值；hash不证明可信宿主。U4/U7/U8既有限定裁定和Windows/LSP/历史Warning限制保持，不代签U6/D/总任务书，无产品/包/版本或发布变更。

## U6实际输入测量交接（2026-11-19，待Astra独立审查）

离线v2 measured plan已实施：双源码/Git内容冻结、解释器与安装依赖字节、完整配置/题目/判题/采样和原生prompt构造器锁；worker在真实初始请求派发前停止，实际动态system/parameters hash逐request分列。prepare输出未批准模板；measured preflight重新测量observed后严格匹配，不接受自带manifest替代实际输入。双Python最终定向各16项/0skip通过；CLI链路、负例、失败轮次、最终源码/指纹及结束后核验见 `/var/tmp/feiyu-eval-measurement-20261119/report.md`。详细协议见architecture-evaluation最新节。

本批不授权付费或接通live；单次批准消费、恢复预算、真实凭据/账单/模型收益未交付。runtime不等于OS/完整stdlib镜像，hash不证明恶意host或批准者身份，未来动态请求不能声称已静态冻结。R1/R2/AR1、U4/U7/U8限定裁定及1.5秒取消未解释失败保持，Windows/LSP/历史Warning不扩大。产品/当前Linux包/HEAD d82d943/0.87.0及继承修改不变，无安装替换、提交推送发布或子代理。交Astra新独立审查，不自行验收U6/D/任务书。

## U6 durable synthetic consumption/budget handoff (2026-11-19, not accepted)

Implemented an independent eval-only Linux API (`evals/architecture_durable.py`), with actual v2 remeasurement/preflight, atomic record/run consumption, a single writer flock, pre-dispatch physical-attempt reservation and durable results. Restart retains count, known fixed estimates, partial/unknown and original deadline; unresolved dispatch blocks replay. Global limits span observations/auxiliary/retries and only tighten; measured per-observation limits remain additional restrictions. Supplier invoice remains separate from estimates. It uses a fixed subprocess fake, not actual product observation scheduling/judging or a remote transport.

This is an implementation handoff to Astra, not U6/D/taskbook acceptance. Product/U4/U7/U8/packages and prior decisions remain. Actual fee approval, approver authentication, malicious same-UID protection, remote revocation, credentials/HTTPS/real invoices and real-model benefit remain unfinished/outside this local scope. Inherited cancellation discrepancy, Anthropic no-transport scripted recovery KeyError, Windows and blocked LSP review are unchanged. Full protocol and rollback are in architecture-evaluation.md; evidence is `/var/tmp/feiyu-eval-durable-budget-20261119/`.

中文：本批仅交审独立Linux离线持久控制器，合成批准/原子消费/请求前预留/结果与重启预算已实施；不验收U6/D/任务书，不改变产品及包。真实费用批准、身份认证、凭据/HTTPS/账单与收益仍缺；unknown不重放，迁移回退必须保留完整registry，不能删账本补额。精确测试结果以本批报告及进度最新节为准。

## U6 durable native SDK wiring increment (2026-11-19, independent review pending)

| Delivery | Actual state |
|---|---|
| One durable parent for native primary/helper/retry requests | Implemented in eval-only Controller + DurableLedger; legacy Ledger charging bypassed |
| Actual measured create→SDK product loopback→durable result→new-process resume | OpenAI/3.14 and Anthropic/3.10 each 8 observations/36 physical requests; 6 success, recovery 2 agent_failure |
| Boundaries | Both Python versions: 5 targeted boundaries + 1 later synchronized native cancellation/timeout + 1 crash evidence rerun pass; both mutation negative controls fail as expected |
| Existing four-module regression | 3.14: 39 pass; 3.10: 38 pass/1 inherited timed Anthropic cancellation failure, retained unresolved |
| Full schedule/holdout/repeats/strict aggregate export | Not implemented by this increment; API rejects unsupported observation scope |
| Real remote authorization/credential ingestion/HTTPS/invoices/benefit | Not implemented; live remains refused, no session fee authorization inferred |

中文：证据入口 `/var/tmp/feiyu-eval-durable-sdk-20261119/report.md`；初轮实现/脚本/归档失败保留。程序定向边界已验证，旧取消回归仍有失败，真实模型收益尚未验证。不代签U6/D/任务书。来源/请求绑定、预留后复检截止、超期事实先落盘、failed-resume毒化和unknown不补额/不重放保持。产品、Linux包、版本和全部累计修改保留，无发布。迁移/回退保留完整registry，详见evaluation最新节；Windows/LSP/历史Warning等继承限制不扩大。


## U6 schedule/export 实施交接（2026-11-19，待主控独立审查）

已实现配置生成的完整arm/group/split/repeat调度、同一持久父账本跨批次/进程续接，以及从registry独立判题证据导出的v2结果与严格aggregate；保留旧schema/数值/防改标门禁，controller.json仅诊断。原始预算不补额，started/interrupted/unknown不重放；人工解除中断尚未实现。协议与短AF_UNIX路径要求见architecture-evaluation最新节。

实测严格分列：OpenAI/3.14 72/96评分、360请求，72 success，首个recovery因证据长路径AF_UNIX失败留1 interrupted/23未开始，后续仍exit2；不能宣称该全计划通过。Anthropic/3.10 96/96评分、432请求，72 success、24 recovery agent_failure；48观察后迁短measured路径沿用同一registry/plan/预算完成，batch-05退出状态未收集单列null，其余命令内部退出码见证据。另两provider/runtime组合未完整运行。全快照混杂/合成布线，不是live或模型收益。

双版五模块各39项、原生边界各5项、最终调度/导出各9项分别通过，精确源码时点不合并冒称单次全绿；导出真实registry审计各20类、优化模式/live拒绝、有效负对照见 /var/tmp/feiyu-eval-schedule-export-20261119/report.md。全部源漂移、长路径、测试异常类型与负对照探针失败保留。旧40项error/单项补验分别保留，历史Anthropic3.10定时失败仍未归属，adapter R1/durable R1/R2有限关闭不扩大。

只改eval/tests/相关docs，不动产品包/HEAD d82d943/0.87.0与累计修改，无真实凭据历史/远端付费、受阻LSP、提交推送发布安装改版本或子代理。不自验U6/D/整任务书。迁移回退必须保留完整registry及证据，不能清除中断或回滚预算；真实授权/凭据/HTTPS/账单/收益及人工处理仍缺。

| 本批交付矩阵 | 实际状态 |
|---|---|
| 完整配置计划/holdout/repeats调度与单父预算 | 已实施，批次与新进程保留计划/预算/截止 |
| registry权威judge导出与严格aggregate | 已实施并实测；缺失/未知如实保留，不靠诊断补账 |
| 完整96实测（最新补证见文末） | 新独立当前OpenAI3.14已96评分（72 success/24 recovery agent_failure）；Anthropic3.10旧96证据只读继承。旧OpenAI72中断保持，另两组合未全跑；非当前双provider双版全量 |
| 中断观察人工核对/解除 | 未实施，不自动清除或重放 |
| live/真实授权/账单/模型收益 | 未交付，继续拒绝；U6/D/任务书待独立裁定 |


## U6 新独立 OpenAI3.14 完整计划补证（2026-11-19，交主控审阅）

证据 `/var/tmp/feiyu-eval-openai-completion-20261119/report.md`。固定当前源码，新独立run/record，短物理非symlink目录 `/var/tmp/foc19/m`，全96路径预检最长61字节；公共prepare→create实际重测/preflight/原子消费→24批新进程→registry export/严格aggregate，均取得真实内部exit0。96/96评分、96 finished：72 success、24 recovery agent_failure原判据保留；432物理请求（408 primary/24 auxiliary，全部attempt1、无实际retry），未知0。仅本地原生OpenAI SDK/Python3.14.10合成HTTP，不是远端或真实模型收益。

全局上限在prepare前固定1000请求/7200秒/1 CNY合成估算，逐观察30轮/120秒/3 CNY/2 attempts未变。23项定向审计通过：24批同plan/measurement/record/started/deadline/limits，entries前缀连续，累计费用单调、无补额；导出/局部重算hash后的judge/request/receipt篡改拒绝，已消费身份不能重用，三类增额拒绝。审计前后registry不变；live仍在配置/凭据前exit2。所有内部exit/完整日志和恢复失败、连续性全快照、源码/依赖/解释器前后指纹及完整执行包已保留，日志结束后散列。244工作区文件、6183依赖文件未漂移；测试结束后才追加本三文档。

旧OpenAI72评分＋1 interrupted/23未开始保持，未解锁/重放/回填，新run不填旧缺口。Anthropic3.10原96/96、432请求只读继承核对；不是当前源码重跑，更不是双provider双Python版全量。旧Anthropic batch05 exit=null、历史定时取消未归属、旧40项error及单项补验分列、受阻LSP和历史Warning继续保留。socket R1/receipt R2沿用有限关闭。

当前本地完整调度/holdout/repeats、同一持久预算、实际preflight/合成消费、权威judge导出/aggregate均已实现并有本批完整规模证据，不再列作缺实现。仍缺远端正向授权消费/批准来源认证与撤销、专用凭据摄取、受审HTTPS/live期限/取消/用量及供应商账单适配、真实版本/费率确认及授权后真实收益；本地合成消费不授远端权限。interrupted/unknown人工核对解除、generic eval父硬死监管、跨boot等加强边界未新增。仅证据缺口另列：当前源码Anthropic3.10完整96及OpenAI3.10/Anthropic3.14组合未重跑，真实收益/缓存收益/远端费用语义未实证。

下批可审本报告、audit.json、24批registry/连续性、export/aggregate及前后源码/依赖指纹，裁定是否接受本run完整规模证据；不需重建旧run或重跑无关产品/桌面。无真实凭据历史/远端请求/费用授权/付费，无子代理、版本/包/HEAD d82d943变更或提交推送发布安装。仅更新三文档真实状态，不代签U6/D/任务书。回退只撤本段与交付矩阵本次更新，完整保留新旧账本/测量包/证据，不回滚预算。


## Windows stdio：request异常清理补修待复核（2026-11-19）
独立审查发现新传播的UnicodeError会在Protocol.request的try外逃离，遗留_waiting。已将send移入现有try/finally；新增write/flush失败均保留原异常且_waiting为空的回归。双Python serve/stdio各106项通过、0skip、内部exit0，未重跑无关全量。
措辞限定：直接Protocol.send不吞UnicodeError；既有events._deliver仍是best-effort并吞投递异常，本次未改，不保证所有非法Unicode事件都向用户报告。正常合法中文/emoji走UTF8保真。Windows现场未确认；先前新Linux冻结实验包尚未包含这次request清理补修，不能当作最新源码包。未提交发布、未改版本。证据 /var/tmp/feiyu-windows-stdio-waiter-fix-20261119/。


## Astra：Windows stdio源码修复有限接受（2026-11-19）
已核对 /var/tmp/feiyu-windows-stdio-waiter-review-20261119/report.md：request异常清理P2有限关闭。双Python原失败回归、各9项独立边界及各106项serve/stdio均通过，所测等待项清空、无死锁、原异常保留。结合前轮已审UTF-8入口/Node/负对照证据，接受本次源码编码缺口修复；不确诊或验收Windows0.84.5现场故障。
后续需要Windows原生构建与管道/GUI验证；当前旧发行包及先前Linux冻结实验包均不含最终request补修。events._deliver仍为best-effort，非法surrogate投递可能被吞，不宣称所有投递异常可见。本次不改Windows TaskStore/LSP/jobs范围、不提交推送发布安装改版本，所有累计修改保留。
