return {
  {
    "coder/claudecode.nvim",
    dependencies = { "folke/snacks.nvim" },
    opts = {
      git_repo_cwd = true,
    },
    keys = {
      { "<leader>ap", "<cmd>ClaudeCode<cr>", mode = { "n", "v" }, desc = "Toggle Claude" },
      { "<leader>aP", "<cmd>ClaudeCode --continue<cr>", mode = { "n", "v" }, desc = "Continue Claude" },
      { "<leader>ar", "<cmd>ClaudeCode --resume<cr>", mode = { "n", "v" }, desc = "Resume Claude" },

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
