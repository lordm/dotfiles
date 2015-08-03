#!/usr/bin/env bash

echo "Initializing submodules..."
git submodule update --init --force --recursive

echo "Deleting old files..."
rm ~/.vimrc
rm -rf ~/.vim
rm ~/.gvimrc
rm ~/.gitconfig
#rm ~/.gitignore
#rm ~/.zshrc
#rm ~/.tmux.conf
rm -rf ~/.fonts/ubuntu-mono

echo "Symlinking files..."
ln -fs "$PWD/vim/vimrc" ~/.vimrc
ln -fs "$PWD/vim" ~/.vim
ln -fs "$PWD/vim/gvimrc" ~/.gvimrc
ln -fs "$PWD/gitconfig" ~/.gitconfig
#ln -fs "$PWD/gitignore" ~/.gitignore
#ln -fs "$PWD/zshrc" ~/.zshrc
#ln -fs "$PWD/tmux.conf" ~/.tmux.conf
ln -fs "$PWD/fonts/ubuntu-mono" ~/.fonts/ubuntu-mono

echo "Updating submodules..."
git submodule foreach git pull --force origin master

echo "All Done."
