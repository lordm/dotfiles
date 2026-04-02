local neotest = require("neotest")

neotest.setup({
  adapters = {
    require("neotest-python")({
      -- Extra arguments for pytest
      args = { "--log-level=INFO", "--log-disable=py.warnings", "-v" },
      -- Use the Python from active virtualenv or pyenv
      python = function()
        local venv = vim.env.VIRTUAL_ENV
        if venv then
          return venv .. "/bin/python"
        end
        return vim.fn.exepath("python3") or vim.fn.exepath("python")
      end,
      runner = "pytest",
    }),
  },
  icons = {
    running_animated = { "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏" },
    passed = "",
    failed = "",
    skipped = "",
    running = "",
    unknown = "",
  },
  floating = {
    border = "rounded",
    max_height = 0.6,
    max_width = 0.6,
  },
  summary = {
    open = "botright vsplit | vertical resize 50",
  },
  output = {
    open_on_run = true,
  },
  quickfix = {
    enabled = true,
    open = false,
  },
  status = {
    enabled = true,
    virtual_text = true,
    signs = true,
  },
  strategies = {
    integrated = {
      width = 120,
      height = 40,
    },
  },
})

-- Keymaps
local map = vim.keymap.set

-- Running tests
map("n", "<leader>tt", function()
  neotest.run.run()
end, { desc = "Neotest: Run nearest test" })

map("n", "<leader>tT", function()
  neotest.run.run(vim.fn.expand("%"))
end, { desc = "Neotest: Run all tests in file" })

map("n", "<leader>td", function()
  neotest.run.run({ strategy = "dap" })
end, { desc = "Neotest: Debug nearest test" })

map("n", "<leader>ta", function()
  neotest.run.run(vim.fn.getcwd())
end, { desc = "Neotest: Run all tests" })

map("n", "<leader>tl", function()
  neotest.run.run_last()
end, { desc = "Neotest: Run last test" })

map("n", "<leader>tL", function()
  neotest.run.run_last({ strategy = "dap" })
end, { desc = "Neotest: Debug last test" })

-- UI controls
map("n", "<leader>ts", function()
  neotest.summary.toggle()
end, { desc = "Neotest: Toggle summary" })

map("n", "<leader>to", function()
  neotest.output.open({ enter = true, auto_close = true })
end, { desc = "Neotest: Show output" })

map("n", "<leader>tO", function()
  neotest.output_panel.toggle()
end, { desc = "Neotest: Toggle output panel" })

-- Navigation
map("n", "[t", function()
  neotest.jump.prev({ status = "failed" })
end, { desc = "Neotest: Jump to previous failed test" })

map("n", "]t", function()
  neotest.jump.next({ status = "failed" })
end, { desc = "Neotest: Jump to next failed test" })

-- Stop and attach
map("n", "<leader>tx", function()
  neotest.run.stop()
end, { desc = "Neotest: Stop nearest test" })

map("n", "<leader>tw", function()
  neotest.watch.toggle()
end, { desc = "Neotest: Toggle watch mode" })
