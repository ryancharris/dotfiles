# Login shells (including non-interactive `zsh -l -c`) get Homebrew on PATH
# ahead of system dirs, plus HOMEBREW_* vars. .zshrc handles interactive setup.
eval "$(/opt/homebrew/bin/brew shellenv zsh)"
