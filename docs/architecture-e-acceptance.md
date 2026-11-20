# E 首批实施交接（0.87.0，待 Astra 审阅）

> 2026-11-19 最终限定交付状态见 [交付矩阵与证据核对](architecture-delivery.md)。本页保留历史时点；后续明确裁决更新局部状态，全量通过不能自动关闭待审事项，D仍未整体验收。最终双版完整发现回归及§7逐项阻碍见交付主体表；LSP受阻独立审查未关闭，不能勾全部通过。

范围是原 E 第1/4/5项。不代表 E、D 或任务书总验收通过；D10接受点与cleanup unknown禁重发保留。Windows实现/实机缺口、父硬死亡限制及平台拒绝的LSP独立审查均未关闭，未重试该审查。

## 最小设计和实际接线

- `ContextLayers`保留rules/project/task/evidence/recall五段。agent原项目、人格、模式、memory、工具目录刷新入口保留；task引用D的原请求/约束/验收/unknown/预算/verification_refs，近期evidence来自Ledger ID及execution/exit_code/validity，而非assistant文本。recall是既有progress；按需技能正文及历史仍留在原生messages/transcript，不复制到稳定前缀。分层不改变权限门禁。
- `Billing.set_context`保留公开system字符串和set_system兼容；Anthropic system分成稳定带断点块+易变不带断点块，tools一个断点、历史至多两个；OpenAI兼容请求首system内容按同样边界拆块，原生messages仍是字符串，cache关闭/拒绝fallback回到原来字符串形态。缓存命中/费用没有真实provider证据。
- `native_history.read/replace/export_session/restore_session`只有原生列表，无统一消息模型。agent历史瘦身、同类型模型切换、恢复、session保存及provider compact_to接通。read是借用的可变列表，replace不自动审核候选历史；export/restore递归model_dump并复制，保留图片、thinking/signature、reasoning、工具配对与未知字段。跨provider切换继续原来不转历史的行为；custom backend只需原messages与set_system契约。
- session schema仍为1，旧会话可读；以前已去掉的图片不能恢复，新存盘不再主动去掉图片。600权限及安全writer不变，磁盘占用可能增大。摘要transcript继续忽略图片载荷。SDK接受前只撤本次append的D10机制未移动/改写。

## 后续压缩核验接口和剩余项

ContextLayers可读取本次构建的分段；TaskState仍是必须保留项的程序真源，Ledger仍负责有效性重核；native_history可供候选导出/验证后替换，现有history.slots只替换工具文本而保留配对。首批分层快照不是压缩核验器；本批E2/3在agent.compact增加候选事务，provider.compact_to仍是底层构造接口，不可单独作为任务压缩核验入口。

| 原E项 | 本批状态/下一步 |
|---|---|
| 1 分层 | 已实施，待审阅；五段与按需原生历史有实际调用 |
| 2 压缩程序核验 | 已实施待Astra审阅；双原生配对闸、TaskState/job快照、程序事实补回、候选持久化后接受；详见本页E2/3节 |
| 3 摘要引用验证 | 已实施待Astra审阅；assistant_claim与program_state分块，Ledger真实ID引用逐条重核owner/指纹/日志，stale/unknown不提升 |
| 4 缓存意识 | 已实施请求边界，离线验证；真实命中/费用收益未验证 |
| 5 原生历史小接口 | 已接通，待审阅；无跨provider有损转换 |
| 6 结构化事件 | 已实施待独立审阅；执行边界/验证失效/停止恢复由运行层生产，兼容CLI/serve/Desktop，详见设计30 |
| 7 sink隔离 | 已实施待独立审阅；显式Route/session/task/run/seq、线程传递、关闭丢迟到，详见设计30 |
| 8 来源链 | 未实施；摘要/子报告/memory全链路不可升级来源权限 |
| 9 Dreaming | 原有机制保留，本批未重构；后续结合来源链核验，纯对话不可作执行证据 |

回退：停活动请求/writer、备份完整session/journal，只撤本批差量；旧代码读schema1但再保存会丢图片，需保留备份；不回退D10修复、不重放unknown操作、不补预算。无版本bump、依赖、UI/协议变更、付费评测或提交。验证结果见证据目录及进度追加，完成后交Astra裁决。


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


## E2/3 压缩事务实施（2026-11-17，交 Astra 审阅）

本节更新上表第2/3项的“未实施”状态，不改写历史记录，不自验收E/D。`compact()`为显式、自动、overflow摘要救援共同入口；trim/shrink/fold只处理工具文本，沿用原配对协议且不调用重摘要。先拒绝双provider未配对、重复/孤立结果及打断工具结果的历史。抓取TaskState完整请求/目标/约束/验收/todo/操作/预算/验证引用和job观察；摘要后比较受保护任务事实及操作ID保留，重新生成最新程序事实。job终态/验证有效性允许向现实推进，预算保留实际摘要attempt消耗，不能撤销或补充。

