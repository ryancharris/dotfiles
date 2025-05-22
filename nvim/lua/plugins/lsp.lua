return {
    {
        "williamboman/mason.nvim", opts = {}
    },
    {
        "neovim/nvim-lspconfig",
        config = function()
            require"lspconfig".pyright.setup{}
            require"lspconfig".yamlls.setup{}
            require"lspconfig".bashls.setup{}
            require"lspconfig".dockerls.setup{}
            require"lspconfig".gopls.setup{}
            require"lspconfig".jsonls.setup{}
            require"lspconfig".cssls.setup{}
            require"lspconfig".eslint.setup{
                filetypes = {"javascript", "javascriptreact", "javascript.jsx", "vue", "svelte", "astro"}
            }
            require"lspconfig".html.setup{}
            require"lspconfig".ts_ls.setup{
                on_attach = function(client, bufnr)
                    client.server_capabilities.documentFormattingProvider = false
                end,
                filetypes = {"typescript", "typescriptreact", "typescript.tsx"}
            }
            require"lspconfig".terraformls.setup{}
            require"lspconfig".rust_analyzer.setup{}
        end
    }
}
