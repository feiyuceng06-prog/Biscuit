# Architecture evaluation preparation / 架构评测准备

程序回归已验证，真实模型收益尚未验证。Program regressions are verified; real-model benefit is unverified. This is an offline handoff for taskbook §6, not acceptance of D, E or the taskbook. No paid authorization is present. Version remains unpublished 0.87.0, HEAD d82d943e64dcf4129e5bc44f4798abff6949da83.

## Implemented offline path / 已实现的离线路径

`evals.architecture` has no product/provider imports. It consumes `evals/architecture.json`, materializes actual temporary fixtures, rejects unsolved fixtures, accepts scripted reference artifacts, rejects added agent tests, writes a source/environment/schedule lock, synthetic JSONL and a strict aggregate. It does not use `evals.run._isolate`: that routine copies real model credentials and state. The existing `run._drive` executes `Feiyu.send`, but does not support controller-triggered compression/restart, immutable judging, exact model request attestations or complete unknown-cost accounting. Its `agent.cost or 0.0` cannot be imported as evidence of zero cost. Existing `evals.report` pairs by task name and omits certain failures; the new aggregator preserves task/repetition/arm identity, explicit failure categories and missing rows. Existing suites and runner behavior are unchanged, and their regression tests are included.

每组 1 个开发任务 + 1 个保留任务，各 6 次、两臂交替先后，共 96 条计划观察。开发/保留不混合聚合；保留题是已公开的固定夹具，不是秘密 benchmark，不能在看过结果后继续调参再称保留收益。只有一题/分组的样本多样性远不足以推断整体能力。真实评测前需冻结更多未用于调试的任务及判据。

| Group / 对照 | Concrete fixture / 实际夹具 | Live controller action still required / 待接通 |
|---|---|---|
| Original baseline vs extracted executor | Cross-file rename, exact final artifact inventory | Dual-source agent startup and fixed four-tool allowlist |
| Original vs version-linked verification | Set a constant, preserve unrelated artifact; final content plus controller verification fact | Inject mutation after first pass; independently observe verification of final bytes |
| Original compression vs task-state check | Two constrained deliverables plus protected file | Invoke real compaction after first write; continue without restating constraints |
| Original vs new recovery | Once-only operation request plus completion artifact | External service receipts, disconnect at acceptance, real session restart and unknown handling |

`architecture_cases.spec/setup/judge` implement fixture and final artifact checking. `golden` supplies **synthetic controller facts** only. The live action schedule is data, not an implemented product hook. In particular, offline `compacted=True` or `exactly_one_operation=True` proves no real compression or recovery behavior. Tamper checks reject changed/extra artifacts without executing submitted tests. A real agent must run as another UID/container unable to access controller code, expected answers, locks, external receipts and result files; this isolation is **not implemented here**, and filesystem read-only bits under the same UID would not suffice. Hence live execution fails closed with exit 2.

## Frozen inputs and confounding / 固定输入与混杂

The configuration proposes exact `openai/gpt-4.1-2025-04-14`, temperature 0, top_p 1; seed is unspecified because provider support has not been established. Auxiliary calls must use the same exact version. Availability and returned model revision are unverified; an alias or changed response model must stop the run. No model availability claim is made. Model metadata is a proposed run contract, not evidence that this harness configures live API parameters.

Prompt text, fixture/event contents and judge code receive SHA-256 locks; native system prompts must be captured and locked per arm by the pending startup adapter. Tools are limited to read_file/write_file/edit_file/bash. Each observation has total 30 rounds, 120 seconds, CNY 3 and 2 attempts including retries; helper calls and failed calls consume those totals. Exhaustion is `budget_stop`, not success. Unknown prices never replenish a budget: monetary enforcement is a live prerequisite. Tools do not include external web, memory or Dreaming; compression and once-only operation service are controller actions, not invented product switches. A compatible controller/service adapter remains necessary.

Two arms are immutable HEAD and the complete uncommitted product/evals snapshot, with separate content hashes. There is **no reliable single-feature old variant** in this handoff: HEAD vs current includes B/C/D/E and native prompt differences. All four comparisons are therefore `confounded_full_snapshot`, never causal isolation of executor, verification, compression or recovery. Feature-specific historical reconstruction, review and negative controls remain pending; no shell worktree or product flags have been invented.

Each dry-run lock includes full per-file product/evals hashes, HEAD hashes, interpreter SHA-256, exact installed distribution versions, Python/platform and ordered schedule. Python 3.14 and 3.10 are separate environments, never pooled as interchangeable runs. Before paid runs, select and freeze one identical dependency/runtime/container image for both arms, resolve install/build differences, materialize read-only source bundles without changing this workspace, and capture rendered prompts/tool schemas/provider request settings. The present source snapshot alone does not freeze OS binaries or remote provider behavior.

## Commands / 命令

All commands below run from `/home/Feiyu/AI_Agent/feiyu-agent`. Use a new absolute D_RUN and a new `--out` each time; the unchanged `/var/tmp/feiyu-stage-d/run.py` supplies fresh HOME/XDG, an environment whitelist and a 240-second process-group hard timeout. Inspect the **internal** `full-314-result.json` or `full-310-result.json` exit code; outer exit 0 is insufficient.

```sh
D_RUN=/var/tmp/feiyu-evaluation-preparation-20261118/recheck-314 \
 .venv/bin/python /var/tmp/feiyu-stage-d/run.py \
 /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python \
 -m unittest tests.test_architecture_evals tests.test_evals -q

D_RUN=/var/tmp/feiyu-evaluation-preparation-20261118/recheck-310 \
 .venv/bin/python /var/tmp/feiyu-stage-d/run.py \
 /var/tmp/feiyu-stage-b/py310/bin/python \
 -m unittest tests.test_architecture_evals tests.test_evals -q

D_RUN=/var/tmp/feiyu-evaluation-preparation-20261118/recheck-dry-314 \
 .venv/bin/python /var/tmp/feiyu-stage-d/run.py \
 /home/Feiyu/AI_Agent/feiyu-agent/.venv/bin/python \
 -m evals.architecture dry-run \
 --out /var/tmp/feiyu-evaluation-preparation-20261118/recheck-dry-data-314
```

Inside the same isolation mechanism, `-m evals.architecture validate` checks config/schedule, and `-m evals.architecture aggregate --input <dry-output>/synthetic.jsonl --lock <dry-output>/lock.json` validates and aggregates. Use Python without `-O`; optimized execution is rejected. Exact executed commands and both versions' results are retained in the evidence directory's `commands.json`.

Future paid invocation contract (currently intentionally blocked):

```sh
# ONLY after explicit fee authorization, dedicated credentials, exact model and
# environment/source/prompt locks, protected judge and live adapters are ready:
<locked-python> -m evals.architecture live --config evals/architecture.json \
 --out <new-protected-result-directory>
```

