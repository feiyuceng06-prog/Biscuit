# 从现有 PPTX 到馆务会排班简报

![同一页经营结论在接入前后的实际导出](comparison.png)

| 三页可编辑文件 | 逐页实际预览 | 检查 |
| --- | --- | --- |
| [接入前 PPTX](before/deck.pptx)，基线 `57227a9` | [封面](before/review/slide-1.png) · [到访分布](before/review/slide-2.png) · [开放范围](before/review/slide-3.png) | [预检报告](before/review/report.json) |
| [接入后 PPTX](after/deck.pptx) · [可重新打开的源稿](after/source.deck.json)，实现 `bc249f7` | [封面](after/review/slide-1.png) · [到访分布](after/review/slide-2.png) · [开放范围](after/review/slide-3.png) | [预检报告](after/review/report.json) · [两份原生文件核对](package-audit.json) |

## 工作室里实际发生了什么

在 Linux Electron 的「办公 → 新建演示文稿 → 导入 PPTX 内容」选择仓库已有的四页经营简报。导入的 555 个字符包含四个分区的到访人数、单位和材料备注。自动化操作文件选择器、设计控件和保存位置。给模型的制作要求指定了三页标题、角色、企业汇报方向及会前阅读场景；四项统计数字仅出现在导入的材料中。deepseek-flash 实际生成大纲及正文，Planner 规划页面，工作室显示 Canvas 并保存 Biscuit 源稿、导出 PPTX。正文生成后单页手工修改次数为零。在实现提交 bc249f7 用 Linux 冻结后端重新打开同一源稿，核对 Canvas，再通过工作室导出交付文件。[工作室第 3 页](after/canvas-page3.png)[输入 PPTX](../phase-3/evidence/operations/phase3/deck.pptx) · [实际制作要求与输出逐字稿](after/source.deck.json)

较早的试跑中，开发环境启动器先指向旧后端，修正包路径后完成导入；自动化也改用了稳定的材料控件定位。一次仅给页序描述的输入两次得到不合格式的大纲。最终输入明确给出大纲字段，并让模型从材料提取图表数字。三页范例说明指定大纲下的运行结果，自主确定大纲的可靠性仍需独立评价。

旧版采用 `57227a9` 的 `readDeck → powerPoint → reviewExport`，读取同一份已生成源稿和相同的设计偏好。接入后使用工作室的「导出 PPTX」。这样可以只比较布局决策，避免第二次自由生成改变经营事实。

- 第 3 页旧版把标题挤为两行，正文在右侧两块较窄的栏里换行。会前阅读方案把同一标题留在一行，两段采用左对齐的小标题和正文，去掉段间横线。参会者可以从标题向下连续阅读。新版下半页留白较多，投影演讲是否适合这种密度仍需设计审查。
- 第 1、2 页的原生幻灯片 XML 在两版间逐字节一致。两轮渲染的像素差异局限于页脚页码。第 2 页仍是带内嵌 Excel 工作簿的原生柱形图，按原材料顺序记录阅览室 48、少儿借阅区 26、地方文献查询台 11、数字资源体验区 7 人次。两版都保留三页的可编辑文字及演讲者备注。[逐项审计脚本](../../../evals/presentation/runtime-pptx-audit.py)
- 两份 PPTX 各经 LibreOffice 26.8.3.1 和 Poppler 26.11.0 渲染为三页，确定性预检均为 `checked`、零项告警。报告记录了实际字体（含 Noto Sans CJK SC）、PDF、逐页 PNG 及导出文件摘要。此项评估包括看图和文件检查。未调用视觉模型打分，未经独立设计师评审。
- 边界回归覆盖了 85 个显式换行紧邻两个短段的情况。旧分配会产生负高度，新版先为各段标题和正文预留空间，超量内容继续触发拆页建议。复核三页样例的幻灯片 XML 与修正后导出逐字节一致。

对话 Agent 也使用了新能力。在另一份三页经营简报上，真实 deepseek-flash 会话 `f87a8074` 发出一次内建 `read_file`，按页取得标题、备注和 26、35、48 三个数值。留存的工具返回与同一文件的 CLI 提取一致。[原始调用与返回](checks/agent-read-file.json) · [运行事件](checks/agent-trace.jsonl) · [CLI 对照](checks/commercial-cli.json)

## 附件来源与适配范围

