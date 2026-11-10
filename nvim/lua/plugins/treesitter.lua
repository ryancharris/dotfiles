-- nvim-treesitter `main` branch (Neovim 0.12+). Parsers are compiled with
-- tree-sitter-cli (Brewfile) and a C compiler. Highlighting is Neovim's own
-- vim.treesitter.start(); this plugin installs parsers and queries.
local parsers = { "bash", "go", "gomod", "hcl", "json", "lua", "terraform", "yaml" }
local filetypes = { "sh", "bash", "go", "gomod", "hcl", "json", "lua", "terraform", "terraform-vars", "yaml" }

return {
    {
        "nvim-treesitter/nvim-treesitter",
        branch = "main",
        lazy = false,
        build = ":TSUpdate",
        config = function()
            require("nvim-treesitter").install(parsers)
            vim.api.nvim_create_autocmd("FileType", {
                pattern = filetypes,
                callback = function(args)
                    pcall(vim.treesitter.start, args.buf)
                end,
            })
        end,
    },
}
