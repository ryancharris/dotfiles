set nocompatible

filetype on
filetype plugin on
filetype indent on

syntax on

set backspace=2
set number
set incsearch
set ignorecase
set smartcase
set expandtab
set shiftwidth=4
set softtabstop=4
set autoindent
set smartindent
set showcmd
set showmode
set showmatch
set history=1000

set wildmenu
set wildmode=list:longest
set wildignore=*.docx,*.jpg,*.png,*.gif,*.pdf,*.pyc,*.exe,*.flv,*.img,*.xlsx

set statusline=
set statusline+=\ %F\ %M\ %Y\ %R
set statusline+=%=
set statusline+=\ w:\ %l\ col:\ %c\ percent:\ %p%%
set laststatus=2
