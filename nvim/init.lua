vim.cmd([[
set runtimepath^=~/.vim runtimepath+=~/.vim/after
filetype on
filetype plugin on
filetype indent on
]])

vim.o.autoindent = true
vim.opt.clipboard:append("unnamedplus")
vim.o.completeopt = "menu"
vim.o.expandtab = true
vim.o.ignorecase = true
vim.g.mapleader = " "
vim.o.number = true
vim.o.relativenumber = true
vim.o.shiftwidth = 4
vim.o.showmatch = true
vim.o.smartcase = true
vim.o.smartindent = true
vim.o.softtabstop = 4
vim.o.termguicolors = true

require("config.lazy")
require('config.keymaps')

vim.cmd.colorscheme "catppuccin"
