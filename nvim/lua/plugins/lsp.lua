return {
    {
        "pmizio/typescript-tools.nvim",
        dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig" },
        opts = {},
    },
    {
        "williamboman/mason.nvim",
        opts = {},
    },
    {
        "williamboman/mason-lspconfig.nvim",
        opts = {
            ensure_installed = {
                "bashls", "cssls", "dockerls", "eslint", "gopls",
                "html", "jsonls", "pyright", "rust_analyzer",
                "terraformls", "yamlls"
            },
        },
    },
    {
        "neovim/nvim-lspconfig",
        config = function()
            local lspconfig = require("lspconfig")
            local mason_lspconfig = require("mason-lspconfig")

            -- Standard setup for all servers installed via Mason
            mason_lspconfig.setup_handlers({
                -- The default handler: setup with default settings
                function(server_name)
                    lspconfig[server_name].setup({})
                end,

                -- Custom handler for 'eslint'
                ["eslint"] = function()
                    lspconfig.eslint.setup({
                        filetypes = { "javascript", "javascriptreact", "javascript.jsx", "vue", "svelte", "astro" },
                    })
                end,
            })
        end,
    },
}