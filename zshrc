# Path to your oh-my-zsh configuration.
ZSH=$HOME/.oh-my-zsh

# Set name of the theme to load.
# Look in ~/.oh-my-zsh/themes/
# Optionally, if you set this to "random", it'll load a random theme each
# time that oh-my-zsh is loaded.
ZSH_THEME="robbyrussell"

# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

# Set to this to use case-sensitive completion
# CASE_SENSITIVE="true"

# Comment this out to disable bi-weekly auto-update checks
# DISABLE_AUTO_UPDATE="true"

# Uncomment to change how often before auto-updates occur? (in days)
# export UPDATE_ZSH_DAYS=13

# Uncomment following line if you want to disable colors in ls
# DISABLE_LS_COLORS="true"

# Uncomment following line if you want to disable autosetting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment following line if you want to disable command autocorrection
# DISABLE_CORRECTION="true"

# Uncomment following line if you want red dots to be displayed while waiting for completion
# COMPLETION_WAITING_DOTS="true"

# Uncomment following line if you want to disable marking untracked files under
# VCS as dirty. This makes repository status check for large repositories much,
# much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Which plugins would you like to load? (plugins can be found in ~/.oh-my-zsh/plugins/*)
# Custom plugins may be added to ~/.oh-my-zsh/custom/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
plugins=(git catimg rvm ruby python pip node ng npm command-time)

source $ZSH/oh-my-zsh.sh

# not using anymore
#export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3
#export WORKON_HOME=/home/marwan/.local/bin/.virtualenvs
#export VIRTUALENVWRAPPER_VIRTUALENV=$HOME/.local/bin/virtualenv
#source /home/marwan/.local/bin/virtualenvwrapper.sh

# NVIDIA CUDA Toolkit
export PATH=/usr/local/cuda/bin${PATH:+:${PATH}}
export LD_LIBRARY_PATH=/usr/local/cuda/lib64

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/marwan/anaconda3/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/marwan/anaconda3/etc/profile.d/conda.sh" ]; then
        . "/home/marwan/anaconda3/etc/profile.d/conda.sh"
    else
        export PATH="/home/marwan/anaconda3/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

export EDITOR="vim"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm

export PATH="$PATH:$HOME/.rvm/bin" # Add RVM to PATH for scripting
export rvmsudo_secure_path=1

# use vim keybindings
bindkey -v
bindkey '^R' history-incremental-search-backward

# widget to show vim status
function zle-line-init zle-keymap-select {
   RPS1="${${KEYMAP/vicmd/ N }/(main|viins)/ I }"
   RPS2=$RPS1
   zle reset-prompt
}
zle -N zle-line-init
zle -N zle-keymap-select
#eval "$(thefuck --alias)"

alias restartswap='sudo swapoff -a && sudo swapon -a'
#source /opt/ros/kinetic/setup.zsh
#source ~/catkin_ws/devel/setup.zsh

# place this after nvm initialization!
# auto use .nvmrc files
#autoload -U add-zsh-hook


load-nvmrc() {
  local node_version="$(nvm version)"
  local nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$node_version" ]; then
      nvm use
    fi
  elif [ "$node_version" != "$(nvm version default)" ]; then
    echo "Reverting to nvm default version"
    nvm use default
  fi
}

#add-zsh-hook chpwd load-nvmrc
load-nvmrc

# Force tmux to assume that the terminal support 256 colors
alias tmux="tmux -2"

alias dose='docker compose'

# pyenv
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# tmux theme
powerline-config tmux setup

# work related
