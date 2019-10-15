# Marwan Osman's Dot Files
Configurations and dotfiles for my development machine.

## Vim Plugins Used (Managed by vim-plug)
- Ack
- Ctrlp
- Fugitive
- Python-mode
- Tagbar
- Gundo (disabled till it upgrades to py3)
- Nerdtree
- Vim-Powerline
- Vim-Rails
- Vim-Javascript
- Vim-browser-reload-linux
- Numbers.vim
- Vim-Pasta
- Star-search
- Vim-Startify
- YouCompleteMe
- YCM-Generator
- #Syntastic
- Ale
- Ultisnips
- vim-indent-guides
- vim-surround
- vim-snippets
- vim-better-whitespace
- Nercommenter
- html5.vim
- vim.jsx
- vim-prettier
- vim-ros (disabled till it upgrades to py3)

## Adding a New Plugin
Add your new plugin to the vimrc file using vim-plug, e.g.:
```
  Plug 'scrooloose/nerdtree'
```

## Installation
- required packages
```bash
  sudo apt-get install libncurses5 libncurses5-dev libncursesw5 ncurses-bin ncurses-base ctags ack-grep clang
  sudo dpkg-divert --local --divert /usr/bin/ack --rename --add /usr/bin/ack-grep
```

- Compile vim from source using YCM installation guide [https://github.com/ycm-core/YouCompleteMe/wiki/Building-Vim-from-source](YCM VIM Installation)
- Those are my prefered vim configuration flags
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

- Run install.sh (Caution: Revise before running)
```bash
./install.sh
```

- Open vim and run `:PlugInstall`
