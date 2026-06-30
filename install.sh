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
  colima \
  difftastic \
  direnv \
  docker \
  eza \
  fd \
  fzf \
  gh \
  gh-dash \
  git-delta \
  git-lfs \
  jq \
  nvim \
  ripgrep \
  starship \
  tig \
  tldr \
  trufflehog \
  wget \
  yq \
  zoxide \
  zsh-autosuggestions \
  zsh-history-substring-search \
  zsh-syntax-highlighting

brew tap nikitabobko/tap
brew install --cask \
  nikitabobko/tap/aerospace \
  bruno \
  claude-code \
  ghostty \
  kitty \
  maccy \
  notion

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

# gh-dash
link "$DOTFILES/gh-dash/config.yml"           "$HOME/.config/gh-dash/config.yml"

# diffnav
link "$DOTFILES/diffnav/config.yml"           "$HOME/.config/diffnav/config.yml"

# aerospace
link "$DOTFILES/aerospace/aerospace.toml"     "$HOME/.config/aerospace/aerospace.toml"

# agents
link "$DOTFILES/agents/gemini/settings.json"   "$HOME/.gemini/settings.json"
link "$DOTFILES/agents/opencode/opencode.json" "$HOME/.config/opencode/opencode.json"
link "$DOTFILES/agents/commands"               "$HOME/.config/opencode/commands"
link "$DOTFILES/agents/claude/settings.json"   "$HOME/.claude/settings.json"
link "$DOTFILES/agents/claude/statusline.sh"   "$HOME/.claude/statusline.sh"
link "$DOTFILES/agents/commands"               "$HOME/.claude/commands"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/.gemini/GEMINI.md"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/.config/opencode/AGENTS.md"

# ── GitHub Extensions ─────────────────────────────────────────────────────────
echo "Installing gh extensions..."
gh extension install dlvhdr/gh-dash || true
gh extension install dlvhdr/gh-enhance || true

echo "Done."
