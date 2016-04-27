#!/usr/bin/env bash

echo "Initializing submodules..."
git submodule update --init --force --recursive

echo "Backing up the old files..."
mv ~/.vimrc ~/vimrc_old
mv ~/.vim ~/.vim_old
mv ~/.gvimrc ~/.gvimrc
mv ~/.gitconfig ~/.gitconfig
mv ~/.fonts/ubuntu-mono ~/.fonts/ubuntu-mono-old

#rm ~/.gitignore
#rm ~/.zshrc
#rm ~/.tmux.conf


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