This command **currently exits 2 without calling a provider**, regardless of credentials. It is not an assertion that running it performs a paid evaluation. Implement the adapters listed above and review their budget/billing/isolation tests before enabling this entry. A fresh frozen config and protected locks must then be produced; do not change `live_ready` to bypass validation. Existing `python -m evals.run` defaults to real calls and must not be used for this preparation.

## Results / 结果契约

`evals/architecture-result.schema.json` is the per-line JSON Schema. `validate_row` and `validate_bundle` additionally check finite nonnegative values, exact task/model/prompt/source/judge/plan identities, duplicate/unplanned observations and mixing synthetic/real data. Runtime validation has no new dependency. Truncated JSONL fails loudly; no silent discarded paid rows. Empty/partial runs report missing observations explicitly. Synthetic and real files must be separate.

Every row includes group/split/task/repeat/arm, schema version, `synthetic`, model/version and content identities, status, wall seconds, human intervention count, `accounting_complete`, and an attempts list with primary/auxiliary/failed costs. A missing invoice/price is `null`, never 0; actual no-charge invoices can explicitly report 0. An unavailable billing ledger must emit at least one unknown attempt and set accounting incomplete. All attempts, including helper and failed retries, remain in cost and time totals. No legacy result conversion is implemented because the old fields cannot establish complete billing, intervention or event provenance.

Status is independently supplied by the pending controller: success / agent_failure / environment_failure / budget_stop / provider_failure / judge_failure. Content failures are agent_failure; fixture/provisioning failures are environment_failure; API/transport failures are provider_failure; unavailable/broken grading is judge_failure. Budget exhaustion stays budget_stop even if partial artifacts look correct. Infra failures never become agent correctness failures.

Aggregate reports per group/split/arm: observation count, distinct task count, successes, judged denominator (success + agent failure + budget stop), all-attempt success rate, status counts, missing planned observations, wall seconds and human interventions. Environment/provider/judge failures remain visible in all-attempt counts/costs but are excluded from judged correctness denominator. Wilson 95% intervals are **descriptive only**: repeats of a task are correlated. No paired improvement or causal effect is reported. `known_cost_cny` is only the known lower subtotal; `total_cost_cny=null` if any unknown attempt or incomplete ledger exists. Missing observations are not zero-cost or failures.

## Handoff and remaining acceptance / 交接与总交付缺口

Evidence: `/var/tmp/feiyu-evaluation-preparation-20261118/`, including initial source archive/status, HEAD and uncommitted content manifests, final locks, commands, internal runner results/logs and report. Initial and final snapshots are distinguished; synthetic files are explicitly labeled. No product runtime changes, version bump, stash/reset, commits, pushes, publication, real credentials/history/memory/Dreaming reads or LSP review attempts occurred.

Taskbook §7: A–E retain earlier limited acceptance and recorded boundaries; this batch supplies §6 offline tooling, bilingual notes and handoff only. Existing final product regressions remain E8/9 final2 (both 1829 tests, 20 skips), not rerun or newly claimed here. Product unchanged, so no full desktop rerun. D platform/Windows, SDK parent hard death, blocked independent LSP review, historical unresolved ResourceWarning origin and real-model benefit gaps remain open. Migration remains the earlier stop-writers/full-session-and-journal backup procedure; unknown operations must never be replayed and spent budget must not be restored. Rollback of this batch removes only these new eval files/test and appended documentation; preserve all inherited changes. Astra must review this handoff; implementation does not sign D/E/taskbook completion.


## 2026-11-18 Astra review fixes / 审查修复（待独立复核）

R1–R5: new locks explicitly bind offline_synthetic / fixture_self_check; all real-labeled rows and live locks are rejected until a protected execution adapter exists. Lock validation now checks its schema, baseline object, nonempty source manifests, SHA formats, judge/source agreement, exact schedule and required environment descriptions. Baseline hashing reads the configured commit, not symbolic HEAD. These are structural and self-consistency checks, **not source authenticity attestation**; protected source-bundle verification and actual execution remain pending.

配置所有字段与精确类型均按显式契约检查。aggregate未传--config时仅使用归档lock中的配置；显式传入时必须完全相同。新锁需要模式/版本/基线字段，旧合成锁保留作历史证据但不自动补字段为有效新锁，应重新dry-run。不得通过手改模式将旧合成数据转为真实结果。

Result validation rejects boolean schema versions and invalid object/hash types; sums must remain finite and JSON output disallows NaN/Infinity. All sixteen planned cells now report planned/observed/missing counts even when empty; empty rates and total cost remain null. 没有改变真实live固定拒绝的状态，四组真实执行适配仍未完成。

双版定向各58项、6skip、52实际通过，内部exit0；证据 `/var/tmp/feiyu-eval-fix-20261118/target-314/`、`target-310/`。8项新增回归覆盖整包改标、损坏锁、配置字段/CLI冲突、类型、费用及时间溢出、空计划单元和固定基线读取。没有重跑未变化产品全量/桌面。程序回归已验证，真实模型收益尚未验证。未提交/推送/发布，未接管受阻LSP审查；D/E既有限定与平台/父硬死等缺口保持。


## Astra裁决：关闭评测R1–R5离线缺陷（2026-11-18）

核对 `/var/tmp/feiyu-eval-fix-review-20261118/report.md`：双版各58次独立CLI检查符合预期，定向各58项/6skip/52实际通过、内部exit0，234文件与工作区状态不变。关闭R1–R5及空计划单元消失的问题，仅限离线结构、自洽、类型和统计；不将输入自带hash解释为源包真实性证明。

下一批沿用已有四组夹具和结果契约，以离线假provider接通真实产品执行：固定基线与当前包的双源码装载/核验、实际验证变更/压缩/恢复事件、控制器判题边界和请求预算账单。保持合成标签及confounded_full_snapshot，不调用收费或真实远端模型；缺授权live继续拒绝。§6尚未完整交付，D/E和整任务书不据此自动验收。平台/SDK父硬死/受阻LSP独立审查/历史ResourceWarning限制保留；所有既有改动、HEAD d82d943、0.87.0保持，不提交推送发布。

## Offline product execution / 离线产品执行（2026-11-18，待 Astra 审阅）

`python -m evals.architecture fake --out <new-absolute-directory>` now executes the actual products from two ordinary frozen source directories. `config.baseline` supplies the git-object bytes; the snapshot includes all tracked/untracked nonignored package files in `feiyu/**`, `evals/**`, and `pyproject.toml`. Exact inventory/byte checks precede and follow execution. Only `feiyu/` is exposed to the worker: evaluation cases/answers remain hidden. Each arm runs in a separate bubblewrap PID/mount/network namespace, using the same selected interpreter and read-only dependency environment. Interpreter bytes, dependency file manifest/digest (excluding generated bytecode), package versions, imported product module paths/bytes and actual native system/tools/request payloads are recorded. Feiyu distribution metadata is excluded from dependency *version* identity because an editable checkout can expose stale duplicate metadata; product identity is the verified source manifest. OS libraries are not a reproducible OS image.

