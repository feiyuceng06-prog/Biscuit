# Phase 2 验收与样例

Phase 2 从 PR #14 的 `8276c7e` 分支开发。PR #14 修复了 Windows 协议测试的就绪事件竞态。修复后，三个 Python 版本、Linux 和 Windows 桌面、两项原生持久化及发布状态检查全部通过。Linux 覆盖启用 PPT 渲染的 Electron 流程，Windows 覆盖四档缩放与解包应用 smoke。PowerPoint 和 Keynote 的本机打开、编辑、放映，以及 macOS Electron 的表现仍待实测。[Phase 1 验收记录](../phase-0-1.md) · [PR #14 CI](https://github.com/feiyuceng06-prog/Biscuit/actions/runs/45003951757)

## 如何使用

在办公工作室的「模板与版式 → 设计方案」填写受众、场景，可选品牌强调色和参考 PPTX，然后应用自动或指定的视觉方向。启用 `presentation_design_engine=1` 时，新建文稿自动制定方案，大纲、内容、页序变动会更新逐页计划。已有源文件可手动应用设计，仍可切回原主题、撤销、重写单页和导出。

Director 在本地根据主题、受众、场景、图表及图片比重、信息密度和参考文件决定方向。结构化方案记录设计主张、选择理由、图片策略、主题 Token 和每页角色。配色、字体、字号、边距、分隔线及图表强调方式来自同一套文稿 Token。用户品牌色用于装饰标记，数据和文字保留可读色。原来的大纲与正文生成接口继续工作，Canvas、PptxGenJS 和渲染预检共用既有六种布局的对象描述。[产品介绍设计方案](evidence/product/after/design.json)

内置库有 16 条原创设计参考，记录内容类型、适用密度、所有者、使用权和可学习的规律。用户选定 PPTX 后，本地提取明暗、标题对齐、文字密度和图表、图片的使用情况。参考文件的文本和素材不会进入生成文稿。参考解析支持 16 MB 内、1–100 页的 PPTX。依赖母版继承、主题色或复杂背景的文稿可能得到混合或近似结果。自动选向采用有界规则，中英文关键词以外的语境可手动指定。

## 同内容新旧对照

每份三页，对照图左列为旧版、右列为新版。每个 PPTX 同目录有 manifest，review 目录包含 PDF、1600 × 900 逐页 PNG、总览以及实际模型意见。旧版 9 张 PNG 与直接从 Phase 1 提交导出的基线逐张哈希一致。

| 场景 | 旧版 PPTX | 新版 PPTX | 逐页对照 | 观察 |
| --- | --- | --- | --- | --- |
| 产品介绍 | [旧版](evidence/product/before/deck.pptx) | [Editorial](evidence/product/after/deck.pptx) | [三页对照](evidence/product/comparison.png) | 旧封面把「家」挤到第二行，新版同一句标题单行呈现。图片按原比例放置，衬线标题和红褐色标记贯穿三页。前两页仍使用同一张输入照片。 |
| 商业汇报 | [旧版](evidence/business/before/deck.pptx) | [Corporate](evidence/business/after/deck.pptx) | [三页对照](evidence/business/comparison.png) | 图表保留 26、35、48 人次，第三周用重点色标明。末页把两种排班方案排成两行，每个方案横向对应说明。标题和标注都出现 48 人次，仍有重复。 |
| 技术演示 | [旧版](evidence/technical/before/deck.pptx) | [Technology](evidence/technical/after/deck.pptx) | [三页对照](evidence/technical/comparison.png) | 深色底、青色节点和细线贯穿全稿。流程按时间顺序横排，异常页使用开放双栏。技术页文字较短，后两页下半部留白明显。 |

将**同一份商业汇报**分别指定四种方向后，封面的对齐方式、图表与标注的相对位置、比较页的阅读顺序均可对照。下图自上而下为 Editorial、Minimal、Corporate、Technology。[同稿四方向，十二页实渲染](evidence/four-directions.png)

## 可验证的结果

