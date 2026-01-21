require("config.options")
require("config.lazy")
require('config.keymaps')

-- file specific
vim.api.nvim_create_autocmd("FileType", {
  pattern = {"javascript", "javascriptreact", "javascript.jsx", "typescript", "typescriptreact", "typescript.tsx"},
  callback = function()
    vim.bo.shiftwidth = 2  -- Indent size for each level
    vim.bo.softtabstop = 2 -- Spaces per Tab press
    vim.bo.expandtab = true -- Use spaces instead of tabs
  end,
})

