# git
ln -s ~/dotfiles/git/.gitconfig ~/.gitconfig
ls -s ~/dotfiles/git/.gitignore ~/.gitignore

# tmux
ln -s ~/dotfiles/tmux/.tmux.conf ~/.tmux.conf

# alacritty
ln -s ~/dotfiles/alacritty/alacritty.toml ~/.config/alacritty/alacritty.toml

# zsh
ln -s ~/dotfiles/zsh/.zshrc ~/.zshrc

# emacs
ln -s ~/dotfiles/emacs/.emacs ~/.emacs

# nvim
ln -s ~/dotfiles/nvim/.vimrc ~/.vimrc
ln -s ~/dotfiles/nvim/ ~/.config

# starship
mkdir -p ~/.config
ln -s ~/dotfiles/starship/starship.toml ~/.config/starship.toml

# k9s
ln -s ~/dotfiles/k9s/skin.yml ~/Library/Application\ Support/k9s/skin.yml

# kitty
ln -s ~/dotfiles/kitty/kitty.conf ~/.config/kitty/kitty.conf
ln -s ~/dotfiles/kitty/current-theme.conf ~/.config/kitty/current-theme.conf

# ghostty
ln -s ~/dotfiles/ghostty/config ~/Library/Application\ Support/com.mitchellh.ghostty/config

# agents
ln -s ~/dotfiles/agents/gemini/settings.json ~/.gemini/settings.json
ln -s ~/dotfiles/agents/opencode/opencode.json ~/.config/opencode/opencode.json
