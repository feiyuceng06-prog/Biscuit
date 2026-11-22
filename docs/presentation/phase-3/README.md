# Phase 3 · Visual Planner

本分支基于 Phase 2 的 `30dc9aa`，依赖尚未合并的 #15 和 #14。Phase 2 已通过验收，六份报告逐项分类，单列 Office 原生应用的验证缺口。[Phase 2 验收](../phase-2/acceptance.md)

## 实物对照

各组使用同一份固定输入、相同方向和全套 Theme Tokens。每份四页。左列基线来自 Phase 2 实际导出，另从 #15 的提交独立重建，16 张基线截图逐页 SHA-256 相同。输入中的业务与数据为虚构样例，产品照片取自仓库已有的阅览室素材。[固定内容](../../../evals/presentation/planner-cases.json)

| 场景 | Phase 2 | Phase 3 | 实渲染，左旧右新 | 逐页质量报告 |
| --- | --- | --- | --- | --- |
| 产品发布会 | [PPTX](evidence/launch/phase2/deck.pptx) | [PPTX](evidence/launch/phase3/deck.pptx) | [对照图](evidence/launch/comparison.png) | [旧](evidence/launch/phase2/review/report.json) · [新](evidence/launch/phase3/review/report.json) |
| 商业汇报 | [PPTX](evidence/operations/phase2/deck.pptx) | [PPTX](evidence/operations/phase3/deck.pptx) | [对照图](evidence/operations/comparison.png) | [旧](evidence/operations/phase2/review/report.json) · [新](evidence/operations/phase3/review/report.json) |
| 技术架构 | [PPTX](evidence/architecture/phase2/deck.pptx) | [PPTX](evidence/architecture/phase3/deck.pptx) | [对照图](evidence/architecture/comparison.png) | [旧](evidence/architecture/phase2/review/report.json) · [新](evidence/architecture/phase3/review/report.json) |
| 数据分析 | [PPTX](evidence/analysis/phase2/deck.pptx) | [PPTX](evidence/analysis/phase3/deck.pptx) | [对照图](evidence/analysis/comparison.png) | [旧](evidence/analysis/phase2/review/report.json) · [新](evidence/analysis/phase3/review/report.json) |

各 PPTX 同目录保存设计方案和 manifest。review 目录包含实际 PDF、每页 1600 × 900 PNG、总览图和带证据的 Issue。可直接打开 PPTX 修改同一页中的文本、原生图表数据和备注。

## 使用与复现

在工作室「模板与版式 → 设计方案」中勾选「根据每页内容规划构图」并应用。面板随当前页显示选择理由；取消勾选再应用即可用相同主题比较全局设计版本。已有 Phase 2 源文件按原版本载入。启用 `presentation_design_engine=1` 时，新建文稿默认随大纲和正文更新逐页规划。

在已安装项目依赖、LibreOffice Impress、Poppler、Pillow 及中文字体的环境下，从仓库根目录运行。输出目录使用新路径。设置视觉模型 alias 后，评审会将样例截图和总览发送给配置的供应商；清除该变量可只做本地检查。

```sh
export PYTHON="$(command -v python)"
export BISCUIT_PRESENTATION_CRITIC=deepseek-flash
node evals/presentation/director-compare.mjs /tmp/biscuit-planner phase2
node evals/presentation/director-compare.mjs /tmp/biscuit-planner phase3
python evals/presentation/director-audit.py /tmp/biscuit-planner --planner
```

## 逐页规划与验证结果

规划器沿用 Design Director 的配色、字号层级、字体与间距。它从封面、观点、图文、对比、序列、数据六类布局中按内容筛选候选，对最多四种可行构图测量文本容量，并在选择时考虑相邻页是否重复。序列页再区分操作流程与时间线。每页保存核心观点、视觉焦点、原始内容绑定、图片使用策略、候选理由和最终变体。容量不足时，工作室显示拆页建议，由作者决定。规划在本地完成，Canvas 和 PPTX 导出共用选中的构图。[规划器](../../../desktop/electron/office/planner.mjs) · [布局测试](../../../desktop/tests/office-planner.test.mjs)

