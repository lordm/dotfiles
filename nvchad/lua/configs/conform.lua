local options = {
  formatters_by_ft = {
    -- Lua
    lua = { "stylua" },

    -- Web development
    javascript = { "prettier" },
    typescript = { "prettier" },
    javascriptreact = { "prettier" },
    typescriptreact = { "prettier" },
    css = { "prettier" },
    scss = { "prettier" },
    html = { "prettier" },
    json = { "prettier" },
    jsonc = { "prettier" },
    yaml = { "prettier" },
    markdown = { "prettier" },

    -- Python
    python = { "ruff_format", "ruff_fix" },

    -- Shell
    sh = { "shfmt" },
    bash = { "shfmt" },
    zsh = { "shfmt" },

    -- Other
    go = { "gofmt", "goimports" },
    rust = { "rustfmt" },
  },

  -- Format on save (optional - uncomment to enable)
  format_on_save = function(bufnr)
    -- Disable with a global or buffer-local variable
    if vim.g.disable_autoformat or vim.b[bufnr].disable_autoformat then
      return
    end
    return {
      timeout_ms = 1000,
      lsp_fallback = true,
    }
  end,

  formatters = {
    shfmt = {
      prepend_args = { "-i", "2", "-ci" }, -- 2 spaces, indent switch cases
    },
  },
}

require("conform").setup(options)

-- Create commands to toggle format on save
vim.api.nvim_create_user_command("FormatToggle", function()
  if vim.g.disable_autoformat then
    vim.g.disable_autoformat = false
    print("Format on save enabled")
  else
    vim.g.disable_autoformat = true
    print("Format on save disabled")
  end
end, {
  desc = "Toggle format on save globally",
})

vim.api.nvim_create_user_command("FormatToggleBuffer", function()
  if vim.b.disable_autoformat then
    vim.b.disable_autoformat = false
    print("Format on save enabled for current buffer")
  else
    vim.b.disable_autoformat = true
    print("Format on save disabled for current buffer")
  end
end, {
  desc = "Toggle format on save for current buffer",
})

-- Manual format keymap
vim.keymap.set({ "n", "v" }, "<leader>fm", function()
  require("conform").format({
    lsp_fallback = true,
    async = false,
    timeout_ms = 1000,
  })
end, { desc = "Format buffer or range" })
