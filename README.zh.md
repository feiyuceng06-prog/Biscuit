# Feiyu Agent

简体中文 | [English](README.md)

一个跑在终端里的编程助手。你把任务交给它，它自己读代码、改文件、跑命令，每一步都打在屏幕上。支持 Claude、DeepSeek、Kimi，以及任何 OpenAI 兼容接口。

约 1.6 万行 Python，没有框架，核心依赖只有 `anthropic`、`pillow`、`prompt_toolkit` 三个。

![demo](docs/demo.gif)

## 安装

### Windows 桌面版

Windows x64 安装包将在 Windows 构建通过后的 [Releases](https://github.com/feiyuceng06-prog/feiyu-agent/releases) 中提供。下载安装程序并打开 Feiyu；Python 后端已包含在安装包中。安装包内含 Git Bash，执行 Agent 命令无需另装 Git。Windows 不提供 Linux 的 bubblewrap 沙箱，命令仍遵循应用内的权限确认。安装包目前未经代码签名。

从源码构建：安装 Python 3.10+、Node.js 22+、MSVC 构建工具和 Git for Windows，在 PowerShell 中运行 `./install-windows.ps1`，安装程序输出在 `desktop/release/`。Windows x64 安装包已通过 Windows 原生 CI 的安装和桌面冒烟测试；尚需更多真实用户环境和模型请求验证。

未发布源码现为桌面/`--serve` JSON 输入输出显式设置 UTF-8；严格 cp936/cp1252 合成管道及 Linux 冻结后端已通过离线 Unicode 验证。这尚不能确认 Windows 0.84.5 部分文字乱码/缺失和对话报错的现场根因或已彻底解决，仍需 Windows 原生验证。既有归档 Linux 安装包早于本次修复，不含此改动。

### Linux 一行装好（桌面版 + 终端版）

```bash
curl -fsSL https://raw.githubusercontent.com/feiyuceng06-prog/feiyu-agent/main/get.sh | bash
```

装的是 [Releases](https://github.com/feiyuceng06-prog/feiyu-agent/releases) 里最新的那一版，放进用户目录：不用 sudo、不用装 Python，也不需要 libfuse2。装完应用菜单里有 **Feiyu**（或者运行 `feiyu-desktop`），终端里运行 `feiyu`；第一次打开会请你「连接模型」。再跑一遍就是升级。没有 curl 就把开头换成 `wget -qO-`（Ubuntu 桌面版默认就没装 curl）。`~/.local/bin` 不在 PATH 里的话（新装的 Ubuntu 就是这样），它会往 `~/.bashrc` 加一行（zsh 是 `~/.zshrc`），新开的终端窗口就能直接敲 `feiyu`；不想改就写成 `… | FEIYU_NO_MODIFY_PATH=1 bash`。这条命令只支持 Linux x86_64，系统要 Ubuntu 22.04 那一代或更新（glibc 2.35 以上）。

手上已经有 AppImage 文件的话（比如在别的机器上下好拷过来）：`bash get.sh Feiyu-x.y.z.AppImage`。不要了就删掉 `~/.local/share/feiyu-desktop`、`~/.local/bin/feiyu`、`~/.local/bin/feiyu-desktop` 和 `~/.local/share/applications/feiyu.desktop`，再删掉 `~/.bashrc` 里「由 feiyu 的 get.sh 加」那两行；模型、key 和对话记录在 `~/.config/feiyu` 和 `~/.local/state/feiyu`。

### Ubuntu 上从主分支装命令行版

```bash
wget -qO- https://raw.githubusercontent.com/feiyuceng06-prog/feiyu-agent/main/bootstrap-ubuntu.sh | bash
```

需要网络和 `wget`。脚本会检查 Python 3.10+ 和 venv；缺少时通过 `sudo apt-get` 安装，可能要求输入密码。程序和依赖安装在用户目录，交互式终端中安装后自动启动，在程序里输入 `/key add` 配置模型。之后运行 `~/.local/bin/feiyu`；若 `~/.local/bin` 已在 PATH，也可以直接运行 `feiyu`。重新执行该命令可安装当前主分支版本，旧版本目录不会自动删除，模型和密钥配置会保留。

### 从源码安装

```
git clone https://github.com/feiyuceng06-prog/feiyu-agent.git && cd feiyu-agent && ./install.sh
```

默认脚本会在源码目录建立命令行版的虚拟环境、安装依赖，并在 `~/.local/bin` 创建 `feiyu`。需要 Python 3.10 以上和网络连接；Debian/Ubuntu 如缺少 venv，先运行 `sudo apt install python3-venv`。命令行版需要保留源码目录；更新代码后重新运行脚本即可。脚本不会自动使用 sudo 或修改 shell 配置。

```bash
./install.sh --cli-only           # 只装命令行，跳过桌面编译
./install.sh --desktop            # 只安装桌面版，不安装终端命令
./install.sh --all                # 分别安装两个版本
./install.sh --python /path/to/python3  # 建虚拟环境时指定 Python
./install.sh --help
```

默认只安装命令行版。桌面版拥有单独的程序和 Python 环境，安装后可以删除源码目录，无需先安装终端版；Electron 安装包携带 Python 后端，不需要系统 Python 或 WebKitGTK；仍需系统的桌面运行库。桌面版从应用列表打开并在设置中配置模型。重新安装时若桌面构建失败，已有桌面启动器会保留。若终端命令不在 PATH，脚本会给出设置方法，也可直接运行 `~/.local/bin/feiyu`。

装完先加一个模型：运行 `feiyu`，输入 `/key add`，填接口地址、模型 id 和密钥。细节见[模型](#模型)一节。

两个可选的系统包，建议装上：

```
sudo pacman -S bubblewrap ripgrep      # Debian/Ubuntu: apt install bubblewrap ripgrep
```

`bubblewrap` 给 bash 加沙箱，`ripgrep` 让搜索快很多。

<details>
<summary>手动安装</summary>

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[openai]"
feiyu
```

`[openai]` 装的是 `openai` 包，DeepSeek、Kimi 和其他 OpenAI 兼容接口都靠它。只用 Claude 的话 `pip install -e .` 就够。

</details>

## 使用

```
feiyu                             # 在当前目录开始对话
feiyu -w ~/code/my-project        # 指定工作目录
feiyu -m ds-flash                 # 用 /key 里的某一条模型（默认上次用的）
feiyu -r                          # 接着上次在这个目录里的对话
feiyu "给 CLI 加一个 --json 参数"    # 跑完一个任务就退出
```

其他参数：

- `--mode default|auto|plan|readonly`：权限模式。一次性任务和管道里没人能点确认，要它自己动手就加 `--mode auto`。
- `--json-schema <文件>`：按 schema 输出 JSON，见[接进别的程序](#接进别的程序)。
- `--review`：跑完让另一个模型给改动打分。

想要窗口就敲 `feiyu-desktop`，见[桌面端](#桌面端)。

## 界面

```
╭─────────────────────────────────── deepseek  ·  上下文 1.4k  ·  ¥0.0014 ─╮
│ > 把 tools.py 里的 search 改成用 rg
╰──────────────────────────────────────────────────────────────────────────╯

⏺ Read(feiyu/tools.py)
  ⎿  读取 217 行

⏺ Update(feiyu/tools.py)
  ⎿  已修改 1 处
       47  -  rx = re.compile(args["regex"])
       47  +  if shutil.which("rg"):

  改完了，search 现在优先走 rg，找不到就退回原来的正则实现。
```

按键：`⏎` 发送，`\⏎` 换行，`@` 带上文件，`shift+tab` 切权限模式，`esc` 中断，`ctrl-d` 退出，`↑` `↓` 翻历史。

顶边框显示上下文用了多少和这次会话花了多少钱。上下文是百分比，没配价格的模型不显示金额。回答里的 Markdown 会渲染（粗体、代码、列表、表格、链接），斜体除外，因为 `*` 在命令行里多半是通配符。

`esc` 打断是安全的：说到一半的话留在历史里，没跑完的调用会补一条「被打断」的结果，对话不会坏。

### `@` 指一个文件

句子里任何位置写 `@路径`，这份文件在消息发出去**之前**就读好附上 —— 你已经知道
要看哪个文件了，不该再花一整轮往返让它去调 `read_file`。`Tab` 补全路径，一次一层。

```
> 照着 @feiyu/serve.py 把 @feiyu/tools.py 里的抓取那段重写一下
  已读好并附上：feiyu/tools.py（400/2331 行）· feiyu/serve.py（400/920 行）
```

`@` 一个目录附的是那一层的清单。图片和二进制不贴正文 —— 路径确认了，让它自己去读。
只有工作区里真的存在的路径才展开，所以 `@property` 和 `user@example.com` 照旧是普通文字。

输入 `/` 弹出命令补全：

| 命令 | 作用 |
|---|---|
| `/help` | 显示帮助 |
| `/model` | 列出模型；`/model <名字>` 切换，对话保留 |
| `/key` | 添加、查看、删除模型配置 |
| `/mode` | 权限模式 |
| `/allow` | 查看或添加权限规则 |
| `/sandbox` | bash 沙箱：`off` / `workspace` / `strict` |
| `/jobs` | 查看或停掉后台命令 |
| `/mcp` | 查看接入的 MCP 服务器 |
| `/undo` | 撤销它最近一次写文件，可以连着撤 |
| `/hooks` | 查看钩子 |
| `/verify` | 查看或设置改完自动跑的命令 |
| `/review` | 让另一个模型给这次改动打分 |
| `/memory` | 查看、添加、删除这个目录的长期记忆 |
| `/context` | 重新加载项目约定文件 |
| `/cost` | 按任务看最近的花费和最慢的那一轮 |
| `/compact` | 把历史压成摘要 |
| `/helper <名字>` | 摘要、子 agent、网页提炼改用一条便宜的模型；`/helper off` 改回 |
| `/style` | 回答风格：`default` / `concise` / `explanatory` / `teaching` |
| `/theme` | 终端配色和记号：`default` / `swiss` / `retro` / `anthropic` |
| `/skills` | 看有哪些技能和自定义命令；`/skills <名字>` 开关一份 |
| `/profile` | 配置档案（人格）：看有哪些、换一份、`/profile off` 摘掉 |
| `/bot` | 机器人：看有哪些、`/bot <名字>` 用那套人格开一段新对话 |
| `/clear` | 清空对话和存盘 |
| `/exit` | 退出 |

## 工具

十八个工具，每次调用都打在屏幕上：

| 工具 | 说明 |
|---|---|
| `bash` | 跑 shell 命令。`cd`、export 的变量、source 进来的环境（venv）和定义的函数都在多次调用之间保持；长命令可以挂后台 |
| `read_file` `write_file` `edit_file` | 读、写、精确替换。路径相对工作区根目录。`edit_file` 能一次改同一文件的多处，对不上时会指出最接近的位置；`write_file` 可以追加 |
| `list_files` `search` | 按通配符列文件、按正则搜内容 |
| `symbol` | 走语言服务器找定义和引用（pyright、clangd、rust-analyzer、typescript-language-server、gopls、lua-language-server，装了才能用） |
| `git` | 看状态、diff、log，提交。不让它提交它不会提交 |
| `web_search` `web_fetch` | 搜网页、抓网页 |
| `task` | 派一个子 agent 去查一件事，只带结论回来 |
| `todo` | 任务清单 |
| `remember` | 记一条跨会话的记忆 |
| `job` | 看后台命令的输出，或停掉它 |
| `exit_plan` | 计划模式下把方案交给你 |
| `ask_user` | 拿不准时问你一句 |
| `skill` | 把一份技能的完整说明读进来 |
| `image_generate` | 生成一张图，存进工作区（配了出图接口才挂上来） |

几件日常会碰到的事：

**截图可以直接给它看。** `read_file` 读到 png、jpg、gif、webp 会把图交给模型。模型能不能看图在 `/key add` 时填，没标的模型会明说看不了。

**跑很久的命令挂后台。** dev server、watch、长构建让它用 `bash` 的 `background` 参数起，之后用 `job` 取新输出。命令结束时它会收到通知。退出 feiyu 时会清理受控 job；进程身份无法核实的仍保持 unknown。

**改文件前必须先读过。** 读过之后文件又被别人改了（你在编辑器里改的，或者格式化工具改的），写操作会被拦下让它重新读。这一道闸挡的是它拿旧内容整份覆盖、把你的改动抹掉的情况。

**只读的调用会并行。** 一批调用全是读文件、搜索、抓网页这类时最多四个一起跑；掺进一个写操作就整批串行。

**连续调满 25 轮工具会停下来问你。** 大重构本来就要几十轮，选「接着做」就继续。一次性任务里没人能回答，它会直接停，进度存着，`feiyu -r` 能接上。

### 子 agent

「这个项目里中断是怎么处理的」这种问题要翻十几个文件，全进主对话会把上下文撑爆。它会派子 agent 去看，只把结论带回来。子 agent 只能读，改不了东西也上不了网，用量算进 `/cost`。

### 任务清单和计划模式

事情多的时候它会先列清单，做完一步改一步。想收尾时清单上还有没做完的，会被拉回去继续。没做完就退出的话，进度留到下次在同一目录开工时带上，七天后作废。

改动大的时候切到计划模式（`shift+tab` 或 `/mode plan`）：它只能读和想，写和执行一律拒绝。方案交给你过目，你点头后才动手。

### 拿不准就问你

答案会影响它接下来怎么做的时候，它会停下来问一句，摆两到四个选项：

```
  │ 这两处的断句逻辑要一起改吗？
  │ [1] 一起改，保持三处同源（推荐）
  │ [2] 只改 writer，nvim 那边我自己来
    [1-2] 选  [t] 自己打字  [esc] 你定
```

小事它自己拿主意。

### 提 PR

没有专门的 PR 工具，用的是 bash 里的 `git` 和 `gh`。它会按这个顺序走：读 CONTRIBUTING 和 `.github` 下的模板，开分支，改，跑测试，提交，push 到自己的远端，fork 的话用 `gh pr create --repo` 指回上游，描述照模板写并带上 issue 号。push 和开 PR 每次都要你确认。

### 文档和网页

`.docx` `.xlsx` `.pptx` `.odt` `.ods` `.odp` `.pdf` 读的时候自动抽成文字，直接问「这份周报写了什么」就行。PDF 需要系统里有 `pdftotext`。只能读，写这类文件让它写脚本调 `python-docx`、`openpyxl`。

`web_fetch` 抓网页转成 Markdown。带 `prompt` 参数时模型读完整页只回答那个问题，原文不进上下文。默认拒绝非公网地址、混合公网/非公网 DNS 结果和无法解析的地址；内置抓取在实际建连时重新核验，并直接连接核验后的 IP，HTTPS 仍验证原主机名。内置页面和图片下载采用直连，不使用 `HTTP_PROXY` / `HTTPS_PROXY` 等环境代理；需要代理时可配置 Firecrawl 服务；用户配置的 Firecrawl 和图片生成 API 端点仍使用系统代理，并支持自托管地址。Firecrawl 在服务端解析目标，需要该服务自己提供同等网络限制。本机开发服务器要用 `FEIYU_ALLOW_LOCAL_FETCH=1 feiyu`。

**抓不动的站可以挂 [Firecrawl](https://firecrawl.dev) 兜底。** 反爬（Cloudflare、UA 检查）是自带抓取治不了的，
在 `~/.config/feiyu/fetch.json` 里填个 key，撞上 401 / 403 / 429 时就自动换它再抓一遍：

```json
{"key": "fc-…"}
```

只在这几种失败上回退 —— 404 换谁抓都是 404，不值得花额度。想一律走它就加 `"provider": "firecrawl"`，
自托管实例加 `"url": "http://localhost:3002"`。花了额度的那次，结果行上会写明 `Firecrawl ·`。

`web_search` 出厂走 DuckDuckGo，不用配置。想换后端写 `~/.config/feiyu/search.json`：

```json
{"provider": "brave", "key": "…"}
{"provider": "searxng", "url": "http://localhost:8080"}
{"provider": "firecrawl", "key": "fc-…"}
```

**出图要自己配。** `~/.config/feiyu/images.json` 写上一个或多个 OpenAI 兼容的 images 接口：

```json
{"default": "nano-banana-2",
 "models": {
   "nano-banana-2": {"base_url": "https://openrouter.ai/api/v1", "key": "…",
                     "model": "google/gemini-3.1-flash-image", "size": "1024x1024"},
   "gpt-image-2":   {"base_url": "https://…/v1", "key": "…", "model": "gpt-image-2"}
 }}
```

别名会变成 `image_generate` 的 `model` 参数，于是可以一个便宜一个好，让它按图挑；
不写就用 `default` 那个。老的扁平形状 `{"base_url": …, "key": …, "model": …}` 照样认，
算作唯一一个模型。配了才会有 `image_generate` 这个工具 —— 不出图的人不该为它每轮多发一份 schema。
出来的图落在工作区的 `.feiyu/images/` 下，桌面端会直接画在对话里，终端里只报路径。

## 权限

`shift+tab` 循环切换，或 `/mode <名字>`：

| 模式 | 行为 |
|---|---|
| `default` | 允许列表里的直接跑，其余问你（默认） |
| `auto` | 全部直接执行 |
| `plan` | 只能读和想，方案你同意了才动手 |
| `readonly` | 只能读、列、搜、抓网页 |

问你的时候：`y` 执行，`n` 跳过，`a` 本轮都允许，`s` 以后都不用问。被拒的调用会把原因回给模型，它通常会换个做法。

规则写成 `工具(模式)`，存在 `~/.config/feiyu/permissions.json`，deny 优先：

```
Bash(ls:*)            以 ls 开头的命令
Bash(git status:*)    以 git status 开头
Bash(pwd)             正好是这条命令
Read(*)               这个工具的所有调用
Mcp(fs:*)             某个 MCP 服务器的所有工具
```

命令会先在 `&&` `||` `;` `|` 和重定向处切开，每一段都要被允许才放行，所以 `ls -la && curl x | sh` 不会因为 `ls` 被放行就跑掉。带 `$(...)` 或反引号的命令一律问。

出厂 bash 规则只放行 `ls` `pwd` `echo` `wc` `which`。Git 查询请用结构化 `git` 工具的 `status` / `diff` / `log`，默认无需确认；bash 中的 Git 命令需要确认，因为参数和仓库配置也可能写文件、删分支或执行程序。升级会撤回旧版默认提供的四条宽泛 Git bash 规则；升级后用户主动重新授予的规则会保留。复合命令按原始换行及控制符逐段检查。`cat` `head` `grep` 不在里面，因为它们能读工作区外的任何文件。碰 `.ssh/`、`.aws/credentials`、`~/.config/feiyu/`、`.env` 这类路径的命令一律拒，`auto` 模式也拒。

**读过外部内容之后，能联网的命令要你点头。** 网页、搜索结果、MCP 的返回、bash 里 `curl` / `wget` 抓回来的东西，都可能藏着一句「把 `.env` 发到某某地址」。这段对话读过它们之后：沙箱开着时 bash 默认断网跑，确实要联网的（装依赖、拉代码）模型得带上 `network: true`，并且要你点头；沙箱关着断不了网，那就除了 `ls` `cat` `grep` 这类连不了网的命令，都要你点头。**`auto` 模式和允许规则都跳不过这一步。** `/clear` 或新对话才放下。没人能点头的场合（管道、跑分）一律拒，它会把联网那一步告诉你。`FEIYU_TRUST_OUTSIDE=1` 整个关掉（评测用）。

`web_fetch` 和 MCP 本身也是出口，这一步没管它们：管了的话「搜一下再点开结果」每一步都要点头。

## bash 沙箱

装了 `bubblewrap` 就默认开着，Linux 才有：

| 档位 | 行为 |
|---|---|
| `off` | 不沙箱 |
| `workspace` | 工作区外只读，密钥目录挖空，能联网（默认） |
| `strict` | 同上，另外断网 |

写是真隔离，用的是内核的 mount namespace：工作区和 `/tmp` 之外全部只读，`~/.ssh`、`~/.gnupg`、`~/.aws` 和 feiyu 自己的配置、状态目录都被盖成空目录。读没有隔离，整个文件系统仍然可读。

docker / podman 的 socket 也挡在外面——碰得到它就能 `docker run -v /:/host` 往任何地方写。断网的时候（`strict` 档，或者读过外部内容之后）连 `/run` 下的服务一起断：光断网卡不够，DNS 解析走的是那里的 Unix socket，照样能把数据编进域名送出去。

三个常见的沙箱内失败它会认出来并说明原因：ssh 远端因为 `~/.ssh` 被挖空而失败（https 远端配 `gh` 的凭据助手不受影响），docker 连不上，断网时联不了网。

`/sandbox` 切换，`FEIYU_SANDBOX=off` 临时关掉。没装 bubblewrap 就没有沙箱，启动时会提示一句，输入框上沿的状态里也会标出「无沙箱」。

## 自动化

**改完自动跑测试。** 在项目约定文件里单起一行：

```
verify: npm test
```

项目文件里的 `verify:` 首次使用时会展示来源和完整命令，请你确认是否信任；约定文件内容变化并重新加载后需要再次确认。拒绝或无人回答时不会执行，`auto` 模式也不会跳过这次信任确认。`/verify <命令>` 是用户主动设置，只作用于当前会话。已信任的命令在首次改动前及每次写完或改完文件后运行；这些命令遵循共用 Shell 沙箱、命令权限及出网规则。没过就把报错交给它自己修。报错会先给一份要点（哪个用例挂了、断言是什么、编译错在哪行），再附原文。

0.85.0 起，首次复现和自动验证把机器可读证据保存到会话：命令、工作区/cwd、任务/会话 ID、起止时间、退出码、超时/取消、前后内容指纹，以及 `$XDG_STATE_HOME/feiyu/verification`（默认 `~/.local/state` 下）的私有持久 stdout/stderr 日志。执行结果与当前有效性分开保存。编辑、Shell/MCP/hooks、后台工作均保守失效旧结论；消费结论前重新核对内容。恢复记录只作历史证据，须重跑。代码工作结束会展示验证范围与状态；闲聊无需代码验收。

默认覆盖 Git tracked 与非忽略 untracked，无 Git 时有界扫描目录（20,000 文件、每次读取 256 MiB、5 秒；读两次内容）。扫描失败、超限、软链/子模块、后台任务仍运行或日志缺失时不能得到当前通过。状态/日志目录应放在工作区外。忽略依赖、外部服务和动态环境输入未完整覆盖；这不是原子文件系统快照。日志目前无自动清理策略。hooks/verify 分别检查来源信任和命令权限，现在复用 bash 沙箱。


**长任务的三道闸。** 同一份约定文件里，另起一行：

```
max-rounds: 0
budget: 5
time-budget: 30m
```

`max-rounds` 是连续调多少轮工具之后停下来问一句（出厂 25，**0 是不限**）。出厂那个数是给交互用的：改一行、编译、看报错、再改这种循环几百轮起步，事先给不出一个对的数字。

**放开轮数就得把 `budget` 填上。** 非交互场景（管道、一次性任务）没人回答那句问话，轮数不设闸时钱是唯一那道闸；而没填过价格的模型算不出花了多少，那时两道闸一道都不在。

`time-budget` 是这一句话最多跑多久（不写单位按分钟算，也可以写 `90s` / `45m` / `1.5h`，**0 是不限**）。它按**每一句话**计，不是整个会话——交互里你想事情的那几分钟不算在内。**快到点时它会收到一句「该收口了」**：把做成的那部分弄到能用、改到一半的别留在半路。被外面掐掉时，改到一半的文件比什么都没做更糟。

命令行的 `--max-rounds` / `--budget` / `--time-budget` 比约定文件优先，`/context` 重载也不会把它盖回去。

**钩子。** 全局写在 `~/.config/feiyu/hooks.json`，项目写在 `.feiyu/hooks.json`：

```json
{
  "PreToolUse":       [{"matcher": "Bash(git push:*)", "command": "echo '请开 PR' >&2; exit 1"}],
  "PostToolUse":      [{"matcher": "Write|Update", "command": "ruff check ."}],
  "UserPromptSubmit": [{"command": "git branch --show-current"}],
  "Stop":             [{"command": "notify-send 'feiyu 干完了'"}]
}
```

退出码 0 放行、非 0 拦下。`PreToolUse` 拦下这次调用，`PostToolUse` 把输出交给模型自己修，`UserPromptSubmit` 放行时把 stdout 当背景带上，`Stop` 只记日志。`matcher` 用权限规则的语法。钩子从 stdin 收一份 JSON。

项目里的钩子第一次见到要你点头才启用，文件改了会重新问。仓库里带下来的命令不该一 clone 就自动执行。

**独立评分。** `/review` 或 `--review` 另开一个模型，只给它看任务和最终 diff，按完成度、有没有 bug、有没有多做没要求的事打 0 到 10 分。要多花一次 API 调用，所以手动触发。

## 编辑器（nvim / VS Code）

在编辑器里开着的项目下跑 feiyu 时，`write_file` / `edit_file` 的确认就从终端里
那十四行 +/- 变成编辑器原生的左右对照。接受、拒绝，或者**先把右边改成你想要的样子
再接受** —— 写进文件的是你看到的那份，不是模型原来那份。

```
nvim       ~/.config/nvim/lua/feiyu_ide.lua     ga 接受 · gA 以后都接受 · gr 拒绝
VS Code    「Feiyu IDE Bridge」扩展              alt+y  · alt+shift+y   · alt+n
```

编辑器在 unix socket 上监听，并在 `$XDG_RUNTIME_DIR/feiyu/ide/` 下放一个几百字节的
lock 文件报到；feiyu 按**工作区完全相同**找到它，在上面说行分隔 JSON。
不引新依赖，也不监听任何 TCP 端口。

**谁先起来都行。** feiyu 先跑着、回头才打开编辑器也接得上：每次要确认写操作时看一眼，
最多五秒试一次连接，中途编辑器重启同理。接上和断开各说一句，你不用猜现在走的是哪条路。

降级只往一个方向：没有编辑器、编辑器崩了、回的东西认不出、答得太慢 —— 一律退回
原来终端里那套确认。**这座桥不可能挡住 agent。** `FEIYU_NO_IDE=1` 整个关掉；
`FEIYU_IDE_TIMEOUT`（默认 600 秒）是它等你多久之后放手、回终端问。

只管 diff。bash、`git commit`、`web_fetch` 这些照旧在终端确认 —— 它们没有 diff 可开。

## 桌面端

模型清单只在点击「列出模型」后请求。切换接口地址或类型会清空输入的 key；复用已保存的 key 要求协议、主机、端口和接口类型一致。修改表单后，旧的清单响应会被丢弃。

```
feiyu-desktop                     # 在当前目录开一个窗口
feiyu-desktop -w ~/code/project   # 指定工作目录
feiyu-desktop -r                  # 接着上次在这个目录里的对话
```

装完在应用列表里也能搜到 **Feiyu**。

**不想从源码装**：「安装」一节开头那行命令最省事；也可以到 [Releases](https://github.com/feiyuceng06-prog/feiyu-agent/releases) 下载 Linux 的 deb（`sudo apt install ./文件名.deb`，Ubuntu 上选这个）或 AppImage（`chmod +x` 之后双击）。AppImage 要系统里有 libfuse2，Ubuntu 从 22.04 起默认不装，先 `sudo apt install libfuse2`（24.04 上包名是 `libfuse2t64`），不然双击没反应。包里带着 Python 后端，不用装 Python、Node，也不用开终端。第一次打开会请你「连接模型」：选个接口（OpenRouter、DeepSeek、Kimi、通义千问、硅基流动、OpenAI、Anthropic，或者自己填地址），贴上那一家的 key，从现场拉回来的模型清单里点一个就能用。从应用菜单打开时，会接着用上一次选的工作台。Windows 安装包的构建和发布流程见上方 Windows 安装说明；macOS 暂无已验证的安装包。

**窗口里的东西不会跑到终端上。** agent 那半边人看的输出（还有桥接自己那几行 `→ op`）写进 `~/.local/state/feiyu/desktop.log`，跟对话存盘一样按 0600 存，攒到 4 MB 从头写。要它回到终端上看：`FEIYU_DESKTOP_STDERR=1 feiyu-desktop`。

输入框右下角是当前模型，**点一下弹出清单就能换**：条数多了直接打字筛，在用的那条标着。

**要你点头的时候可以用键盘答**：按钮上标着 `1` `2` `3` `4`，跟摆的顺序一样。卡片出来之后稍等一下才接键（回不去的操作再多等一倍），正在打字时落下去的那个数字只会进输入框，不会变成「同意」；输入框里有字时数字就是字。「自己写」就在卡片里展开一行，不弹系统对话框。

**你没在看的时候它会记着。** 往回翻着看、或者切到别的窗口时底下长出来的东西，第一条前面会铺一条「以下是新的」，右下角那个箭头上数着有几条，点它落到那条线上而不是直接到底。窗口在后台时，它要你点头（带着命令原文）、或者一轮跑了十秒以上结束了，会弹一条系统通知（`notify-send`）。

左边是侧栏：新建会话、技能与工具，底下是历史对话——点一条切过去（agent 的上下文跟着换，不只是换画面），`shift+点` 置顶，划上去点 `×` 删掉（会先问一句），搜索框只筛本地那份列表。`Ctrl B` 收起侧栏，`Ctrl N` 开新会话。最上面那行是工作台，点一下换目录。

**设置**（`Ctrl K`）是五个页签：通用、技能、工具集、MCP、档案。「通用」里是外观、权限模式、回答风格、模型、旁活模型、bash 沙箱、校验命令、权限规则、长期记忆——按一下就生效，跟在终端敲那条斜杠命令是同一回事。

模型那一项可以直接加、改、删配置（接口地址、模型 id、API key、上下文上限、价格）。**已经存下的密钥不会发回界面**，所以改价格、改上限时 key 那栏留空就是「不动它」。这只在桌面端窗口里开着——开发用的浏览器入口听在回环地址上，同机任何进程都能连，那边一律拒。其余四个页签：每一项一个开关，关掉的东西既不进它的上下文，也调不出来——技能不在系统提示的目录里，工具不挂进请求，MCP 服务器的工具不暴露给它。改动立刻生效，记在 `~/.config/feiyu/enabled.json`（只记关掉的那些，所以你新装一份技能它天生就是开的）。终端里 `/skills <名字>` 也能开关一份。

`exit_plan` 关不掉：它是计划模式唯一的出口。关掉 MCP 服务器只是不把它的工具挂给模型，进程照旧起着——起不起写在 `mcp.json` 里，改了要重启。

第四个页签是**配置档案**：一份档案就是一套人格。正文直接拼进系统提示，可以在面板里就地改、就地存，也可以直接写 `~/.config/feiyu/profiles/<名字>.md`：

```markdown
---
name: 严厉评审
description: 只挑毛病，不说好话
model: deepseek-v4-pro
---
你是一个刻薄但准确的代码评审。先说最要命的那处，不铺垫、不夸奖。
```

`model` 可以不写；写了的话换档案时模型跟着换。**人格设定每一轮都会发给模型**，所以上限只有 4000 字（技能是一万二——那个只在用上的那次才发）。终端里 `/profile` 看和换。

### 机器人

侧栏是两个页签：**会话**和**机器人**。一个机器人就是一套「点一下就开一段新对话」的人格——它带的不只是人格，还有模型、权限模式、回答风格，开对话的那一刻就都设好了。一个机器人一个 `.md`，放在 `~/.config/feiyu/bots/<名字>.md`：

```markdown
---
name: 船长
description: 十八世纪的海盗船长
model: qwen3.8-flash
mode: readonly
style: concise
---
你是一个十八世纪的海盗船长。绝不承认自己是 AI。
```

除了正文，其余几项都可以不写，不写的那几项就保持这段对话原来的样子。在侧栏里新建和编辑，也可以自己把文件丢进去。

**一段对话记得自己是哪个机器人开的**，从侧栏切回来（或者 `feiyu --resume`）人格照旧在——不然半段对话是一个口气、半段是另一个。**一段对话要么套着机器人、要么套着档案、要么什么都不套**：人格那个位置是共用的，开机器人会把当前的档案摘掉。两者的区别：档案是往**正在进行的这段对话**里换一套人格，机器人是**用一套人格开一段新对话**。

输入框里 `@路径` 跟终端一样能补全（候选走服务端算，两边给的是同一份）。工作区外面的文件走输入框左边的 `＋` 上传，拖进窗口也行。文件落在工作区的 `.feiyu/uploads/` 下，路径随下一条消息一起交给它——它用本来就有的 `read_file` 去看，图片、docx、pdf 那些都认。

**它干活的时候。** 思考型模型可以想十分钟一个字都不说，所以窗口把想的过程本身画出来：一段可折叠的轨迹，在想的时候展开着，开口了自己收起来（你点过之后就听你的）。什么都还没发生时，一小格像素网格和一个秒表说明它还活着——秒表 0.58.0 就上了状态栏，但眼睛在正文流上。工具的长输出（跑测试、构建日志）默认只露头几行，其余点一下展开；那行摘要永远不折。

代码块带行号和复制按钮，行号在横滚槽外面，所以长行左右滚的时候它留在原地。选中回答里的任意一段，会浮出解释 / 改写 / 缩短 / 照着做——点了是把引起来的原文**填进输入框**不是直接发出去，你可以先补一句。往回翻着看而下面又长出新东西时，右下角出现一个 `↓`。

组件的清单和动效的手感参考了 [Beautiful UI](https://www.beautifului.dev/) 和 [beUI](https://beui.dev/)——借的是形态和节奏，不是皮：这扇窗照旧白纸、直角、不套卡片，而且 `prefers-reduced-motion` 一开所有动效全关。

跟终端版是同一个 agent、同一套权限、同一份会话存盘——只是画面换成了窗口。要改文件、跑命令时在页面上画出 diff 和命令原文，点了同意才动手。斜杠命令、技能、`esc` 中断都在。模型配置可以在桌面「设置 → 通用 → 模型」里管理，已保存的密钥不会回传给界面。

实现上是 **Electron 主进程 + React 工作台面板 + Python agent 子进程**。Electron 管理窗口、文件、终端和 agent 生命周期；聊天与设置沿用现有界面，通过受限 preload 桥接传输逐行 JSON。默认不监听网络端口，模型调用和权限确认仍由原来的 Python agent 处理。

右侧「文件」面板支持目录浏览、文件名筛选、多标签文本/代码和图片预览；`Ctrl Shift E` 收起或展开。文件预览只读，限制在当前工作区内。底部终端是独立 PTY，`Ctrl \`` 切换；它不会替代 agent 的命令审批流程。

开发和构建说明见 [desktop/README.md](desktop/README.md)。源码安装桌面端需要 Node.js 22+、npm、Python 3.10+ 和本地 C/C++ 构建工具，运行 `./install.sh --desktop`。该流程用 PyInstaller 准备独立 Python 后端，再用 electron-builder 打包。安装后的应用不需要源码、Node.js 或系统 Python。

旧的 Tauri/Rust 目录保留供兼容与对照，默认桌面安装已改用 Electron。Linux 发布构建工作流运行在 Ubuntu 22.04，生成 `.deb` 和 AppImage；本机在更新发行版上构建的包不保证兼容旧 Ubuntu。

## 技能和自定义命令

给它一套写好的做法，不用改代码。都是一个 `.md` 文件，开头可以写 frontmatter：

```markdown
---
name: 发版
description: 这个项目怎么发一个新版本
---

1. 跑 `.venv/bin/python -m unittest discover -s tests -t .`
2. bump `feiyu/__init__.py` 的 `__version__`
3. 在 CHANGELOG 顶部写一节
```

放的位置决定谁来触发：

| 放哪 | 谁触发 |
|---|---|
| `~/.config/feiyu/skills/` `.feiyu/skills/` | **它自己**。系统提示里只有名字和用途，它判断这次用得上才把正文读进来 |
| `~/.config/feiyu/commands/` `.feiyu/commands/` | **你**。敲 `/发版` 触发，正文当成你说的话送进对话 |

命令的正文里写 `$ARGUMENTS`，会换成你跟在命令后面的东西：

```markdown
查一下 $ARGUMENTS 在这个仓库里是怎么实现的，只看代码，别改任何文件。
```

敲 `/查 上下文压缩` 就等于把整句话打了一遍。没写这个占位符的话参数附在末尾。

**为什么分成两种。** 系统提示每一轮请求都要重发一次。一份用得上一次的做法要是常驻在里面，一百轮就付了一百次钱。技能只有名字和用途常驻（一份约一行），正文等真用上那次才进上下文。

`/skills` 看有哪些、各自是哪来的。同名时项目那份盖过全局那份。

**一套版面，三套配色。** 桌面端是照 [Fluid Functionalism](https://fluidfunctionalism.com) 的规则做的极简版面：控件只有 36 / 28 两档高、界面字六档、每组列表共用一块会滑的高亮，你说的话是气泡，输入区是一张浮起来的卡片，空对话那几个例子框在 [mdxcn](https://mdxcn.dev) 式的虚线框里。三套主题只换颜色：纯白纸配 IBM Blue（默认）、泛黄的纸配赭色（复古）、暖象牙纸配陶土色（Anthropic）。终端那边另有 `/theme`（换 ANSI 配色和记号，可选 `default` / `swiss` / `retro` / `anthropic`），两边互不相干。

**技能可以是一个包。** 一个 `.md` 是一份，一个带 `SKILL.md` 的目录也是一份，后者旁边可以放附属文件：

```
~/.config/feiyu/skills/
├── 发版.md              ← 一个文件一份
└── 教/                  ← 一个目录一份
    ├── SKILL.md         ← 正文
    └── MISSION-FORMAT.md  ← 附属文件，它按需读
```

附属文件**不进正文**——读正文时只会看到有哪些，要哪份它自己再取一次。网上下的技能包多半是 zip，直接丢进 `skills/` 就行，会自动解开（原 zip 留着，解过一次就不再解）。

**项目技能第一次见到要你点头**，目录里的内容改了会重新问 —— 技能是它自己决定加载的，仓库里带下来的一段指令不该一 clone 就进它的上下文。**项目命令不用点头**：你不敲就不会生效，敲了等于你自己把那段字打了一遍。

## 它记得什么

**项目约定。** 工作区放一个 `FEIYU.md`（也认 `AGENTS.md`、`CLAUDE.md`，取第一个），启动时读进系统提示。`/context` 重新加载。

**长期记忆。** 值得留到下次的事它会自己记一句，比如构建怎么跑、某个坑的原因、你说过的偏好。记之前要你点头。下次在同一个目录开工自动带上，`/memory` 查看和删除。存在 `~/.local/state/feiyu/memory/`，不会写进你的项目。

```
⏺ Remember(这个项目的测试必须用 pytest -q 跑，conftest 里有 fixture)
  ⎿  记住了
```

**同一件事栽第二次会被提醒。** 同一条命令报同样的错、同一个文件同样的替换失败，第二次时结果里会多一句「别再原样重试，先弄清楚为什么」，第三次叫它停下来问你。缓过来之后它会被提示：原因要是这个项目特有的，就用 remember 记一句（照样要你点头），下次别再踩。

**会话。** 每轮自动存盘，`feiyu -r` 接着聊。存盘是完整对话原文，在 `~/.local/state/feiyu/sessions/`，权限 600。`/clear` 连存盘一起删。

**上下文管理。** 每轮请求都要重发全部历史，所以它会自动收着：同一个文件又读了一次或被改过，旧的那份换成一行说明；很久以前的长输出只留头尾；实在超过上限才压成一段摘要继续。上下文上限在 `/key add` 时填，没填的话撞过一次「输入太长」就会自动记住那个模型的真实上限。

anthropic 接口会打缓存断点，重发的历史按缓存价计费。**走 OpenAI 兼容格式的 Claude（OpenRouter、中转站）同样得打**，它自己认得出来——不打的话每一轮都是全价，实测贵十倍。其余 OpenAI 兼容接口是服务端自动缓存。`/cost` 里能看到命中率。

## 接进别的程序

给一份 JSON schema，跑完按它输出：

```
feiyu --json-schema review.schema.json "检查 calc.py 有没有 bug" > out.json
```

stdout 里只有 JSON，界面和日志全走 stderr。不合 schema 会让它重出，最多两次，还不行就非零退出。支持 `type` `required` `properties` `items` `enum` `additionalProperties`。

**历史瘦身会看缓存。** 接口对重发的历史是按前缀缓存的——改了中间某一条，它后面的全部从缓存价掉回原价。所以「把旧的工具输出折叠掉」这件事只在两种时候做：这个接口压根不缓存（那折叠纯赚），或者上下文已经过半（快撞窗口了，省地方比省钱要紧）。`/cost` 里的命中率就是判断依据。

**日志。** 每件事一行 JSONL 写到 `~/.local/state/feiyu/logs/<日期>.jsonl`：每次工具调用、参数、权限判定、耗时、token 用量。排查「它为什么干了那件怪事」按 `run` 字段过滤。`FEIYU_NO_LOG=1` 关掉。

**额度。** 状态栏右边显示接口那边还剩多少（`余 $9.78`），点一下现查一次，每轮跑完自动同步。这跟左边那个 `¥` 不是一回事——那个是按你填的价格估的这一趟花了多少，这个是人家账上的余额。

认得出的接口：OpenRouter、DeepSeek、Moonshot、SiliconFlow，以及一堆抄 OpenAI 早年计费接口的中转站。**OpenAI 和 anthropic 的普通 key 查不到余额**（那是账号后台的事），这时候就整个不显示，不会编一个数给你。密钥只会发给你自己填的那个 `base_url` 的 host。

**花费。** `/cost` 按任务汇总最近七天：

```
   08-27 00:14  修好 parser.py 的错误处理       5轮    8.2k   71%   最慢12s   ¥0.031
   08-27 09:02  给 CLI 加 --json 参数         12轮   31.5k   84%   最慢38s   ¥0.118

   合计  39.7k  ¥0.149  缓存命中 81%
```

百分比是缓存命中率。长任务贵不贵主要看它：一直是 0 说明这个接口不缓存，每轮重发的历史都按全价算。

「最慢」是这个任务里**最慢的那一轮**，不是平均——九轮五秒、一轮十分钟的话，平均会把那十分钟摊没，而你要查的正是它。这个数大得离谱多半是接口当时抽风；日志里那一行还记着这轮出了多少 token，能分清是「说了很多」还是「接口就是慢」。

## MCP

外部 [MCP](https://modelcontextprotocol.io) 服务器的工具可以直接给它用。配置跟 Claude Code 一个格式，全局在 `~/.config/feiyu/mcp.json`，项目在 `.feiyu/mcp.json`：

```json
{"mcpServers": {
  "fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]},
  "db": {"command": "uvx", "args": ["mcp-server-sqlite", "--db-path", "app.db"], "env": {"X": "1"}},
  "resume": {"type": "http", "url": "http://localhost:3100/mcp",
             "headers": {"x-api-key": "${RR_API_KEY}"}}
}}
```

- 两种传输：**stdio**（起一条本地命令）和 **streamable-http**（连一个远端服务器）。
  没写 `type` 时，有 `url` 的当 http，没有的当 stdio。
- **`${VAR}` 从环境变量取**，key 不必落在配置文件里：http 那条在 `url` 和 `headers` 里认，
  stdio 那条在 `env` 块里认。`args` 里刻意不认 —— argv 会被 `/mcp` 原样印出来。
  （stdio 服务器**拿不到**环境里名字带 KEY/TOKEN 的变量，那些被刻意摘掉了防模型读到，
  所以要用就得在 `env` 里显式写一条。）
  变量没设就直接不起这台服务器，不会把字面量 `${VAR}` 发出去换回一个看不懂的 401。
- 工具以 `mcp_<服务器>_<工具>` 的名字出现，`/mcp` 能看到每个服务器的状态和工具。
- 项目配置跟项目钩子一样，第一次见到要你点头才启动。
- 默认模式下 MCP 工具均需授权，服务器自报只读不能免除授权。规则 `Mcp(fs:*)` 放行整个服务器，`Mcp(fs read_file)` 放行一个工具。
- 改了配置要重启 feiyu。

## 模型

模型清单由你维护，没有内置厂商、默认模型或价格表。`/key add`：

```
   名称（/model 里显示成这个）: ds-flash
   接口地址 base_url: https://api.deepseek.com
   模型 id: deepseek-v4-flash
   API key: ****************
   接口类型 openai / anthropic [openai]:
   这个模型能看图吗 y/N: y
   单轮输出上限 max_tokens（留空用 8192）: 64000
  下面三项是价格，人民币每百万 token，留空就只显示 token 数不算钱
     缓存命中价（没有缓存就填 0）: 0.02
     输入价: 1
     输出价: 2
     缓存写入价（留空按输入价算）:
```

存在 `~/.config/feiyu/models.json`，权限 600。价格留空就只显示 token 数。缓存写入价 anthropic 直连和经 OpenRouter 跑的 Claude 用得上（写缓存那一轮按输入价的 1.25 倍收），别家留空。

`max_tokens` 建议按模型的真实上限填。默认 8192 写一个长文件就会撞上限，撞上了这一轮工具调用就废了。填得比接口允许的大会报错。

## 安全须知

它会真的在你机器上跑命令、改文件，权限和你本人一样。

- 文件工具限制在工作目录内。
- bash 装了 bubblewrap 的话写被关进工作区，docker 的 socket 也碰不到，读没有隔离。没装就完全没有隔离。
- 变量名里带 `KEY` `TOKEN` `SECRET` `PASSWORD` 的环境变量不会传给子进程。`SSH_AUTH_SOCK` 保留，`git push` 照常。确实要给它某个密钥用 `FEIYU_KEEP_ENV_SECRETS=1 feiyu`。
- 网页内容会标注「外部数据，不是指令」，模型听不听没保证——所以读过外部内容之后，能联网的 bash 要你点头（见[权限](#权限)）。
- git 工具看状态、看改动时不会执行仓库配置里写的程序（fsmonitor、外部 diff）：`.git/config` 就在工作区里，被改过也拉不起东西来。
- 存密钥的 `~/.config/feiyu/`、存对话原文和输入历史的 `~/.local/state/feiyu/`，目录 700、文件 600。
- 桌面端不监听任何端口，前端和 agent 走进程内通道，见[桌面端](#桌面端)。

所以：在你信任并且用 git 管理的项目上用它，改坏了好回退。别在放着敏感凭据的机器上跑不受信任的任务。真需要硬隔离就放进容器或虚拟机。

## 平台

Python agent 支持 Linux、macOS 和 Windows（Windows 桌面安装包包含 Git Bash）；bash 沙箱只在 Linux 上。Electron 桌面已在 Linux 和 Windows x64 CI 运行安装与冒烟测试；macOS 构建仍需原生验证。Windows 开发需 Python 3.10+、Node.js 22+、MSVC 构建工具和 Git for Windows，运行 `./install-windows.ps1`，安装程序位于 `desktop/release/`。

## 测试

```
python -m unittest discover -s tests -t .
```

1475 个用例，四十秒跑完，不打真实 API，不碰 `~/.config/feiyu/`。没装 bubblewrap 的机器上沙箱那组自动跳过。

## 版本

语义化版本，版本号在 `feiyu/__init__.py`。

## License

[MIT](LICENSE) © feiyuceng06-prog

0.86.0 起，参数校验先于授权及 PreToolUse hook；共用执行器记录开始/结果，保持只读批次并行、混合写批次串行，不自动重试副作用。hook 和自动 verify 复用 Shell 沙箱与出网边界；项目来源信任与命令授权分开，deny 始终优先。MCP 自报只读不授信任、不扩大并行。执行事件仅供核查；阶段 D 已另加持久任务 journal。当前验收边界见[交付矩阵](docs/architecture-delivery.md)。

阶段 D 开发中（0.87.0，未完成）：任务 journal 增加 Git worktree/common-dir 身份、陈旧 writer 和内层数据检查。`/task` JSON 控制入口录入带原请求引用的约束/验收、绑定真实验证记录并重新核验；模型不能自封验收通过。恢复保存逐操作文件/Git观察，未知副作用阻止继续，须用户明确记录核对依据才能解除阻断，不授予重跑权限；reset/new 不能绕过当前 unknown。完整任务事实回到上下文，取消/异常保存最终 checkpoint。开发树已实现父模型账本和 Linux 后台 job 协议，Shell/hooks/MCP/SDK 取消路径已实现并在记录范围内审过，LSP 实现仍缺受阻的独立审查；任意外部副作用仍需人工核对，不保证恰好一次。见[当前设计与控制命令](docs/architecture-evolution.md#15-d1--d2-unknown-续作0870待-astra-审阅)。

开发说明（未发布0.87.0）：main、helper、压缩、reviewer 和子调查的模型请求已共享持久化任务费用/截止账本。缺失 usage 保留未知；恢复不会补充额度或延长已记录的截止时间。provider retry/部分 usage、动态预算收紧及 Shell/hooks/MCP/SDK 等待取消已有局部审查证据；平台缺口、受阻 LSP 审查及历史警告仍未关闭；SDK 父硬退出仅在交付矩阵规定的普通 Linux 范围有限接受。迁移限制和证据见[设计第17节](docs/architecture-evolution.md)及[进度记录](docs/architecture-progress.md)，不得据此验收 D 完成。

Linux 后台 job 现在保持 journal running，直到监管进程保存真实退出/取消状态与持久输出。`job` 支持 list/status/output/wait/kill，wait 检查取消和截止。恢复仅观测 boot ID/starttime 与持久收据，不重放；signal 必须通过 pidfd 身份校验。日志/退出证据缺失或终态保存失败保持 unknown。running/pending job 阻止切换任务，仍存活的 job 不能人工 resolve。仅控制原进程组，不涵盖主动逃逸的后代；非支持平台拒绝新后台 job。日志尚无自动清理策略。崩溃窗口与限制见[第18节协议](docs/architecture-evolution.md)，后台父限制修复已在 Linux 范围有限接受，不代表 D 整体验收通过。

任务结果控制：`/task {"action":"result","result":"partial","reason":"已交付X，Y尚未完成"}` 记录人工声明；验证无法运行时用 `unverifiable` 并提供原因，撤回结论用 `unfinished`。`/task complete`（或 JSON result `completed`）仍要求当前有效验收事实且无未决副作用。声明不把测试改为通过、不解除 unknown。继续 partial/unverifiable 的工作会将结果清回 unfinished，保留要求和证据；`/task` 与 `/task {"action":"show"}` 分别展示结果和运行状态。CLI 与 serve 共用这些控制。

D10开发更新（未发布0.87.0，F1/F2修复已在审查范围关闭）：内建Anthropic/OpenAI同步生成attempt现使用每次独立SDK worker。父进程可在网络静默和管道背压时观察取消及更早截止，终止并wait回收自身worker后返回。完成未知时usage仅为下界；本地停止不能撤销远端生成或收费。IPC每帧上限64MiB。Linux已测，Windows/macOS未验证；Linux新增独立监管者，在父SIGKILL后终止并回收直接SDK子进程，写有界私有本地收据（已在普通Linux审查范围有限接受）；前提是监管者存活且子进程可杀，收据不证明远端取消或授予重放权限；Fake/custom client保持原接口。兼容和恢复限制见[设计第27节](docs/architecture-evolution.md)，D仍未整体验收。

上下文构建区分稳定规则/项目背景与易变任务事实、近期验证引用、恢复进度；缓存断点放在稳定前缀之后，不保证接口支持或实际缓存收益。原生会话存盘现保留图片、推理/签名和工具字段以供恢复（图片会话会占更多磁盘空间）；文本摘要仍省略图片载荷。摘要压缩先拒绝未配对工具历史，将模型文字标为 assistant_claim，并从 TaskState/job/Ledger 重建程序事实与验证引用；核对、停止检查及候选存盘成功后才替换历史。压缩仍会删除旧图片/推理等原生消息，不是无损归档；原会话备份应另行保留。验证引用消费时重核归属和有效性，未知或过期不能升级为通过。

运行诊断现在携带会话、任务、运行归属及运行内递增序号。执行边界、验证失效和任务停止/恢复事实来自运行层；CLI 工具输出与桌面工具卡片旧协议保持兼容。事件投递仅为展示，不能替代任务 journal 或验证证据。并行工具显式携带原运行路由，运行关闭后迟到事件丢弃。全链路来源及 Dreaming 集成已获 E8/9 有限接受；E 各批验收边界见[交付矩阵](docs/architecture-delivery.md)。

记忆、压缩摘要和子调查报告保留来源引用。生成的文字仍是助手陈述；引用内容不授予权限，也不证明测试通过。Dreaming 应用前重新核对来源与候选指纹，验证仍以执行账本为准。旧记忆继续可读，来源未知时不补造可信类别。

架构评测交付准备（仅离线，不调用远端 provider）：参见
[可复现配置、命令与尚待接通的真实运行适配](docs/architecture-evaluation.md)。
程序回归已验证，真实模型收益尚未验证。

离线架构接线：`python -m evals.architecture fake --out <全新绝对目录>` 使用隔离假 provider 实跑冻结基线/当前产品。见[执行协议与限制](docs/architecture-evaluation.md)。程序回归已验证，真实模型收益尚未验证；`live` 仍阻断，不代表获得费用授权。

未发布0.87.0平台范围：历史安装/CI支持不代表本次D/E支持。Windows TaskStore/LSP/持久job仍缺实现，MCP/SDK仍缺原生实机证据；当前 Linux Electron unpacked 发行产物已通过离线 smoke/信任及合成中文流式/会话检查，deb/AppImage 内容与该构建匹配；安装行为及其他平台尚未验证。见[交付矩阵](docs/architecture-delivery.md)。

离线SDK适配：`python -m evals.architecture loopback --out <全新绝对目录>` 通过原生OpenAI SDK和合成本地HTTP服务运行冻结双源码产品。usage固定价格估算与供应商真实账单分列，未知用量停止预算；全部结果仍为synthetic且全快照对照有混杂。`live`仍在读取凭证前拒绝，不代表费用授权或真实收益验证。`python -m evals.architecture anthropic-loopback --out <全新绝对目录>` 新增实际SDK的Anthropic原生Messages、工具往返和辅助压缩，缓存计价也是合成固定价。远端授权/账单仍待后续，见[评测协议](docs/architecture-evaluation.md)。

U6评测准备新增 `python -m evals.architecture_authorization template --plan <candidate.json>` 和 `preflight --plan <plan.json> --authorization <record.json> --observed <observed.json>`。它们校验显式本地计划/批准记录绑定并输出JSON指纹；模板不默认批准。有效收据不证明可信宿主或本会话费用授权，不消费批准，也不开放远端执行。专用凭据路径仅作引用；`live`仍在配置/凭据前拒绝。合成消费/重启预算已在独立持久控制器实现；真实付费运行、凭据与账单仍需另行授权的live路径。详见[评测边界](docs/architecture-evaluation.md)。

实际测量准备：`python -m evals.architecture_measurement prepare --policy <v1-candidate.json> --config <config.json> --out <新目录>` 冻结双源码、测量已安装运行时文件，并在隔离worker中捕获初始原生请求而不派发。输出v2 observed计划、测量manifest和未批准模板。`preflight` 使用同一policy/config，另加 `--plan <v2-plan.json> --authorization <record.json>`，重新测量后严格匹配。系统提示/模板/构造器锁与实际请求hash分列，后续会话提示仍动态产生。这只是本机字节绑定，不是用户费用授权或可信宿主证明；远端仍拒绝。见[测量边界](docs/architecture-evaluation.md)。

新增仅评测用Linux持久预算API，演练合成批准单次消费、物理子进程fake调用前预留/结果落盘及重启恢复。全局次数/原截止/固定估算额度覆盖观察与重试；未决结果阻断重放。本地合成范围已有限接受，包括OpenAI/Python3.14完整96观察调度与权威判题/导出；recovery失败仍保留失败。不赋予真实费用授权；live、真实账单与模型收益仍未验证。见[持久API与恢复协议](docs/architecture-evaluation.md)。
