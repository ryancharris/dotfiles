lua require('plugins')
set runtimepath^=~/.vim runtimepath+=~/.vim/after
let &packpath = &runtimepath
source ~/.vimrc
set termguicolors
set clipboard+=unnamedplus
colorscheme catppuccin-mocha

lua << EOF
require("bufferline").setup{}
EOF

lua << END
require('lualine').setup()
END

