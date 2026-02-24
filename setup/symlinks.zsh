# git
ln -s ~/dotfiles/git/.gitconfig ~/.gitconfig
ln -s ~/dotfiles/git/.gitignore ~/.gitignore

# zsh
ln -s ~/dotfiles/zsh/.zshrc ~/.zshrc

# nvim
mkdir -p ~/.config
ln -s ~/dotfiles/nvim/ ~/.config/nvim

# starship
ln -s ~/dotfiles/starship/starship.toml ~/.config/starship.toml

# kitty
ln -s ~/dotfiles/kitty ~/.config/kitty

# ghostty
ln -s ~/dotfiles/ghostty/config ~/Library/Application\ Support/com.mitchellh.ghostty/config

# agents
ln -s ~/dotfiles/agents/gemini/settings.json ~/.gemini/settings.json
ln -s ~/dotfiles/agents/opencode/opencode.json ~/.config/opencode/opencode.json
