# Feiyu Agent

简体中文 | [English](README.md)

用自然语言交代任务，让 Feiyu 帮你读代码、改文件、运行命令。

## Linux 安装

**推荐：一条命令，装好桌面版和终端版。** 适用于 Linux x86_64，需要能联网。

```bash
curl -fsSL https://raw.githubusercontent.com/feiyuceng06-prog/feiyu-agent/main/get.sh | bash
```

不需要预装 Python 或 Node.js，也不需要 sudo。程序安装在用户目录；脚本会在需要时把命令目录加入 Bash 或 Zsh 配置。

安装完成后，从应用菜单打开 **Feiyu**。也可以新开一个终端运行：

```bash
feiyu-desktop  # 桌面版
feiyu          # 终端版
```

升级时，重新运行上面的安装命令即可。

### 手动下载安装包

到 [下载页面](https://github.com/feiyuceng06-prog/feiyu-agent/releases/latest) 选择一种格式：

- **deb**：适用于使用 apt 的发行版。下载后在文件所在目录运行 `sudo apt install ./feiyu-desktop_0.87.0_amd64.deb`。
- **AppImage**：下载后运行 `chmod +x Feiyu-0.87.0.AppImage`，再双击打开。若提示缺少 FUSE，建议使用上方一键安装方式。

安装包未签名。各版本的系统验证范围和已知限制见下载页面。

## 首次启动

**桌面版**：点击「连接模型」，选择服务商，填入 API Key，再选择模型。

**终端版**：运行 `feiyu`，输入 `/key add`，按提示填写接口地址、模型 ID 和 API Key。

配置完成后，选择项目文件夹，就可以开始交代任务。API Key 需向对应模型服务商获取，调用费用由服务商收取。

## 从源码安装终端版

需要 Git、Python 3.10+ 和网络连接。在 Linux 终端执行：

```bash
git clone https://github.com/feiyuceng06-prog/feiyu-agent.git
cd feiyu-agent
./install.sh --cli-only
~/.local/bin/feiyu
```

若提示缺少 venv，Debian/Ubuntu 可先运行 `sudo apt install python3-venv`。请保留源码目录；更新代码后重新运行安装脚本即可。

## Windows / macOS

当前 0.87.0 发布仅提供 Linux x64 安装包，Windows 和 macOS 暂无本版本安装包。