The adapter filters native schemas to the four configured tools and explicitly injects temperature=0/top_p=1 at the fake transport boundary. It uses native OpenAI-compatible request construction, stream parsing, tool execution, compact, session save and restore; it does not initialize an SDK client or load real credentials. Missing optional APIs on HEAD are observed without simulating new features. Both interpreters produce separate evidence; they are not equivalent environments or pooled observations.

The parent owns the judge, expected files, locks, ledger and service receipts. Synthetic sentinel answer/result/receipt/lock files exist outside the namespace; actual read/write probes fail, and product/adapter writes fail on read-only mounts. The worker has writable task and synthetic session directories only. Missing bwrap/namespaces is an environment failure, with stderr retained; there is no same-UID chmod fallback. The trusted adapter reports program observations, not model-supplied booleans. This is a wiring boundary check, not an adversarial security certification.

Four development paths now execute: rename after real reads; real automatic verification followed by controller VALUE=0 mutation, stale check, reread/repair and final verification; real compact after the first write followed by `continue` without repeated constraints; and an actual Unix operation-service accept followed by disconnect/process kill, native saved-session restart and a requested replay. In the recovery fixture an unknown operation intentionally leaves the requested completion artifact unfinished: `agent_failure` is retained even when the safety guard correctly refuses replay. No invented completion receipt or golden answer is supplied. HEAD lacks the durable unknown guard; the current product rejects replay with its real PersistenceError. Public holdout and full 96-row schedule are not executed by this small wiring run.

`Ledger.invoke(request_id, role, transport)` admits at most two physical attempts per logical request; role is primary/auxiliary and failure is an outcome, never an additional charge. The parent ledger survives child restarts. Thirty primary rounds, 120 elapsed seconds and CNY 3 are cumulative observation limits, not per restart. Unknown price/missing invoice fail closed; failed/auxiliary attempts retain their invoices; exhausted retries or exceeded budgets remain budget_stop. Offline boundaries cover zero, unknown, missing, duplicate identity, retry exhaustion, round/time/cost limits. Fake zero invoices describe synthetic requests only. The worker subprocess has parent-selected deadline/process-group cleanup in finally. Provider transports must themselves honor deadlines; the callback interface alone is not a reviewed live SDK timeout/billing adapter.

Output: `execution-lock.json`, verified package/dependency manifests, per-observation `controller.json` (requests and SHA locks, facts, ledger, worker exits), worker logs, and `synthetic.jsonl` validated by the existing row validator/schema. Execution locks use `artifact_type=synthetic_product_execution`; they are deliberately distinct from dry-run fixture locks. Existing aggregate rejects them; the execution summary is the controller wiring report, not a real-results aggregate. R1–R5 remain closed within their prior scope. Portable receipts are not cryptographic attestation against a malicious host/controller.

For an authorized future run, the concrete parent adapter seam is `execute(out, manifests, config, arm, group, adapter, transport=callback)`. The callback receives `(native_parameters, request_id, attempt, role)` and returns `{cost_cny, invoice, outcome, response: {version, text, calls}}`; failed attempts must return an invoice or unknown cost. This reuses verified packages, worker, native product actions and Ledger.invoke. A dedicated credential/version-pinned provider implementation, deadline enforcement and independent review must be added before this seam is approved for paid use. `live` still exits 2 without loading configuration/keys or calling a provider. This batch does not deliver a live SDK/billing adapter or authorization mechanism; do not invoke default `evals.run`.

程序回归已验证，真实模型收益尚未验证。Confounded full snapshots, scripted responses and a few public cases support no model, cost-benefit or single-feature causal claim. Evidence/protocol/failures: `/var/tmp/feiyu-eval-execution-20261118/`. Product code and version remain unchanged by this batch. D platform/Windows, SDK parent hard death, blocked LSP independent review and historical ResourceWarning limits remain; D/E/taskbook acceptance requires Astra's independent review.


## Astra F1读帧期限修复（2026-11-18，待独立复核）

父worker stdout改为非阻塞字节读取、自有换行缓冲；每次select/读取后及处理完整帧前检查同一观察deadline。半帧保持开启超期为budget_stop，半帧EOF明确environment_failure，帧大小上限8MiB。父回复改为非阻塞os.write和可写等待，同一期限控制背压，避免readline/flush无限等待。finally保留杀组和回收。没有改变已声明同步transport callback自身须实现deadline的live接线限制。

新增真实bwrap半帧保持/EOF回归和真实管道写背压回归。双Python各65项、6skip、59实际通过，内部exit0；两版fake各8条真实产品观察均跑完：executor/verification/compaction各双臂success，recovery双臂agent_failure，未将unknown阻断冒充任务完成。证据 `/var/tmp/feiyu-eval-frame-fix-20261118/` 的target-314/310、fake-314/310内部result和data-314/310。产品源码未变，不重跑产品全量或桌面；原final8仅为修复前证据。真实模型收益未验证，D/平台/SDK父硬死/受阻LSP/历史ResourceWarning限制保持。未提交发布。


## Astra裁决：评测F1关闭与§7总交付核对（2026-11-18）

已核对 `/var/tmp/feiyu-eval-frame-review-20261118/report.md`：双版65项/6skip/59实际通过，独立真实worker/pipe验证半帧deadline、分段帧、EOF、回复背压、8MiB上限及kill/reap/关闭。修复后两版各8产品观察与当前声明源码包一致。关闭F1，仅限离线fake父控制器读写帧；不覆盖同步live callback内部期限。

接受§6当前离线准备交付范围：四组配置/夹具/命令/结果契约、结构与统计校验、双源码实际装载及小规模假provider产品路径。真实运行仍缺受审live SDK callback、专用凭证及费用授权、固定远端版本确认、真实开发/保留任务多次试验与收益报告。恢复题agent_failure保持，未知阻断不冒充完成；整体快照对照不推导单特性因果收益。该有限接受不等于§6真实运行或D/E/总任务书验收。

接下来按任务书§7核对每项交付及证据、迁移回退、当前D/E状态和剩余阻碍，形成统一矩阵，避免历史待办与最新裁决混淆。平台/SDK父硬死/受阻LSP独立审查/历史ResourceWarning继续保留；任务书完成前不提交推送发布。HEAD d82d943、未发布0.87.0与全部既有修改保持。

## U6 SDK minimum batch / SDK最小批次（2026-11-19，交Astra独立审查）

`python -m evals.architecture loopback --out <new-absolute-directory>` now runs the eight development observations through the installed **OpenAI native SDK and a local synthetic HTTP service**. Use the same fresh D_RUN/whitelist runner shown above. `fake` retains its earlier meaning. Both modes remain synthetic; neither is a real-model experiment. All full-snapshot confounding, native per-arm prompts/requests, protected judge and recovery `agent_failure` facts above remain in force. The endpoint responses deliberately follow the existing public wiring script, not model reasoning. Only OpenAI-compatible product request construction is adapted; an Anthropic-native product path is **not delivered** by this batch.

