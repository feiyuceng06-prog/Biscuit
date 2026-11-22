# Biscuit 演示文稿实测报告 · Phase 0 / 1

## 复现与入口

[架构图、原有接口与固定输入](../../evals/presentation/README.md)记录了模型、大纲、编辑器、草稿和导出器的边界。原有 PptxGenJS 导出器和六种布局继续生成可编辑 PPTX。适配器在用户选择文件并成功保存后，把同一份字节快照交给独立 Python 后端。检查不会写回演示文稿。

在开发环境安装项目原有依赖，并让 `soffice` 或 `libreoffice`、`pdftoppm`、`pdftotext`、`pdffonts` 在 PATH 中可执行。建议安装覆盖材料语言的字体。Linux 桌面 CI 使用 LibreOffice Impress、Poppler 和 Noto CJK。

```sh
(cd desktop && presentation_design_engine=1 npm start)
```

在「办公 → 演示文稿」编辑或打开一份草稿，点击「导出 PPTX」。状态栏给出检查结果和报告路径。每次导出会在 PPTX 旁生成独立的 `.review-*` 目录，含 PDF、1600 × 900 的逐页 PNG、总览图和 JSON 报告。移除环境变量即可回到原有导出方式。报告和 PNG 随用户文件本地保存，可以一并清理。

如需调用视觉模型，再显式设置 `BISCUIT_PRESENTATION_CRITIC` 为已在 Biscuit 配置且启用 vision 的模型别名。启用后，该供应商会收到当前页 PNG、整套缩略图、制作要求、布局对象和本页检查证据。每页一次审查请求，复用 SDK 的传输重试；每份文稿最多 20 页，整个检查进程上限 10 分钟。默认仅执行本地检查。

## 质量报告与实现

| 模块 | 输入与结果 |
| --- | --- |
| `desktop/electron/office/review.mjs` | 复用 composition 生成与源 slideId、字段或对象序号关联的清单；固定实际导出字节；隔离并发导出目录。 |
| `feiyu/presentation_review.py` | 核对源页数、PPTX、PDF 和 PNG。读取原生对象坐标、文本、可解码的图像和图表类别/数值；使用 PDF 字词坐标判断容纳情况，实色文本与背景计算对比度，PNG 检测纯色空白页。 |
| `feiyu/presentation_critic.py` | 通过现有 Anthropic / OpenAI 兼容后端发送页面和总览图。逐条校验页与元素引用、类别、严重性、置信度、证据和改进建议。模型输出只进入报告。 |
| `feiyu/__main__.py`、Electron main、Office.jsx | 开发环境和打包后端共用检查入口，桌面状态栏显示原文件和检查结果。 |
| `tests/test_presentation_review.py`、桌面 office-ui、Linux CI | 实际文件损坏测试、渲染器缺失、两种 SDK 的本地 HTTP 往返以及从八页草稿到桌面导出的检查。 |

JSON v1 的 `pptxSha256` 绑定当次导出。`pages[]` 包含源 slideId、PNG 文件名和 SHA-256。`issues[]` 包含 issueId、slideId、elementIds、kind、severity、source、confidence、evidence、suggestedChange；报告另存实测耗时、渲染器版本、PDF 哈希和实际嵌入字体列表。内置渲染规则与模型观察保留各自的来源。

- `checked` 表示已完成的基础规则没有发现问题。视觉模型状态独立记录为 `not_requested`、`checked` 或 `unavailable`。
- `needs_review` 表示需要查看截图、渲染警告或未完成的模型审查。`blocked` 表示出现确定性阻断问题；用户仍可取得原文件。
- 无法渲染、页数不一致或检查后端不可用时，报告为 `preview_unavailable`。模型返回截断或无效 JSON 时会保留本地结果。

## 两阶段实测

**Phase 0。** 12 份输入覆盖 16 页，连续两次从源草稿生成旧版 PPTX，16 页 PNG 哈希全部一致。PPTX 导出耗时中位数为 2 ms，单独预览基线中位数约 745 ms。原有 Python 演示测试 3/3、Node 布局测试 4/4 通过。[基线记录](evidence/before/baseline.json)

**Phase 1。** 重新导出同一批输入，通过生产检查入口再次打开 PPTX，16/16 页与基线逐页哈希相同。10 份通过基础检查，1 份需复核，1 份阻断。本地渲染与检查耗时中位数约 1.35 秒，范围 1.28–2.19 秒，不包含按需调用模型的时间。测量环境为 Linux、LibreOffice 26.8.3.1、Poppler 26.11.0。[逐份结果](evidence/comparison.json) · [16 页总览](evidence/golden.png)

| 样例 | 实际看到的结果 | 文件 |
| --- | --- | --- |
| 五页夜读月报 | 封面图片、备注和原生柱状图保留。第 2 页展示 26、35、48 人次和单位。左侧说明第二行向右超出文本框 17 pt，仍与图表分开，判为需复核。 | [旧版](evidence/before/monthly.pptx) · [新版](evidence/after/monthly.pptx) · [逐页 PDF](evidence/after/deck.pdf) · [截图](evidence/after/slide-2.png) · [报告](evidence/after/report.json) |
| 人为损坏的原生月报 | 第 1 页图下注释与背景同色，标题丢失「之后的」，右侧副标题溢出，页码越过右边界。门禁分别定位了这些问题。 | [PPTX](evidence/negative/monthly.pptx) · [实际截图](evidence/negative/slide-1.png) · [报告](evidence/negative/report.json) |
| 异常图片与字形 | 实际截图左侧是纯色块，右侧原文包含替代符。程序测得图片仅 2 × 2 px，并检出替代符。用已配置的 deepseek-flash 对这一页虚构数据实际调用视觉模型，返回了右侧文字和左侧图片的两条可定位建议。 | [PPTX](evidence/vision/exception.pptx) · [实际截图](evidence/vision/slide-1.png) · [含真实模型输出的报告](evidence/vision/report.json) |

模型首次实测出现 JSON 截断，管线记录无法完成模型审查。限制每页建议数量并调整输出预算后，同一输入完成了校验。模型成功与否均保留原来的确定性阻断结果。

## 测试命令

在已安装项目依赖的 Python 环境、仓库根目录执行。全量 Python 回归使用 CI 固定的 Anthropic SDK 2.8.0。

```sh
python -m unittest -v tests.test_presentations tests.test_presentation_review
(cd desktop && npm test && npm run build && npm run payload)
(cd desktop && presentation_design_engine=1 xvfb-run -a npm run test:desktop)
python evals/presentation/baseline.py /tmp/biscuit-before
PYTHON=$(command -v python) node evals/presentation/compare.mjs /tmp/biscuit-before /tmp/biscuit-after
python -u -X faulthandler -m unittest discover -v -s tests -t .
```

4 项新增 Python 测试通过，包含同色文字、真实缺字、溢出、越界、失败回退、非法模型输出及双供应商传输。33 项桌面 Node 测试、前端构建、Linux 冻结后端构建、真实 Electron 编辑与导出 smoke 和信任边界测试通过。

## 已知边界

当前仅检查 Biscuit 原生 16:9 导出。跨平台字体替换会改变断行；同环境哈希用于复现，跨系统应核对截图。PDF 字词边界包含字体度量留白，越过文本框不一定代表文字被裁掉；报告保留这一区别。带图片或透明层的背景、复杂矢量遮挡，以及能正确抽取文字但屏幕上显示方框的字形，仍需核对实际图片。PowerPoint、Keynote 原生应用及多人盲评未在此次实测中覆盖。Phase 0/1 建立观察能力，暂不改动布局或自动修复内容。
