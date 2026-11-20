# D 验收矩阵与 E 接续计划（交 Astra）

> 2026-11-19 最终限定交付状态见 [交付矩阵与证据核对](architecture-delivery.md)。本页保留历史时点；后续明确裁决更新局部状态，全量通过不能自动关闭待审事项，D仍未整体验收。最终双版完整发现回归及§7逐项阻碍见交付主体表；LSP受阻独立审查未关闭，不能勾全部通过。

2026-11-16；工作区 `/home/Feiyu/AI_Agent/feiyu-agent`；HEAD `d82d943e64dcf4129e5bc44f4798abff6949da83`；未发布 **0.87.0**。本文是文档核对与接续建议，**不宣布 D 通过**，不更改任务书勾选。

依据：[原任务书 D 十项/必要回归及 E 原范围](architecture-evolution-taskbook.md)、[设计第5、14—24节](architecture-evolution.md)、[进度中的最新 Astra 裁决](architecture-progress.md)。较早“未实现”描述按后续实现及裁决更新解释，历史保留。已读 `/home/Feiyu/AGENTS.md`、项目 `CLAUDE.md`、`pyproject.toml` 和桌面测试脚本约定；本次用户“仅文档、版本不变”优先于通常 bump/实施测试要求。

本次只读取既有实现入口、测试名及已落盘报告，不执行测试、故障注入、安全审查或模型调用，不启动子代理、提交或发布。**LSP 独立审查曾被平台中止；本文不执行、接管、重试或通过换渠道绕过该审查。** 下文列出其既有实施证据仅供定位，不构成独立复核。

## 1. 状态与证据口径

- **已实现且审过（限定范围）**：有实现及 Astra/独立审查结论；不把局部结论扩大为整个 D 或全部平台通过。
- **已实现待审/缺证据**：实现存在，但独立审查、目标平台或最终代码状态证据不足。
- **实质未实现/未满足**：可指向缺少的行为；不能用说明文字代替实现。与同步 SDK、OS 等明确能力限制分开记录。
- **非本次硬要求**：原任务书未要求的加强项；不因填表新增项目。
- **明确平台限制**：本环境无法提供的运行或审查条件；skip 不算通过，说明限制也不自动豁免验收。

证据索引（以下均为既有证据，本次未重跑）：

