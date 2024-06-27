lua require('plugins')
set runtimepath^=~/.vim runtimepath+=~/.vim/after
let &packpath = &runtimepath
source ~/.vimrc
set termguicolors
set clipboard+=unnamedplus

lua << EOF
require("bufferline").setup{}
EOF

lua << END
require('lualine').setup()
END

