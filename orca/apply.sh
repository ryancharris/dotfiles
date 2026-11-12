#!/bin/zsh
# Apply the parts of Orca's config that its CLI can manage, then report
# settings drift. Orca must be running (the CLI talks to it).
set -e

DIR="${0:A:h}"

command -v orca &>/dev/null || { echo "orca CLI not found" >&2; exit 1; }
orca status &>/dev/null || orca open

# Plugins: bundled ones are installed by Orca itself; list the rest here.
PLUGINS=(stablyai.orca-rose-pine-theme)
installed="$(orca plugin list)"
for p in $PLUGINS; do
  if grep -q "^$p " <<< "$installed"; then
    echo "plugin $p: already installed"
  else
    orca plugin install "$p"
  fi
done

# Repos: path-registered projects.
REPOS=("$HOME/dotfiles" "$HOME/git/helm-charts")
registered="$(orca repo list)"
for r in $REPOS; do
  [[ -d "$r" ]] || { echo "repo $r: missing on disk, skipping"; continue; }
  if grep -qF "$r" <<< "$registered"; then
    echo "repo $r: already registered"
  else
    orca repo add --path "$r"
  fi
done

python3 "$DIR/check.py"
