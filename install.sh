#!/usr/bin/env bash

sudo apt update

# install docker
sudo apt install ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo groupadd docker
sudo usermod -aG docker $USER

# Essential packages
sudo apt install checkinstall git make build-essential libssl-dev zlib1g-dev cloudflare-warp nmap powertop iotop tlp tlp-rdw zip gnome-power-manager gparted jq

# Media packages
sudo apt install vlc ffmpeg gimp audacity guitarix blender obs-studio

# ohmyzsh
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# install lazygit
LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep -Po '"tag_name": "v\K[^"]*')
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz lazygit
sudo install lazygit /usr/local/bin

# install UbuntuMono Nerd font
mkdir -p ~/.local/share/fonts
cd ~/.local/share/fonts && curl -fLO https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/UbuntuMono/Regular/UbuntuMonoNerdFont-Regular.ttf

# nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install node

# pyenv
curl https://pyenv.run | bash

pyenv install 3.11
pyenv global 3.11
pip install s3cmd
pip install uv
pip install poetry

# neovim dependencies
sudo apt install ripgrep fd

# install lazyman
git clone https://github.com/doctorfree/nvim-lazyman $HOME/.config/nvim-Lazyman
$HOME/.config/nvim-Lazyman/lazyman.sh

# k9s
wget https://github.com/derailed/k9s/releases/download/v0.31.9/k9s_linux_amd64.deb && dpkg -i k9s_linux_amd64.deb

# az cli
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

echo "Backing up the old files..."
cp ~/.vimrc ~/vimrc.old
cp ~/.gvimrc ~/.gvimrc.old
cp ~/.gitconfig ~/.gitconfig.old
cp ~/.tmux.conf ~/.tmux.old.conf
cp ~/.zshrc ~/.zshrc_old

echo "Installing Powerline"
pip install powerline-status

echo "Installing Zsh command-time"
git clone https://github.com/popstas/zsh-command-time.git ~/.oh-my-zsh/custom/plugins/command-time 2> /dev/null ||  (cd ~/.oh-my-zsh/custom/plugins/command-time; git pull)

echo "Symlinking files..."
ln -fs "$PWD/vim/vimrc" ~/.vimrc
ln -fs "$PWD/vim" ~/.vim
ln -fs "$PWD/vim/gvimrc" ~/.gvimrc
ln -fs "$PWD/gitconfig" ~/.gitconfig
ln -fs "$PWD/gitignore" ~/.gitignore
ln -fs "$PWD/tmux.conf" ~/.tmux.conf
ln -fs "$PWD/zshrc" ~/.zshrc
ln -fs "$PWD/nvim" ~/.config/nvim

echo "All Done."