| 编号 | 既有证据与适用范围 |
|---|---|
| S1 | [进度：D中期P1复查](architecture-progress.md#astra-p1-复查及-d-剩余工作启动)：Astra 接受 active 指针/同 session 未决集合修复，`astra-p1-recheck` 28项、0skip、内部exit0；日志 [full-314.log](/var/tmp/feiyu-stage-d/astra-p1-recheck/full-314.log)。D1/D2 的实现与此前 local_path、finish 修复见该节前文。不是后续 LSP/SDK/MCP 审查。 |
| S2 | [进度：后台产物修复后裁决](architecture-progress.md#astra-修复后最终验证与裁决)：日志摘要绑定、安全路径两P2修复获接受；双版各1678项/19skip，实际1659通过。后续版本全量保留回归，但不外推为所有异步服务审查。 |
| S3 | [前台独立复核](/var/tmp/feiyu-fg-rereview-sol/REVIEW-resumed.md)：Shell/hooks 启动交接及重复SIGINT两P1关闭，双版真实入口/进程证据；原退出7、unknown及收尾语义保留。 |
| S4 | [SDK独立报告](/var/tmp/feiyu-sdk-review-20261116/report.md)：双版各26项（17既有+9独立探针）、0skip、内部exit0；普通离线SDK尝试记账范围无确定缺陷。覆盖真实产品接缝+Fake响应，不是供应商网络/账单/收益证明。 |
| S5 | [MCP最新独立续复核](/var/tmp/feiyu-mcp-close-review-20261116/report.md)、[命令结果](/var/tmp/feiyu-mcp-close-review-20261116/command-results.md)：Linux 3.14/3.10源码及新真实ELF范围兼容P1、两P2关闭；各52项定向、18个独立交错、10项smoke，均0skip/内部exit0。Windows仅假API控制流，不是实机证据。 |
| S6 | [LSP实施结果/精确命令](/var/tmp/feiyu-stage-d/lsp-command-results.md)、[进度：LSP最终冻结](architecture-progress.md#lsp-最终冻结结果已检查内部result及日志末尾)：双版各76项/10skip，实际66通过；当时全量1709项/19skip，实际1690通过。21项生命周期用例是实施方证据；独立审查受阻，未验收。 |
| S7 | [最后MCP兼容批次命令](/var/tmp/feiyu-stage-d/mcp-p1-command-results.md)、[进度：MCP P1兼容交审](architecture-progress.md#d-mcp-p1-兼容实现交审2026-11-16未验收)：`mcp-p1-final-full-{314,310}` 各1750项/20skip、实际1730通过、内部exit0。**在最后响应导入后close小修之前**，不可称当前最终全量。小修后只有 S5 等定向/交错/smoke及重建ELF证据。 |

S5 新ELF：[feiyu-backend](/var/tmp/feiyu-mcp-close-review-20261116/build/payload/feiyu-backend/feiyu-backend)，SHA256 `17822b9dee90b1c986b9fda56e713fc9628584fac5583b8cc7d9beb53dae11e0`；provenance已对归档与源码核对。生产冻结父 `--serve` 无mock覆盖初始化/list/session/EOF DELETE；工具/取消由源码父驱动真实冻结worker，不是完整GUI/模型对话。两版探针使用同一个3.14构建ELF，不是两种冻结解释器构建。旧 `/var/tmp/feiyu-mcp-p1-final-build/` 产物不包含最后小修。

## 2. 原 D 十项逐条矩阵

测试名采用 `文件::类.方法`；代表直接入口与边界，不把“存在测试”写成“本次执行通过”。同一条含不同状态时分别列明。

| 原D项与全部要求 | 具体实现入口 | 现有测试/独立证据 | 当前裁定与剩余边界 |
|---|---|---|---|
| D1 在session/progress基础上增加schema_version、session_id、task_id、明确workspace | [taskstate.py](../feiyu/taskstate.py) `TaskState/read/workspace_identity/matches_workspace`；[session.py](../feiyu/session.py) `save/load/_journal_stub`；[progress.py](../feiyu/progress.py) `selected` | `tests/test_taskstate.py::TaskTests.test_full_request_revision_and_checksum`、`RecoveryClosureTests.test_inner_schema_and_legacy_identity/test_git_common_worktree_identity_and_unsafe_link`；S1及后续S7回归基线 | **已实现且审过基础范围**。v2身份含canonical root、Git dir/common-dir路径/dev/inode；旧身份只读兼容，不补造旧证据。TaskStore使用POSIX安全打开/flock；Windows writer未适配、未验，见平台表，不能仅称缺测试。 |
| D2 保存原要求/后续修订引用、目标、约束、验收、待办、预算消耗、验证引用 | `TaskState.revise/add_requirement/context`；[agent.py](../feiyu/agent.py) `_ensure_task_storage/task_control/_task_checkpoint/_check_task_acceptance`；[runcontrol.py](../feiyu/runcontrol.py) `attempt`；[providers.py](../feiyu/providers.py) `request_attempt/Billing` | `TaskTests.test_full_request_revision_and_checksum/test_agent_continues_unfinished_task_and_explicit_new`；`RecoveryClosureTests.test_cli_control_requirement_binding_rejects_forgery/test_real_verification_binding_rechecks_files_and_logs/test_restore_reconciles_unknown_and_recovers_full_facts`；`tests/test_sdk_accounting.py::SDKAccounting.test_main_helper_compact_reviewer_and_subagent_sdk_seams/test_session_unknown_survives_task_switch_and_restore`；S1/S4 | **已实现且审过相应范围**。原文UUID引用独立于压缩历史；约束/验收经用户 `/task` 录入，不再是空字段占位；验收绑定真实Ledger记录。无自动从自然语言抽取所有要求的硬要求。预算精度与停止边界见D10，不因存了数字就认定硬预算完成。 |
| D3 区分运行状态与任务结果；等待用户/中断/预算停止不能混同完成/部分完成/无法验证 | `TaskState.run_state/result/read`；`RunControl.check`；`Feiyu.send/task_control/_check_task_acceptance` | `tests/test_runcontrol.py::ParentControlTests.test_missing_usage_is_unknown_and_blocks_finite_budget/test_cancel_blocks_helper_reviewer_and_executor`；`TaskTests.test_agent_continues_unfinished_task_and_explicit_new`、`RecoveryClosureTests.test_real_verification_binding_rechecks_files_and_logs`；新增 `tests/test_task_results.py::Results` 8项；S1/S4及进度D3最新离线证据 | **D3补齐实施完成待审，未验收**。result明确unfinished/completed/partial/unverifiable；后两者仅由CLI/serve显式人工声明并保留说明、请求与验收/验证快照，不产生passed事实。继续工作清回unfinished，完成仍核对事实验收与未决操作；旧值只读兼容。见设计第25节、进度末尾及 `tests/test_task_results.py`；不将waiting_user/中断/预算停止推断为结果。 |
| D4 会话/任务隔离；同workspace多session互不覆盖；workspace进度为明确选定任务视图 | `TaskStore.__init__/save/activate/recover/pending`；`session.save`；`progress.selected`；`Feiyu._guard_task_switch/task_control` | `TaskTests.test_single_writer_and_multiple_sessions`、`RecoveryClosureTests.test_stale_object_and_unloaded_writer_cannot_overwrite`；`ActivePointerTests.test_multiple_pending_selection_does_not_bypass_guard_or_rewrite_history/test_recovery_validates_all_journals_before_rewriting_and_missing_pointer_blocks`；S1 | **已实现且审过同session与隔离范围**。同session单writer、active指针及全部journal未决集合；不同session拥有独立文件/状态，不互覆。不是所有session互锁；共享workspace文件并发冲突仍由文件版本/验证机制处理。本次不新增跨session全局pending阻断。 |
| D5 副作用前准备、完成后结果；崩溃窗口标结果未知 | [execution.py](../feiyu/execution.py) `Executor.invoke`→`TaskStore.activate/prepare/finish`；[tools.py](../feiyu/tools.py) `_tool_bash`；[jobrunner.py](../feiyu/jobrunner.py) `main`；[jobs.py](../feiyu/jobs.py) `DurableJob.refresh`；[lsp.py](../feiyu/lsp.py) `Client/Pool`服务接缝；[mcp.py](../feiyu/mcp.py) `Server.request/Registry.call` | `TaskTests.test_prepare_failure_starts_no_effect/test_finished_failure_unknown_no_replay/test_crash_windows_in_real_process`；`ActivePointerTests.test_isolated_hook_crashes_restart_via_session_and_serve`；`tests/test_job_lifecycle.py::Lifecycle.test_crash_windows_recovery_never_replays`；S1/S2/S3/S5；LSP S6 | **基础、job、前台及Linux MCP已实现且审过限定范围；LSP已实现待审**。启动不等于后台完成，serving不等于symbol结果；HTTP已发无匹配响应unknown，发送前明确拒绝not_run。prepared后即使实际上尚未启动也保守unknown。 |
| D6 恢复先核对当前文件/Git/进程或可查询外部状态；未知不得盲重跑 | `Feiyu.restore/task_control`；`TaskStore.recover/observe/reconcile/resolve`；`jobs.identity/restore_jobs/DurableJob.refresh` | `RecoveryClosureTests.test_unknown_reconcile_change_and_explicit_acknowledgement/test_restore_reconciles_unknown_and_recovers_full_facts`；`Lifecycle.test_identity_mismatch_never_signals/test_exit_without_receipt_does_not_become_success/test_running_recovery_old_pointer_pending_select_and_kill`；S1/S2；LSP `TestLifecycle.test_recovery`仅S6 | **本地/后台已实现且审过；LSP观察待审**。恢复校验身份/快照及文件Git指纹；job核对boot/starttime、收据及输出摘要。未知外部动作由现有只读查询+用户依据声明解除阻断；resolved=acknowledged-unknown，非成功、未执行证明或重放授权。通用外部查询适配器**非本次硬要求**，没有可查询事实时保留unknown，不能自行补造成功。 |
| D7 调用ID仅关联；任意Shell/外部写不宣称exactly-once | `TaskStore.prepare/resolve`、`Executor.invoke`、`Server.request` | D5/D6测试；`tests/test_mcp_lifecycle.py::MCP.test_after_send_http_cancel_is_unknown_remote_can_finish/test_timeout_late_stdio_response_cannot_be_reused`；S1/S5 | **已实现且审过所列范围**。不自动重发未知操作；取消本地等待/DELETE不撤销POST。exactly-once、外部状态原子快照、任意远端回滚**非本次硬要求**。 |
| D8 关键持久化失败显式处理，不能诊断式忽略 | `taskstate.atomic_json/critical_write/TaskStore.save`；`Executor.invoke` finally；`RunControl._save`；`Feiyu._task_checkpoint/cancel`；前台 `processwait.run` | `RecoveryClosureTests.test_raw_handler_critical_failure_is_not_tool_result/test_finish_cleans_every_resource_after_checkpoint_failure`；`Lifecycle.test_finish_write_failure_still_cleans/test_checkpoint_storage_failure_still_cleans_live_job`；`tests/test_foreground_lifecycle.py::Foreground.test_terminal_save_failure_preserves_exit_and_cleans_group`；SDK `test_pending_and_finish_save_failure_block_later_calls`；MCP `test_primary_wait_error_survives_cleanup_failure`；S1—S5；LSP S6 | **基础、SDK、前台、job、Linux MCP已实现且审过；LSP清理路径待审**。失败锁存blocked、阻新调用；执行后失败保留unknown与真实exit下界，清理错误不遮主PersistenceError。诊断sink可降级，不能代替关键journal。真实断电/内核阻塞不是已验证保证。 |
| D9 旧会话可读；按需迁移/适配，不批量重写用户历史 | `session.load/_read/_journal_stub/save`；`TaskState.read`、`Feiyu.restore/_ensure_task_storage` | `TaskTests.test_legacy_save_never_overwrites_original`、`RecoveryClosureTests.test_inner_schema_and_legacy_identity`；`tests/test_runcontrol.py::ParentControlTests.test_legacy_session_totals_are_not_task_spending`；S1/S4 | **已实现且审过兼容范围**。显式续接新增sidecar/ID，原件保留；丢失的旧原文无法重建。schema仍1不意味着旧writer可写新attempt_records/serving/not_run；降级先关闭writer/服务并备份完整session+journal，仅只读旧历史。不是无损双向降级承诺。 |
| D10 统一父总预算、截止、取消传播，覆盖helper/子Agent/reviewer/后台任务；安全收尾 | `Feiyu._control/_model_call/cancel`；`RunControl.attempt/check/tighten/wait`；`providers.request_attempt`；[subagent.py](../feiyu/subagent.py) `run`；前台[processwait.py](../feiyu/processwait.py) `run/_run/_cleanup`；`tools._tool_bash`→`jobrunner.main`；`DurableJob.monitor/wait`；MCP `_Wait/Server.request`；LSP `Client/Pool`普通入口 | `ParentControlTests.test_shared_main_helper_compact_reviewer_and_failed_attempt/test_deadline_and_allowance_survive_new_control/test_child_failure_accounts_usage_and_session_even_without_report`；SDK `test_parallel_helpers_share_parent_allowance/test_running_limit_tightening_and_restore_never_refills/test_cancel_during_sync_call_accounts_return_without_background_thread`；job `test_parent_cancel_api_cleans_even_without_wait/test_deadline_wait_and_newtask_reset_guard`；前台 `test_standalone_hook_parent_cancel_and_deadline/test_sigint_during_launch_and_repeated_cleanup`；MCP `test_deadline_restored_stdio_and_http/test_agent_cancel_pairs_protocol_result_once`；S2—S5；LSP S6 | **混合状态，未整体满足**。共享实际attempt账本、恢复不补额、失败/重试/fallback/partial/unknown累计已审；前台/job取消及启动时deadline、Linux MCP已审；LSP已实现待审。同步SDK静默等待是明确限制，后台运行中收紧已实施待审（设计第26节、tests/test_job_limits.py）；详见下一节。不能宣称硬总费用/总时限/即时取消已全覆盖。 |

## 3. 预算、截止和取消的精确裁定

| 行为 | 已有能力与裁定 | 最小下一步/可验收标准 |
|---|---|---|
| 总费用累计与准入 | S4已审：SDK内部max_retries=0，显式retry/fallback逐attempt写pending/结算；累计流usage去重；已知费用下界和未知总额分离。主/helper/compact/reviewer/subagent共父账本；失败和未知不免费；恢复/切任务不清旧未知。不是历史第17节所说“尚未计SDK重试”。 | 不重做记账项目。保留S4及现有回归。请求准入时不能预测服务端最终费用，单次已准入请求可超支；原文“总预算”不据此被改写为供应商硬扣费上限。Astra应明确其接受的边界，不能声称永不超额。 |
| 取消和deadline传递 | 受控Shell/hooks、job、MCP已有共享控制/有界轮询与清理证据；job监管者有独立启动时deadline，父死后仍按该值收尾；LSP只有实施证据。 | 保留LSP外部审查阻碍。OS调用/不可中断I/O、主动setsid逃逸及远端已执行动作不能承诺瞬停/回滚；不为此扩建通用监管框架。 |
| 同步SDK静默等待 | **明确未满足即时中止/请求总时限**。create、stream enter/next/close等待无法安全即时取消；事件、返回、重试等待处检查父控制。`FEIYU_STREAM_TIMEOUT`默认600秒是相邻读取等socket超时，非父任务总deadline。持父RLock的请求还会延迟其他线程检查/动态收紧。S4明确接受为已声明限制，不是硬取消通过。 | 若原D10按合作取消验收，须Astra显式裁定该例外并保留用户可见限制；若要求所有分支在父deadline内返回，则仍有真实能力缺口，需另行授权可中断SDK方案及相应审查条件。本文不通过改文案降低要求，不提出不可停止线程作为完成方式，不调用真实模型验证。 |
| 已运行后台job的父限制收紧 | **已实施待 Astra 审阅**：RunControl.background_limits锁存最严限制，父请求锁仅非阻塞尝试；DurableJob.monitor经原私有管道传更早deadline/停止原因，jobrunner独立收尾并保存真实exit/摘要收据。无wait亦覆盖费用已到、unknown遇有限值、显式cancel及持父锁场景；保存失败锁存原异常、收尾并保留unknown。不是新安全审查。 | 设计第26节、tests/test_job_limits.py九项及进度末尾双版证据。Astra需检查单调限制/无父锁阻塞、真实退出优先、关键错误传播及恢复仅观察；父已死只承诺最后传给监管者的deadline，未传出的配置不作实时保证。D整体仍未验收。 |

上表动态job缺口最初来自普通入口文档比对；现按授权完成最小实现与本地合成回归，实施证据仍待Astra审阅，未扩为新安全审查。费用/时间收紧已经覆盖SDK下一次准入（S4），不能将此缺口误写成整个RunControl未实现。

## 4. 原 D 必要回归逐项定位

| 原必要回归 | 真实入口与现有测试 | 证据/状态 |
|---|---|---|
| 写前崩溃 | `TaskStore.activate/prepare`→实际副作用；`TaskTests.test_crash_windows_in_real_process`、`ActivePointerTests.test_pointer_failure_prevents_hook_even_without_backend/test_isolated_hook_crashes_restart_via_session_and_serve`；job `test_crash_windows_recovery_never_replays` | S1/S2及S7基线。prepared前无本次副作用，prepared后即使未启动也unknown；不把进程退出当真实断电测试。 |
| 写后、记录前崩溃 | Executor/hook/job门禁、完成收据；`TaskTests.test_finished_failure_unknown_no_replay/test_crash_windows_in_real_process`；上述独立hook重启及job崩溃用例 | S1/S2。未知不重放；后台有独立收据也须身份/产物核对，不凭启动调用completed判完成。 |
| 重启后状态变化 | `Feiyu.restore`→fingerprint/reconcile/restore_jobs；`RecoveryClosureTests.test_restore_reconciles_unknown_and_recovers_full_facts/test_real_verification_binding_rechecks_files_and_logs`；job `test_replaced_output_is_unknown_before_and_after_restore/test_identity_mismatch_never_signals` | S1/S2；LSP `TestLifecycle.test_recovery`仅S6、待审。相同文件/PID不证明外部无副作用。 |
| 取消传播 | 父control→SDK/工具/进程；前台 `Foreground.test_shell_cancel_has_real_exit_and_unknown_journal/test_pre_post_and_verification_cancel`；job `Lifecycle.test_parent_cancel_and_job_wait_are_cancellable/test_parent_cancel_api_cleans_even_without_wait`；MCP `MCP.test_before_send_cancel_is_not_run/test_after_send_stdio_cancel_is_unknown_no_reuse/test_agent_cancel_pairs_protocol_result_once`；SDK `test_cancel_during_sync_call_accounts_return_without_background_thread` | S2—S5。同步SDK用例只证明返回后计账/停止，非静默中硬中止；LSP `test_cancel_init/test_idle_cancel/test_output_cancel/test_stdin_cancel`为S6，未独立审过。 |
| 预算累计 | 实际provider接缝→父账本；`ParentControlTests.test_crash_pending_usage_is_not_reset_on_restart/test_unknown_usage_keeps_known_lower_bound_and_explicit_zero`；SDK `test_retry_success_counts_each_attempt/test_fallback_is_separate_attempt/test_partial_input_missing_and_duplicate_usage/test_main_helper_compact_reviewer_and_subagent_sdk_seams` | S4。部分/未知保持下界、有限额度保守阻断；不据零字段缺省判免费。后台动态收紧缺口不能由这些用例替代。 |
| 损坏快照 | `TaskState.read/TaskStore.recover/session.load`；`TaskTests.test_future_sidecar_preserved`、`ActivePointerTests.test_pointer_corruption_future_missing_and_escape_preserve_originals/test_recovery_validates_all_journals_before_rewriting_and_missing_pointer_blocks` | S1，后续S7回归基线。校验失败保留原件、阻断，不以空状态覆盖。 |
| 旧格式读取 | session legacy适配→按需sidecar；`TaskTests.test_legacy_save_never_overwrites_original`、`RecoveryClosureTests.test_inner_schema_and_legacy_identity`；`ParentControlTests.test_legacy_session_totals_are_not_task_spending` | S1/S4。旧原文若已丢不可重建；新格式不能交给旧writer继续运行。 |
| 同工作区多会话 | 不同sid路径、writer锁、selected视图；`TaskTests.test_single_writer_and_multiple_sessions`、`RecoveryClosureTests.test_stale_object_and_unloaded_writer_cannot_overwrite`、`ActivePointerTests.test_multiple_pending_selection_does_not_bypass_guard_or_rewrite_history` | S1。最后一例是同session多任务，不替代前一例跨session测试；不扩大为所有session互锁。 |
| 恢复不会扩大授权 | `Feiyu.restore/task_control`→当前gate；`RecoveryClosureTests.test_cli_control_requirement_binding_rejects_forgery/test_cli_cancel_final_session_and_unknown_reset_blocked/test_unknown_reconcile_change_and_explicit_acknowledgement`；`TaskStore.prepare`授权仅exact-call/reusable=false；select清临时确认 | S1及S7基线。resolve只记人工依据，不重用旧确认、旧mode或调用ID授权；本次没有另做安全审查。 |

必要回归的定位不能代替最终冻结状态证据：S7之后变更了MCP响应消费检查；S5覆盖该变更及兼容/清理交错，但当前不存在最后小修后的双版全量结论。

## 5. 最小剩余工作、依赖与验收门槛

| 顺序/最小事项 | 依赖与可执行环境 | 可验收标准 |
|---|---|---|
| 1. 明确D3部分完成/无法验证结果 | **Astra已关闭本批范围**；复用TaskState、CLI/serve控制与verification/acceptance事实，证据见进度末尾及设计第25节。 | 持久化/恢复能明确区分completed、部分完成、无法验证与unfinished；运行状态仍独立，停止原因不自动冒充结果；不丢未完成验收项，兼容旧格式。无需新任务框架。 |
| 2. 后台job父限制收紧同步 | **实施完成待 Astra 审阅**；Linux普通本地预算范围，设计第26节、tests/test_job_limits.py及进度末尾。 | 存活父无wait场景中收紧后实际停止，保存真实收据与原因；关键存储失败照常收尾，恢复不发新授权、不重放、不加额度。9项真实合成回归覆盖无wait/持父锁/保存失败/父死亡/真实终态，普通回归不替代独立审阅。 |
| 3. 对同步SDK等待作明确D10裁定 | 需Astra/用户对原要求的验收边界裁定；技术能力限制非Linux多跑测试可消除。若要求可中断方案，须另有实施范围/条件。 | 清楚记录是接受合作取消的限定验收，还是继续保持未满足；不得称600秒socket timeout为父总时限，不称一次请求永不超额。裁定不能由本文代签。 |
| 4. LSP独立审查条件 | **外部阻碍**：仅在平台明确允许且另有有效审查条件后由负责人处理。当前Linux环境不得重试、接管、变更渠道或以矩阵工作替代。 | 有合法可用的独立结论且确定问题已处理；实施测试/最后全量均不能替代。条件未满足就保持未验收，不制造替代审查项目。 |
| 5. Windows MCP真实运行/冻结/NSIS证据 | **需用户Windows平台**。现有Linux假Win32 API/语法检查不够；`tests/test_mcp_compat.py::Compatibility.test_windows_backpressure_cancel_and_reap`在Linux skip。TaskStore安全writer未适配及LSP/job非Linux限制须分别声明，不因MCP适配而称整个D跨平台支持。 | 覆盖真实管道背压、CancelSynchronousIo权限/竞态/join、taskkill子树及失败路径、同exe冻结worker路由；安装器有其自身运行证据。Linux兼容P1已关范围不重开，但全平台结论继续待证据。若需D在Windows全功能通过，安全writer/LSP/job还需单独明确支持范围，不能用MCP通过代替。 |
| 6. 最终代码状态核验与D汇总 | 前述可实施修正完成、源码冻结后；Linux可在后续授权中按既有隔离runner执行适用双版回归，桌面路径有改动才跑相应现有检查。本批已授权普通离线双版冻结全量，结果见进度末尾；不执行受限LSP独立审查。 | 精确记录最终revision/未提交指纹、命令、内部exit、总数/skip/实际通过；不沿用小修前1750项当最终全量。如普通测试也受平台限制，则保留缺证据，不换渠道。Astra最后逐项裁定D，不勾任务书代验收。 |

历史ResourceWarning仍是未归属观察：前台3.10全量及后来MCP 3.14全量曾出现；无复现不等于排除，无即时创建栈也不能按旧PID推断泄漏。不新开审查；后续若自然复现，保留创建栈与即时状态后交负责人判断。macOS未验；没有承诺本批扩展到所有平台。

D3已由Astra关闭本批范围；运行中后台限制同步已实施待审；此外LSP/Windows/SDK裁定为外部或能力边界。除这些项及最终证据收口外，不重复开发已补的active指针、结构化要求、unknown人工闭环、job收据、前台等待、SDK尝试账本、冻结MCP路由和DELETE。

## 6. E 原任务接续顺序（仅计划，不实施）

遵循[设计第6节](architecture-evolution.md#6-e上下文与前端)及原E九项；先完成D的事实与结果接口、处理验收阻碍，再启动E。接口梳理不意味着当前E已实现或D已验收。

| 顺序/原E范围 | D依赖 | 最小交付与原必要回归 |
|---|---|---|
| E1 上下文分层；缓存意识（原第1、4项） | D1/D2稳定请求引用、约束/验收/预算/验证事实；D3结果表达 | 稳定规则/项目事实与易变任务状态/近期证据/按需历史分开；不每轮改写稳定前缀。按provider验证缓存相关行为；不用统一有损消息格式。 |
| E2 小步封装provider历史访问（原第5项） | 保留D请求账本/调用关联及C协议配对；沿用provider原生消息 | 只提取有调用方的小接口，保留图片、thinking及工具必需协议。回归切换模型、图片与工具历史，不重写整个provider。 |
| E3 压缩后程序核对；摘要引用验证（原第2、3项） | E1/E2；D pending/unknown、未完成验收、job/服务状态与B验证有效性 | 压缩前后程序比对目标/约束引用、未完成验收、未配对调用、unknown及运行job；缺失则补结构化事实或拒绝替换。强制压缩续作、约束保持、验证引用失效；assistant声称通过不能升格执行证据。 |
| E4 运行层结构化事件；会话/run隔离sink（原第6、7项） | D状态/operation/停止恢复事实；LSP服务事实仍受其验收条件约束 | 先执行开始/结束、验证失效、停止/恢复，CLI/Desktop各自渲染且兼容旧协议；显式携带session/task/run/seq，线程/嵌套不串sink、不双发。回归两个会话事件隔离、终端/桌面一致。无需重写全部UI。 |
| E5 来源跨摘要/子报告/记忆保留；保留Dreaming校验（原第8、9项） | E2/E3来源与引用接口；D请求user-control/执行证据区分 | 外部数据/assistant_claim/execution_evidence不在转述中升级权限；保留Dream来源、指纹、应用前检查，纯对话不作测试通过证据。回归来源标记保持，结合E3/E4核对跨压缩/前端链路。 |

E实施后才按影响运行对应普通回归与桌面检查；不得以本次文档工作宣称E完成。不实现F、多候选、可写子Agent、通用外部状态适配器或不可实现的exactly-once。真实模型收益与费用对账仍未验证，需另有明确费用授权及固定配置，不纳入本次文档任务。

## 7. 交接边界

保留HEAD、0.87.0、所有既有未提交文件及历史记录。只新增本文并在进度末尾追加索引/事实；不改原任务书勾选或覆盖旧裁决。将来回退须先退出writer/关闭服务，备份完整session目录和journal；不得只拷会话JSON、删unknown、重置预算或让旧writer覆盖新格式。本文引用临时目录证据仅在本机有效，正式归档前应保留报告、命令、result、日志及对应代码状态，不能仅留“通过”文字。

### D3 实施增量（2026-11-16，待审）

本文前述 S1—S7、历史“本次仅文档/不运行”均是矩阵初稿时点。本批仅按授权实施 D3 并执行普通离线回归，不进行或接管 LSP 独立审查。最新源码全量证据与精确命令见进度末尾 D3 节；不以普通回归代替独立审阅，不勾选 D。后台限制同步留下一批，E/F 未推进。


## 最新裁决补充：D3

D3已实现明确partial/unverifiable；独立审查发现select展示P2，Astra复用checkpoint修复并新增两项真实serve入口回归。原独立14项双版全通过，相关定向通过，D3本批可关闭；正文历史“待审”以本节和进度末尾为准。后台限制动态同步本批已实施待审，D整体未验收。


### D 后台限制同步实施增量（待 Astra 审阅）

第3节动态job缺口已按授权补实现，最新设计见第26/26.1节；九项真实合成后台回归和双版普通回归见进度末尾。保留D3 select checkpoint及全部10项结果测试；本批普通全量暴露旧LSP手构Feiyu夹具缺空Ledger，仅补夹具两行，不更改LSP产品/SDK语义，不构成受限LSP独立审查。无新安全审查/子代理/发布或E/F。

历史1759全量早于D3两新增；当前实测1770=原1761+本批9项，不能猜测1761即最终总数。所有失败轮次（wait错误锁存、旧夹具、kill次错遮主错、启动deadline理由竞争）和修正前已通过轮次保留在进度/命令索引，不当最终冻结证据。最终适用证据以job-limit-frozen-full双版内部result及冻结源码指纹为准；不凭外层runner退出0，不以20skip当通过。

审阅重点：持父锁时单调限制快照不阻塞与后续持久化不补额；pending与未知/到限费用区分；更早deadline/EOF与已死父的准确承诺；真实退出先观察及停止理由来源；保存失败仍收尾、原异常不被monitor/kill掩盖；恢复仅观察和pending/resolve保护不退。同步SDK静默等待、LSP受阻审查、Windows安全writer/MCP实机及macOS证据仍分别保留，D整体未验收。


### 最新裁决：后台父限制同步

独立审查发现首次take刷新后保存失败的P2，Astra补刷新后原异常检查及真实终态回归。双版定向各36项、原独立探针各5项通过，内部exit0，本批在已测Linux范围关闭。末次实施全量实际为job-limit-eof-final-full双版1770/20skip（更早frozen-full不适用末次stdin修复），但仍早于此次两行修复；当前最终全量缺口继续保留。精确命令见进度末尾。D整体仍未验收，SDK等待边界、受阻LSP审查与Windows实机等条件不变。

### 最新证据补充：2026-11-17 末次 take 修复后全量与 SDK 方案（待 Astra 裁决）

此节补充事实，不覆盖前述Astra已关闭D3/后台父限制同步的裁决，不自行验收D。末次take修复后的当前工作树已冻结并完成普通双版全量：3.14.10与3.10.20内部exit均0，各1771项、20skip、1751实际通过；runner分别181.664330/169.930096秒。此前1770项全量早于take修复，不用作本次最终证据。Node测试9/9及build内部exit0；真实Electron普通smoke/verify-trust使用归档夹具副本指向当前源码后端，在既有显示会话授权环境下均exit0。首轮缺XAUTHORITY导致两夹具exit1已保留日志，不计通过；未验证当前冻结包、Windows或NSIS。

完整归档`/var/tmp/feiyu-d-close-20261117/`：report.md、commands.txt、results-summary.json、内部result/日志、source-snapshot.tar.gz及source-sha256.json；109个Python源码/测试清单SHA256 `895da88566b45d8de21b572e1581771cf3cb5d8f0b81e03934a841ae85f3c845`。测试前后180个归档文件无变化，文档本次追加单列；精确命令与夹具修改范围见进度最新节。内部退出与日志均已核对，不能仅凭外层runner0。20skip不是通过，无本轮ResourceWarning不代表历史观察被排除。

原D10同步SDK等待仍未满足：只读方案sdk-plan.md比较既有transport/close、短timeout、隔离worker，建议每attempt可回收子进程，保留父账本与原生历史，父轮询取消/截止并kill+wait确认回收；需补锁等待、动态收紧、IPC/usage/冻结入口回归。未实施，不接受以合作取消替代原要求，不将后台线程残留称完成，不以usage缺失作零。

Windows缺口分开：MCP Windows已有实现但缺真实pipe背压/取消竞态/子树/冻结/NSIS证据；TaskStore安全writer、LSP Linux gate、durable job可靠身份与树监管还缺跨平台实现，不是只差实机。具体位置与下一步见windows-boundary.md。无Windows不做模拟通过；MCP Linux已关闭范围不重开。LSP独立审查受平台安全机制阻碍，本批未执行/接管/改写重试/换渠道，普通既有回归不替代。

HEAD仍d82d943、0.87.0未发布，未改产品/版本、未提交推送安装发布、未付费模型、未启动子代理。保留全部未提交修改；本批只追加两份状态文档，不实施E，不勾任务书。交Astra据本批Linux证据继续原D10实施与剩余条件处理，D整体及后续E/总验收仍未完成。

### D10 worker 实施证据补充（2026-11-17，非验收裁决）

同步SDK等待已由实施角色按Astra选择落地每attempt可回收worker，设计§27/27.1、进度最新节和`/var/tmp/feiyu-d10-sdk-worker-20261117/report.md`为最新事实；此前“仅方案/未实施”描述对应历史时点。父保有唯一准入/pending/usage与原生历史，worker仅一次真实SDK调用、max_retries=0；取消/更早deadline/锁等待/私有IPC背压、拒收迟到帧、kill+wait与管道关闭、原错误和partial/unknown下界已有实现。未将pending当已知超支，未改MCP业务协议、版本及已有P2。

最终冻结源码双版全量内部exit0，各1786项/20skip/1766实际通过（3.14 unittest210.349秒，3.10 209.201秒）；冻结后定向各108项exit0。Node9/9/build、真实源码Electron smoke/trust、当前PyInstaller冻结backend/MCP/SDK smoke内部exit0。SDK冻结覆盖两provider直接ask/stream及真实CLI父同exe success/cancel、无外部Python。源码122文件清单SHA256 `4fff3fd60399080e789cfd5f5f2064b4d3a56030232cbf5162653abcc5581018`，检查零差异后才追加交接状态文档。失败轮次及副本负对照完整保留，早期1785全量不代替最终1786证据。

仍需独立审查而非实施角色自行豁免：回收unknown/原错误优先、预算/锁/动态收紧竞态、SDK模型及异常兼容、冻结路由、敏感数据不出stdin和usage完整性。Windows/macOS无实机；真实SDK父硬死恢复及回收失败/连续非事件噪音/完整tool回调loopback矩阵未新增穷尽。父硬死亡无独立SDK监管保证，本地取消不撤远端生成或收费，单次可超额；模型列表和custom client旧路径边界明确。见report逐项说明和迁移回退。

D10实施交接不等于D验收；本批不勾D、不推进E/F、不接管/重试受阻LSP独立审查、不提交推送发布。HEAD d82d943/0.87.0未发布和全部既有未提交工作保留。待Astra据代码及证据独立裁决/安排剩余故障验证和平台证据。


## Astra裁决：D10 F1/F2关闭与E接续（2026-11-17）

已读 /var/tmp/feiyu-d10-sdk-fix-review-20261117/report.md。双版新增5项/16子情形及原独立2项通过；新隔离冻结SDK smoke通过，8个代码对象与当前源码匹配。接受本次限定范围关闭F1/F2：接受前停止撤销本次历史并保留partial/failed_or_interrupted，接受后由工具门禁停止且补配对；cleanup unknown不被retry/cache/agent救援隐藏。不是D10/D整体验收，也不宣称全平台或硬死亡清理通过。修复后全量仍待后续最终冻结验证。

原任务书第7节允许逐项记录阻碍及下一步；用户已授权推进E和总验收。现启动不依赖缺失Windows/LSP审查证据的E上下文/历史整理，不以E启动倒推D通过。Windows安全writer/LSP/jobs实现与MCP/SDK实机缺证据分开保留；受阻LSP审查不重试；SDK父硬死亡/平台等限制继续列入最终交付。整个任务书满足完成条件前不提交、不推送、不发布。
