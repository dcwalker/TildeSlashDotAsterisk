set background=dark

syntax enable
set tabstop=4
set expandtab
set list
set listchars=tab:>-
set autoindent
set cindent
set cinoptions=>4
set pastetoggle=<F12>
:filetype on
set wildmode=longest,list,full
set wildmenu
hi MatchParen ctermbg=darkgreen ctermfg=white
set nohlsearch
set ignorecase
set smartcase
set incsearch
hi Pmenu        ctermbg=black
hi PmenuSel     ctermbg=green
hi PmenuSbar    ctermbg=blue
hi PmenuThumb   ctermfg=yellow
set laststatus=2
set statusline=%1*\ %f\ %2*%y\ %4*%r\ %m%=%3*%(<%c,%l/%L>%3p%%%)\
hi User1 ctermfg=green ctermbg=blue
hi User2 ctermfg=cyan ctermbg=blue
hi User3 ctermfg=yellow ctermbg=blue
hi User4 ctermfg=red ctermbg=blue
autocmd BufReadPost *
            \ if line("'\"") > 0 && line("'\"") <= line("$") |
            \ exe "normal g`\"" |
            \ endif
nmap <silent> <F3> :set nu! <CR>
nmap <silent> <F4>  : if &background == 'dark' <CR>
            \set background=light <CR>
            \else <CR>
            \set background=dark <CR>
            \endif <CR>
map <silent> <F5> :call Tidy() <CR>

function! Tidy() range abort
    let savelnum = line(".")
    if &ft == 'perl'
        if a:firstline == a:lastline
            exe  "%!perltidy -q"
        else
            silent exe a:firstline .",". a:lastline ."!perltidy -q"
        endif
    else
        exe  "%!tidy"
    endif
    exec "normal " . savelnum . "G"
endfunction

autocmd FileType gitcommit set textwidth=72
map <silent> <F7> :call Comment() <CR>
function! Comment() range abort
    let lnum = a:firstline
    let lend = a:lastline
    if lnum == lend
        "no visual area, just do one line
        let lnum = line(".")
        let lend = line(".")
    endif
    exec ":". lnum .",". lend . "s/^/#/e"
endfunction

map <silent> <F8> :call UnComment() <CR>
function! UnComment() range abort
    let lnum = a:firstline
    let lend = a:lastline
    if lnum == lend
        "no visual area, just do one line
        let lnum = line(".")
        let lend = line(".")
    endif
    exec ":". lnum .",". lend . "s/#//e"
endfunction

function! InsertTabWrapper(direction)
    let col = col('.') - 1
    if !col || getline('.')[col - 1] !~ '\k'
        return "\<tab>"
    elseif "backward" == a:direction
        return "\<c-p>"
    elseif "forward" == a:direction
        return "\<c-n>"
    else
        return "\<c-x>\<c-k>"
    endif
endfunction
inoremap <tab> <c-r>=InsertTabWrapper ("forward")<cr>
inoremap <s-tab> <c-r>=InsertTabWrapper ("backward")<cr>
inoremap <c-tab> <c-r>=InsertTabWrapper ("startkey")<cr>

nmap <silent> <F9> :resize <CR>
nmap <silent> <F10> :wincmd w<CR> :resize <CR>


function! BufSel(pattern)
  let bufcount = bufnr("$")
  let currbufnr = 1
  let nummatches = 0
  let firstmatchingbufnr = 0
  while currbufnr <= bufcount
    if(bufexists(currbufnr))
      let currbufname = bufname(currbufnr)
      if(match(currbufname, a:pattern) > -1)
        echo currbufnr . ": ". bufname(currbufnr)
        let nummatches += 1
        let firstmatchingbufnr = currbufnr
      endif
    endif
    let currbufnr = currbufnr + 1
  endwhile
  if(nummatches == 1)
    execute ":buffer ". firstmatchingbufnr
  elseif(nummatches > 1)
    let desiredbufnr = input("Enter buffer number: ")
    if(strlen(desiredbufnr) != 0)
      execute ":buffer ". desiredbufnr
    endif
  else
    echo "No matching buffers"
  endif
endfunction

command! -nargs=1 Bs :call BufSel("<args>")
