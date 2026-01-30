return {
    {
        "windwp/nvim-autopairs", opts = {}
    },
    {
        "nvim-tree/nvim-web-devicons"
    },
    {
        "nvim-lualine/lualine.nvim",
        dependencies = { "nvim-tree/nvim-web-devicons", opt = true },
        config = function()
            require ("lualine").setup{
                options = { section_separators = "", component_separators = "" },
                sections = {
                    lualine_a = {
                        {
                            "mode",
                            fmt = function(str) return str:sub(1,1) end
                        }
                    },
                    lualine_b = {}, -- Git branch removed
                    lualine_c = {
                        {
                            "filename",
                            path = 1,
                        }
                    },
                    lualine_x = {"filetype"},
                    lualine_y = {},
                }

            }
        end
    },
    {
        "hrsh7th/nvim-cmp", -- Completion framework
        event = 'InsertEnter',
        dependencies = {
          "hrsh7th/cmp-buffer",   -- Buffer completions
          "hrsh7th/cmp-path",     -- Path completions
          "hrsh7th/cmp-nvim-lsp", -- LSP completions
          "L3MON4D3/LuaSnip",     -- Snippet engine
          "saadparwaiz1/cmp_luasnip", -- Snippet source
        },
        config = function()
            local cmp = require("cmp")
            local luasnip = require("luasnip")

            cmp.setup {
                snippet = {
                    expand = function(args)
                        luasnip.lsp_expand(args.body)
                    end,
                },
                mapping = cmp.mapping.preset.insert({
                    ["<Tab>"] = cmp.mapping(function(fallback)
                        if cmp.visible() then
                            cmp.confirm({ select = true })
                        else
                            fallback()
                        end
                    end, { "i", "s" }),
                    ["<Down>"] = cmp.mapping.select_next_item(),
                    ["<Up>"] = cmp.mapping.select_prev_item(),
                }),
                sources = {
                    { name = "nvim_lsp" },
                    { name = "luasnip" },
                    { name = "buffer" },
                    { name = "path" },
                },
            }
        end
    },
	--    {
	-- "rose-pine/neovim",
	-- name = "rose-pine",
	-- config = function()
	-- 	vim.cmd("colorscheme rose-pine")
	-- end
	--    },
    {
        "ellisonleao/gruvbox.nvim",
        config = function()
            vim.cmd("colorscheme gruvbox")
            vim.o.background = "dark" -- or "light" for light mode
        end
    }
}