Design was saved before implementation at `/var/tmp/feiyu-eval-sdk-adapter-20261119/design.md`. The eval-only SDK child imports no `feiyu` module, so the current product cannot replace baseline code via the SDK helper. It uses the selected interpreter/installed SDK, records SDK version, source/child/interpreter fingerprints and binds native request hash, requested/returned model and literal endpoint to parent-generated receipts. The frozen snapshot supplies the child script. Installed SDKs using httpx and httpx2 are selected from the client's declared interface. Existing product SDK lifecycle workers were read but not reused: their exception path imports current product providers and their control interface belongs to product RunControl. This small eval process keeps that source boundary explicit.

The new `transport.invoke(native_parameters, request_id, attempt, role, absolute_deadline)` seam passes the **same observation deadline** into SDK startup, nonblocking request writes and response reads, including silence, half IPC/SSE frames and backpressure. Parent finally kills the process group, waits and closes pipes on normal failure, timeout and cancellation. Legacy callable transport remains supported but is not given this deadline guarantee. Ordinary Linux cleanup assumes the parent survives, scheduling/local I/O work and direct children are killable. Simultaneous parent death, escaped descendants and remote request revocation are not guaranteed; existing U4 product acceptance does not automatically cover this new eval child. Child stderr is suppressed; structured error type/EOF and parent events are retained, not supplier error prose.

Ledger reserves an unknown attempt **before** dispatch, including spawn/exception/cancellation failures. SDK `max_retries=0`; only parent attempts may retry. Primary and auxiliary attempts share time/money/attempt budgets across restores. Usage observations are nonnegative monotonic lower bounds. Missing/incomplete usage leaves `cost_cny=null`, `usage_complete=false` and stops admission without restoring budget. A separate `estimate_lower_bound_cny` retains partial observed usage × rates; it does not complete the bill. Complete successful usage is priced with the recorded fixed input/output CNY-per-million rates, under `accounting_basis=usage_fixed_price_estimate`. These fixture rates (1/2) are synthetic, **not provider tariffs**. `invoice` and `supplier_invoice` remain null. Successful synthetic estimates can enforce the offline budget; they do not prove a vendor invoice or authorize live estimation. HTTP failure without usage stops after one physical request, rather than assuming failed requests are free; parent retry mechanics with complete synthetic estimated receipts are tested separately. No remote billing/reconciliation adapter is delivered.

Receipt files are generated by actual parent execution. `execution-lock.json` identifies `openai_sdk_loopback`; all rows remain synthetic and existing aggregate still refuses execution locks and whole-bundle synthetic-to-real relabeling. Local host/controller tampering is outside this receipt trust boundary. No old data conversion is added.

`live` still exits 2 **before reading configuration or credentials**. Both transport and child restrict endpoints to literal `http://127.0.0.1:<port>/v1`, use only `synthetic-evaluation-key`, disable HTTP redirects/proxy environment and never load a provider key store. The remote contract design requires explicit fee authorization tied to endpoint/model, dedicated credential file, source/runtime/prompt locks, cumulative budget and an explicit estimate-versus-invoice billing policy. `require_remote_contract` rejects missing fields and also rejects a fully supplied object: it is a denial gate, not a reviewed positive authorization validator. Remote enabling, credential ingestion, exact supplier-version verification and billing policy need a future reviewed batch plus user fee authorization. Do not invoke `evals.run` for this work.

双Python最终final3-target定向各76项、6skip、70实际通过，内部exit0；locked-loopback两版各8观察，前三组双臂success，恢复双臂agent_failure。覆盖真实SDK正常流/辅助响应、HTTP失败不隐式retry、usage未知/partial下界、返回版本漂移、静默/半帧、IPC写背压、取消清理、真实产品保存失败、授权缺失及HTTP跳转拒绝；既有混标与整包改标拒绝回归仍通过。副本负对照把SDK max_retries改1后预期失败，真实保存失败观察及其账本/日志单独留存。首轮httpx不匹配的失败完整保留，不能计作成功。

Evidence/report: `/var/tmp/feiyu-eval-sdk-adapter-20261119/`. This batch changes only evals, its new test and necessary documentation; no product/version/build/package update, real keys, real provider/history/memory/Dreaming access, LSP review, install, commit, push or release. Product full-suite/desktop checks are not repeated for eval-only changes; prior U4/U7/U8 evidence keeps its original scope. Windows, blocked LSP and historical Warning limitations remain. 程序回归已验证，真实模型收益尚未验证。U6/D/整任务书不自行验收，交Astra独立审查。


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

## Anthropic native offline path / Anthropic原生离线路径（2026-11-19，待Astra独立审查）

`python -m evals.architecture anthropic-loopback --out <new-absolute-directory>` uses the installed Anthropic SDK 2.8.0 and literal local HTTP with a synthetic key. Both frozen arms independently use their own `AnthropicBackend` to construct Messages, system/cache blocks, native tools, tool_use/tool_result history, auxiliary nonstream compaction and native restore. No OpenAI request conversion or current-product substitution for HEAD is used. `claude-sonnet-4-5-20250929` is the locked synthetic request/response label, **not verified remote availability**. Native temperature/top_p are omitted by the products and recorded as null (unspecified), rather than falsely asserting OpenAI's explicit sampling values. Both arms share frozen dependencies; prompts and full product snapshots differ and remain confounded.

本批先写设计 `/var/tmp/feiyu-eval-anthropic-20261119/design.md`。仅复用原HTTP guard的有界分行副本：按请求stream选择、CR/LF/CRLF及跨chunk、多data行、SDK转换前检查；OpenAI默认校验保持。Anthropic使用带类型Messages事件而非choices/[DONE]，原始message_start/message_delta usage分别校验；输出计数累计取最大值，不把增量事件与最终Message再加一遍。普通input、output、cache_read和cache_creation四项分列；可选缓存项缺省为零，显式null/bool/负数/非整数、未知字段/事件和不支持的usage metadata拒绝。嵌套5m/1h creation明细只校验总和，不重复计价；本地合成固定价(1,2,0.1,1.25) CNY/百万token不代表供应商报价或TTL价格。invoice/supplier_invoice始终null，partial仅作下界，未知完整成本null并停止准入。

The original controller deadline, reservations per physical attempt, retry admission and cancellation persistence remain shared. SDK implicit retries, environment proxies and redirects are disabled. SDK children are killed/waited on timeout/cancel/backpressure; the surviving controller saves requests/events/partial ledger and rethrows the original cancellation even if persistence fails (with a separate diagnostic). This does not extend U4 guarantees to controller hard death. Receipts bind endpoint/model/SDK version, interpreter, adapter/semantics/child hashes, request hashes and full frozen product/dependency manifests. Source drift fails closed.

Evidence: `/var/tmp/feiyu-eval-anthropic-20261119/`, including design, exact internal command/result/logs, failed rounds, copied-source negative control, native and OpenAI product locks, source/artifact fingerprints and report. Dual Python targeted suites: 86 tests each, 6 skipped, 80 passed, internal exit0. Actual SDK checks cover stream/nonstream, cumulative/cache usage, malformed/missing usage, cancellation and persistence failure, silence/partial frames/backpressure, retry/remote refusal and source drift. Four groups execute in both arms; recovery stays agent_failure, including snapshot unknown-operation replay refusal. These observations are synthetic wiring checks, not model benefit. See the report for final frozen runs and additional probes.

