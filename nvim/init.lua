vim.cmd([[
set runtimepath^=~/.vim runtimepath+=~/.vim/after
let &packpath = &runtimepath
filetype on
filetype plugin on
filetype indent on
colorscheme catppuccin-mocha
]])

vim.o.autoindent = true
vim.opt.clipboard:append("unnamedplus")
vim.o.expandtab = true
vim.o.ignorecase = true
vim.g.mapleader = " "
vim.o.number = true
vim.o.shiftwidth = 4
vim.o.showmatch = true
vim.o.smartcase = true
vim.o.smartindent = true
vim.o.softtabstop = 4
vim.o.termguicolors = true

require('plugins')
require('keymaps')

