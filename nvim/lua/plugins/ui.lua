return {
    {
        "windwp/nvim-autopairs", opts = {}
    },
    {
        "nvim-tree/nvim-web-devicons"
    },
    {
        "nvim-lualine/lualine.nvim",
        requires = { "nvim-tree/nvim-web-devicons", opt = true },
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
        },
        config = function()
            local cmp = require("cmp")
            cmp.setup {
                mapping = {
                    ["<C-n>"] = cmp.mapping.select_next_item(),
                    ["<C-p>"] = cmp.mapping.select_prev_item(),
                    ["<C-d>"] = cmp.mapping.scroll_docs(-4),
                    ["<C-f>"] = cmp.mapping.scroll_docs(4),
                    ["<C-Space>"] = cmp.mapping.complete(),
                    ["<C-e>"] = cmp.mapping.close(),
                    ["<CR>"] = cmp.mapping.confirm { select = true },
                },
                sources = {
                    { name = "nvim_lsp" },
                    { name = "buffer" },
                    { name = "path" },
                    { name = "avante" },
                },
            }
        end
    },
    {
	"rose-pine/neovim",
	name = "rose-pine",
	config = function()
		vim.cmd("colorscheme rose-pine")
	end
    }
}