Live remains exit2 before config/real credentials access. Positive remote authorization, dedicated credentials, fee authorization, real invoice reconciliation and real-model benefit remain undelivered. U4/U7/U8 limited rulings, blocked LSP independent review, Windows follow-up and historical Warning limits remain unchanged. No product/build/version/install/commit/push/release changes; inherited edits preserved. Next: Astra independent review; this implementation does not accept U6, D or the taskbook.


## Astra Anthropic AR1终态修复交审（2026-11-19）

针对 `/var/tmp/feiyu-eval-anthropic-review-20261119/report.md` 的P2，父适配complete显式检查原生stream事件顺序：message_start未提前停止、message_delta含有效终态停止原因和output计数、随后message_stop；重复/逆序/缺失终态拒绝。SDK final snapshot/HTTP EOF/child done不再单独证明完成。非流Message校验独立保留；失败保留已观察usage下界、cost=null并阻止账本继续准入。原始HTTP usage校验与产品代码未改。

新增真实SDK正常/缺stop/缺delta/start提前完成回归。双版五模块各87项、6skip、81通过、内部exit0。原独立10模式探针改为缺stop和start提前完成也必须失败，双版各10观察全部符合断言。修复后两版各8个四组原生产品观察通过布线检查，前三组双臂success、恢复双臂agent_failure，未冒充恢复任务完成。证据 `/var/tmp/feiyu-eval-anthropic-fix-20261119/` 含source/hash、每轮argv/env/内部result/完整log与产品源锁；本轮无失败测试，故障注入stderr如实保留。

AR1仍待新的独立复核，不自行关闭U6/D/任务书。全部本地synthetic，无真实模型费用/收益，无产品包变化、提交推送发布，HEAD/0.87.0保持。Anthropic正向远端授权/专用凭据/真实账单仍未完成。


## Astra Anthropic AR1有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-anthropic-fix-review-20261119/report.md`，接受AR1在Anthropic2.8.0受控eval路径有限关闭：双版各27实际SDK观察和12父层断言通过，旧semantics负对照复现原缺陷；缺失/逆序/重复终态保持下界/null成本并停止准入，正常工具块/非流保持。原始guard/共享adapter/child未变。继承双版87/6skip/81通过及各8原生观察已核对，不称新重跑。

原审查指纹唯一不符为finalize314/full-314.log，源于指纹扫描后同一脚本继续打印日志；该自指生成限制和provenance首轮失败保留。其余旧条目匹配，修复源码、产品观察与新独立证据匹配；不宣称旧清单全部字节吻合，下一次归档排除运行中的自生成文件，结束后另核验。

U6两供应商原生离线最小路径具有限接受证据，但正向远端授权、专用凭据、真实账单/远端版本与收益仍未交付。下一批实现可离线审核的授权契约/预算与输入绑定，真实网络执行继续默认拒绝，未获费用授权不调用provider。未验收U6/D/总任务书，无提交推送发布，产品和Linux包保持。

## U6 positive local authorization preflight / 正向本地授权预检（2026-11-19，待Astra独立审查）

`evals.architecture_authorization` now validates a separate exact-schema plan and asserted authorization record. `require_remote_contract` (also re-exported by `architecture_sdk`) returns a **local** acceptance receipt for matching valid inputs; it never enables a transport. This supersedes only the earlier statement that the function always denies. `python -m evals.architecture live` still exits2 before config/credentials, and both SDK transports/children still accept only synthetic literal loopback. No remote credential ingestion, execution or paid eval is implemented or authorized by this delegation.

准备完整候选计划JSON后，运行：

```sh
python -m evals.architecture_authorization template --plan candidate-plan.json > unapproved-template.json
python -m evals.architecture_authorization preflight --plan candidate-plan.json --authorization explicit-record.json --observed independently-prepared-plan.json
```

Template输出包含原计划及`fee_authorization`，默认`approved=false`、approver/record_id/granted_at/expires_at=null；不可直接通过预检。`--authorization`只接受单独提取并明确填写的记录对象。不得把示例合成身份、价格或模型版本当成真实授权/报价。CLI只读取显式提供的三个JSON输入，不stat/open计划中的`dedicated_credential_file`，不读产品keys/store/history/memory/dream。无效输入输出JSON rejected及exit2；有效预检exit0的JSON含计划/观察/授权hash与时间，明确remote_execution_allowed/session_fee_authorization/approval_consumed/host_attestation=false，invoice/supplier_invoice=null。重复JSON字段、NaN/Infinity、缺失/额外字段、错误类型（含bool数值）、过期/未来授权、漂移和预算扩大拒绝；同一授权不能匹配改变后的计划hash。

Plan schema is defined by `validate_plan`: run/provider/canonical HTTPS endpoint, model ID+exact version and SDK version; head/snapshot `source_lock` digests; per-arm interpreter+dependency digests; per-arm source-native `prompt_lock`; `task_lock`; explicit temperature/top_p/seed (null means unspecified) and same-version/sampling auxiliary policy; global max CNY/seconds/physical requests; issued/expiry timestamps; dedicated absolute credential filename. Locks must represent **all** frozen inputs: source digests over the full per-arm manifests, runtime digests over interpreter/dependency byte inventories, prompts over actual per-arm prompt bytes, task_lock over config/schedule/tasks/tools/judge; use canonical JSON SHA256 for structured manifests. The observed plan must be independently reconstructed from the intended current inputs rather than copied as proof of identity. This batch validates supplied digest syntax and equality, **does not itself measure those artifacts or verify model availability, approval origin or host integrity**. Self-consistent hashes are reproducibility identifiers, not trusted host attestation.

价格政策固定为CNY/百万token，各provider类别及每物理请求token上界锁定（Anthropic分列input/output/cache_read/cache_creation）；所有请求上界×类别价之和不得超过max_cny。此数仅`estimated_allowance_cny`，不是供应商invoice、实际费用或供应商保证的上界；rate_source是待核实的显式来源说明。unknown_cost=block，replenishment=forbidden，real_only_no_synthetic_merge固定。请求cap包含失败、重试、辅助请求，两源码臂共同消耗；未来远端控制器必须强制token上界并覆盖所有供应商费用类别，本批未实现该控制器，也未将本地Ledger的synthetic估算改成真实账单。零/未知总估算拒绝；缺任何类别价格拒绝。

Before any future live dispatch, the master must obtain concrete user fee approval for the finalized plan, review supplier endpoint/exact version/price provenance and budgets, then implement and independently review actual artifact measurement, approval-origin verification, dedicated no-follow credential ingestion and remote policy. A durable controller must atomically consume a single-use run ID **before** credentials/network and reserve every physical attempt before dispatch. Restart must retain the consumed approval, original deadline, reservations and spent/unknown costs; pending/unknown blocks until reconciled, never restores budgets or assumes a failed request is free. Preflight does **not** consume approval and is intentionally repeatable; no single-use/restart journal or real invoice reconciliation is delivered in this batch. The delegation and a locally valid asserted approval are not session fee authorization.

