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
            "b0o/schemastore.nvim",
        },
        config = function()
            require("mason").setup()

            local servers = {
                "bashls", "cssls", "dockerls", "eslint", "gopls",
                "helm_ls", "html", "jsonls", "pyright", "rust_analyzer",
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
            local has_schemastore, schemastore = pcall(require, "schemastore")

            for _, server in ipairs(servers) do
                local opts = {}
                if server == "eslint" then
                    opts.filetypes = { "javascript", "javascriptreact", "javascript.jsx", "typescript", "typescriptreact", "typescript.tsx", "vue", "svelte", "astro" }
                elseif server == "yamlls" and has_schemastore then
                    -- Helm templates are detected as filetype "helm" (config/filetype.lua)
                    -- and served by helm_ls instead, so yamlls only ever sees real YAML.
                    opts.settings = {
                        yaml = {
                            schemaStore = { enable = false, url = "" },
                            schemas = schemastore.yaml.schemas(),
                        },
                    }
                end
                vim.lsp.config(server, opts)
            end

            vim.lsp.enable(servers)
        end,
    },
}
