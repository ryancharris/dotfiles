return {
    {
        "tpope/vim-sleuth"
    },
    {
        "ibhagwan/fzf-lua",
        dependencies = { "nvim-tree/nvim-web-devicons" },
        opts = {
            winopts = {
                preview = {
                    layout = "vertical",
                }
            }
        }
    },
    {
        "lukas-reineke/indent-blankline.nvim",
        main = "ibl",
        opts = {}
    }
}