模型输出封装为JSON `model_summary.source_kind=assistant_claim`；程序另建`program_facts.source_kind=program_state`，逐条`verification_refs.source_kind=execution_evidence`引用Ledger真实ID、owner、execution/validity/reason/source/workspace/run_id。缺记录或跨owner为unknown，Ledger消费重核代码/config/epoch和日志；历史passed不等于当前有效通过，不通过摘要新增Ledger记录。当前仅摘要块有来源类型，不宣称E8全链路/子报告/memory/Dreaming完成。

在浅复制backend与独立原生历史上调用现有compact_to，再核对程序块完整保留及配对；先持久化当前原历史并建立同目录硬链接回滚副本，再保存候选；关键session原子保存成功才在内存接受候选并清理瘦身索引。候选replace后目录fsync失败也以os.replace恢复原文件；回滚失败保留原副本并在异常compaction_rollback记录位置，关键writer仍blocked，须人工核对。派生备份清理失败不推翻已接受事务。模型失败、取消、关键持久失败不替换原历史；已花预算不回滚。成功存盘为接受顺序点，此后停止走既有门禁。要求单agent串行历史writer，非新并发会话事务系统；job仍由既有TaskStore锁/日志观察。未新增schema或依赖，custom backend沿用messages/compact_to；丢弃程序块会拒绝。保留稳定rules/project前缀，副本不重建规则。

多模态策略明确：普通保存恢复/工具瘦身保持原生图片/thinking/signature/reasoning/扩展字段；整段摘要沿用旧策略删除早期原生消息，transcript不含图片载荷，不声称无损压缩或可重建已删图片。模型失败保留全部原生历史。迁移无需转换schema1；旧已压缩会话无法补造原请求/证据。回退先停请求/writer并备份完整session/journal，只撤本批compaction.py、agent.compact和Ledger引用重核差量，保留首批分层/R1及D10修复、全部既有修改、unknown/pending与预算，不重放。不更改版本、不提交发布。

验证命令、失败轮次、结果及冻结指纹见 `/var/tmp/feiyu-stage-e-compaction-20261117/` 与进度追加。E6/7事件/sink、E8全链路来源及E9 Dreaming仍留后续；D平台、SDK父硬死、受阻LSP独立审查均保留，未接管或重试。


### E2/3 最终冻结验证交接

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

183项源码/测试/桌面/README最终指纹复核一致；15项新增、最终独立副本负对照、双版R1探针及全部失败轮次见证据report.md。双版1810/20skip是最后回滚修复后的结果；旧1809不替代。以上仅交Astra审阅，不代签E/D总验收；剩余E6/7/8/9与D限制保持。


## Astra裁决：E2/3有限接受及E6/7接续（2026-11-18）

已核对 /var/tmp/feiyu-e23-fix-review-20261117/report.md：双版独立7项通过，183项指纹和工作区状态保持，原Astra双版8项反例及290项相关回归有效。关闭F1/F2；接受压缩事务、程序事实保全与Ledger引用本批已验证范围。清理unknown原样传播，单user原生历史先落盘再备份，候选失败原异常/预算/原历史保留。不是D/E整体验收；修复后全量尚待最终冻结验证，平台/硬死亡/受阻LSP限制不变。

下一批实施E原6/7：关键运行事件和session/run隔离sink，兼容CLI/Desktop并避免双发。E8/9来源链与Dreaming后续继续。任务书完成前不提交推送发布，0.87.0与全部未提交改动保留。


## E6/7 实施交接（2026-11-18，待独立审阅）

实现与兼容契约见设计30；证据 `/var/tmp/feiyu-stage-e-events-20261118/report.md`。运行层事件带session/task/run/operation/seq，显式Route及worker传播，旧卡片单生产者/协议字段保留，CLI/Desktop分别呈现，关闭run丢弃迟到事件。checkpoint/session持久化错误不由sink吞掉；无schema/依赖/版本迁移。

最终双版定向各479项、全量各1820/20skip/1800实际通过，内部exit0；原R1/E2/3及新增子调查/持久化失败probe双版通过；Node10/10/build、源码后端Electron smoke/trust通过，160项最终指纹无差异。负对照仅独立副本撤worker上下文传递，确定exit1；失败轮次及3.14全量一条ResourceWarning（进程事后已退出）如实保留，见report/progress。

E6/7交Astra独立审阅，未自行接受；E8全链路来源/E9 Dreaming、D平台/SDK父硬死/受阻LSP限制及真实模型收益缺证据保留，不勾E/D/总验收。不提交推送发布，0.87.0和全部既有修改保持。


## Astra裁决：E6/7有限接受与来源链接续（2026-11-18）

核对 /var/tmp/feiyu-e-events-review-20261118/report.md：双版各5项独立入口探针通过，14组最终frozen证据与160源码/归档指纹一致；有限范围未发现确定缺陷。接受关键执行事实和session/run隔离本批范围，不宣称可靠重放或同agent并发历史支持。ResourceWarning具体创建来源未定，既有事后PID退出不等于排除全部生命周期问题。D平台/SDK父硬死/受阻LSP/真实模型收益等限制保持。

