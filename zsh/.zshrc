# ###########################
# zsh setup
# ###########################

export ZSH="/Users/ryan/.oh-my-zsh"

ZSH_THEME="robbyrussell"
ZSH_DISABLE_COMPFIX=true

plugins=(git fzf asdf kubectl)
export FZF_BASE="/usr/local/bin/fzf"

source $ZSH/oh-my-zsh.sh
source $HOME/dotfiles/dbt.sh

# ###########################
# aliases
# ###########################

alias gbd="git branch -d"
alias gcb="git checkout -b"
alias gco="git checkout"
alias gcm="git commit -m"
alias gd="git diff"
alias gst="git status"

alias ngrok="/usr/local/bin/ngrok"
alias gcloud="/usr/local/google-cloud-sdk/bin/gcloud"
alias k="/opt/homebrew/bin/kubecolor"
alias watch="watch "
alias cat="bat "
alias emacs="emacs -nw"
alias mux="tmuxinator"
alias python="python3"
alias pip="pip3"
alias codecov="/usr/local/bin/codecov"

alias d5="/usr/local/bin/devspace5"
alias devspace5="/usr/local/bin/devspace5"
alias d6="/usr/local/bin/devspace6"
alias devspace6="/usr/local/bin/devspace6"

# ###########################
# key bindings
# ###########################

bindkey "^[[1;3C" forward-word
bindkey "^[[1;3D" backward-word

# ###########################
# general
# ###########################

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/usr/local/google-cloud-sdk/path.zsh.inc' ]; then . '/usr/local/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/usr/local/google-cloud-sdk/completion.zsh.inc' ]; then . '/usr/local/google-cloud-sdk/completion.zsh.inc'; fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

export PATH="$HOME/go/bin:/usr/local/bin:$HOME/.cargo/bin:/usr/local/opt/ruby@2.7/bin:/usr/local/lib/ruby/gems/2.7.0/bin:/Users/ryan/.local/share/solana/install/active_release/bin:$PATH"

# tabtab source for packages
# uninstall by removing these lines
[[ -f ~/.config/tabtab/__tabtab.zsh ]] && . ~/.config/tabtab/__tabtab.zsh || true

eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
eval "$(starship init zsh)"

export GIT_PROJECTS_WORKDIR="/Users/ryan/git"
