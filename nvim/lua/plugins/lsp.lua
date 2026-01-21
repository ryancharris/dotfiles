return {
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
                "terraformls", "ts_ls", "yamlls"
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

                -- Custom handler for 'ts_ls' (TypeScript)
                ["ts_ls"] = function()
                    lspconfig.ts_ls.setup({
                        filetypes = { "typescript", "typescriptreact", "typescript.tsx" },
                        settings = {
                            typescript = {
                                inlayHints = {
                                    includeInlayParameterNameHints = "all",
                                    includeInlayParameterNameHintsWhenArgumentMatchesName = false,
                                    includeInlayFunctionParameterTypeHints = true,
                                    includeInlayVariableTypeHints = true,
                                    includeInlayPropertyDeclarationTypeHints = true,
                                    includeInlayFunctionLikeReturnTypeHints = true,
                                    includeInlayEnumMemberValueHints = true,
                                },
                            },
                            javascript = {
                                inlayHints = {
                                    includeInlayParameterNameHints = "all",
                                    includeInlayParameterNameHintsWhenArgumentMatchesName = false,
                                    includeInlayFunctionParameterTypeHints = true,
                                    includeInlayVariableTypeHints = true,
                                    includeInlayPropertyDeclarationTypeHints = true,
                                    includeInlayFunctionLikeReturnTypeHints = true,
                                    includeInlayEnumMemberValueHints = true,
                                },
                            },
                        },
                    })
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