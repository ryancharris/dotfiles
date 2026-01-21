return {
    {
        "linrongbin16/gitlinker.nvim",
        config = function()
            require('gitlinker').setup()
        end
    },
    {
        "lewis6991/gitsigns.nvim",
        config = function()
            require("gitsigns").setup{
                current_line_blame = true,
            }
        end
    }
}
