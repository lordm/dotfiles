# Marwan Osman's Dot Files
Configurations and dotfiles for my development machine.
Mostly inspired by:
- https://github.com/myusuf3/dotfiles
- https://github.com/tejr/dotfiles 

## Plugins Used
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
- Syntastic
- Snipmate
- YouCompleteMe
- Star-search
- TPlugin
- Vim-Pasta
- Vim-Startify

## Adding a New Plugin
```bash
  cd .vim
  git submodule init
  git submodule add git://foo/bar bundle/foobar
```

## Installation
- Compile vim from source using YCM installation guide [https://github.com/ycm-core/YouCompleteMe/wiki/Building-Vim-from-source](YCM VIM Installation)
- I prefer those vim configuration flags
```bash
./configure --with-features=huge \
            --enable-multibyte \
	    --with-x \
	    --enable-rubyinterp=yes \
	    --with-ruby-command=/usr/bin/ruby \
	    --enable-python3interp=yes \
	    --with-python3-config-dir=/usr/lib/python3.5/config \
	    --enable-perlinterp=yes \
	    --enable-tclinterp=yes \
	    --enable-luainterp=yes \
            --enable-gui=gtk2 \
            --enable-cscope \
            --enable-fontset \
	   --prefix=/usr/local
```

- required packages
```bash
  sudo apt-get install libncurses5 libncurses5-dev libncursesw5 ncurses-bin ncurses-base ctags ack-grep
  sudo dpkg-divert --local --divert /usr/bin/ack --rename --add /usr/bin/ack-grep
```

- Run install.sh
```bash
./install.sh
```
