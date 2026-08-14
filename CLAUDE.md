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
- Auto-switches Node.js versions based on `.nvmrc` (zshrc:76-99)
- Pyenv integration for Python version management
- Custom aliases: `dose` (docker compose), `tmux` (tmux -2)

**Auto-loading**: Conditionally sources `~/.zshrc_imi` if present (zshrc:138-141)

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
Both Neovim configs launch plain `claude` — there is no `CLAUDE_CONFIG_DIR` override anywhere,
so they use the default config at `~/.claude`.

LazyVim (the active config) uses `coder/claudecode.nvim` (lazyvim/lua/plugins/claudecode.lua):
- Toggle: `<leader>ap`, continue: `<leader>aP`, resume: `<leader>ar`
- Focus: `<C-,>` (terminal), select model: `<leader>am`, send selection: `<leader>as` (visual)

NvChad uses `greggh/claude-code.nvim` (nvchad/lua/plugins/init.lua:211-250):
- Toggle: `<leader>c,` (normal), `<C-,>` (terminal)
- Variants: `<leader>cC` (continue), `<leader>cV` (verbose)
- Auto-refresh enabled with git root detection

### Python Debugging
Configured nvim-dap-python using Mason-installed debugpy (nvim/lua/plugins/init.lua:55-62).

### Testing
Neotest configured for Python testing (nvim/lua/configs/neotest.lua).

### Power Management (hibernate, not suspend)
`scripts/setup-hibernate.sh` makes the laptop hibernate rather than suspend when it is on
battery, so a power cut doesn't cost the session. Run it manually — `install.sh` only
symlinks it, since it needs sudo and is a one-time system tweak.

It changes two things, neither of which lives in this repo:
- `/etc/UPower/UPower.conf`: `CriticalPowerAction=Hibernate` (was `HybridSleep`, which
  writes an image but stays in S3 and keeps draining until it dies mid-suspend), and
  thresholds `PercentageLow/Critical/Action=20/10/5` (was `20/5/2` — 2% is thin margin
  for a multi-second image write).
- dconf: `org.gnome.settings-daemon.plugins.power lid-close-battery-action=hibernate`.
  AC is deliberately left on `suspend`.

Gotchas worth knowing before changing any of this:
- **gsd-power holds the logind `handle-lid-switch` inhibitor**, so `/etc/systemd/logind.conf`
  is inert on this machine. gsettings is the only effective lid knob under GNOME.
- **`suspend-then-hibernate` is not available per-power-source here.** GNOME's action enum
  doesn't include it, and systemd 255 lacks `HibernateOnACPower=` (added in 256) to scope
  it to battery. Hence immediate hibernate on lid close, at the cost of instant wake.
- **Swap (14.9G) is smaller than RAM (31G).** The kernel caps the image at
  `/sys/power/image_size` (2/5 of RAM ≈ 11.6 GiB) so it works in practice, but hibernation
  fails if active memory ever exceeds that cap. The script warns rather than fails.
- NVIDIA needs `NVreg_PreserveVideoMemoryAllocations=1` (already set in
  `/etc/modprobe.d/nvidia-graphics-drivers-kms.conf`) or resume comes back with a
  corrupted display.

## Path Variables
Key paths added in zshrc:
- CUDA Toolkit: `/usr/local/cuda/bin`
- RVM: `~/.rvm/bin`
- Luarocks: `~/.luarocks/bin`
- Pyenv: `~/.pyenv/bin`
