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
- `scripts/` → `~/scripts` (the whole directory, so a new script is usable the
  moment it lands in the repo — this was per-file links, and forgetting to add
  one left tmux running a path that did not exist, which fails silently)

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

### Agent TTS (spoken responses)
`tts/` narrates Claude Code and Codex output through Kokoro, a local ONNX model — no
network calls at runtime. A warm daemon (`tts/ttsd.py`) holds the model behind a Unix
socket (`$XDG_RUNTIME_DIR/tts.sock`) so no turn pays model-load cost; hook adapters in
`tts/hooks/` extract text from each harness's payload and hand it to `tts/client.py`'s
`send()`, which is non-blocking by default (~18ms measured) — it autostarts the daemon
and retries once immediately, never waits. `wait=True` exists only so the interactive
CLI (`tts/tts`) can poll out a cold start; a hook must never pass it.

Run `scripts/setup-tts.sh` manually — `install.sh` only symlinks `tts/config.toml` and
the `tts` CLI, since setup pulls ~353MB (`kokoro-v1.0.onnx` 325MB, `voices-v1.0.bin`
28MB), installs `tts.service` as a systemd user unit, and merges the hook fragments
into `~/.claude/settings.json` and `~/.codex/config.toml` (see the gotcha below). Measured synthesis speed on
this machine is RTF 0.41 — comfortably faster than realtime. The daemon holds steady
at roughly 830MB RSS once it has synthesized at least once; a reading taken right
after the service starts (before the ONNX session has actually run) reads far lower
and is not the number to trust.

Control it with `tts stop` (aliased `shh`), `tts toggle` (aliased `tts-off`), `tts
status`, or the tmux bindings `prefix + S` (stop) and `prefix + T` (toggle).

The tmux status line shows the state as a single Material Design Nerd Font glyph
via `scripts/tmux-tts-status.sh`: `󰕾` idle (grey) or speaking (gold), `󰖁` muted
(grey), `󰀦` no daemon (gold). Grey is a resting state, gold means something wants
noticing. It always draws exactly one glyph, and sits at the left of
`status-right` — that block is right-aligned, so a variable-width segment there
would drag the load figures sideways on every state change.

Gotchas worth knowing before changing any of this:
- **`tts/paths.py` is a stdlib-only leaf module.** It holds `socket_path()` and
  `share_dir()`, pulled out of `tts/ttsd.py` so the CLI and both hook adapters never
  transitively import numpy. They run under a bare `python3`, not the venv
  `scripts/setup-tts.sh` builds — importing `tts.ttsd` from them (which imports
  `tts.engine`, which imports numpy at module scope) would crash on any machine that
  followed the documented install. Don't fold it back into `ttsd.py`.
- **Model and venv locations honor `$XDG_DATA_HOME`**, with `$TTS_MODEL_DIR`
  overriding just the model directory. `scripts/setup-tts.sh`, `tts/engine.py`, and
  `tts/ttsd.py` all resolve it the same way so a bootstrap run and the running daemon
  never disagree about where the models live.
- **The model download is atomic.** `scripts/setup-tts.sh` fetches each file to a
  `.part` sidecar and only `mv`s it into place on success, so a run that dies
  mid-download never leaves a truncated file that a later run mistakes for complete.
- **paplay is retired, not killed, at the end of an utterance.** `write()` returns
  as soon as the pipe accepts the bytes, so audio is still playing when the queue
  drains — `_retire_playback` closes stdin and `wait()`s, on the worker thread and
  never under the lock. Killing there instead would truncate the tail of every
  utterance; not retiring at all (the original bug) leaves a paplay alive forever
  holding the output sink open, which on this machine meant an audio interface
  stuck in RUNNING and drawing power with nothing to say. `kill()` stays the
  interruption path and must stay immediate.
- **The socket accept loop must never wait on a subprocess.** An AF_UNIX
  `connect()` to a full backlog blocks rather than being refused, so a stalled
  accept loop reaches back through `listen(16)` into the agent whose hook is
  connecting. The tmux focus query and `notify-send` therefore live on the intake
  thread, and `notify()` is spawned and forgotten. Commands (`stop`, `toggle`) stay
  on the accept thread on purpose — a stop queued behind an utterance is not a stop.
- **A stop carries an epoch, because the intake queue can otherwise outrun it.**
  Answering `stop` on the accept thread while `handle()` runs on the intake thread
  means an utterance that arrived *before* the stop can queue its audio *after* it
  and start talking. `_cancel_pending()` bumps `_stop_epoch` and drains the intake
  queue; `handle()` snapshots the epoch before the focus query and re-checks it
  under the lock before queueing a sentence. Only an explicit stop or mute does
  this — the "newest utterance wins" path must not, since messages queued behind
  an utterance are newer than it and dropping them would lose the awaited turn.
