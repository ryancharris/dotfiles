# ###########################
# general environment
# ###########################
export KITTY_CONFIG_DIRECTORY=/Users/ryan/dotfiles/kitty/
export ASDF_HASHICORP_OVERWRITE_ARCH=amd64
export ASDF_DATA_DIR="/Users/ryan/.asdf"
export GOPATH="/Users/ryan/go"
export GOBIN="/Users/ryan/go/bin"
export GIT_PROJECTS_WORKDIR="/Users/ryan/git"
export AWS_USER="ryan.harris"

# ###########################
# path configuration
# ###########################
# Prioritize local bin > asdf > go > brew > system > cargo > gcloud
BREW_PREFIX="$(brew --prefix)"
export PATH="$HOME/.local/bin:$ASDF_DATA_DIR/shims:$GOBIN:$BREW_PREFIX/bin:$BREW_PREFIX/sbin:/usr/local/bin:$HOME/.cargo/bin:/usr/local/google-cloud-sdk/bin:$PATH"

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
alias gcb="git checkout -b"
alias gcm="git commit"
alias gap="git add --patch"
alias gst="git status"

# ###########################
# aliases
# ###########################
alias p="podman"
alias pp="podman pull"
alias pr="podman run"
alias prm="podman rm"
alias prmi="podman rmi"
alias k="kubectl"
alias kgp="kubectl get pods"
alias kgns="kubectl get namespaces"
alias cat="bat "
alias emacs="emacs -nw"
alias python="python3"
alias pip="pip3"
alias ls="eza"
alias tf="terraform"

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
# dbt & private
# ###########################
[ -f "$HOME/dotfiles/private/dbt.sh" ] && source "$HOME/dotfiles/private/dbt.sh"

# ###########################
# zsh plugins
# ###########################
[ -f "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ] && \
    source "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh"

[ -f "$BREW_PREFIX/share/forgit/forgit.plugin.zsh" ] && \
    source "$BREW_PREFIX/share/forgit/forgit.plugin.zsh"

[ -f "$BREW_PREFIX/share/zsh-history-substring-search/zsh-history-substring-search.zsh" ] && \
    source "$BREW_PREFIX/share/zsh-history-substring-search/zsh-history-substring-search.zsh"

[ -f "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ] && \
    source "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"

# forgit + difftastic configuration
export FORGIT_DIFF_PAGER="cat"
export FORGIT_DIFF_COMMAND="git -c diff.external=difft diff"


export HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND=""
bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down

eval "$(zoxide init zsh)"

# dbt aliases
alias dbtf="$HOME/.local/bin/dbt"
export GOPATH=$HOME/go
export GOROOT="$(brew --prefix golang)/libexec"
export PATH="$PATH:${GOPATH}/bin:${GOROOT}/bin"
export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
export PATH="${ASDF_DATA_DIR:-$HOME/.asdf}/shims:$PATH"
export TELEPORT_PROXY='dbtlabs.teleport.sh'
export TELEPORT_AUTH='okta'
