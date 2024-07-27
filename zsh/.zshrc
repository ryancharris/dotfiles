# ###########################
# git aliases
# ###########################
alias gbd="git branch -d"
alias gcb="git checkout -b"
alias gco="git checkout"
alias gcm="git commit"
alias ga="git add"
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

alias ngrok="/opt/homebrew/bin/ngrok"
alias gcloud="/usr/local/google-cloud-sdk/bin/gcloud"
alias k="/usr/local/bin/kubectl"
alias kgp="kubectl get pods"
alias kgns="kubectl get namespaces"
alias watch="watch "
alias cat="bat "
alias emacs="emacs -nw"
alias mux="tmuxinator"
alias python="python3"
alias pip="pip3"
alias codecov="/usr/local/bin/codecov"
alias ls="eza"

# ###########################
# key bindings
# ###########################
bindkey "^[[1;3C" forward-word
bindkey "^[[1;3D" backward-word

bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down

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
. $HOMEBREW_PREFIX/etc/profile.d/z.sh
eval "$(starship init zsh)"
source <(fzf --zsh)

# ###########################
# dbt
# ###########################
source $HOME/dotfiles/private/dbt.sh
export GIT_PROJECTS_WORKDIR="/Users/ryan/git"
export AWS_USER="ryan.harris"
echo -e "\n. $(brew --prefix asdf)/libexec/asdf.sh" >> ${ZDOTDIR:-~}/.zshrc

# ###########################
# general
# ###########################
export KITTY_CONFIG_DIRECTORY=/Users/ryan/dotfiles/kitty/

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

export PATH="$HOME/go/bin:/usr/local/bin:$HOME/.cargo/bin:/usr/local/opt/ruby@2.7/bin:/usr/local/lib/ruby/gems/2.7.0/bin:/Users/ryan/.local/share/solana/install/active_release/bin:$PATH"
export PATH="/Users/ryan/.local/bin:$PATH"
export ASDF_HASHICORP_OVERWRITE_ARCH=amd64

# disable zsh-history-substring-search highlighting
export HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND=""

# ###########################
# zsh plugins
# ###########################
source $(brew --prefix)/share/zsh-autosuggestions/zsh-autosuggestions.zsh
source $(brew --prefix)/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
source $(brew --prefix)/share/zsh-history-substring-search/zsh-history-substring-search.zsh

