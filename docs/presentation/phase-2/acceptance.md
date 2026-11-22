# Phase 2 验收交接

复核对象为 #14 的 `8276c7e` 和 #15 的 `30dc9aa`。每层的三组 Python、Linux/Windows 桌面、两组持久化及发布状态检查共八项。两层各八项均已通过。两个 PR 均为 Draft，发布作业按条件跳过。[#14 CI](https://github.com/feiyuceng06-prog/Biscuit/actions/runs/45003951757) · [#15 CI](https://github.com/feiyuceng06-prog/Biscuit/actions/runs/45005525056)

## 渲染与源文件

在 #15 原提交复跑 43 项 Node 和 15 项 Python 演示文稿测试，通过。重新执行 `evals/presentation/director-audit.py`，三对文稿的文本、媒体哈希、图表数、缓存值、工作表及备注相同，PPTX、PDF 和 18 张 PNG 的哈希逐一吻合。在同一字体及渲染环境中重新打开全部六份 PPTX，18 张新渲染 PNG 与提交的 PNG 逐页哈希相同，确定性告警集合一致。原生文本框、图表和内嵌工作簿均可从包内读取。逐一比对新版产品 30、商业 29、技术 41 个设计对象与导出 XML，位置和尺寸误差均小于 0.01 pt，文本与字号匹配。九张 PNG 的右下角采样与对应主题底色一致。对照图可直接检查 Editorial 左图右文、Corporate 数据强调和 Technology 流程节点。[文件与逐页数据](evidence/audit.json)

## 六份报告的逐项裁定

以下编号按各页报告中的 issueId 末尾序号排列；确定性记录另列。每份报告均为 needs_review。审查依据为实图、PDF 边界和原生对象，模型的严重性保留在原报告中。

| 报告 | 真实设计问题 | 误报或分类偏差 | 主观设计建议 |
| --- | --- | --- | --- |
| [产品旧版](evidence/product/before/review/report.json) | 第 1 页正文的 PDF 边界超框 16.4 pt，文字仍可见。标题尾字「家」单独成行。 | 第 1 页 #1 将标题折行判为溢出；#2 重述已测量的正文边界，未见新增裁字。第 3 页 #1 称标题有三行，截图为两行。 | 第 2 页 #1 希望说明更深；第 3 页 #1 希望调整标题换行。 |
| [产品新版](evidence/product/after/review/report.json) | 无确定性问题。 | 第 3 页 #1 的文字对比度实际为 6.92:1。#3 要求为两个待验证的问题提供内测数据，原文未陈述实验结果。 | 第 3 页 #2 建议收紧两组问题之间的留白。 |
| [商业旧版](evidence/business/before/review/report.json) | 第 3 页 #2 指出平行方案中只有右侧带满幅底色，实际确有视觉权重偏差。 | 第 3 页 #1 使用“拥挤”描述空白过多；标签不能作为文字遮挡证据。 | 第 1 页 #1 希望调整封面信息密度，#2 希望页码与说明对齐。第 3 页 #1 关于重心的意见可供取舍。 |
| [商业新版](evidence/business/after/review/report.json) | 无确定性问题。 | 第 2 页 #1 称图内重复显示增量说明，实图只在旁注显示一次；#2 的文本框存在空白，完整字形均在框内。 | 第 1 页 #1 希望封面提供更多信息。第 3 页 #1、#2 建议突出两行说明，#3 建议改变相同结构的分隔线。 |
| [技术旧版](evidence/technical/before/review/report.json) | 第 3 页 #1 的非对称底色与截图一致。 | 第 2 页 #1 所称末字「骤」完整可见；#2 中间标签与说明原生起点均为 337 pt；#3 将节点左边缘当作定位点，截图的线端与节点相接。 | 第 3 页 #2 希望提高两栏正文的视觉权重。 |
| [技术新版](evidence/technical/after/review/report.json) | 第 3 页 #1 指出的内容偏上、下半页空置在实图可见；“拥挤”不能推出重叠。 | 两条意见均无可见裁字或越界证据。 | 第 3 页 #2 希望缩短标题与两种故障处理之间的字号差。这是 Phase 3 的对照点。 |

## 对比度与平台

按 sRGB 相对亮度计算，产品 22 pt 正文 `#61524B` 对 `#FAF6F0` 为 6.92:1。普通文字以 4.5:1 为参考，大字（18 pt 或 14 pt 粗体及以上）以 3:1 为参考。商业图表的浅柱承载数值关系，以图形对相邻背景 3:1 核对，从 2.79:1 修至 3.39:1；柱顶数字作为文本单独检查。此处借用 WCAG 对比度指标评估特定颜色，并非整份 PPT 的可访问性认证。[文字标准](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [非文字图形标准](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)

Linux 的 LibreOffice/Poppler 提供真实排版证据。Linux、Windows Electron CI 覆盖编辑及导出流程，两者的测试范围见工作流；没有在 PowerPoint、Keynote 或 macOS Electron 中复核字形替换、编辑或放映。[桌面工作流](../../../.github/workflows/desktop-linux.yml)
