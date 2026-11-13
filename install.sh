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
# Homebrew refuses to load formulae/casks from untrusted third-party taps.
# Tap first so the entries exist to trust.
brew tap anomalyco/tap
brew tap dlvhdr/formulae
brew tap nikitabobko/tap
brew trust --formula dlvhdr/formulae/diffnav anomalyco/tap/opencode-v2
brew trust --cask nikitabobko/tap/aerospace
brew bundle --file="$DOTFILES/Brewfile"

# ── Optional Packages ────────────────────────────────────────────────────────
OPTIONAL_PACKAGES=(ollama)

for pkg in "${OPTIONAL_PACKAGES[@]}"; do
  if read -q "?Install optional package '$pkg'? [y/N] "; then
    echo
    brew install "$pkg"
  else
    echo
  fi
done

# ── Symlinks ──────────────────────────────────────────────────────────────────
echo "Creating symlinks..."

link() {
  mkdir -p "$(dirname "$2")"
  # Remove existing file/dir/symlink unless it's already the correct symlink
  if [[ "$(readlink "$2" 2>/dev/null)" != "$1" ]]; then
    rm -rf "$2"
  fi
  ln -sfn "$1" "$2"
}

# git
link "$DOTFILES/git/.gitconfig"                "$HOME/.gitconfig"
link "$DOTFILES/git/.gitignore"                "$HOME/.gitignore"

# zsh
link "$DOTFILES/zsh/.zshrc"                    "$HOME/.zshrc"
link "$DOTFILES/zsh/.zprofile"                 "$HOME/.zprofile"

# asdf
link "$DOTFILES/asdf/.tool-versions"          "$HOME/.tool-versions"

# nvim
link "$DOTFILES/nvim"                          "$HOME/.config/nvim"

# starship
link "$DOTFILES/starship/starship.toml"        "$HOME/.config/starship.toml"

# kitty
link "$DOTFILES/kitty"                         "$HOME/.config/kitty"

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
link "$DOTFILES/agents/claude/CLAUDE.md"       "$HOME/.claude/CLAUDE.md"
link "$DOTFILES/agents/commands"               "$HOME/.claude/commands"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/AGENTS.md"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/.gemini/GEMINI.md"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/.config/opencode/AGENTS.md"
link "$DOTFILES/agents/AGENTS.md"              "$HOME/.pi/agent/AGENTS.md"
link "$DOTFILES/agents/codex/config.toml"      "$HOME/.codex/config.toml"
link "$DOTFILES/agents/codex/hooks.json"       "$HOME/.codex/hooks.json"
link "$DOTFILES/agents/antigravity/hooks.json"  "$HOME/.gemini/config/hooks.json"
link "$DOTFILES/agents/skills"                 "$HOME/.agents/skills"
link "$DOTFILES/agents/skills"                 "$HOME/.claude/skills"
link "$DOTFILES/agents/skills"                 "$HOME/.gemini/config/skills"

# paseo
link "$DOTFILES/paseo/config.json"           "$HOME/.paseo/config.json"
# Codex reserves ~/.codex/skills/.system for its own bundled skills, so link
# each skill individually instead of symlinking the whole directory over it.
for skill_dir in "$DOTFILES"/agents/skills/*/; do
  skill_name="$(basename "$skill_dir")"
  link "$skill_dir" "$HOME/.codex/skills/$skill_name"
done

# ── asdf ──────────────────────────────────────────────────────────────────────
# Plugins (name + source URL) and global versions are tracked in the repo;
# ~/.tool-versions is linked above.
echo "Installing asdf plugins and tool versions..."
while read -r name url; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  asdf plugin list 2>/dev/null | grep -qx "$name" || asdf plugin add "$name" "$url"
done < "$DOTFILES/asdf/plugins"
(cd "$HOME" && asdf install)

# ── Colima ────────────────────────────────────────────────────────────────────
echo "Starting colima..."
colima start --memory 8 || echo "warning: colima failed to start" >&2

# ── GitHub Extensions ─────────────────────────────────────────────────────────
echo "Installing gh extensions..."
gh extension install dlvhdr/gh-dash || true
gh extension install dlvhdr/gh-enhance || true

# ── Standalone CLIs ───────────────────────────────────────────────────────────
echo "Installing antigravity CLI wrapper..."
mkdir -p "$HOME/.local/bin"
rm -f "$HOME/.local/bin/antigravity"
cat > "$HOME/.local/bin/antigravity" << 'EOF'
#!/bin/sh
set -eu

if [ $# -eq 0 ]; then
  exec open -a "Antigravity"
fi

exec open -a "Antigravity" "$@"
EOF
chmod 0755 "$HOME/.local/bin/antigravity"

# claude-sessions lives in a private repo, so fetch through gh, which carries
# auth. An unauthenticated curl to raw.githubusercontent.com 404s on private
# content.
echo "Installing claude-sessions..."
_cs_tmp="$(mktemp)"
if gh api repos/ryancharris/claude-sessions/contents/claude-sessions \
     -H "Accept: application/vnd.github.raw" > "$_cs_tmp" \
   && head -n 1 "$_cs_tmp" | grep -q '^#!'; then
  mkdir -p "$HOME/.local/bin"
  install -m 0755 "$_cs_tmp" "$HOME/.local/bin/claude-sessions"
else
  echo "warning: could not fetch claude-sessions — check 'gh auth status'" >&2
fi
rm -f "$_cs_tmp"
unset _cs_tmp

echo "Done."
