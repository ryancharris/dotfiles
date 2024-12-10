-- buffers
vim.api.nvim_set_keymap('n', '<leader><Tab>', ':b#<CR>', { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wd", "<cmd>bdelete<CR>", { noremap = true, silent = true })

-- editing
vim.api.nvim_set_keymap("i", "<leader><Tab>", "<cmd>lua vim.lsp.omnifunc()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>rr", "<cmd>redo<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>uu", "<cmd>undo<CR>", { noremap = true, silent = true })

-- lsp
vim.api.nvim_set_keymap("n", "<leader>cd", "<cmd>lua vim.lsp.buf.definition()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>cr", "<cmd>lua vim.lsp.buf.references()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>co", "<cmd>lua vim.diagnostic.open_float()<CR>", { noremap = true, silent = true })

-- searching
vim.o.grepprg="git grep -n"
vim.api.nvim_create_user_command("SearchWithPrompt", 'silent grep! <args> | copen', { nargs = '+'})
vim.api.nvim_set_keymap("n", "<leader>ps", "<cmd>silent grep! <cword> | copen <CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>ss", ":SearchWithPrompt", { noremap = true })

-- windows
vim.api.nvim_set_keymap("n", "<leader>wv", "<cmd>vsplit<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wl", "<cmd>wincmd l<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wh", "<cmd>wincmd h<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wj", "<cmd>wincmd j<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wk", "<cmd>wincmd k<CR>", { noremap = true, silent = true })

