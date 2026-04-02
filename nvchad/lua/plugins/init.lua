return {
  {
    "stevearc/conform.nvim",
    -- event = 'BufWritePre', -- uncomment for format on save
    config = function()
      require "configs.conform"
    end,
  },

  -- These are some examples, uncomment them if you want to see them work!
  {
    "neovim/nvim-lspconfig",
    config = function()
      require("nvchad.configs.lspconfig").defaults()
      require "configs.lspconfig"
    end,
  },
  --
  {
  	"williamboman/mason.nvim",
  	opts = {
  		ensure_installed = {
        -- Lua
  			"lua-language-server",
        "stylua",

        -- Web
  			"html-lsp",
        "css-lsp",
        "typescript-language-server",
        "prettier",

        -- Python
        "mypy",
        "ruff",
        "debugpy",

        -- Shell
        "bash-language-server",
        "shfmt",

        -- Other useful tools
        "json-lsp",
        "yaml-language-server",
        "marksman", -- Markdown LSP
  		},
  	},
  },
  --
  {
  	"nvim-treesitter/nvim-treesitter",
  	opts = {
  		ensure_installed = {
  			"vim", "lua", "vimdoc",
        "cpp", "python",
        "html", "css",
        "yaml", "dockerfile",
        "json", "proto",
  		},
  	},
  },

  -- Debugging
  {
    "mfussenegger/nvim-dap",
    dependencies = {
      "rcarriga/nvim-dap-ui",
      "nvim-neotest/nvim-nio",
      "theHamsta/nvim-dap-virtual-text",
    },
    config = function()
      require("configs.dap")
      -- Enable virtual text
      require("nvim-dap-virtual-text").setup({
        enabled = true,
        enabled_commands = true,
        highlight_changed_variables = true,
        highlight_new_as_changed = false,
        show_stop_reason = true,
        commented = false,
        only_first_definition = true,
        all_references = false,
        filter_references_pattern = "<module",
        virt_text_pos = "eol",
        all_frames = false,
        virt_lines = false,
        virt_text_win_col = nil,
      })
    end,
  },

  -- Python debugging
  {
    "mfussenegger/nvim-dap-python",
    ft = "python",
    dependencies = { "mfussenegger/nvim-dap", "williamboman/mason.nvim" },
    config = function()
      -- Use Mason-installed debugpy
      local mason_registry_ok, mason_registry = pcall(require, "mason-registry")
      if mason_registry_ok then
        local debugpy_path = mason_registry.get_package("debugpy"):get_install_path()
        require("dap-python").setup(debugpy_path .. "/venv/bin/python")
      else
        -- Fallback to system python
        require("dap-python").setup("python3")
      end

      -- Add pytest test runner
      table.insert(require("dap").configurations.python, {
        type = "python",
        request = "launch",
        name = "pytest: Current File",
        module = "pytest",
        args = { "${file}", "-v", "-s" },
        console = "integratedTerminal",
      })

      -- Keymaps for Python debugging
      vim.keymap.set("n", "<leader>dpt", function()
        require("dap-python").test_method()
      end, { desc = "DAP Python: Test Method" })

      vim.keymap.set("n", "<leader>dpc", function()
        require("dap-python").test_class()
      end, { desc = "DAP Python: Test Class" })

      vim.keymap.set("v", "<leader>dps", function()
        require("dap-python").debug_selection()
      end, { desc = "DAP Python: Debug Selection" })
    end,
  },

  {
    "nvim-neotest/neotest",
    dependencies = {
      "nvim-neotest/neotest-python"
    },
    config = function ()
      require("configs.neotest")
    end
  },

  {
    "kdheepak/lazygit.nvim",
    cmd = {
      "LazyGit",
      "LazyGitConfig",
      "LazyGitCurrentFile",
      "LazyGitFilter",
      "LazyGitFilterCurrentFile",
    },
    -- optional for floating window border decoration
    dependencies = {
      "nvim-lua/plenary.nvim",
    },
    -- setting the keybinding for LazyGit with 'keys' is recommended in
    -- order to load the plugin when the command is run for the first time
    keys = {
      { "<leader>gg", "<cmd>LazyGit<cr>", desc = "LazyGit" }
    }
  },
  -- Completion configuration
  {
    "hrsh7th/nvim-cmp",
    event = "InsertEnter",
    dependencies = {
      "hrsh7th/cmp-nvim-lsp",
      "hrsh7th/cmp-buffer",
      "hrsh7th/cmp-path",
      "hrsh7th/cmp-cmdline",
      "saadparwaiz1/cmp_luasnip",
      "zbirenbaum/copilot-cmp",
    },
    config = function()
      require("configs.cmp")
    end,
  },

  -- Copilot setup (must load before copilot-cmp)
  {
    "zbirenbaum/copilot.lua",
    cmd = "Copilot",
    event = "InsertEnter",
    config = function()
      require("copilot").setup({
        panel = { enabled = false }, -- Use cmp instead
        suggestion = { enabled = false }, -- Use cmp instead
        filetypes = {
          yaml = true,
          markdown = true,
          help = false,
          gitcommit = true,
          gitrebase = false,
          hgcommit = false,
          svn = false,
          cvs = false,
          ["."] = false,
        },
      })
    end,
  },

  -- Copilot completion source
  {
    "zbirenbaum/copilot-cmp",
    dependencies = { "zbirenbaum/copilot.lua" },
    config = function()
      require("copilot_cmp").setup()
    end,
  },
  {
    "greggh/claude-code.nvim",
    lazy = false,
    dependencies = {
      "nvim-lua/plenary.nvim",
    },
    config = function()
      require("claude-code").setup({
        window = {
          split_ratio = 0.3,
          position = "botright",
          enter_insert = true,
          hide_numbers = true,
          hide_signcolumn = true,
        },
        refresh = {
          enable = true,
          updatetime = 100,
          timer_interval = 1000,
          show_notifications = true,
        },
        git = {
          use_git_root = true,
        },
        command = "claude-imi",
        keymaps = {
          toggle = {
            normal = "<leader>c,",
            terminal = "<C-,>",
            variants = {
              continue = "<leader>cC",
              verbose = "<leader>cV",
            },
          },
          window_navigation = true,
          scrolling = true,
        }
      })
    end
  },
}
