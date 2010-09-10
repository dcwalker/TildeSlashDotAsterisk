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
HISTSIZE=50000
export HISTSIZE

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
PS1="$GREEN\u@\h$WHITE:$BLUE\w $LIGHTBLUE\${RAILS_ENV:+(RAILS_ENV=\$RAILS_ENV) }$YELLOW\$(parse_git_branch)$WHITE\$ "


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

###
# SSH Agent setup

# Identifies the path of a unix-domain socket used to communicate with the agent.
SSH_AUTH_SOCK=/tmp/ssh-agent/SSHAuthSock
export SSH_AUTH_SOCK

# If the tmp location for the sock file doesn't
# exist then create it with correct permissions.
if [ ! -d /tmp/ssh-agent ]; then
  mkdir /tmp/ssh-agent
  chmod 700 /tmp/ssh-agent
fi

# If the agent isn't running then start it
if [ ! -S $SSH_AUTH_SOCK ]; then
	# Bind agent to given SSH_AUTH_SOCK
    eval `ssh-agent -a $SSH_AUTH_SOCK`
	# Add keys to agent
    eval `ssh-add`
	# Include private keys outside of the standard id_dsa and id_rsa
	eval `ssh-add $HOME/.ssh/*_dsa`
	eval `ssh-add $HOME/.ssh/*_rsa`
fi


# Special cases based on OS type
case `uname` in
Darwin)
	# Use 32bit Perl instead of 64
	VERSIONER_PERL_PREFER_32_BIT=yes
	export VERSIONER_PERL_PREFER_32_BIT
	# For use in plugins script (http://github.com/nazar/git-rails-plugins)
	GIT_RAILS_PLUGINS_GIT_PATH='/usr/local/git/bin/'
	export GIT_RAILS_PLUGINS_GIT_PATH
	GIT_RAILS_PLUGINS_SVN_PATH='/usr/local/bin/'
	export GIT_RAILS_PLUGINS_SVN_PATH
	# If /Volumes exists then add it to the CDPATH to make navigating easier
	if [ -d /Volumes ]; then
	    CDPATH="$CDPATH:/Volumes"
	fi
	# Use TextMate as editor (http://manual.macromates.com/en/using_textmate_from_terminal.html)
	export EDITOR="mate --wait"
	export GIT_EDITOR="mate --wait --line 1"
	export TEXEDIT='mate --wait --line %d "%s"'
	export LESSEDIT='mate --line %lm %f'
	;;
Linux)
	# Color directory listings
	eval "`dircolors -b`"
	alias ls='ls -h --color=auto'
	# Simulate the 'open' command in OS X
	#alias open='xdg-open'
	alias open='gnome-open 2> /dev/null'
	# If /media exists then add it to the CDPATH to make navigating easier
	if [ -d /media ]; then
	    CDPATH="$CDPATH:/media"
	fi
	# Set the terminal title to user@host:dir (RAILS_ENV) (Git Branch)
	PROMPT_COMMAND='echo -ne "\033]0;${USER}@${HOSTNAME}: ${PWD}${RAILS_ENV:+ (RAILS_ENV=$RAILS_ENV)} $(parse_git_branch)\007"'
	;;
*)
	# A place for non-Darwin/non-Linux configurations
    ;;
esac


###
# Alias definitions

# Who wouldn't want "human readable"
alias ls='ls -h'

# For my co-workers who are addicted to 'll'
alias ll='ls -l'

# Alias mysql to a mysql that includes the defaults-group-suffix option
# This allows for groups in the .my.cnf file to specify host/user/password options
# based on the RAILS_ENV thats set.
alias mysql='mysql --defaults-group-suffix=_$RAILS_ENV'

# RVM config items:
#   RVM documentation says this should be at the end of the config file.
if [[ -s "$HOME/.rvm/scripts/rvm" ]] ; then source "$HOME/.rvm/scripts/rvm" ; fi
if [[ -r $rvm_path/scripts/completion ]] ; then source $rvm_path/scripts/completion ; fi
