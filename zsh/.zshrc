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
export PATH="$HOME/.local/bin:$ASDF_DATA_DIR/shims:$GOBIN:$(brew --prefix)/bin:$(brew --prefix)/sbin:/usr/local/bin:$HOME/.cargo/bin:/usr/local/google-cloud-sdk/bin:$PATH"

# ###########################
# git aliases
# ###########################
alias gbd="git branch -d"
alias gcb="git checkout -b"
alias gco="git checkout"
alias gcm="git commit"
alias ga="git add"
alias gap="git add --patch"
alias gd="git diff"
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
alias watch="watch "
alias cat="bat "
alias emacs="emacs -nw"
alias python="python3"
alias pip="pip3"
alias ls="eza"

# ###########################
# key bindings
# ###########################
bindkey "^[[1;3C" forward-word
bindkey "^[[1;3D" backward-word

# ###########################
# functions
# ###########################
ggp() {
    git grep -C 3 "$1" -- "*.py"
}
ggy() {
    git grep -C 3 "$1" -- "*.yaml"
}

# ###########################
# tools
# ###########################
eval "$(starship init zsh)"
source <(fzf --zsh)

# ###########################
# dbt & private
# ###########################
[ -f "$HOME/dotfiles/private/dbt.sh" ] && source "$HOME/dotfiles/private/dbt.sh"

# ###########################
# zsh plugins
# ###########################
[ -f "$(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ] && \
    source "$(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh"

[ -f "$(brew --prefix)/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ] && \
    source "$(brew --prefix)/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"

[ -f "$(brew --prefix)/share/zsh-history-substring-search/zsh-history-substring-search.zsh" ] && \
    source "$(brew --prefix)/share/zsh-history-substring-search/zsh-history-substring-search.zsh"

export HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND=""
bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down

eval "$(zoxide init zsh)"

# dbt aliases
alias dbtf="$HOME/.local/bin/dbt"
