require("config.options")
require("config.lazy")
require('config.keymaps')

-- lsps
vim.lsp.enable('bashls')
vim.lsp.enable('cssls')
vim.lsp.enable('dockerls')
vim.lsp.enable('eslint', {
    filetypes = {"javascript", "javascriptreact", "javascript.jsx", "vue", "svelte", "astro"}
})
vim.lsp.enable('gopls')
vim.lsp.enable('html')
vim.lsp.enable('jsonls')
vim.lsp.enable('pyright')
vim.lsp.enable('rust_analyzer')
vim.lsp.enable('terraformls')
vim.lsp.enable('ts_ls', {
    filetypes = {"typescript", "typescriptreact", "typescript.tsx"},
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
            }
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
            }
        }
    }
})
vim.lsp.enable('yamlls')

-- file specific
vim.api.nvim_create_autocmd("FileType", {
  pattern = {"javascript", "javascriptreact", "javascript.jsx", "typescript", "typescriptreact", "typescript.tsx"},
  callback = function()
    vim.bo.shiftwidth = 2  -- Indent size for each level
    vim.bo.softtabstop = 2 -- Spaces per Tab press
    vim.bo.expandtab = true -- Use spaces instead of tabs
  end,
})