| 场景与页码 | 实际变化 | 可复核证据 |
| --- | --- | --- |
| 产品第 3 页 | 原稿明确标出的「核心问题」从 22 pt 放大至 46 pt，页标题降至 27 pt。原句、标点和可编辑文本框均保留。 | [旧图](evidence/launch/phase2/review/slide-3.png) · [新图](evidence/launch/phase3/review/slide-3.png) |
| 商业第 2、4 页 | 四个场所的到访量改用横向条形图，长类别名沿同一列阅读。后三周任务保持按时间排列，图表页与时间线有明显的阅读顺序差异。 | [实际渲染](evidence/operations/comparison.png) |
| 技术第 2、3、4 页 | 三个有顺序的步骤从通用观点页变为流程图。比较页分隔线缩至正文附近，末页短结论可横向读完。首次渲染的过长分隔线与触发修改的评语一并保留。 | [改动前的比较页](revision/architecture-comparison.png) · [初次评语](revision/architecture-comparison.json) · [最终渲染](evidence/architecture/comparison.png) |
| 数据第 2、3 页 | 连续四周的 18、15、12、9 分钟用折线表示。四项有符号差值 −3、0、2、−1 用共用零线的横条表示，保留原顺序及零值。 | [实际渲染](evidence/analysis/comparison.png) · [可编辑图表](evidence/analysis/phase3/deck.pptx) |

16 个新版页面实际使用 11 种构图变体，覆盖全部六类。逐页审计核对新旧设计 Tokens、原始文字与备注、嵌入图片、图表缓存和可编辑工作表，并验证 PPTX、PDF 与 PNG 的哈希。每页的原生对象数、字号、图表编码、像素变化比例与评审状态均可追溯。像素变化只描述版面差异。[审计结果](evidence/audit.json) · [审计脚本](../../../evals/presentation/director-audit.py)

本地桌面 Node 测试通过 52/52，Python 演示文稿测试通过 15/15。渲染器构建及 Linux Xvfb Electron 冒烟测试通过，覆盖导入参考、切换方案、检查逐页理由、保存、导出和恢复编辑。对照样例 32 页均完成 LibreOffice 与 Poppler 实际渲染和确定性预检，未报溢出、裁切或低对比度。视觉模型逐页检查后，八份报告均标记为 `needs_review`。技术新版首次模型返回在第 2 页解析失败，单独使用相同截图、模型别名和上下文补查余下三页，原始结果及补查记录分别保留。[GUI 测试](../../../desktop/tests/office-ui.mjs) · [技术新版补查](evidence/architecture/phase3/review/critic-retry.json)

实图仍有值得人工取舍的地方。产品的前两页复用同一张阅览室图片，符合输入中的素材限制，但没有具体展示书签交互。商业封面的报告称句号在缩略图中疑似裁切，完整 PNG 可清楚读到句号。几个纯文字封面在短标题之后留白较多。以上证据支持判断信息层级与表达方式的变化，目前没有读者盲评数据足以推出整体审美偏好。[产品图文页](evidence/launch/phase3/review/slide-2.png) · [商业封面](evidence/operations/phase3/review/slide-1.png)

本次在 Linux 执行真实导出、界面和渲染测试。PowerPoint、Keynote、macOS Electron 的重新排版、编辑与放映仍待验证。极长的横条类别名会额外导出为独立的可编辑文本框，在 PowerPoint 改名时需同步修改对应文本框。

验收期间发现，最初的分析新版图表正确显示了 0，但内嵌工作表的数据单元格为空。已修复导出和回归断言，并用同一输入生成替代样例。以上表格保留原始对照。[修复后的分析 PPTX 与逐单元格核对](repairs/editable-zero/README.md)
