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
let mapleader = " "
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

-- editing
vim.api.nvim_set_keymap("i", "<leader><Tab>", "<cmd>lua vim.lsp.omnifunc()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>rr", "<cmd>redo<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>uu", "<cmd>undo<CR>", { noremap = true, silent = true })

-- lsp
vim.api.nvim_set_keymap("n", "<leader>cd", "<cmd>lua vim.lsp.buf.definition()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>cr", "<cmd>lua vim.lsp.buf.references()<CR>", { noremap = true, silent = true })


-- windows
vim.api.nvim_set_keymap("n", "<leader>wh", "<cmd>hsplit<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wv", "<cmd>vsplit<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wl", "<cmd>wincmd l<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wh", "<cmd>wincmd h<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wj", "<cmd>wincmd j<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wk", "<cmd>wincmd k<CR>", { noremap = true, silent = true })
