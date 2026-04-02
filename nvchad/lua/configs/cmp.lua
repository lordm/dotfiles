local cmp = require("cmp")

-- Load default NvChad cmp config styling
dofile(vim.g.base46_cache .. "cmp")

local options = {
  completion = {
    completeopt = "menu,menuone,noinsert",
  },

  window = {
    completion = cmp.config.window.bordered(),
    documentation = cmp.config.window.bordered(),
  },

  performance = {
    debounce = 150,
    throttle = 60,
    fetching_timeout = 500,
  },

  snippet = {
    expand = function(args)
      require("luasnip").lsp_expand(args.body)
    end,
  },

  mapping = {
    ["<C-p>"] = cmp.mapping.select_prev_item(),
    ["<C-n>"] = cmp.mapping.select_next_item(),
    ["<C-d>"] = cmp.mapping.scroll_docs(-4),
    ["<C-f>"] = cmp.mapping.scroll_docs(4),
    ["<C-Space>"] = cmp.mapping.complete(),
    ["<C-e>"] = cmp.mapping.close(),

    -- Enter confirms selection
    ["<CR>"] = cmp.mapping.confirm({
      behavior = cmp.ConfirmBehavior.Insert,
      select = false,
    }),

    -- Tab: select next item or expand snippet
    ["<Tab>"] = cmp.mapping(function(fallback)
      if cmp.visible() then
        cmp.select_next_item()
      elseif require("luasnip").expand_or_jumpable() then
        require("luasnip").expand_or_jump()
      else
        fallback()
      end
    end, { "i", "s" }),

    -- Shift-Tab: select previous item or jump back in snippet
    ["<S-Tab>"] = cmp.mapping(function(fallback)
      if cmp.visible() then
        cmp.select_prev_item()
      elseif require("luasnip").jumpable(-1) then
        require("luasnip").jump(-1)
      else
        fallback()
      end
    end, { "i", "s" }),
  },

  sources = cmp.config.sources({
    -- Copilot suggestions (via copilot-cmp) have high priority
    { name = "copilot", group_index = 1, priority = 100 },
    { name = "nvim_lsp", group_index = 1, priority = 90, keyword_length = 2 },
    { name = "luasnip", group_index = 1, priority = 80 },
    { name = "buffer", group_index = 2, priority = 50, keyword_length = 3 },
    { name = "nvim_lua", group_index = 2, priority = 40 },
    { name = "path", group_index = 2, priority = 30 },
  }),

  sorting = {
    priority_weight = 2,
    comparators = {
      require("copilot_cmp.comparators").prioritize,
      cmp.config.compare.offset,
      cmp.config.compare.exact,
      cmp.config.compare.score,
      cmp.config.compare.recently_used,
      cmp.config.compare.locality,
      cmp.config.compare.kind,
      cmp.config.compare.sort_text,
      cmp.config.compare.length,
      cmp.config.compare.order,
    },
  },

  formatting = {
    format = function(entry, vim_item)
      -- Icons for different sources
      local icons = {
        copilot = "",
        nvim_lsp = "",
        luasnip = "",
        buffer = "",
        path = "",
        nvim_lua = "",
      }

      -- Set icon based on source
      if icons[entry.source.name] then
        vim_item.kind = icons[entry.source.name] .. " " .. vim_item.kind
      end

      -- Add source name as menu
      vim_item.menu = ({
        copilot = "[Copilot]",
        nvim_lsp = "[LSP]",
        luasnip = "[Snippet]",
        buffer = "[Buffer]",
        path = "[Path]",
        nvim_lua = "[Lua]",
      })[entry.source.name]

      return vim_item
    end,
  },

  experimental = {
    ghost_text = true, -- Shows completion preview inline (safe with copilot-cmp)
  },
}

cmp.setup(options)

-- Command-line completion for ':'
cmp.setup.cmdline(':', {
  mapping = cmp.mapping.preset.cmdline(),
  sources = cmp.config.sources({
    { name = 'path' }
  }, {
    { name = 'cmdline' }
  }),
  matching = { disallow_symbol_nonprefix_matching = false }
})

-- Command-line completion for '/' and '?'
cmp.setup.cmdline({'/', '?'}, {
  mapping = cmp.mapping.preset.cmdline(),
  sources = {
    { name = 'buffer' }
  }
})
