return {
    {
        "windwp/nvim-autopairs", opts = {}
    },
    {
        "nvim-tree/nvim-web-devicons"
    },
    {
        "ellisonleao/gruvbox.nvim",
        config = function()
            require("gruvbox").setup {
                contrast = "hard", -- can be "hard", "soft" or empty string
            }
            vim.cmd("colorscheme gruvbox")
        end
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
}
