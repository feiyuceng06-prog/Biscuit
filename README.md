# Biscuit

English | [简体中文](README.zh.md)

Describe a task in plain language. Biscuit helps you read code, edit files, and run commands.

Biscuit was previously named Feiyu. The commands and existing data locations stay the same.

The chat composer offers four thinking levels. Drag the meteorite or use the arrow keys, then send your message. Pro requests `xhigh` on the current model. Available reasoning levels depend on your provider. Use the reset button to return to the model configuration.

## Install on Linux

**Recommended: one command installs both the desktop app and CLI.** Requires Linux x86_64 and an internet connection.

```bash
curl -fsSL https://raw.githubusercontent.com/feiyuceng06-prog/Biscuit/main/get.sh | bash
```

No Python, Node.js, or sudo required. The installer uses your user directory and adds the command directory to your Bash or Zsh configuration when needed.

Once installed, open **Biscuit** (previous releases: **Feiyu**) from your application menu. Or open a new terminal and run:

```bash
feiyu-desktop  # Desktop app
feiyu          # CLI
```

To update, run the same installation command again.

### Download an installer

Visit the [download page](https://github.com/feiyuceng06-prog/Biscuit/releases/latest) and choose a format:

- **deb**: for distributions using apt. In the download directory, run `sudo apt install ./feiyu-desktop_0.89.0_amd64.deb`.
- **AppImage**: run `chmod +x Biscuit-0.89.0.AppImage`, then double-click the file. If FUSE is missing, use the one-command installer above.

Packages are unsigned. See the download page for tested systems and known limitations.

## Update notifications

The desktop app checks GitHub stable releases at startup and every six hours while running. When a compatible release is available, the sidebar offers a release-page link and dismissal, alongside a **Check for updates** button. Offline checks do not interrupt chat.

Download the installer from the release page and upgrade using your existing installation method. Downloading an AppImage does not replace the old file or shortcut. Versions 0.87.2 and earlier need one manual upgrade to gain update notifications.

## First launch

**Desktop**: click “Connect model,” choose a provider, enter your API key, and select a model.

**CLI**: run `feiyu`, enter `/key add`, and follow the prompts for the API endpoint, model ID, and API key.

Then select your project folder and describe your task. Obtain an API key from your model provider; usage is billed by that provider.

## Install the CLI from source

Requires Git, Python 3.10+, and an internet connection. Run in a Linux terminal:

```bash
git clone https://github.com/feiyuceng06-prog/Biscuit.git
cd Biscuit
./install.sh --cli-only
~/.local/bin/feiyu
```

If venv is missing on Debian/Ubuntu, run `sudo apt install python3-venv` first. Keep the source directory; after updating the code, run the installer again.

## Windows

On the [download page](https://github.com/feiyuceng06-prog/Biscuit/releases/latest), download **Biscuit Setup 0.89.0.exe** and run it. Git Bash is included. Existing Feiyu settings and conversations are retained.

The installer is unsigned, so Windows may show a security warning. Check the source and published SHA256 before installing. See the release notes for Windows limitations.

A macOS installer is not available yet.
