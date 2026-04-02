# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal dotfiles repository for setting up a complete development environment on Debian-based Linux systems (Ubuntu). It contains configurations for Zsh, Tmux, Git, Neovim, and Vim, with automated installation through `install.sh`.

## Installation and Setup

### Initial Setup
```bash
./install.sh
```

**Important**: Always review `install.sh` before running. The script:
- Installs system packages (Docker, lazygit, k9s, nvm, pyenv, etc.)
- Backs up existing dotfiles to `~/*_old` or `~/*.old`
- Creates symlinks from home directory to this repo's files
- Installs Oh My Zsh, Nerd Fonts, and development tools

### Post-Installation Steps
- **Vim**: Open vim and run `:PlugInstall`
- **Neovim**: Plugins auto-install on first launch (managed by lazy.nvim)
- **Tmux**: Plugins are managed by TPM (Tmux Plugin Manager)

## Configuration Architecture

### Neovim (Primary Editor)
- **Framework**: NvChad v2.5
- **Plugin Manager**: lazy.nvim
- **Structure**:
  - `nvim/init.lua`: Entry point, bootstraps lazy.nvim and loads NvChad
  - `nvim/lua/chadrc.lua`: User overrides (theme: tokyonight, nvdash settings)
  - `nvim/lua/plugins/init.lua`: Custom plugin configurations
  - `nvim/lua/configs/`: Individual plugin config files

**Key Plugins**:
- LSP: pyright, html-lsp, css-lsp, ts_ls (TypeScript), ruff (Python linting)
- Debugging: nvim-dap, nvim-dap-python, nvim-dap-ui
- Testing: neotest with neotest-python
- Git: lazygit.nvim (keybind: `<leader>gg`)
- AI: copilot.lua + copilot-cmp, claude-code.nvim
- Formatting: conform.nvim, prettier

**LSP Servers** (nvim/lua/configs/lspconfig.lua:6):
- HTML, CSS, Python (pyright), TypeScript (ts_ls), Ruff

**Adding New Plugins**: Add to `nvim/lua/plugins/init.lua` following the lazy.nvim spec format.

### Vim (Legacy)
- **Plugin Manager**: vim-plug
- **Config**: `vim/vimrc`
- **Notable Plugins**: YouCompleteMe, ALE, NERDTree, Fugitive, Ctrlp

### Zsh
- **Framework**: Oh My Zsh (theme: robbyrussell)
- **Config**: `zshrc`
- **Plugins**: git, catimg, rvm, ruby, python, pip, node, ng, npm, command-time

**Key Features**:
- Vim keybindings (`bindkey -v`)
- Auto-switches Node.js versions based on `.nvmrc` (zshrc:103-119)
- Pyenv integration for Python version management
- Custom aliases: `dose` (docker compose), `tmux` (tmux -2)
- Claude Code aliases:
  - `claude-phi`: Personal Claude config
  - `claude-imi`: Work Claude config with Bedrock

**Auto-loading**: Conditionally sources `~/.zshrc_imi` if present (zshrc:152-155)

### Tmux
- **Config**: `tmux.conf`
- **Prefix**: `C-a` (screen-like binding, not default `C-b`)
- **Keybindings**: Vim-style pane navigation (h/j/k/l)
- **Plugins** (via TPM):
  - tmux-sensible
  - tmux-resurrect (session restoration)
  - tmux-continuum (auto-save: enabled)
- **Splits**: `|` for horizontal, `-` for vertical (preserves current path)

### Git
- **Config**: `gitconfig`
- **Editor**: nvim
- **Signing**: SSH key signing (gitconfig:4, 51-52)

**Useful Aliases**:
- `git lg`: Formatted graph log with colors
- `git cleanup`: Delete merged branches (excludes 'main')
- `git nuke <branch>`: Delete local + remote branch
- `git co`, `git ci -m`, `git st`, `git df`, `git br`

## Development Workflow

### Modifying Configurations
All config files are symlinked from this repo to home directory. Edit files in this repo, changes take effect immediately (except tmux: use `C-a r` to reload).

### Symlink Structure (install.sh:78-86)
- `vim/vimrc` → `~/.vimrc`
- `vim/` → `~/.vim`
- `gitconfig` → `~/.gitconfig`
- `tmux.conf` → `~/.tmux.conf`
- `zshrc` → `~/.zshrc`
- `nvim/` → `~/.config/nvim`

### Version Managers
- **Node.js**: nvm (auto-detects `.nvmrc` files)
- **Python**: pyenv (global: 3.12)
- **Ruby**: rvm (optional)

### Docker
Installed via script with user added to docker group. Use `dose` alias for `docker compose`.

## Technology Stack

- **Shell**: Zsh + Oh My Zsh
- **Terminal Multiplexer**: Tmux with vim-style keybindings
- **Editors**: Neovim (NvChad), Vim (vim-plug)
- **Version Control**: Git with SSH signing
- **Containers**: Docker + Docker Compose
- **Languages**: Python (pyenv), Node.js (nvm), Ruby (rvm)
- **Tools**: lazygit, k9s (Kubernetes), Azure CLI

## Special Configurations

### Claude Code Integration
Neovim has `claude-code.nvim` plugin with custom keybinds (nvim/lua/plugins/init.lua:111-148):
- Toggle: `<leader>c,` (normal), `<C-,>` (terminal)
- Variants: `<leader>cC` (continue), `<leader>cV` (verbose)
- Auto-refresh enabled with git root detection

### Python Debugging
Configured nvim-dap-python using Mason-installed debugpy (nvim/lua/plugins/init.lua:55-62).

### Testing
Neotest configured for Python testing (nvim/lua/configs/neotest.lua).

## Path Variables
Key paths added in zshrc:
- CUDA Toolkit: `/usr/local/cuda/bin`
- RVM: `~/.rvm/bin`
- Luarocks: `~/.luarocks/bin`
- Pyenv: `~/.pyenv/bin`
