#!/usr/bin/env bash

echo "Initializing submodules..."
git submodule --quiet update --init

echo "Deleting old files..."
rm ~/.vimrc
rm ~/.vim
#rm ~/.gvimrc
#rm ~/.gitconfig
#rm ~/.gitignore
#rm ~/.zshrc
#rm ~/.tmux.conf

echo "Symlinking files..."
ln -fs ~/workspace/dotfiles/vim/vimrc ~/.vimrc
ln -fs ~/workspace/dotfiles/vim ~/.vim
#ln -fs ~/workspace/dotfiles/vim/gvimrc ~/.gvimrc
#ln -fs ~/workspace/dotfiles/zshrc ~/.zshrc
#ln -fs ~/workspace/dotfiles/gitconfig ~/.gitconfig
#ln -fs ~/workspace/dotfiles/gitignore ~/.gitignore
#ln -fs ~/workspace/dotfiles/tmux.conf ~/.tmux.conf

echo "Updating submodules..."
git submodule foreach git pull origin master

echo "All Done."
