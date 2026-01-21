vim.cmd([[
  set runtimepath^=~/.vim runtimepath+=~/.vim/after
]])

vim.g.mapleader = " "

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
vim.o.wrap = false
