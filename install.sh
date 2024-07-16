#!/usr/bin/env bash

sudo apt-get update
sudo apt-get install ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io
sudo groupadd docker
sudo usermod -aG docker $USER


# install lazygit
LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep -Po '"tag_name": "v\K[^"]*')
curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz"
tar xf lazygit.tar.gz lazygit
sudo install lazygit /usr/local/bin


echo "Backing up the old files..."
cp ~/.vimrc ~/vimrc.old
cp ~/.gvimrc ~/.gvimrc.old
cp ~/.gitconfig ~/.gitconfig.old
cp ~/.tmux.conf ~/.tmux.old.conf
cp ~/.zshrc ~/.zshrc_old

echo "Installing Powerline"
sudo pip install powerline-status

echo "Installing Zsh command-time"
git clone https://github.com/popstas/zsh-command-time.git ~/.oh-my-zsh/custom/plugins/command-time 2> /dev/null ||  (cd ~/.oh-my-zsh/custom/plugins/command-time; git pull)

echo "Cloning Ubuntu Mono powerline patched font"
git clone https://github.com/scotu/ubuntu-mono-powerline.git fonts/ubuntu-mono 2> /dev/null || (cd fonts/ubuntu-mono; git pull)

echo "Symlinking files..."
ln -fs "$PWD/vim/vimrc" ~/.vimrc
ln -fs "$PWD/vim" ~/.vim
ln -fs "$PWD/vim/gvimrc" ~/.gvimrc
ln -fs "$PWD/gitconfig" ~/.gitconfig
ln -fs "$PWD/fonts/ubuntu-mono" ~/.fonts/ubuntu-mono
#ln -fs "$PWD/gitignore" ~/.gitignore
ln -fs "$PWD/tmux.conf" ~/.tmux.conf
ln -fs "$PWD/zshrc" ~/.zshrc

echo "All Done."
