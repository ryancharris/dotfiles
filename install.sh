#!/bin/zsh
set -e

DOTFILES="$HOME/dotfiles"

# ── Homebrew ──────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
  echo "Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add Homebrew to PATH for the remainder of this session (Apple Silicon path)
  [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# ── Packages ──────────────────────────────────────────────────────────────────
echo "Installing packages..."

brew install \
  asdf \
  bat \
  direnv \
  eza \
  fd \
  fzf \
  gh \
  git-lfs \
  jq \
  nvim \
  podman \
  ripgrep \
  starship \
  tig \
  tldr \
  wget \
  yq \
  zoxide \
  zsh-autosuggestions \
  zsh-history-substring-search \
  zsh-syntax-highlighting

brew install --cask \
  bruno \
  claude-code \
  ghostty \
  kitty \
  maccy \
  notion \
  podman-desktop \
  rectangle

# ── Symlinks ──────────────────────────────────────────────────────────────────
echo "Creating symlinks..."

link() {
  mkdir -p "$(dirname "$2")"
  ln -sf "$1" "$2"
}

# git
link "$DOTFILES/git/.gitconfig"                "$HOME/.gitconfig"
link "$DOTFILES/git/.gitignore"                "$HOME/.gitignore"

# zsh
link "$DOTFILES/zsh/.zshrc"                    "$HOME/.zshrc"

# nvim
link "$DOTFILES/nvim"                          "$HOME/.config/nvim"

# starship
link "$DOTFILES/starship/starship.toml"        "$HOME/.config/starship.toml"

# kitty
link "$DOTFILES/kitty"                         "$HOME/.config/kitty"

# ghostty
link "$DOTFILES/ghostty/config"                "$HOME/Library/Application Support/com.mitchellh.ghostty/config"

# agents
link "$DOTFILES/agents/gemini/settings.json"   "$HOME/.gemini/settings.json"
link "$DOTFILES/agents/opencode/opencode.json" "$HOME/.config/opencode/opencode.json"
link "$DOTFILES/agents/commands"               "$HOME/.config/opencode/commands"
link "$DOTFILES/agents/claude/settings.json"   "$HOME/.claude/settings.json"
link "$DOTFILES/agents/commands"               "$HOME/.claude/commands"

echo "Done."
