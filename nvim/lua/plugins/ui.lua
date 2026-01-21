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
                sources = {
                    { name = "nvim_lsp" },
                    { name = "buffer" },
                    { name = "path" },
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
