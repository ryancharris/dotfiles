return {
    {
        "pmizio/typescript-tools.nvim",
        dependencies = { "nvim-lua/plenary.nvim", "neovim/nvim-lspconfig" },
        opts = {},
    },
    {
        "neovim/nvim-lspconfig",
        dependencies = {
            "williamboman/mason.nvim",
            "williamboman/mason-lspconfig.nvim",
        },
        config = function()
            require("mason").setup()

            local servers = {
                "bashls", "cssls", "dockerls", "eslint", "gopls",
                "html", "jsonls", "pyright", "rust_analyzer",
                "terraformls", "yamlls"
            }

            require("mason-lspconfig").setup({
                ensure_installed = servers,
            })

            local lspconfig = require("lspconfig")

            for _, server in ipairs(servers) do
                if server == "eslint" then
                    lspconfig.eslint.setup({
                        filetypes = { "javascript", "javascriptreact", "javascript.jsx", "vue", "svelte", "astro" },
                    })
                else
                    lspconfig[server].setup({})
                end
            end
        end,
    },
}