- **`[events]` in `config.toml` gates the four wired events**, keyed on
  `(source, kind)` from the hook payload. Off means neither spoken nor sent to
  `notify-send`. Everything defaults to on, and `load_config` discards unknown or
  non-boolean keys with a warning rather than letting a typo silence an event.
- **Only the focused pane speaks.** The active pane of an attached tmux session
  narrates; everything else falls back to `notify-send`. Sessions with no
  `$TMUX_PANE` at all — the desktop app, editor integrations — are treated as
  focused and always speak.
- **Terminal window focus is not checked.** Wayland has no reliable unprivileged
  query for it, so alt-tabbing to a browser does not stop narration. This is
  deliberate.
- **The status line must never ask the daemon anything.** `scripts/tmux-tts-status.sh`
  runs on every tmux status tick *and* twice per utterance, so it is bash builtins
  only — it stats files the daemon maintains (`$XDG_RUNTIME_DIR/tts.pid`,
  `tts.speaking`, and the `muted` flag) rather than forking `tts status`, which
  would spawn a Python interpreter and round-trip the socket. `tts/paths.py` owns
  those locations and the script mirrors it; change one and you must change both.
- **Liveness is the pid file, not the socket.** An AF_UNIX socket file outlives
  the process that bound it, and the daemon installs no SIGTERM handler, so
  `systemctl stop tts.service` leaves `tts.sock` on disk and `serve()`'s `finally`
  never runs. A `[ -S ]` test therefore called a stopped daemon "running" — that
  was a real bug in the first version of the indicator. `/proc/<pid>` is the only
  honest check. The same missing handler is why the speaking flag is cleared
  unconditionally at startup: that, not shutdown, is where the cleanup can run.
- **The daemon pushes the status line; it does not wait to be polled.**
  `poke_status_line()` runs `tmux refresh-client -S` fire-and-forget on each
  speaking transition, because a 5-second `status-interval` is longer than many
  utterances and the icon would otherwise light up after the speech had finished.
  A forced refresh genuinely re-executes `#()` jobs rather than redrawing cached
  output (measured: ~5ms). It is spawned and forgotten exactly like `notify()`,
  since it is called from the worker thread and, on an interruption, from the
  accept thread — which may never wait on a subprocess.
- **The speaking flag is written outside `_lock`, under its own `_flag_lock`.**
  The module's rule is that no I/O happens under `_lock`, but a bare read-then-write
  would let a stop racing a claim leave the flag inverted. `_flag_lock` serialises
  the pair and takes `_lock` inside itself, never the reverse.
- **Status-bar icons come from the Material Design (Plane 15) range, not FontAwesome.**
  Ghostty's configured font is plain JetBrains Mono, so these resolve through
  fontconfig fallback. The `U+F0xx` FontAwesome codepoints are also claimed by
  Webdings and some legacy CJK fonts, where fallback can draw a *wrong* glyph
  instead of an obvious missing-glyph box; the `U+F0xxx` Material Design ones
  resolve to exactly one installed font (`UbuntuMono Nerd Font`) and are patched
  to single-cell width, so the status-right column budget still holds.
- **Hook adapters exit zero on every failure path.** A dead daemon or missing model
  must never break a turn. That also means failures are silent — debug by piping a
  payload into the adapter by hand.
- **Codex's `PermissionRequest` payload has no `reason` field.** The adapter keys on
  `tool_name` instead, confirmed against the machine-generated JSON Schema fixtures
  for `rust-v0.151.0` — codex-cli's own generated schema, not a guess from binary
  strings. `reason` only exists on hook *output* structs, never on this input
  payload; don't "fix" the adapter back to preferring it.
- **Codex hooks need trusting by hash.** After changing `tts/codex-hooks.toml` and
  re-merging, approve them again via `/hooks` in the Codex TUI.
- **The harness configs are merged, not symlinked.** `~/.claude/settings.json` and
  `~/.codex/config.toml` hold live machine state — including, on this machine,
  work-project paths that must never enter this public repo — so the repo keeps the
  canonical fragments (`tts/claude-hooks.json`, `tts/codex-hooks.toml`) and
  `scripts/setup-tts.sh` merges them in: `jq` keyed on the hook command for the
  JSON, a `# >>> agent-tts >>>` marked block for the TOML. Both back the file up
  first, both parse the result before letting it land, and both are no-ops on a
  re-run — a hook is identified by its command string, so nothing is ever
  duplicated and nothing the user configured themselves is replaced. Sourcing the
  script with `TTS_SETUP_LIB=1` defines the merge helpers without running the
  install, which is how `tts/tests/test_setup_hooks.py` exercises them against a
  scratch `HOME`.

## Path Variables
Key paths added in zshrc:
- CUDA Toolkit: `/usr/local/cuda/bin`
- RVM: `~/.rvm/bin`
- Luarocks: `~/.luarocks/bin`
- Pyenv: `~/.pyenv/bin`