接续原E8/9来源经摘要、子报告、记忆的保留，以及Dreaming原来源/指纹/应用前校验；不把已有source_kind字段当作全链路完成。全部任务书完成前不提交推送发布，0.87.0与所有既有改动保留。

## E8/9 来源转述实施（2026-11-18，交 Astra 独立审阅）

实现设计31；证据 `/var/tmp/feiyu-stage-e-provenance-20261118/`。本批非E/D/整任务书验收。

|路径|结构化保留与消费边界|
|---|---|
|send/工具|原始请求关联原TaskState ID；附加数据独立external_data；工具返回即时登记，避免同批remember遗漏；最终输出引用继续留存|
|web_fetch提炼|真实辅助模型调用前记录外部输入摘要，返回为assistant_claim；不按输出自称分类|
|子调查|原只读集合；原报告字符串/长度/计费接口；程序属性带子工具来源，主回注JSON为claim；并发引用合并有实例锁|
|压缩/再压缩|原E2/3程序信封加source_refs；模型摘要claim；不从user-role摘要构造新用户授权|
|remember/recall|tuple兼容，新增JSON行保留来源，旧Markdown为unknown；来源由调用程序提供，忽略模型类别参数；读取再记保留引用集合|
|session restore|可选引用表随原生历史存取；缺失不从正文补信任；旧请求适配unknown/legacy；reset清当前会话表|
|Dreaming|仍限人/助手文本；候选为claim，逐字quote与原base保留，新增完整选中来源/metadata/候选指纹；apply重核并读回完整记录|
|执行证据|来源表拒绝execution_evidence类别；唯一事实消费仍原Ledger.reference检查真实记录、owner、指纹、日志；missing/跨owner为unknown；记忆和对话不能写Ledger或自动验收|

新增普通行为回归见tests/test_provenance.py；纯对话“通过”仅为claim，保持现有memory/Dreaming可用性。来源引用是保守依赖集合，不是逐句事实证明或授权。旧version1 Dream候选仍按当前来源重parse，不补造旧指纹；旧writer不理解JSON记忆行，降级前停writer和完整备份，不能用旧writer覆盖新文件。无运行依赖/版本/UI协议变化，不实施F。

最终证据以报告中final2-*和source-sha256.json为准；先前frozen-*、final-*在补web提炼/同批登记之前，名称不代表最终冻结。保留所有失败及负对照，详见report.md及results-summary.json。D10取消接受点/cleanup unknown禁重试、每轮volatile、压缩首user备份回滚、事件身份及唯一生产者不改；D平台/SDK父硬死/受阻LSP/真实模型收益、ResourceWarning来源未定限制保持。

### E8/9 最终冻结验证交接（待 Astra 独立审阅）

双版全量各1829项 / 20skip / 1809实际通过，内部exit0；3.14 runner216.859272秒，3.10 runner234.178922秒。双版定向各220项、原E2/3独立八项及R1各一项通过；Node10/10、build、当前源码Electron smoke/trust通过。最终两独立副本负对照各exit1（预期来源保留/来源指纹断言失败）。唯一最终轮次final2-*；137项产品/测试/README指纹与当前源码一致，支持文件指纹另存，git diff --check通过。精确命令/内部result/log、保留失败、指纹与审阅限界见 `/var/tmp/feiyu-stage-e-provenance-20261118/report.md`。最后双版全量无ResourceWarning，不据此排除此前未定来源问题。原限制与未提交0.87.0保持，不自行接受E/D/任务书。


## Astra裁决：E8/9有限接受与总交付准备（2026-11-18）

已核对 `/var/tmp/feiyu-e-provenance-review-20261118/report.md`：137项源码、15项支持文件与归档匹配，双版各5项独立实际入口探针、85项定向及2项D10回归内部exit0；有限范围未发现确定缺陷。接受来源依赖集合跨子报告/压缩/记忆/恢复保留及Dreaming应用前重核本批范围，不承诺逐句归因、语义真伪、绝对模型免疫或多writer记忆事务。旧v1候选不具有缺失的历史指纹，仍须当前来源/base/quote校验。

当前产品最终全量证据仍为E8/9 final2双版各1829项、20skip、1809实际通过，Node10/10、build和源码Electron smoke/trust通过。本轮仅记录裁决，不重复未变化产品的全量测试。E各批已分别有限接受；此结论不是D/E跨平台或整任务书总验收。D平台/SDK父硬死/受阻LSP独立审查、真实模型收益和既有ResourceWarning来源未定缺口继续保留。

下一步按任务书第6节补齐四组对照评测的可复现配置、命令和输出格式，仅离线验证，不调用付费或真实模型；随后逐项核对第7节交付条件、迁移回退与实际阻碍。整份任务书完成前不提交，HEAD d82d943、未发布0.87.0及全部既有改动保留。
