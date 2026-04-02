return {
  {
    "coder/claudecode.nvim",
    dependencies = { "folke/snacks.nvim" },
    opts = function()
      local home = vim.fn.expand("~")
      return {
        terminal_cmd = "env CLAUDE_CONFIG_DIR=" .. home .. "/.config/claude-personal claude",
        git_repo_cwd = true,
      }
    end,
    config = function(_, opts)
      require("claudecode").setup(opts)

      -- Custom commands for different Claude configs
      vim.api.nvim_create_user_command("ClaudePersonal", function(cmd_opts)
        local args = cmd_opts.args ~= "" and " " .. cmd_opts.args or ""
        vim.cmd("ClaudeCode" .. args)
      end, { nargs = "*", desc = "Toggle Claude (Personal)" })

      vim.api.nvim_create_user_command("ClaudeWork", function(cmd_opts)
        -- Temporarily change terminal_cmd for this session
        local home = vim.fn.expand("~")
        local original_cmd = require("claudecode.config").opts.terminal_cmd
        require("claudecode.config").opts.terminal_cmd = "env CLAUDE_CONFIG_DIR=" .. home .. "/.config/claude-imi claude"

        local args = cmd_opts.args ~= "" and " " .. cmd_opts.args or ""
        vim.cmd("ClaudeCode" .. args)

        -- Restore original command
        vim.schedule(function()
          require("claudecode.config").opts.terminal_cmd = original_cmd
        end)
      end, { nargs = "*", desc = "Toggle Claude (Work)" })
    end,
    keys = {
      -- Personal Claude (claude-phi) keymaps
      { "<leader>ap", "<cmd>ClaudePersonal<cr>", mode = { "n", "v" }, desc = "Toggle Claude (Personal)" },
      { "<leader>aP", "<cmd>ClaudePersonal --continue<cr>", mode = { "n", "v" }, desc = "Continue Claude (Personal)" },
      { "<leader>ar", "<cmd>ClaudePersonal --resume<cr>", mode = { "n", "v" }, desc = "Resume Claude (Personal)" },

      -- Work Claude (claude-imi) keymaps
      { "<leader>aw", "<cmd>ClaudeWork<cr>", mode = { "n", "v" }, desc = "Toggle Claude (Work)" },
      { "<leader>aW", "<cmd>ClaudeWork --continue<cr>", mode = { "n", "v" }, desc = "Continue Claude (Work)" },
      { "<leader>aR", "<cmd>ClaudeWork --resume<cr>", mode = { "n", "v" }, desc = "Resume Claude (Work)" },

      -- Generic toggle (uses default from opts)
      -- { "<leader>cc", "<cmd>ClaudeCode<cr>", mode = { "n", "v" }, desc = "Toggle Claude (Default)" },
      -- { "<leader>cC", "<cmd>ClaudeCode --continue<cr>", mode = { "n", "v" }, desc = "Continue Claude (Default)" },

      -- Terminal mode bindings
      { "<C-,>", "<cmd>ClaudeCodeFocus<cr>", mode = "t", desc = "Focus Claude" },

      -- Diff management
      -- { "<leader>ca", "<cmd>ClaudeCodeDiffAccept<cr>", desc = "Accept Claude diff" },
      -- { "<leader>cd", "<cmd>ClaudeCodeDiffDeny<cr>", desc = "Deny Claude diff" },

      -- Other commands
      -- { "<leader>cf", "<cmd>ClaudeCodeFocus<cr>", desc = "Focus Claude" },
      { "<leader>am", "<cmd>ClaudeCodeSelectModel<cr>", desc = "Select Claude model" },
      -- { "<leader>ab", "<cmd>ClaudeCodeAdd %<cr>", desc = "Add current buffer" },
      { "<leader>as", "<cmd>ClaudeCodeSend<cr>", mode = "v", desc = "Send to Claude" },
    },
  },
}