Evidence/design/report: `/var/tmp/feiyu-eval-authorization-20261119/`. Only eval/tests and necessary bilingual README/docs change; product/package/HEAD d82d943/0.87.0 and inherited modifications remain. 程序回归已验证的范围以本批报告内部结果为准，真实模型收益尚未验证。交Astra独立审查，不代签U6/D/总任务书；U4/U7/U8有限裁定、Windows后续、受阻LSP独立审查及历史Warning限制保持。


## Astra U6本地授权预检有限接受（2026-11-19）

核对 `/var/tmp/feiyu-eval-authorization-review-20261119/report.md`，接受本地契约语法/输入匹配/预算估算/未批准模板及预检收据限定范围。双版各5独立测试通过，删除observed绑定的副本负对照均预期失败；604旧指纹及30最终源码匹配，live/远端transport拒绝保持。不是批准来源认证、实际锁测量、用户费用授权或真实账单证明。

首轮3.10取消用例usage={}而预期8/2仍保留为未解释证据：1.5秒计时未与父层已观察事件同步，现有日志不足区分取消早于帧到达和已观察事实丢失。不据后续通过宣称根因修复，不无限重跑。后续若调整此夹具应增加可观测同步再作诊断，独立列明，不改变产品语义。

下一批补实际输入锁测量与测量预检，仍离线、不得读取真实凭据或发远端请求。单次批准消费/恢复预算及真实执行/账单/收益继续未完成。无提交发布或产品包变化，不验收U6/D/任务书。

## U6 actual measurement / 实际输入测量（2026-11-19，实施交Astra，未验收）

`evals.architecture_measurement` adds a separate **v2 measured plan**. The v1 contract and its caller-input-only receipt remain available for compatibility; they are not measurement evidence. Measured preflight accepts v2 only and does not accept a user-supplied observed manifest. It independently freezes/rechecks both packages with `freeze`/`verify_package`, reads baseline Git blobs and the explicit repository scope (`feiyu/`, `evals/`, `pyproject.toml` inventory), and regenerates the observed plan. Source symlinks and changed inventories/bytes reject. Only the repository containing the module is measured; run the module from an isolated repository copy to measure that copy.

Runtime scope is the selected interpreter executable bytes, Python version, installed package metadata and every non-pyc/non-`__pycache__` file in its `purelib`/`platlib` trees. The dependency manifest is saved, not just a caller hash. Worker hello must match the actual parent environment, imported product origins must match frozen package bytes, and before/after runtime/source/config checks must match. This is not an OS image, complete stdlib/system-library inventory or malicious-host attestation. No credential reference is stat/opened; no real keys/history/memory/dream are scanned. Measurement workers have fresh fixture work/state and no network namespace access.

The static measurement manifest locks exact config bytes and parsed fields, complete counterbalanced repeat schedule, development/holdout cases, judge source, actual native tool schemas, sampling, both source manifests and the current constructor/adapter sources. Each arm/group/split is probed once (16 initial requests); repeats remain scheduled, not falsely reported as completed observations. Worker hello and actual native request construction run; a measurement stop ends the worker before any transport/SDK request dispatch. A failure leaves diagnostic partial output but no observed plan/template/valid preflight receipt. Output directories must be new.

**Prompt semantics:** task startup adds UUIDs, timestamps, task facts and budget state even to the system prompt. The worker reports the exact native **pre-send constructor system UTF8 bytes**, which are locked along with tools/task prompts/constructor source. Actual post-send full system UTF8, canonical native parameter JSON and hashes are saved separately in `actual_requests`, with arm/group/split/request identity, attempt, role, plan hash and measurement lock. No normalization is used to pretend dynamic fields are frozen. `bind_request` can bind further concrete primary/auxiliary requests and rejects model/sampling drift, but is evidence only, with `budget_reserved=false`; it does not reserve budget or admit dispatch. Future conversation/tool/compaction/recovery prompts remain dynamic and require this binding for every physical request/attempt in a future controller. Full future prompt fixed is explicitly false.

```sh
# policy is an explicit valid v1 candidate; its credential path is reference only.
# Measured locks and installed SDK version replace the candidate's placeholder locks.
python -m evals.architecture_measurement prepare --policy candidate.json --config evals/architecture.json --out /absolute/new-prepare
# Output: observed.json, measurement-manifest.json, unapproved-template.json,
# frozen packages/manifests, per-worker controller/hello/request/exit records/logs.
python -m evals.architecture_measurement measure --policy candidate.json --config evals/architecture.json --out /absolute/new-measure
python -m evals.architecture_measurement preflight --policy candidate.json --config evals/architecture.json --plan /absolute/new-prepare/observed.json --authorization explicit-record.json --out /absolute/new-preflight
```

`prepare` never manufactures approval: template is false/null. A synthetic approval is used only in offline tests/evidence, clearly labeled. Preflight freshly measures and applies strict full plan/authorization/time/budget matching; old v1 plans, forged locks, source/judge/prompt-constructor/dependency/interpreter/config/sampling drift reject. `measurement_lock` covers the static manifest, while dynamic actual request hashes are separate. Credential/endpoint/model availability/rate provenance and approver identity remain assertions, not measured supplier facts. A valid local receipt does not constitute session fee authorization. `live` still exits2 before config/credentials; both remote transports still reject.

Evidence/design/report: `/var/tmp/feiyu-eval-measurement-20261119/`. Single-use approval consumption, durable restart reservations/spent/unknown budgets, real credential ingestion, supplier version/rates/invoice verification and real-model benefit remain unimplemented. Unknown must block without replay/replenishment. Hashes bind local content only. R1/R2/AR1 and U4/U7/U8 limited rulings remain unchanged. The historical Anthropic 1.5s cancellation `usage {}` vs 8/2 failure remains unexplained; this batch does not expand that lifecycle work or use reruns to close it. Windows, blocked LSP review and historical Warning limits remain. Product/Linux package/HEAD d82d943/unpublished 0.87.0/inherited edits preserved; no install, stash/reset/bump/commit/push/release, paid call or subagent. Rollback removes this batch's measurement module/test and narrow eval protocol changes/appended notes only; preserve inherited changes and evidence. 程序回归以内部结果为准，真实模型收益尚未验证；交Astra新独立审查，不自行验收U6/D/整任务书。


## Astra U6测量优化模式修复交审（2026-11-19）

按 `/var/tmp/feiyu-eval-measurement-review-20261119/report.md` 的P2，在CLI、measure、preflight公共入口用不依赖assert的auth.need(__debug__)拒绝-O/-OO，先于输入读取/输出创建。新真实子进程回归覆盖三个CLI命令及两个导入入口；普通测量/授权/执行定向双版各17项、0skip、内部exit0。证据 `/var/tmp/feiyu-eval-measurement-fix-20261119/`，内部命令/env/结果/log、修复源码hash与快照均保留。未改产品包/版本，不提交发布或付费。本P2待新独立复核，不验收U6/D/任务书。继承的Anthropic无transport scripted恢复组合KeyError及定时取消未解释限制保留，不称本批修复。


