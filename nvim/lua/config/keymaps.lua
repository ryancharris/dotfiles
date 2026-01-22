-- buffers
vim.keymap.set('n', '<leader><Tab>', ':b#<CR>', { silent = true })
vim.keymap.set("n", "<leader>wd", "<cmd>bdelete<CR>", { silent = true })
vim.keymap.set("n", "<leader>bb", "<cmd>FzfLua buffers<CR>", { silent = true })

-- editing
vim.keymap.set("n", "<leader>rr", "<cmd>redo<CR>", { silent = true })
vim.keymap.set("n", "<leader>uu", "<cmd>undo<CR>", { silent = true })

-- files
vim.keymap.set("n", "<leader>ff", "<cmd>FzfLua files<CR>", { silent = true })
vim.keymap.set("n", "<leader>ee", "<cmd>Explore<CR>", { silent = true })
vim.keymap.set("n", "<leader>re", "<cmd>Rexplore<CR>", { silent = true })

-- git
vim.keymap.set("n", "<leader>mb", "<cmd>FzfLua git_blame<CR>", { silent = true })

-- github
vim.keymap.set("n", "<leader>gg", "<cmd>GitLink<CR>", { desc = "Open in GitHub", silent = true })

-- lsp
vim.api.nvim_set_option('omnifunc', 'v:lua.vim.lsp.omnifunc')
vim.keymap.set("n", "<leader>cd", "<cmd>FzfLua lsp_definitions<CR>", { silent = true })
vim.keymap.set("n", "<leader>cr", "<cmd>FzfLua lsp_references<CR>", { silent = true })
vim.keymap.set("n", "<leader>co", vim.diagnostic.open_float, { silent = true })

-- searching
vim.o.grepprg = "git grep -n"
vim.keymap.set("n", "<leader>ps", "<cmd>FzfLua grep_cword<CR>", { silent = true })
vim.keymap.set("n", "<leader>ss", "<cmd>FzfLua grep<CR>")

-- windows
vim.keymap.set("n", "<leader>wv", "<cmd>vsplit<CR>", { silent = true })
vim.keymap.set("n", "<leader>ws", "<cmd>split<CR>", { silent = true })
vim.keymap.set("n", "<leader>wl", "<cmd>wincmd l<CR>", { silent = true })
vim.keymap.set("n", "<leader>wh", "<cmd>wincmd h<CR>", { silent = true })
vim.keymap.set("n", "<leader>wj", "<cmd>wincmd j<CR>", { silent = true })
vim.keymap.set("n", "<leader>wk", "<cmd>wincmd k<CR>", { silent = true })
