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

            -- Setup completion capabilities if available
            local capabilities = {}
            local has_cmp, cmp_lsp = pcall(require, "cmp_nvim_lsp")
            if has_cmp then
                capabilities = cmp_lsp.default_capabilities()
            end

            -- Set global defaults for all LSP servers
            vim.lsp.config("*", { capabilities = capabilities })

            -- Configure and enable servers using the new Neovim 0.11+ API
            for _, server in ipairs(servers) do
                local opts = {}
                if server == "eslint" then
                    opts.filetypes = { "javascript", "javascriptreact", "javascript.jsx", "vue", "svelte", "astro" }
                end
                vim.lsp.config(server, opts)
            end

            vim.lsp.enable(servers)
        end,
    },
}
