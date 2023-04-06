# git
ln -s ~/dotfiles/git/.gitconfig ~/.gitconfig
ls -s ~/dotfiles/git/.gitignore ~/.gitignore

# tmux
ln -s ~/dotfiles/.tmux/.tmux.conf ~/.tmux.conf
ln -s ~/dotfiles/.tmux/.tmux.conf.local ~/.tmux.conf.local
ln -s ~/dotfiles/.tmuxinator/ ~/.tmuxinator

# alacritty
ln -s ~/dotfiles/.alacritty.yml ~/.alacritty.yml

# zsh
ln -s ~/dotfiles/zsh/.zshrc ~/.zshrc

# emacs
ln -s ~/dotfiles/.doom.d ~/.doom.d
ln -s ~/dotfiles/.emacs ~/.emacs

# vim
ln -s ~/dotfiles/vim/.vimrc ~/.vimrc
ln -s ~/dotfiles/nvim/ ~/.config

# starship
mkdir -p ~/.config
ln -s ~/dotfiles/starship/starship.toml ~/.config/starship.toml

# k9s
ln -s ~/dotfiles/k9s/skin.yml ~/Library/Application\ Support/k9s/skin.yml

# kitty
ln -s ~/dotfiles/kitty/kitty.conf ~/.config/kitty/kitty.conf