## Astra 测量优化模式P2有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-measurement-fix-review-20261119/report.md`，关闭当前测量CLI/measure/preflight优化解释器绕过P2。双版各18条独立命令覆盖原非法删减配置、-O/-OO、缺输入优先拒绝、导入访问trap与正常非法配置拒绝，无测量/预检产物；当前源码双版17项普通路径证据已匹配。仅此入口范围，不扩为全产品assert保证。

U6实际输入测量/本地预检具有限接受证据；调用方批准来源并未认证，测量收据不赋予远端权限。下一项补一次性批准消费和运行预算持久化，验证仍只用临时合成记录/本地transport，不发真实请求。单次消费/重启保留额度/unknown不重放的控制器必须先完成并审查，实际费用授权另行取得。既有取消时序及scripted Anthropic恢复组合限制保留。无提交发布或产品包变化，不验收U6/D/整任务书。

## U6 durable synthetic budget API (2026-11-19, pending independent review)

`evals.architecture_durable.Controller` is an independent Linux eval-only API, not a new live command. `create(plan, approval, policy, config_path, fresh_measurement_out, synthetic=True)` calls actual v2 remeasurement/preflight before committing consumption. `resume(run_id)` checks stored measurement binding and current source/runtime, retaining the original boot/monotonic deadline. Use a context manager to hold the nonblocking flock across all operations. Every cooperative writer must use the same persistent registry directory. The single atomic `registry.json` contains both record consumption and run state: record_id cannot create another run and run_id cannot consume another record. Repeated create is rejected; resume is explicit. Callers must not remove, roll back, fork or replace that directory. Damaged inputs fail closed; old pending entries become unknown, never automatic replay. Hostile same-UID mutation, approver identity authentication and remote revocation are outside this local boundary.

`invoke_fake(observation, request, attempt, role, parameters, system, outcome='ok', usage=None)` reserves an attempt durably, invokes a fixed Python subprocess fake, then saves facts. There is no caller transport callback, URL, credential read or automatic retry. All observations, roles and attempts share the original global max_requests/max_seconds/max_cny. Observation names do not reset the global budget; the measured config's per-observation rounds/attempts/seconds/CNY are additional restrictions. This API exercises durable dispatch accounting; it does not run or judge the scheduled product observations, and does not replace the existing parent Ledger. Dynamic request hashes are evidence, not full-future-prompt locks.

Reservation holds the policy's per-request token-ceiling fixed estimate; complete fake usage settles at those rates. Known failed outcomes remain charged; partial/unknown have cost_cny=null and block subsequent calls. Supplier invoice is a separate null field. The cap cannot guarantee a real supplier bill. `tighten(limits)` persists only nonincreasing global limits; elapsed seconds are always measured from original consumption. Same-boot monotonic deadline survives restart; another boot blocks rather than replenishing. Authorization wall expiry also continues to apply. A write failure poisons the handle before dispatch. Failure to save after dispatch leaves a disk reservation/unknown and raises; any original transport exception is retained with persistence_error and durable_attempt facts.

Migration: new separate eval registry only; no TaskStore/user-state conversion. Recovery keeps the entire registry and lock location; do not copy back an older registry or clear unknown. Rollback stops writers and archives the entire registry plus measured evidence before removing this optional API; never import its synthetic receipts as live evidence. Credentials/HTTPS/real invoices, source-authenticated user fee approval and real-model benefit remain unfinished. Existing 1.5-second cancellation usage discrepancy and Anthropic no-transport scripted recovery KeyError are unchanged. U4/U7/U8/product/package and U6/D/taskbook acceptance remain outside this implementation handoff.

中文：独立Linux离线API先真实v2重测预检，再在单一原子registry中同时消费合成批准并建立run；flock持有到物理fake调用及落盘结束。记录ID/run/plan/measurement绑定，重建拒绝、恢复显式进行。每个物理attempt先持久预留；重启未决转unknown，不自动重放。全部观察/辅助/重试共用原全局次数、原截止与固定估算CNY；逐观察预算是额外约束，不重置全局额度。限额只能收紧，未知成本null，已知失败计费，supplier invoice独立为null。写失败先阻断，执行后保存失败保留原异常及事实。仅内置子进程fake，未接入实际产品观察执行/判题；非真实用户费用授权。身份认证、恶意同UID、远端撤销不在本Linux本地范围；真实凭据、HTTPS、账单与收益仍待完成及独立审查。


## Astra durable R1/R2修复交审（2026-11-19）

按 `/var/tmp/feiyu-eval-durable-budget-review-20261119/report.md` 修复两P2。R1恢复任何校验/持久化异常即毒化句柄，后续invoke和resume拒绝，不能因捕获原异常继续派发。R2观察绝对截止从首条reserved_at推导，预留落盘后再次检查，physical timeout与调用后检查均取全局/观察截止较小值。超期前未派发仍保留reservation为unknown，不补额度；真实结果已返回则先保存事实再报告超期。

双版durable套件各9项通过（含实际create/preflight/恢复），随后新增的timeout传递及执行后事实保存回归双版各1项通过，内部exit均0；不能称套件运行时已含最后新增方法。无产品/SDK/包变更，不重跑不相关全量。证据 `/var/tmp/feiyu-eval-durable-fix-20261119/` 含精确argv/env/内部结果/log和源码快照。两P2待独立复核，不验收U6/D/任务书，不付费/提交发布。


## Astra durable R1/R2有限关闭（2026-11-19）

核对 `/var/tmp/feiyu-eval-durable-fix-review-20261119/report.md`，接受两P2在独立synthetic API限定关闭。真实公开测量/create后，双版恢复源/runtime/绑定/保存/中断等失败均毒化句柄；捕获后invoke/resume/tighten/create不能恢复派发。合法120秒观察限额下慢保存越界零派发并留unknown，真实子进程timeout取全局/观察较小值，实际结果后超期先保存事实再报停止。复核分轮夹具失败/修正记录保留，不称一次最终全套通过；3165指纹无变化。

本批独立控制器具有限接受证据，尚未两SDK/schedule持久接线。下一批将已审原生loopback评测接入同一持久run账本，跨观察/辅助/重试不重置预算。live/远端授权/专用凭据/HTTPS/真实账单收益继续未完成，不将本地合成批准解释为用户费用授权。无提交发布，不验收U6/D/任务书。

## Durable native SDK loopback / 持久原生SDK接线（2026-11-19，实施交审）

