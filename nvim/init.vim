lua require('plugins')
# lua require('keymaps')
set runtimepath^=~/.vim runtimepath+=~/.vim/after
let &packpath = &runtimepath
source ~/.vimrc
set termguicolors

lua << EOF
require("bufferline").setup{}
EOF

lua << END
require('lualine').setup()
END

