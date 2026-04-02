# Neovim Configuration Enhancements

This document details the enhancements made to the Neovim configuration to fix conflicts, improve the debugger, and enhance the overall development experience.

## Summary of Changes

### 1. Fixed Tab Completion Conflict (Copilot + nvim-cmp)

**File Created**: `lua/configs/cmp.lua`

**Problem Solved**: Tab key conflict between Copilot suggestions and nvim-cmp autocompletion.

**Solution**:
- Integrated `copilot-cmp` as a completion source with high priority
- Configured proper source ordering: Copilot → LSP → Snippets → Buffer → Path
- Added custom comparators to prioritize Copilot suggestions
- Disabled ghost text to avoid visual conflicts
- Tab now properly cycles through completion items
- Shift-Tab navigates backward through completion items

**Key Features**:
- `<Tab>` - Select next completion item or expand snippet
- `<Shift-Tab>` - Select previous completion item or jump back in snippet
- `<CR>` - Confirm selected item (doesn't auto-select first item)
- `<C-Space>` - Manually trigger completion
- `<C-e>` - Close completion menu

---

### 2. Enhanced Debugger (DAP) Configuration

**Files Modified**:
- `lua/configs/dap.lua` (completely rewritten)
- `lua/plugins/init.lua` (DAP plugin config enhanced)

**Enhancements**:
- Added comprehensive UI layout with scopes, breakpoints, stacks, and watches
- Integrated `nvim-dap-virtual-text` for inline variable values during debugging
- Added visual breakpoint signs with icons
- Improved auto-open/close behavior of DAP UI
- Added conditional breakpoints support

**New Keymaps**:

| Keymap | Action | Description |
|--------|--------|-------------|
| `<leader>db` | Toggle Breakpoint | Set/remove breakpoint at current line |
| `<leader>dB` | Conditional Breakpoint | Set breakpoint with condition |
| `<leader>dc` | Continue/Start | Start debugging or continue to next breakpoint |
| `<leader>dC` | Run to Cursor | Run until cursor position |
| `<leader>di` | Step Into | Step into function |
| `<leader>do` | Step Over | Step over function |
| `<leader>dO` | Step Out | Step out of function |
| `<leader>dp` | Pause | Pause execution |
| `<leader>dr` | Open REPL | Open debug REPL |
| `<leader>dl` | Run Last | Re-run last debug configuration |
| `<leader>dt` | Terminate | Stop debugging session |
| `<leader>dR` | Restart | Restart debugging session |
| `<leader>du` | Toggle UI | Show/hide DAP UI |
| `<leader>de` | Eval | Evaluate expression (normal/visual) |
| `<leader>dh` | Hover | Show variable value hover |

**Python-Specific Debug Features**:
- Added pytest configuration for debugging tests
- Mason-integrated debugpy with fallback to system Python
- Python-specific debug commands:
  - `<leader>dpt` - Debug test method under cursor
  - `<leader>dpc` - Debug test class
  - `<leader>dps` - Debug selected Python code (visual mode)

---

### 3. Enhanced Testing (Neotest)

**File Modified**: `lua/configs/neotest.lua`

**Enhancements**:
- Auto-detects Python virtualenv or pyenv
- Integrated with DAP for debugging tests
- Better UI with custom icons and layouts
- Virtual text showing test status
- Watch mode for continuous testing

**New Keymaps**:

| Keymap | Action | Description |
|--------|--------|-------------|
| `<leader>tt` | Run Nearest Test | Run test under cursor |
| `<leader>tT` | Run File Tests | Run all tests in current file |
| `<leader>td` | Debug Nearest Test | Debug test under cursor (uses DAP) |
| `<leader>ta` | Run All Tests | Run all tests in project |
| `<leader>tl` | Run Last Test | Re-run last test |
| `<leader>tL` | Debug Last Test | Re-debug last test |
| `<leader>ts` | Toggle Summary | Show/hide test summary window |
| `<leader>to` | Show Output | Open test output |
| `<leader>tO` | Toggle Output Panel | Toggle output panel |
| `<leader>tx` | Stop Test | Stop running test |
| `<leader>tw` | Toggle Watch | Enable/disable watch mode |
| `[t` | Previous Failed | Jump to previous failed test |
| `]t` | Next Failed | Jump to next failed test |

---

### 4. Enhanced Formatting (Conform)

**File Modified**: `lua/configs/conform.lua`

**Enhancements**:
- Added formatters for multiple languages:
  - **Python**: ruff_format + ruff_fix
  - **JavaScript/TypeScript**: prettier
  - **HTML/CSS/JSON/YAML**: prettier
  - **Shell scripts**: shfmt
  - **Go**: gofmt + goimports
  - **Rust**: rustfmt
- Format on save enabled by default (can be toggled)
- Custom shfmt configuration (2 spaces, indent switch cases)

**New Commands**:
- `:FormatToggle` - Toggle format on save globally
- `:FormatToggleBuffer` - Toggle format on save for current buffer

**New Keymap**:
- `<leader>fm` - Manually format buffer or visual selection

---

### 5. Enhanced LSP Configuration

**File Modified**: `lua/configs/lspconfig.lua`

**Enhancements**:
- Added language servers: jsonls, yamlls, bashls, marksman
- Enhanced Python configuration (Pyright + Ruff)
- TypeScript with inlay hints
- Better diagnostic configuration with icons
- Custom on_attach with comprehensive keymaps
- Rounded borders for floating windows

**LSP Keymaps**:

| Keymap | Action | Description |
|--------|--------|-------------|
| `gD` | Go to Declaration | Jump to symbol declaration |
| `gd` | Go to Definition | Jump to symbol definition |
| `gi` | Go to Implementation | Jump to implementation |
| `gr` | Show References | List all references |
| `K` | Hover Documentation | Show hover info |
| `<leader>sh` | Signature Help | Show function signature |
| `<leader>D` | Type Definition | Go to type definition |
| `<leader>ra` | Rename | Rename symbol |
| `<leader>ca` | Code Action | Show available code actions |
| `[d` | Previous Diagnostic | Jump to previous diagnostic |
| `]d` | Next Diagnostic | Jump to next diagnostic |
| `<leader>e` | Show Diagnostic | Open diagnostic float |
| `<leader>q` | Set Loclist | Add diagnostics to location list |

**Diagnostic Signs**: ✗ (Error), ! (Warn), ⚑ (Hint), i (Info)

---

### 6. Enhanced Editor Options

**File Modified**: `lua/options.lua`

**New Options**:
- Relative line numbers enabled
- Scroll offset of 8 lines (cursor stays centered)
- Smart case-sensitive search
- Persistent undo enabled
- System clipboard integration
- No swap/backup files
- Fast completion (250ms updatetime)
- File-type specific indentation:
  - Python: 4 spaces
  - Go: tabs (4 width)
  - Markdown/Text: wrap enabled, spell check on

---

### 7. Enhanced General Mappings

**File Modified**: `lua/mappings.lua`

**New General Keymaps**:

**Editing**:
- `jk` - Exit insert mode
- `<C-s>` - Save file (works in normal, insert, visual)
- `<leader>w` - Save file
- `<leader>q` - Quit
- `<leader>Q` - Force quit all
- `Y` - Yank to end of line
- `p` (visual) - Paste without yanking

**Navigation**:
- `<C-h/j/k/l>` - Window navigation
- `<S-h/l>` - Buffer navigation (previous/next)
- `n/N` - Search results (centered)
- `<C-d/u>` - Scroll (centered)

**Window Management**:
- `<C-Up/Down/Left/Right>` - Resize windows
- `<leader>sv` - Vertical split
- `<leader>sh` - Horizontal split
- `<leader>se` - Equal split sizes
- `<leader>sx` - Close split

**Line Movement**:
- `<A-j/k>` - Move line/selection up/down (works in normal, insert, visual)

**Indentation**:
- `</>` (visual) - Indent and reselect

**Toggles**:
- `<leader>ow` - Toggle line wrap
- `<leader>on` - Toggle relative numbers
- `<leader>os` - Toggle spell check
- `<leader>nh` - Clear search highlights

**Lists**:
- `<leader>co/cc` - Open/close quickfix
- `[q/]q` - Navigate quickfix items
- `<leader>lo/lc` - Open/close location list
- `[l/]l` - Navigate location items

**Terminal**:
- `<C-x>` - Exit terminal mode

---

### 8. Updated Mason Tool Installation

**File Modified**: `lua/plugins/init.lua`

**Tools Auto-installed**:
- **Language Servers**: lua-language-server, html-lsp, css-lsp, typescript-language-server, pyright, bash-language-server, json-lsp, yaml-language-server, marksman
- **Formatters**: stylua, prettier, ruff, shfmt
- **Linters**: mypy, ruff
- **Debuggers**: debugpy

---

## Quick Reference Card

### Completion
- `<Tab>` - Next completion / expand snippet
- `<Shift-Tab>` - Previous completion / previous snippet placeholder
- `<CR>` - Confirm selection
- `<C-Space>` - Trigger completion

### Debugging
- `<leader>db` - Toggle breakpoint
- `<leader>dc` - Start/continue
- `<leader>di/o/O` - Step into/over/out
- `<leader>du` - Toggle DAP UI
- `<leader>dpt` - Debug Python test

### Testing
- `<leader>tt` - Run test
- `<leader>td` - Debug test
- `<leader>ts` - Toggle summary
- `[t/]t` - Navigate failed tests

### LSP
- `gd` - Go to definition
- `gr` - Show references
- `<leader>ra` - Rename
- `<leader>ca` - Code actions
- `[d/]d` - Navigate diagnostics

### Formatting
- `<leader>fm` - Format buffer/selection
- `:FormatToggle` - Toggle auto-format

### General
- `jk` - Exit insert mode
- `<leader>w` - Save
- `<leader>gg` - LazyGit
- `<leader>c,` - Toggle Claude Code

---

## Installation Notes

After pulling these changes:

1. Open Neovim and run `:Lazy sync` to install new plugins
2. Run `:Mason` to verify all tools are installed
3. Restart Neovim to apply all changes
4. Run `:checkhealth` to verify everything is working

## Troubleshooting

**If Copilot completion doesn't work**:
- Run `:Copilot auth` to authenticate
- Check `:Copilot status`

**If DAP doesn't work**:
- Ensure debugpy is installed: `:Mason` → find debugpy
- For Python, check virtualenv is activated

**If formatters don't work**:
- Check Mason has installed formatters: `:Mason`
- Toggle format on save: `:FormatToggle`

**If LSP doesn't start**:
- Run `:LspInfo` to see active servers
- Run `:Mason` to install missing servers
- Check `:checkhealth lspconfig`
