vim.cmd([[
set runtimepath^=~/.vim runtimepath+=~/.vim/after
filetype on
filetype plugin on
filetype indent on
]])

vim.g.mapleader = " "
vim.g.netrw_banner = 0
vim.g.netrw_liststyle = 3

vim.o.autoindent = true
vim.o.background = "dark"
vim.opt.clipboard:append("unnamedplus")
vim.o.cursorline = true
vim.o.cursorlineopt = "both"
vim.o.completeopt = "menu"
vim.o.expandtab = true
vim.o.ignorecase = true
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
