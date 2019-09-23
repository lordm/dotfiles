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
plugins=(git catimg rvm ruby python pip node ng npm)

source $ZSH/oh-my-zsh.sh

# Customize to your needs...
export PATH=$PATH:bin:/home/lordm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/home/lordm/google_appengine:/home/lordm/Setups/phantomjs/bin:/usr/lib/jvm/java-6-openjdk/jre/bin:/home/lordm/setups/ViSP-2.10.0/bin;

export ANDROID_HOME=/home/lordm/Android/Sdk;
export PATH=$PATH:ANRDOID_HOME:/home/lordm/Android/Sdk/tools:/home/lordm/Android/Sdk/platform-tools:/home/lordm/Android/Sdk/build-tools

export WORKON_HOME=~/.virtualenvs
source /usr/local/bin/virtualenvwrapper.sh

export EDITOR="vim"

export LUA_PATH='/home/lordm/.luarocks/share/lua/5.1/?.lua;/home/lordm/.luarocks/share/lua/5.1/?/init.lua;/home/lordm/torch/install/share/lua/5.1/?.lua;/home/lordm/torch/install/share/lua/5.1/?/init.lua;./?.lua;/home/lordm/torch/install/share/luajit-2.1.0-alpha/?.lua;/usr/local/share/lua/5.1/?.lua;/usr/local/share/lua/5.1/?/init.lua'
export LUA_CPATH='/home/lordm/.luarocks/lib/lua/5.1/?.so;/home/lordm/torch/install/lib/lua/5.1/?.so;./?.so;/usr/local/lib/lua/5.1/?.so;/usr/local/lib/lua/5.1/loadall.so'
export PATH=/home/lordm/torch/install/bin:$PATH  # Added automatically by torch-dist
export LD_LIBRARY_PATH=/home/lordm/torch/install/lib:$LD_LIBRARY_PATH  # Added automatically by torch-dist
#export DYLD_LIBRARY_PATH=/home/lordm/torch/install/lib:$DYLD_LIBRARY_PATH  # Added automatically by torch-dist
export KAFKA_URL='localhost:9092'
export MONGO_URL='localhost:27017'

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm

export PATH="$PATH:$HOME/.rvm/bin" # Add RVM to PATH for scripting
export rvmsudo_secure_path=1

#cuda
export PATH=$PATH:/usr/local/cuda-8.0/bin # Add RVM to PATH for scripting
export LD_LIBRARY_PATH=/usr/local/cuda-8.0/lib64:$LD_LIBRARY_PATH  # Added automatically by torch-dist

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
eval "$(thefuck --alias)"
#source /opt/ros/kinetic/setup.zsh
#source ~/catkin_ws/devel/setup.zsh

# place this after nvm initialization!
# auto use .nvmrc files
autoload -U add-zsh-hook
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
add-zsh-hook chpwd load-nvmrc
load-nvmrc

#Knowledge officer
alias sshkoold='ssh m.osman@50.116.16.131'
alias sshko='ssh km@3.16.67.160'
alias sshkoubuntu='ssh ubuntu@3.16.67.160'
alias sshkostaging='ssh marwan@69.164.202.153'
alias sshkoproduction='ssh marwan@api.knowledgeofficer.com'
alias sshengines='ssh marwan@18.216.202.61'
alias sshkocontainerold='ssh ubuntu@18.191.231.197'
alias sshkocontainer='ssh ubuntu@3.15.205.228'
alias sshkomongo='ssh ubuntu@3.17.78.48'
alias sshkoscrapper='ssh ubuntu@3.17.176.167'
