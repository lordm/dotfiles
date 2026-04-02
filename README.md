# Marwan Osman's Dotfiles

Complete development environment configurations for Debian-based Linux systems (Ubuntu). Includes dual Neovim setups (NvChad + LazyVim), Vim, Zsh, Tmux, Git, and automated installation scripts.

## Quick Start

**⚠️ Important**: Review `install.sh` before running!

```bash
./install.sh
```

The script will:

- Install system packages (Docker, lazygit, k9s, nvm, pyenv, htop, etc.)
- Backup existing dotfiles to `~/*_old` or `~/*.old`
- Create symlinks from home directory to this repository
- Install Oh My Zsh, Nerd Fonts, and development tools
- Set up Python 3.12 via pyenv and Node.js via nvm

## Neovim Configuration (Dual Setup)

This repository includes **two complete Neovim configurations** that can be switched on-the-fly:

### LazyVim (Primary)

- **Framework**: LazyVim
- **Plugin Manager**: lazy.nvim
- **Location**: `lazyvim/`
- **Claude Code Integration**: Dual config support (personal/work)
- `<leader>ap`: Toggle Claude (Personal)
- `<leader>aw`: Toggle Claude (Work)

### NvChad (Legacy)

- **Framework**: NvChad v2.5
- **Plugin Manager**: lazy.nvim
- **Theme**: tokyonight
- **Location**: `nvchad/`

**Key Features**:

- LSP support for Python (pyright, ruff), TypeScript, HTML, CSS
- Debugging with nvim-dap, nvim-dap-python, nvim-dap-ui
- Testing with neotest-python
- Git integration via lazygit.nvim (`<leader>gg`)
- AI assistance: copilot.lua, claude-code.nvim
- Auto-formatting with conform.nvim and prettier

### Switching Between Configs

```bash
# Switch to NvChad
nvchad

# Switch to LazyVim
lazyvim
```

These aliases unlink and relink `~/.config/nvim` to the selected configuration.

### Post-Installation

- **NvChad/LazyVim**: Plugins auto-install on first launch
- **Vim**: Open vim and run `:PlugInstall`

## Vim Configuration (Legacy)

### Plugin Manager: vim-plug

**Notable Plugins**:

- YouCompleteMe, ALE (linting)
- NERDTree, Fugitive (Git)
- Ctrlp (fuzzy finder)
- UltiSnips, vim-snippets
- vim-prettier, vim-surround
- vim-better-whitespace

### Adding a New Plugin

Add to `vim/vimrc`:

```vim
Plug 'scrooloose/nerdtree'
```

Then run `:PlugInstall` in Vim.

## Zsh Configuration

### Framework: Oh My Zsh

- **Theme**: robbyrussell
- **Keybindings**: Vim mode (`bindkey -v`)
- **Plugins**: git, catimg, rvm, ruby, python, pip, node, ng, npm, command-time

### Key Features

- **Auto Node.js version switching**: Detects `.nvmrc` files
- **Pyenv integration**: Python version management (global: 3.12)
- **Editor**: nvim (set as `$EDITOR`)
- **Zoxide**: Smart directory jumping (if installed)

### Useful Aliases

```bash
dose                # docker compose
tmux                # tmux -2 (256 color support)
claude-phi          # Claude Code with personal config
nvchad              # Switch Neovim to NvChad
lazyvim             # Switch Neovim to LazyVim
restartswap         # Restart swap space
```

## Tmux Configuration

### Key Settings

- **Prefix**: `C-a` (screen-like, instead of default `C-b`)
- **Reload config**: `C-a r`
- **Vim-style pane navigation**: `C-a h/j/k/l`
- **Splits**:
  - `C-a |` horizontal split (preserves path)
  - `C-a -` vertical split (preserves path)

### Plugins (via TPM)

- tmux-sensible
- tmux-resurrect (session restoration)
- tmux-continuum (auto-save enabled)

## Git Configuration

### Default Editor: nvim

- **Diff/Merge Tool**: nvimdiff
- **Signing**: SSH key signing enabled

### Useful Aliases

