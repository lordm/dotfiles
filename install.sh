#!/usr/bin/env bash

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
