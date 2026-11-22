# 摄影作品与 Phase 3 验收

| 作品 | 可编辑文件 | 实际导出的逐页 PNG | 工作室源文件 |
| --- | --- | --- | --- |
| A · *A Quiet Gaze* | [PPTX](portrait/deck.pptx) | [封面](portrait/review/slide-1.png) | [在 Biscuit 中打开](portrait/source.deck.json) |
| B · *The Shape of the Horizon* | [PPTX](sea/deck.pptx) | [封面](sea/review/slide-1.png) · [作品](sea/review/slide-2.png) · [说明](sea/review/slide-3.png) | [在 Biscuit 中打开](sea/source.deck.json) |

## 作品怎样生成

在 Linux Electron 工作室新建两份演示文稿，填入英文制作要求和馆藏材料，使用真实配置的 `deepseek-flash` 生成大纲和正文。在「编辑内容」中按原材料校对标题、署名、副标题和逐幅出处，再导入有序 JPEG。A 封面五幅肖像，B 的三页分别使用三、一、一幅海景。工作室保存源文件、导出原生 PPTX，LibreOffice 重新打开 PPTX 后用 Poppler 栅格化。自动操作只代选本地保存路径。初稿和最终源文件均可核对。例如，A 的原始署名行只有「Portrait studies」，在工作室补齐了材料已有的馆藏署名。B 的封面收短为摄影师姓名，完整作品日期保留在备注。[A 的 Agent 初稿](portrait/agent-draft.json) · [B 的 Agent 初稿](sea/agent-draft.json)

## 参考设计特征

- **比例、间距与字体。** A 的 960 × 540 pt 页面上，标题、副标题和图注分别为 60、15、11 pt。五张照片自左至右宽 86、168、236、168、86 pt，高 157、214、274、214、157 pt，相邻间隔均为 7 pt，中心共线。PDF 实际嵌入 Liberation Serif Italic。暖白背景为 `#F7F3F2`。五个图片对象和三个文本框独立存在，源码、原生裁切及实际导出几何已逐个核对。[对象和字体核验](package-audit.json)
- **图片与主体。** 中心肖像 *Julia Jackson* 的眼睛与脸部留在构图中心，两侧的面部均可辨认。保留原照片的明暗、色调和可见装裱边，不在嵌入照片上画边框。参考图是当代人像、服装与静物的混合；这些十九世纪照片以褐调、暗部和纸本边缘为主，中央人像的脸部明暗对比也更强。原照片与原字体均未取得，字体匹配的是可验证的风格特征。[A 全尺寸实图](portrait/review/slide-1.png)
- **跨页适应。** B 从三幅图居中转为单幅横向作品上置、长标题在下分为两行。说明页把带原装裱的港口照片放在左栏，右栏排列标题与说明。水平照片在作品与说明页完整显示，两页没有裁去海浪或船只。整套沿用同一暖白纸色、斜体衬线标题与克制的图注。[B 全稿总览](sea/review/contact.png)
- **根据实际渲染修改。** 第一轮 A 的图注远离中心图片，副标题和图注使用直立无衬线字。最终版把图注移到中心图下约 11 pt 的可见文字位置，三种文字均使用可编辑斜体衬线。B 首次说明页的照片、标题和说明散在三个角，最终改为左右图文分组。原来的渲染和检查记录分别留存。[首次 A](revision/portrait/slide-1.png) · [首次 B 说明页](revision/sea/slide-3.png)

