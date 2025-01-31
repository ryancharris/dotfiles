-- buffers
vim.api.nvim_set_keymap('n', '<leader><Tab>', ':b#<CR>', { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wd", "<cmd>bdelete<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>bb", "<cmd>FzfLua buffers<CR>", { noremap = true, silent = true })

-- editing
vim.api.nvim_set_keymap("i", "<leader><Tab>", "<cmd>lua vim.lsp.omnifunc()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>rr", "<cmd>redo<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>uu", "<cmd>undo<CR>", { noremap = true, silent = true })

-- files
vim.api.nvim_set_keymap("n", "<leader>ff", "<cmd>FzfLua files<CR>", { noremap = true, silent = true })

-- git
vim.api.nvim_set_keymap("n", "<leader>mb", "<cmd>FzfLua git_blame<CR>", { noremap = true, silent = true })

-- lsp
vim.api.nvim_set_keymap("n", "<leader>cd", "<cmd>lua vim.lsp.buf.definition()<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>cr", "<cmd>FzfLua lsp_references<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>co", "<cmd>lua vim.diagnostic.open_float()<CR>", { noremap = true, silent = true })

-- searching
vim.o.grepprg="git grep -n"
vim.api.nvim_set_keymap("n", "<leader>ps", "<cmd>FzfLua grep_cword<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>ss", "<cmd>FzfLua grep<CR>", { noremap = true })

-- windows
vim.api.nvim_set_keymap("n", "<leader>wv", "<cmd>vsplit<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>ws", "<cmd>split<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wl", "<cmd>wincmd l<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wh", "<cmd>wincmd h<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wj", "<cmd>wincmd j<CR>", { noremap = true, silent = true })
vim.api.nvim_set_keymap("n", "<leader>wk", "<cmd>wincmd k<CR>", { noremap = true, silent = true })