```bash
git lg              # Beautiful graph log with colors
git cleanup         # Delete merged branches (excludes 'main')
git nuke <branch>   # Delete local + remote branch
git co              # checkout
git ci -m           # commit with message
git st              # status
git df              # diff
git br              # branch
```

## Ghostty Terminal

- **Config**: `ghostty/config`
- **Custom Theme**: `astigmatism-dark` — warm muted palette optimized for astigmatism (no pure black/white)
- **Font**: JetBrains Mono (ligatures disabled)
- **Keybinds**: Tmux-friendly (tabs/splits disabled), `Shift+Enter` for multi-line input (Claude Code)

## Audio Setup (Neural DSP Guitar Rig)

Low-latency guitar practice setup using Wine + yabridge + REAPER + PipeWire JACK with a Focusrite Scarlett Solo 4th Gen.

- **PipeWire**: 512 quantum @ 48kHz (~10.7ms latency)
- **WirePlumber**: ALSA tuning for Scarlett Solo
- **Yabridge**: Bridge for Neural DSP VST3 plugins (Archetype Nolly X, Petrucci X)
- **Scripts**:
  - `guitar-session.sh` — launch REAPER or standalone plugins with device checks
  - `setup-neuraldsp.sh` — full install of Wine, yabridge, and dependencies

See [NEURAL_DSP_LINUX_GUIDE.md](NEURAL_DSP_LINUX_GUIDE.md) for the complete setup guide.

## Development Tools

### Version Managers

- **Python**: pyenv (global: 3.12)
  - Pre-installed: s3cmd, kubernetes
- **Node.js**: nvm (auto-detects `.nvmrc`)
- **Ruby**: rvm (optional)

### Installed Tools

- **Container/K8s**: Docker, docker-compose, k9s
- **CLI Tools**: lazygit, ripgrep, fd, jq, htop
- **Cloud**: Azure CLI
- **Fonts**: Nerd Fonts (MesloLGS NF)
- **Optional**: zoxide (smart cd)

### System Packages

Media: vlc, ffmpeg, gimp, audacity, guitarix, blender, obs-studio
Power: tlp, tlp-rdw, powertop, iotop
Desktop: gnome-shell-extension-manager, chrome-gnome-shell

## File Structure & Symlinks

All configs are symlinked from this repository to home directory:

```
~/workspace/dotfiles/vim/vimrc        → ~/.vimrc
~/workspace/dotfiles/vim/             → ~/.vim
~/workspace/dotfiles/gitconfig        → ~/.gitconfig
~/workspace/dotfiles/tmux.conf        → ~/.tmux.conf
~/workspace/dotfiles/zshrc            → ~/.zshrc
~/workspace/dotfiles/nvchad/          → ~/.config/nvim (default)
~/workspace/dotfiles/ghostty/         → ~/.config/ghostty
~/workspace/dotfiles/pipewire/...     → ~/.config/pipewire/...
~/workspace/dotfiles/wireplumber/...  → ~/.config/wireplumber/...
~/workspace/dotfiles/yabridge/...     → ~/.config/yabridge/...
~/workspace/dotfiles/zshrc_imi        → ~/.zshrc_imi
```

Edit files in this repository; changes take effect immediately (except Tmux: `C-a r` to reload).

## Installation from Scratch

```bash
# Clone repository
git clone https://github.com/lordm/dotfiles.git ~/workspace/dotfiles
cd ~/workspace/dotfiles

# Review and run installer
cat install.sh  # REVIEW FIRST!
./install.sh

# Post-install
# 1. Restart terminal or source ~/.zshrc
# 2. Open Neovim (plugins auto-install)
# 3. Open Vim and run :PlugInstall
# 4. Install Tmux plugins: C-a I (capital I)
```

## Path Variables

Key paths added to `$PATH`:

- CUDA Toolkit: `/usr/local/cuda/bin`
- RVM: `~/.rvm/bin`
- Luarocks: `~/.luarocks/bin`
- Pyenv: `~/.pyenv/bin`

## Contributing

This is a personal dotfiles repository, but feel free to fork and adapt to your needs!