馆藏作品来自 Julia Margaret Cameron 和 Gustave Le Gray。每项均核对馆方 API 的 `isPublicDomain` 标记，保存原图下载地址、尺寸、SHA-256、馆藏号、作者、日期和来源。每张幻灯片在演讲备注中保留对应馆藏链接。相邻照片的色调来自原件，实际图片导入会按工作室规则重新编码。[逐图来源表](sources.json) · [The Met Open Access 政策](https://www.metmuseum.org/policies/image-resources)

## 原有四组对照

对 #16 的原始 `8492108` 重新打开八份 PPTX、渲染全部 32 页。新渲染截图与对应存档逐页 SHA-256 相同。本次另行检查每页 PNG、四张 comparison 总览和内嵌图表数据。旧版和新版的八份报告保持原状，连同技术补查共有 65 条裁定。其中两条指向可观察的问题，27 条有反证，35 条为设计取舍，一条涉及缺少字面定位依据的细微对齐。独立检查另外发现了一个模型未报出的工作表错误。[逐条裁定](visual-triage.md)

| 既有对照 | 验收结论 |
| --- | --- |
| [产品](../evidence/launch/comparison.png) | 第 3 页的核心问题确实成为视觉焦点，完整问句在框内。第 2 页照片仅能交代环境，演示书签操作仍需真实产品图。 |
| [商业](../evidence/operations/comparison.png) | 排名改用可编辑横条，48、26、11、7 与输入一致，周任务仍按原顺序。封面句号完整。短时间线下方的留白需要作者判断。 |
| [技术](../evidence/architecture/comparison.png) | 第 2 页的三步流程取代原先折出孤字「程」的版面，第 3 页可见分隔线已缩短。首轮完成第 1 页，随后 JSON 解析中断。补查的第 2、3、4 页分别与同一 Git 版本、PPTX、PDF 和原报告逐页 PNG 哈希对应，四页恰好覆盖一次。[版本、对象与图像哈希](package-audit.json) |
| [数据](../evidence/analysis/comparison.png) | 四周趋势与正负条形图在真实导出中清晰可见。原版图上显示了 0，但分析第 3 页数据工作表 B3 为空。#16 的 `547ec11` 修复序列化及逐单元格测试。替代 PPTX 的四张 PNG 与原文件完全相同，第 3 页 B2:B5 现为 −3、0、2、−1。[正确的可编辑分析 PPTX](../repairs/editable-zero/analysis.pptx) |

**超长类别核验。** 用三条不同英文长标签和 −13、0、6.125 通过生产导出路径复现，逐行核对原生 chart cache、嵌入 Excel 的 A/B 两列，以及三段独立文本的内容与坐标。实际渲染中，三个数值的垂直中心各自落在对应类别文本框内。独立文本框没有链接到工作表。Biscuit 中修改并重新导出会重建对应关系，外部软件中直接改类别、排序或增删数据行时，需要手动同步标签文字与位置。[原始样例](chart-labels/original/deck.pptx) · [修复后样例](chart-labels/fixed/deck.pptx) · [逐行审计](package-audit.json)

## 新样例视觉审查

A 的最终模型审查已完成，未报告问题。B 的首轮在第 1 页返回不可解析结果；按与原报告相同的 PNG 哈希、模型别名、总览及预检记录分别补查三页。B 的首轮原件和补查分开保存。[A 报告](portrait/review/report.json) · [B 原报告](sea/review/report.json) · [B 补查四条意见](sea/review/critic-retry.json)

| B 补查意见 | 核实结果 |
| --- | --- |
| 第 1 页，三幅照片看起来像平排 | 三幅确实共用中线。中心图片原生宽 236 pt，两侧各 168 pt，相邻间隔 7 pt，未重叠。是否需要更强主次属于审美建议。 |
| 第 3 页，标题末行裁切 | 「leaves room for」的 PDF 边界下沿为 148.3 pt，原生标题框至 216 pt。实际文字完整。 |
| 第 3 页，分隔线碰到标题 | 原生横线位于约 240 pt，距末行字形下沿约 92 pt，实图有清楚间隔。 |
| 第 3 页，总览中港口照与大图位置不同 | 该页只有一个原生照片对象，总览由同一批 PNG 缩放拼接。图中确有远处船队。是否进一步强调照片是设计取舍。 |

现有检查覆盖 Linux Electron、LibreOffice、Poppler、PPTX XML 与嵌入工作表。PowerPoint、Keynote、macOS Electron 的实际打开、编辑、字体替换及放映仍待验证。当前还没有受众盲评，无法从上述结果推出整体美感偏好。

## Phase 4 最小范围建议

只考虑能用原生几何与实际渲染共同证实的文本越界或图形裁切错误。先锁定文案、像素源、数据和备注，每次候选修改只动一个文本框的可用空间或一张照片的裁切参数。重新导出受影响页，核对超界是否消失，且原有信息和其他对象的位置均保留；失败则恢复原方案。缺真实产品截图、封面留白偏好和外部工作表同步属于不同问题，应继续交由作者或导出层处理。

## 工程复验

审查以 #14（`8276c7e`）→ #15（`30dc9aa`）→ #16 为依赖链。#14 和 #15 各八项检查通过。#16 原提交 `8492108` 的 Python 3.12 首次全套运行中，后台作业丢失日志测试失败；相同 SHA 原作业单独重跑通过，本地专项连续 12 次通过。摄影增补分支以修复零值后的 #16 为基底。[原失败日志](https://github.com/feiyuceng06-prog/Biscuit/actions/runs/45008514914/job/137165375077) · [同提交重跑](https://github.com/feiyuceng06-prog/Biscuit/actions/runs/45008514914/attempts/2) · [修复提交 CI](https://github.com/feiyuceng06-prog/Biscuit/actions/runs/45010394838)

本地桌面 Node 回归、16 项 Python 演示文稿测试、渲染器构建、Python 后端打包及 Linux Xvfb Electron 冒烟均通过。实际改坏导出照片的源裁切和另一个对象的位置后，预检产生独立的阻断告警。复验源文件、原生图表和摄影作品关系可在仓库根运行 `python evals/presentation/phase3-acceptance.py`，输出应与已存的[审计 JSON](package-audit.json)一致。