- 比对三对 PPTX 的原生 XML，逐页正文文本、备注、图表缓存与工作表数据、图片数量和媒体 SHA-256 一致。所有 PPTX、PDF 和逐页 PNG 都与对应报告的哈希匹配。[逐页度量](evidence/audit.json)
- 旧版产品封面出现确定性溢出告警，原图仍能读出完整标题。新版三份文稿共九页，确定性预检未发现阻断或告警。视觉风格取舍以截图为依据，本轮没有开展多人盲评。
- 首次商业图表的浅色柱与背景实测为 2.79:1。核对 PNG 后，实际柱色从 `#8098BC` 调整为 `#7089AE`，对比度提高到 3.39:1。同步降低旁注数值的字号，并为四个方向的明暗色板加入柱色对比度回归测试。[修订前的模型意见](evidence/revision/original-business-critic.json) · [修订前 PNG](evidence/revision/business-2-original.png) · [最终 PNG](evidence/business/after/review/slide-2.png)
- 首轮在线 Critic 存在空回复或无效 JSON。对已配置为视觉模型的官方 DeepSeek Flash，短结构化评审请求使用 JSON 输出并关闭该次请求的思考模式。SDK 仍使用 Biscuit 的现有调用及用量记录。修订前的一次逐页复跑还曾将完整的产品标题与文本框空白误判为溢出，按实图排除；最终提示要求指出越界或被裁的具体字形。模型输出保留给审查者，硬阻断来自确定性证据。[首次传输记录](evidence/revision/previous-transport.json) · [修订前的误报](evidence/revision/product-critic-before-rubric.json) · [产品封面实图](evidence/product/after/review/slide-1.png)
- 本地验证覆盖 43 项桌面 Node 测试、33 项 Python PPT/参考导入/SDK 工作进程测试、前端构建及 Linux Electron 工作室 smoke。真实的参考 PPTX 经过系统对话框入口导入，套用方案后仍保留「48 人次」，再走原编辑与八页导出流程。内容模型在 GUI 测试中使用夹具，视觉评审使用已配置的真实供应商。不同 Office 实现及字体替换仍可能影响断行。

## 最终视觉复核

六份导出的生产报告均记录三页完成真实 Visual Critic 审查，合计 18/18 页；早期传输复跑仅 4/18 页返回有效 JSON。最终六份报告均为 `needs_review`，保留模型的版式意见。三份新版报告的确定性检查共零条问题。

| 新版页面 | 核对结果 |
| --- | --- |
| 产品第 3 页 | 模型认为正文对比度不足。按实色正文 `#61524B` 和底色 `#FAF6F0` 计算为 6.92:1，高于普通文字的 4.5:1。此项判为误报，留白建议保留。[整页](evidence/product/after/review/slide-3.png) · [报告](evidence/product/after/review/report.json) |
| 商业第 2 页 | 模型把旁注框中的空白标成溢出，原证据明确写出字形未越界。截图和 PDF 预检均可读到完整的「比首周增加 22 人次。」此项判为误报，旁注与图表的层级关系交人工评审。[整页](evidence/business/after/review/slide-2.png) · [报告](evidence/business/after/review/report.json) |
| 技术第 3 页 | 模型提出两条 major 意见，均指向版面重心偏上、两栏说明占幅小。截图支持这项取舍，建议审查者按技术评审会投影距离判断。两条故障说明和对应处理均完整保留。[整页](evidence/technical/after/review/slide-3.png) · [报告](evidence/technical/after/review/report.json) |

## 复现

在仓库根目录使用已安装项目依赖的 Python，以及 LibreOffice Impress、Poppler、Pillow 和中文字体。输出到新目录。配置视觉模型后可设置 `BISCUIT_PRESENTATION_CRITIC` 为对应 alias，评审会把实际页面与总览图发送给它。清除该变量可单独复跑渲染和确定性检查。

```sh
export PYTHON="$(command -v python)"
export BISCUIT_PRESENTATION_CRITIC=deepseek-flash
node evals/presentation/director-compare.mjs /tmp/biscuit-director before
node evals/presentation/director-compare.mjs /tmp/biscuit-director after
for direction in editorial minimal corporate technology; do
  BISCUIT_PRESENTATION_CRITIC='' node evals/presentation/director-compare.mjs /tmp/biscuit-directions after business "$direction"
done
python evals/presentation/director-audit.py /tmp/biscuit-director --gallery /tmp/biscuit-directions
```

若某次供应商调用中断，可在同一组渲染图上执行 `python -m evals.presentation.director-critic /tmp/biscuit-director MODEL_ALIAS`。它为每页单独记录实际响应、错误类型和 PNG 哈希。原导出报告保留，可比较两次运行的差异。
