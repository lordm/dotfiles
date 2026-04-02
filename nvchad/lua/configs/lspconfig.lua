local on_attach = require("nvchad.configs.lspconfig").on_attach
local on_init = require("nvchad.configs.lspconfig").on_init
local capabilities = require("nvchad.configs.lspconfig").capabilities

-- Suppress lspconfig deprecation warning for nvim 0.11+
-- This filters out only the lspconfig framework warning while keeping other deprecations
local original_deprecate = vim.deprecate
vim.deprecate = function(name, alternative, version, plugin, backtrace)
  -- Suppress only the lspconfig framework deprecation warning
  if name and name:match("lspconfig") then
    return
  end
  -- Pass through all other deprecation warnings
  if original_deprecate then
    original_deprecate(name, alternative, version, plugin, backtrace)
  end
end

local lspconfig = require("lspconfig")

-- Restore original deprecate function
vim.deprecate = original_deprecate

-- Helper function to setup LSP servers (compatible with nvim 0.11+)
local function setup_server(server_name, config)
  config = config or {}
  config.on_attach = config.on_attach or custom_on_attach
  config.on_init = config.on_init or on_init
  config.capabilities = config.capabilities or capabilities

  -- Use pcall to handle any setup errors gracefully
  local ok, err = pcall(function()
    lspconfig[server_name].setup(config)
  end)

  if not ok then
    vim.notify("Failed to setup " .. server_name .. ": " .. tostring(err), vim.log.levels.WARN)
  end
end

-- Enhanced on_attach with additional keymaps
local function custom_on_attach(client, bufnr)
  -- Call NvChad's default on_attach
  on_attach(client, bufnr)

  -- Additional custom keymaps
  local map = vim.keymap.set
  local opts = { buffer = bufnr, silent = true }

  -- LSP actions
  map("n", "gD", vim.lsp.buf.declaration, vim.tbl_extend("force", opts, { desc = "LSP: Go to declaration" }))
  map("n", "gd", vim.lsp.buf.definition, vim.tbl_extend("force", opts, { desc = "LSP: Go to definition" }))
  map("n", "gi", vim.lsp.buf.implementation, vim.tbl_extend("force", opts, { desc = "LSP: Go to implementation" }))
  map("n", "gr", vim.lsp.buf.references, vim.tbl_extend("force", opts, { desc = "LSP: Show references" }))
  map("n", "K", vim.lsp.buf.hover, vim.tbl_extend("force", opts, { desc = "LSP: Hover documentation" }))
  map("n", "<leader>sh", vim.lsp.buf.signature_help, vim.tbl_extend("force", opts, { desc = "LSP: Signature help" }))
  map("n", "<leader>D", vim.lsp.buf.type_definition, vim.tbl_extend("force", opts, { desc = "LSP: Type definition" }))
  map("n", "<leader>ra", vim.lsp.buf.rename, vim.tbl_extend("force", opts, { desc = "LSP: Rename" }))
  map({ "n", "v" }, "<leader>ca", vim.lsp.buf.code_action, vim.tbl_extend("force", opts, { desc = "LSP: Code action" }))

  -- Diagnostics
  map("n", "[d", vim.diagnostic.goto_prev, vim.tbl_extend("force", opts, { desc = "LSP: Go to previous diagnostic" }))
  map("n", "]d", vim.diagnostic.goto_next, vim.tbl_extend("force", opts, { desc = "LSP: Go to next diagnostic" }))
  map("n", "<leader>e", vim.diagnostic.open_float, vim.tbl_extend("force", opts, { desc = "LSP: Show diagnostic" }))
  map("n", "<leader>q", vim.diagnostic.setloclist, vim.tbl_extend("force", opts, { desc = "LSP: Set loclist" }))
end

-- Configure diagnostics
vim.diagnostic.config({
  virtual_text = {
    prefix = "●",
    source = "if_many",
  },
  signs = true,
  underline = true,
  update_in_insert = false,
  severity_sort = true,
  float = {
    border = "rounded",
    source = "always",
    header = "",
    prefix = "",
  },
})

-- Diagnostic signs
local signs = { Error = "", Warn = "", Hint = "", Info = "" }
for type, icon in pairs(signs) do
  local hl = "DiagnosticSign" .. type
  vim.fn.sign_define(hl, { text = icon, texthl = hl, numhl = "" })
end

-- Basic servers with default config
local servers = { "html", "cssls", "jsonls", "yamlls", "bashls", "marksman" }

for _, server in ipairs(servers) do
  setup_server(server)
end

-- Python - Ruff (linting and formatting)
setup_server("ruff", {
  on_attach = function(client, bufnr)
    custom_on_attach(client, bufnr)
  end,
  init_options = {
    settings = {
      args = { "--select=ALL", "--ignore=E501,D" }, -- Ignore line length and docstrings
    },
  },
})

-- TypeScript/JavaScript
setup_server("ts_ls", {
  settings = {
    typescript = {
      inlayHints = {
        includeInlayParameterNameHints = "all",
        includeInlayParameterNameHintsWhenArgumentMatchesName = false,
        includeInlayFunctionParameterTypeHints = true,
        includeInlayVariableTypeHints = true,
        includeInlayPropertyDeclarationTypeHints = true,
        includeInlayFunctionLikeReturnTypeHints = true,
        includeInlayEnumMemberValueHints = true,
      },
    },
    javascript = {
      inlayHints = {
        includeInlayParameterNameHints = "all",
        includeInlayParameterNameHintsWhenArgumentMatchesName = false,
        includeInlayFunctionParameterTypeHints = true,
        includeInlayVariableTypeHints = true,
        includeInlayPropertyDeclarationTypeHints = true,
        includeInlayFunctionLikeReturnTypeHints = true,
        includeInlayEnumMemberValueHints = true,
      },
    },
  },
})
