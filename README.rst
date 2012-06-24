========================
Marwan Osman's Dot Files
========================
Configurations and dotfiles for my development machine.
Mostly inspired by:
- https://github.com/myusuf3/dotfiles
- https://github.com/tejr/dotfiles 

Plugins Used
------------
- Fugitive
- Python-mode
- Nerdtree
- Tagbar
- Vim-Powerline
- Gundo
- Ctrlp
- Ack
- Vim-Rails
- Vim-Javascript
- JSLint
- Vim-browser-reload-linux

Installation
------------
Just run install.sh script

- Vim configuration
  ::
  ./configure --with-features=huge --enable-cscope --enable-rubyinterp --enable-python3interp=yes --enable-pythoninterp=yes --enable-gui=gnome2 --enable-tclinterp --enable-fontset --with-compiledby=lordm

- required packages
  ::
  sudo apt-get install libncurses5 libncurses5-dev libncursesw5 ncurses-bin ncurses-base ctags
