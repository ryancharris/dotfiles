# ###########################
# general environment
# ###########################
export KITTY_CONFIG_DIRECTORY=/Users/ryan/dotfiles/kitty/
export LESS=R
export ASDF_HASHICORP_OVERWRITE_ARCH=amd64
export ASDF_DATA_DIR="/Users/ryan/.asdf"
export GOPATH="/Users/ryan/go"
export GOBIN="/Users/ryan/go/bin"
export GIT_PROJECTS_WORKDIR="/Users/ryan/git"
export AWS_USER="ryan.harris"
_gh_token=$(gh auth token 2>/dev/null)
if [[ -n "$_gh_token" ]]; then
  export GITHUB_TOKEN="$_gh_token"
else
  echo "⚠ gh CLI not authenticated — run: gh auth login" >&2
fi
unset _gh_token

# ###########################
# path configuration
# ###########################
# Prioritize local bin > asdf > go > brew > system > cargo > gcloud
BREW_PREFIX="/opt/homebrew"
export PATH="$HOME/.local/bin:$ASDF_DATA_DIR/shims:$GOBIN:$BREW_PREFIX/bin:$BREW_PREFIX/sbin:/usr/local/bin:$HOME/.cargo/bin:/usr/local/google-cloud-sdk/bin:$PATH"
# Drop duplicates, keeping first occurrence (~/.zprofile and /etc/paths re-add some).
# -U only dedupes array assignment, so re-assign path after the string export.
typeset -U path
path=($path)

# ###########################
# history
# ###########################
export HISTFILE="$HOME/.zsh_history"
export HISTSIZE=50000
export SAVEHIST=50000
setopt HIST_IGNORE_DUPS HIST_IGNORE_SPACE SHARE_HISTORY

# ###########################
# git aliases
# ###########################
alias gbd="git branch -d"
alias gs="git switch"
alias gsc="git switch -c"
alias gcb="gsc"
alias gco="gs"
alias gcm="git commit"
alias ga="git add"
alias gap="git add --patch"
alias gd="git diff"
alias gst="git status"
alias gpo="git pull origin"
gro() { git rebase "origin/$1"; }

# ###########################
# aliases
# ###########################
alias k="kubectl"
alias kgp="kubectl get pods"
alias kgns="kubectl get namespaces"
alias cat="bat "
alias python="python3"
alias pip="pip3"
alias ls="eza"
alias tf="tofu"

# ###########################
# key bindings
# ###########################
bindkey "^[[1;3C" forward-word
bindkey "^[[1;3D" backward-word

# ###########################
# tools
# ###########################
export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_DEFAULT_OPTS="--ansi"

eval "$(starship init zsh)"
eval "$(direnv hook zsh)"
source <(fzf --zsh)

# ###########################
# zsh plugins
# ###########################
[ -f "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ] && \
    source "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh"

[ -f "$BREW_PREFIX/share/zsh-history-substring-search/zsh-history-substring-search.zsh" ] && \
    source "$BREW_PREFIX/share/zsh-history-substring-search/zsh-history-substring-search.zsh"

[ -f "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ] && \
    source "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"

export HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND=""
bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down

eval "$(zoxide init zsh)"

export TELEPORT_PROXY='dbtlabs.teleport.sh'
export TELEPORT_AUTH='okta'
export AWS_PROFILE='dev-admin'
