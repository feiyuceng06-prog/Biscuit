# Feiyu Agent

English | [简体中文](README.zh.md)

Describe a task in plain language. Feiyu helps you read code, edit files, and run commands.

## Install on Linux

**Recommended: one command installs both the desktop app and CLI.** Requires Linux x86_64 and an internet connection.

```bash
curl -fsSL https://raw.githubusercontent.com/feiyuceng06-prog/feiyu-agent/main/get.sh | bash
```

No Python, Node.js, or sudo required. The installer uses your user directory and adds the command directory to your Bash or Zsh configuration when needed.

Once installed, open **Feiyu** from your application menu. Or open a new terminal and run:

```bash
feiyu-desktop  # Desktop app
feiyu          # CLI
```

To update, run the same installation command again.

### Download an installer

Visit the [download page](https://github.com/feiyuceng06-prog/feiyu-agent/releases/latest) and choose a format:

- **deb**: for distributions using apt. In the download directory, run `sudo apt install ./feiyu-desktop_0.87.0_amd64.deb`.
- **AppImage**: run `chmod +x Feiyu-0.87.0.AppImage`, then double-click the file. If FUSE is missing, use the one-command installer above.

Packages are unsigned. See the download page for tested systems and known limitations.

## First launch

**Desktop**: click “Connect model,” choose a provider, enter your API key, and select a model.

**CLI**: run `feiyu`, enter `/key add`, and follow the prompts for the API endpoint, model ID, and API key.

Then select your project folder and describe your task. Obtain an API key from your model provider; usage is billed by that provider.

## Install the CLI from source

Requires Git, Python 3.10+, and an internet connection. Run in a Linux terminal:

```bash
git clone https://github.com/feiyuceng06-prog/feiyu-agent.git
cd feiyu-agent
./install.sh --cli-only
~/.local/bin/feiyu
```

If venv is missing on Debian/Ubuntu, run `sudo apt install python3-venv` first. Keep the source directory; after updating the code, run the installer again.

## Windows / macOS

The current 0.87.0 release provides Linux x64 packages only. Windows and macOS packages are not available for this version.