`Controller.execute_loopback(measured_out, arm, group)` now uses a consumed v2 bundle's frozen sources, runtime, config and scheduled identity to run the actual product worker with OpenAI/Anthropic native SDK children. Call `create(plan, synthetic_approval, policy, config_path, fresh_remeasurement_out, synthetic=True)` first; it remeasures before atomically consuming the record. On a new process use `resume(run_id)` with the same registry, then only new, unstarted observations. The measurement output passed to execution must contain the verified bundles from that run. `execute_loopback` is deliberately limited to development/repeat=0; it rejects holdout/repeats until the fixture service and complete scheduler are implemented.

`architecture_execution.execute(..., durable_ledger=...)` routes physical requests to `Controller.invoke_sdk`; it never calls the legacy Ledger's reserve/charge path. DurableLedger only routes parent retries and exports observation receipts. Global count/estimate/deadline applies to all primary/helper/retry calls; each physical request is saved as reserved before SDK dispatch and rechecked after saving. The SDK receives the minimum original global/observation absolute deadline. Observation identity is also saved before starting its worker, and cannot be restarted even if it died before its first SDK call. Actual system/parameters, measured arm/source and SDK endpoint/request/usage receipts remain bound. The synthetic loopback endpoint is recorded separately from the proposed remote plan endpoint.

Unknown or partial usage retains its lower bound and null cost, blocks the run and is never replayed. Crash after reservation or after a real SDK return but before result save recovers as unknown. Finished physical facts are saved before reporting a late result; failed resume still poisons the handle. Save failure blocks admission and cancellation preserves its original exception plus persistence diagnostics. Existing OpenAI raw usage/SSE validation and Anthropic message_stop validation are unchanged. Fixed policy estimates and supplier invoices are separate; estimates are not a provider billing guarantee. No tokenization/remote maximum charge proof is claimed.

本批是双源码小规模产品布线，不是完整96条schedule/保留题/重复收益实验。恢复题仍按既有判据为agent_failure；完整观察调度、持久judge输出到严格aggregate schema、恢复未完成观察的显式人工处理策略尚缺。当前registry保存观察结果/事实，controller.json另存请求与产品事件；跨文件事务未实现，registry为预算权威，不能由诊断文件补额。父进程硬死后遗留SDK进程的通用产品级监管、恶意同UID/回滚registry/远端撤销不在本地协作合同保证内。

Evidence and exact internal runner results: `/var/tmp/feiyu-eval-durable-sdk-20261119/report.md`. All approvals, rates, keys and HTTP responses are synthetic; live remains rejected before credentials/config, no HTTPS/provider bill/credential ingestion or actual session fee authorization exists. No real-model benefit is verified. Rollback only this batch's eval/test changes and appended docs; retain the complete registry and previous sources/evidence, never reset an unknown attempt or copy a registry to replenish allowance. Independent controller review remains required; this does not accept U6/D/taskbook.


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

## U6 complete synthetic schedule/export protocol (2026-11-19, implementation pending independent review)

`python -m evals.architecture_measurement prepare --policy POLICY --config CONFIG --out FRESH_PREPARE` produces a measured plan and unapproved template. For synthetic testing only, construct a clearly labeled synthetic approval binding that exact plan. `python -m evals.architecture_schedule create --registry REGISTRY --plan PLAN --authorization SYNTHETIC_APPROVAL --policy POLICY --config CONFIG --measured-out FRESH_MEASURED` publicly remeasures/preflights/consumes once. No real fees or user authorization is inferred.

`python -m evals.architecture_schedule batch --registry REGISTRY --run-id RUN --measured-out MEASURED --limit 8` resumes in a new process and selects at most eight unstarted identities from the consumed configuration's full counterbalanced schedule. Plan length is generated, not a fixed 96. Direct execute_loopback also admits arbitrary unstarted planned order (strict integer repeat); the scheduler always follows stored order. Split-specific service answers, compact constraints and verification targets now use each case. Existing recovery judge remains agent_failure. The same original global count/CNY/deadline is never reset across batches or observations; per-observation rounds/retries/CNY/seconds remain additional caps. SDK primary/helper/retry routes all use the existing single Controller ledger.

Observation state is absent/not_started → durable started → finished or interrupted. Resume turns orphan started into interrupted without replay. All started identities remain ineligible. Interrupted observations and unresolved physical usage block global continuation; no automatic or manual reconciliation/clear/unblock command exists in this batch. Resume retains the original same-boot deadline, runtime/source binding, approval expiry, limits and request entries. A deadline expiring while idle cannot be replenished. Diagnostics cannot authorize replay or reconstruct missing billing facts.

`python -m evals.architecture_schedule export --registry REGISTRY --run-id RUN --out NEW_EXPORT` reads authoritative registry results, not controller.json. The new v2 envelope (`evals/architecture-durable-result.schema.json`) wraps existing v1 observation rows and preserves plan/measurement/source/runtime, per-observation state and actual parent-captured judge artifacts/events/facts/requests, plus physical request receipts. Result and selected-entry hashes are committed in the same registry write as observation finish. Export reruns the independent case judge on captured artifacts and validates dynamic request bindings and fixed-price settlements. Missing/interrupted/no-request observations remain visible without invented scored rows; unknown usage remains null/incomplete. No diagnostic-file recovery is performed. Export files are snapshots, never appended.

`python -m evals.architecture_schedule aggregate --registry REGISTRY --run-id RUN --input EXPORT --out NEW_SUMMARY` regenerates authoritative export and requires exact equality (including order) before the existing numeric/synthetic/duplicate checks and Wilson summaries. Reordered/duplicated/modified/stale exports reject; re-export against current registry. Original fixture aggregate/config/schema gates remain unchanged. Cooperative same-UID authority and hashes do not authenticate a hostile host or approver. Full snapshots remain confounded; repeats of one task are correlated; synthetic SDK wiring results are neither live nor real-model gains. Live continues to reject before reading config/credentials.

Migration/rollback: stop writers, preserve entire registry and consumed measurement bundle plus evidence; remove only this optional schedule/export implementation and appended documentation if reverting. Never roll back/delete registry to replenish budgets. Old finished records without new judge evidence cannot be promoted by export; they reject until independently addressed, with no automatic re-execution. Cross-file transactions, generic parent-hard-death supervision, real authorization/credentials/HTTPS/invoices/benefit, Windows and blocked LSP remain outside this batch. Current measurements bind the changed eval adapter, so older measured plans cannot be resumed through source drift.

This execution adapter uses a filesystem Unix socket for recovery. Keep the **physical, nonsymlink measurement output path short** (for example a fresh `/var/tmp/feiyu-sched-...` directory); the longest observation/service.sock path must fit Linux AF_UNIX's pathname limit. Evidence may be archived under a longer destination after workers exit. If a measurement bundle is moved between batches, stop the outer driver at a finished batch, wait for all its workers to exit, move the whole bundle, resume with its new path and the **same registry/run/limits/deadline**; source/runtime/manifest checks still apply. This is path relocation, not budget renewal. If an observation already became interrupted, path correction does not unblock that run: manual handling is unimplemented. This batch encountered that boundary on OpenAI and retains the blocked run; see evidence report for actual incomplete coverage. No result is promoted to success by moving files.


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
