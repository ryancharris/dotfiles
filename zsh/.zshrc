# ###########################
# zsh setup
# ###########################

export ZSH="/Users/ryan/.oh-my-zsh"

ZSH_THEME="robbyrussell"
ZSH_DISABLE_COMPFIX=true

plugins=(git fzf asdf kubectl)
export FZF_BASE="/usr/local/bin/fzf"

source $ZSH/oh-my-zsh.sh

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
alias k="/usr/local/bin/kubectl"
alias watch="watch "
alias cat="bat "
alias ls="exa -l "
alias emacs="emacs -nw"
alias python="python3"
alias pip="pip3"

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

export PATH="/usr/local/bin:$HOME/.cargo/bin:/usr/local/opt/ruby@2.7/bin:/usr/local/lib/ruby/gems/2.7.0/bin:/Users/ryan/.local/share/solana/install/active_release/bin:$PATH"

# tabtab source for packages
# uninstall by removing these lines
[[ -f ~/.config/tabtab/__tabtab.zsh ]] && . ~/.config/tabtab/__tabtab.zsh || true

export GIT_PROJECTS_WORKDIR="$HOME/git"
export HOMEBREW_GITHUB_API_TOKEN=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
export GITHUB_TOKEN="$HOMEBREW_GITHUB_API_TOKEN"
export PYENV_VIRTUALENV_DISABLE_PROMPT=1

eval "$(pyenv init -)"
eval "$(starship init zsh)"
