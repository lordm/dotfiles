require "nvchad.options"

-- Custom options
local o = vim.o
local opt = vim.opt

-- Cursor and visual
o.cursorlineopt = "both" -- Enable cursorline
o.scrolloff = 8 -- Keep 8 lines visible above/below cursor
o.sidescrolloff = 8 -- Keep 8 columns visible left/right of cursor

-- Line numbers
o.relativenumber = true -- Relative line numbers
o.numberwidth = 4 -- Width of number column

-- Indentation
o.expandtab = true -- Use spaces instead of tabs
o.shiftwidth = 2 -- Size of indent
o.tabstop = 2 -- Number of spaces per tab
o.softtabstop = 2 -- Number of spaces for tab in insert mode
o.smartindent = true -- Smart auto-indenting

-- Search
o.ignorecase = true -- Ignore case in search
o.smartcase = true -- Case-sensitive if uppercase present
o.hlsearch = true -- Highlight search results
o.incsearch = true -- Incremental search

-- Performance
o.updatetime = 250 -- Faster completion (default 4000ms)
o.timeoutlen = 300 -- Time to wait for mapped sequence
o.lazyredraw = false -- Don't redraw while executing macros

-- Completion
opt.completeopt = { "menu", "menuone", "noinsert" }

-- Splits
o.splitbelow = true -- Open horizontal splits below
o.splitright = true -- Open vertical splits to the right

-- File handling
o.undofile = true -- Persistent undo
o.backup = false -- No backup files
o.writebackup = false -- No backup before overwriting
o.swapfile = false -- No swap files

-- Display
o.conceallevel = 0 -- Don't hide special characters (useful for markdown)
o.wrap = false -- No line wrapping by default
o.linebreak = true -- Break lines at word boundaries
o.showmode = false -- Don't show mode (already in statusline)
o.signcolumn = "yes" -- Always show sign column

-- Mouse
o.mouse = "a" -- Enable mouse in all modes

-- Clipboard (classic vim behavior - use "+y to copy to system clipboard)
-- opt.clipboard = "unnamedplus"

-- Filetype-specific settings
vim.api.nvim_create_autocmd("FileType", {
  pattern = { "python" },
  callback = function()
    vim.opt_local.tabstop = 4
    vim.opt_local.shiftwidth = 4
    vim.opt_local.softtabstop = 4
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "go" },
  callback = function()
    vim.opt_local.expandtab = false
    vim.opt_local.tabstop = 4
    vim.opt_local.shiftwidth = 4
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "markdown", "text" },
  callback = function()
    vim.opt_local.wrap = true
    vim.opt_local.spell = true
  end,
})
