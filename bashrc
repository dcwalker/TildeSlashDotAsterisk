###
# Set PATH

# Add alternative bin locations
if [ -d /usr/local/bin ]; then
	PATH="$PATH:/usr/local/bin"
fi
if [ -d /opt/local/bin ]; then
	PATH="$PATH:/opt/local/bin"
fi
for directory in /usr/local/*/bin
do
	PATH="$PATH:${directory}"
done

# Ruby specific bin
if [ -d /var/lib/gems/1.8/bin ]; then
	PATH="$PATH:/var/lib/gems/1.8/bin"
fi
if [ -d $HOME/.gem/ruby/1.8/bin ]; then
	PATH="$PATH:$HOME/.gem/ruby/1.8/bin"
fi

# Include bin from home directory
if [ -d ~/bin ]; then
    PATH="$HOME/bin:$PATH"
fi

# Look for directories in home that have a bin directory,
# if found then add the directory to the front of PATH.
# This allows you to build your own versions and keep them organized.
# ex: If you have gnutar compiled and the binary in ~/gnutar/bin then
#     this will find it and put at the front of your path so it
#     overrides the system version.
for directory in $HOME/*/bin
do
	PATH="${directory}:$PATH"
done


export PATH


# If not running interactively, don't do anything more
if [ -z "$PS1" ]; then
   return
fi

# Make bash check its window size after a process completes
shopt -s checkwinsize

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(lesspipe)"

## cdspell
# If set, minor errors in the spelling of a directory component in a cd command will be corrected.
# The errors checked for are transposed characters, a missing character, and a character too many.
# If a correction is found, the corrected path is printed, and the command proceeds.
# This option is only used by interactive shells.
shopt -s cdspell

## histappend
# If set, the history list is appended to the file named by the value of the HISTFILE variable
# when the shell exits, rather than overwriting the file.
shopt -s histappend

# Include bash_completion if available
if [ -d $HOME/.bash_completion.d ]; then
    BASH_COMPLETION_DIR="$BASH_COMPLETION_DIR:$HOME/.bash_completion.d"
  	export BASH_COMPLETION_DIR
    for extra_completion in $HOME/.bash_completion.d/*
    do
    	source ${extra_completion}
    done
fi
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
fi
if [ -f $HOME/.bash_completion ]; then
	BASH_COMPLETION="$HOME/.bash_completion"
	export BASH_COMPLETION
	source $HOME/.bash_completion
fi


# Pull in aliases from .bash_aliases if it exists
if [ -f $HOME/.bash_aliases ]; then
    . $HOME/.bash_aliases
fi


# Ignore duplicate lines in bash history
HISTCONTROL=ignoredups
export HISTCONTROL

# Create a big history file for expanded ^r use
HISTSIZE=5000000
export HISTSIZE

# Ignore common commands
# [ \t]* means ignore any command that starts with a space
HISTIGNORE="[ \t]*:ls:cd:[bf]g:exit:history:h"
export HISTIGNORE

# Share history file in dropbox if available
if [ -d $HOME/Dropbox ]; then
  HISTFILE=$HOME/Dropbox/bash_history
  export HISTFILE
fi

###
# Setup command prompt

# Function to determine git branch for current directory
function parse_git_branch {
      ref=$(git symbolic-ref HEAD 2> /dev/null) || return
              echo "("${ref#refs/heads/}") "
}

# Easy to read color names
RED="\[\033[0;31m\]"
YELLOW="\[\033[0;33m\]"
GREEN="\[\033[01;32m\]"
WHITE="\[\033[00m\]"
BLUE="\[\033[01;34m\]"
LIGHTBLUE="\[\033[01;36m\]"

# user at host (green) colon (white) present working directory (blue) RAILS_ENV value [if available] (light blue) current Git branch (yellow) dollar sign (white) single space
PS1="$GREEN\u@\h$WHITE:$BLUE\w $LIGHTBLUE\${RAILS_ENV:+(RAILS_ENV=\$RAILS_ENV) }$YELLOW\$(parse_git_branch)$WHITE(!\!) \$ "

# Whenever displaying the prompt:
# 1. write the previous command to the history
# 2. clear the history list for the current session
# 3. read in a fresh history list from the histroy file
# result: command history in sync across all terminals without having to exit
PROMPT_COMMAND='history -a; history -c; history -r'

# Make CPAN not be uselessly slow
FTP_PASSIVE="1"
export FTP_PASSIVE

# Include home directory in CDPATH
CDPATH='.:~'
export CDPATH

# Default editor is vim if available
if [ -x /usr/bin/vim ]; then
	EDITOR="/usr/bin/vim"
	export EDITOR
fi

# Default pager is less
PAGER=less
export PAGER
LESS="--status-column --long-prompt --no-init --quit-if-one-screen --quit-at-eof -R"
export LESS

# Special cases based on OS type
case `uname` in
Darwin)
  if [ -f $HOME/.bash_darwin ]; then
      . $HOME/.bash_darwin
  fi
  ;;
Linux)
  if [ -f $HOME/.bash_linux ]; then
      . $HOME/.bash_linux
  fi
	;;
CYGWIN*)
  if [ -f $HOME/.bash_cygwin ]; then
      . $HOME/.bash_cygwin
  fi
	;;
*)
	# A place for non-Darwin/non-Linux configurations
    ;;
esac

# List loaded ssh keys when terminal opens
# (a reminder of any keys that might have expired with the key agent)
ssh-add -l

# Pull in local (unshared) config from .bash_local if it exists
if [ -f $HOME/.bash_local ]; then
    . $HOME/.bash_local
fi

# RVM config items:
#   RVM documentation says this should be at the end of the config file.
if [[ -s "$HOME/.rvm/scripts/rvm" ]] ; then source "$HOME/.rvm/scripts/rvm" ; fi
if [[ -r $rvm_path/scripts/completion ]] ; then source $rvm_path/scripts/completion ; fi