SkillHub 的 `SOURCE.md` 指向 Anthropic 的 `skills/pptx`，未提供语义版本号。附件 SHA-256 为 `8a44e0212172a84f43e84d270739d98c976e20676b87790e91e4ad813796f27a`。排除打包者添加的 SOURCE.md，其余 58 个文件的 Git blob 均与上游提交 `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` 相同。该快照的 LICENSE.txt 为 Apache License 2.0。仓库保存打包者原始说明和许可全文。运行时代码在 Biscuit 的接口内实现，未分发上游的脚本、图标、字体或 XSD 集合。[上游固定快照](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/pptx) · [打包来源](SOURCE.skillhub.md) · [许可原文](LICENSE.upstream.txt)

| 附件中的能力 | Biscuit 原有行为 | 本次采用的做法 |
| --- | --- | --- |
| `slide_text.py`，提取并理解既有内容 | 对话工具按幻灯片 XML 文件名字典序拼文字。工作室能导入 TXT、Markdown，参考 PPTX 仅产生风格统计 | 读取文稿关系指定的实际页序，保留隐藏页标记、段落、表格行、图表分类与缓存值、图片替代文字及备注。聊天 `read_file` 支持按页读取，文件提及和工作室共用解析器。「分析参考 PPTX」仍只返回风格统计 |
| `office/validate.py` 和校验器 | 已有版面、对比度、字形和真实导出检查 | 在内容读取时检查包入口、页 ID、关系类型及目标、图片、图表和备注部件、XML 根和解析限额。缺损部件使导入失败并保留既有材料。覆盖内容读取的引用链；完整 OOXML XSD、无引用部件以及 PowerPoint 私有扩展不在此验证范围 |
| Skill 指导与 PptxGenJS 手册 | 原有 Design Director、Visual Planner、原生图表和可编辑对象 | 复用全局 tokens、页级容量测量和候选排序。明确的会前阅读场景允许纯文字页按段落设层级。数据、流程、图片仍根据自身语义规划。指定风格参考优先于这一阅读建议。品牌色、品牌字体及明暗背景可选；显式品牌设置优先。保留原句和层级绑定，同一构图供 Canvas、PPTX 和预检使用 |
| `add_slide.py`，`clean.py`，主题辅助函数 | 工作室已有草稿、撤销、删除、设计切换、源文件及另存导出 | 增加「复制本页」。复制可编辑节点、重新分配 ID，图表及工作簿独立。删除副本中的页面再导出，只序列化当前对象；切换字体、品牌色和背景走同一草稿保存机制。原输入 PPTX 作为材料打开，不提供任意外部 PPTX 的原位清理、母版改写或无损往返 |
| 缩略图、LibreOffice 包装脚本、图标依赖 | 已有独立渲染目录、LibreOffice、Poppler 和接触表 | 继续复用真实导出检查；未引入第二个 PPTX 生成器、图标库、模板资源或运行时安装命令 |

导入使用 Python 标准库，无新增运行时库。隔离子进程使用独立任务目录，10 秒超时；工作室 IPC 另设 15 秒上限。包上限 64 MiB、300 页、单个 XML 2 MiB、累计 XML 24 MiB、单次内容输出 28,000 字符。聊天工具标记内容截断，可按页缩小范围；工作室拒绝不完整导入，也会拒绝与原材料合并后超过 30,000 字符的结果。图表取文件保存的缓存，缺少缓存会标明；对于未计算的 Excel 更改，数值需核对。图片读取其说明文字，不进行 OCR。指定品牌字体需要在目标机器安装，当前导出不嵌入字体。

## 验证与审查

桌面构建通过。69 项 Node 测试和 26 项 Python 演示文稿测试通过，含 10 项新增提取测试；另有 290 项相关 Python 回归通过。Linux 冻结后端完成有效和损坏文稿的用户入口冒烟，Electron 冒烟覆盖导入并追加已有材料、复制与撤销、新建、设计切换和保存。Windows PowerPoint、Keynote 和 macOS Electron 的打开、编辑与字形效果仍未验证。[Node 记录](checks/node-tests.log) · [Python 专项](checks/presentation-tests.log) · [相关回归](checks/related-tests.log) · [Electron 记录](checks/electron.log)

运行 `python evals/presentation/runtime-pptx-audit.py` 可从交付文件重新核对逐页文字、演讲备注、图表缓存、工作簿、渲染摘要和像素差异。代码从摄影交付试点 `57227a9` 分支出来，人工审查顺序为 #14 → #15 → #16 → #17 → #18 → 本分支。
