#!/bin/bash

# Install oh-my-zsh custom plugins
# Only runs if oh-my-zsh is installed

# Check if oh-my-zsh is installed
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    echo "oh-my-zsh is not installed. Skipping plugin installation."
    exit 0
fi

ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"

# Install zsh-syntax-highlighting
if [ ! -d "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting" ]; then
    echo "Installing zsh-syntax-highlighting plugin..."
    git clone https://github.com/zsh-users/zsh-syntax-highlighting.git "$ZSH_CUSTOM/plugins/zsh-syntax-highlighting"
    echo "zsh-syntax-highlighting plugin installed successfully!"
else
    echo "zsh-syntax-highlighting plugin is already installed."
fi
