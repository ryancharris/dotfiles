-- function map(mode, shortcut, keymap)
-- 	vim.api.nvim_set_keymap(
-- 		mode,
-- 		shortcut,
-- 		command,
-- 		{ noremap = true, silent = true }
-- 	)
-- end

require('plugins')
require("bufferline").setup{}
require('lualine').setup()

vim.cmd([[
set runtimepath^=~/.vim runtimepath+=~/.vim/after
let &packpath = &runtimepath
filetype on
filetype plugin on
filetype indent on
set clipboard+=unnamedplus
colorscheme catppuccin-mocha
set termguicolors
set number
set ignorecase
set smartcase
set expandtab
set smartindent
set autoindent
set showmatch
set shiftwidth=4
set softtabstop=4
]])

-- map("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>")
-- map("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>")

vim.api.nvim_set_keymap("n", "gd", "<cmd>lua vim.lsp.buf.definition()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "gr", "<cmd>lua vim.lsp.buf.references()<CR>", { noremap = true, silent = true })
