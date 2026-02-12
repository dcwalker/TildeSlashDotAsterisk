#!/bin/bash

# Install GitHub CLI if not already installed
# Supports macOS and Linux

set -e

# Check if gh is already installed
if command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is already installed: $(gh --version | head -n 1)"
    exit 0
fi

echo "GitHub CLI (gh) not found. Installing..."

# Detect OS
OS="$(uname -s)"

case "$OS" in
    Darwin*)
        # macOS
        if command -v brew &> /dev/null; then
            echo "Installing gh via Homebrew..."
            brew install gh
        else
            echo "Error: Homebrew not found. Please install Homebrew first:"
            echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
        ;;
    Linux*)
        # Linux
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            case "$ID" in
                ubuntu|debian)
                    echo "Installing gh on Debian/Ubuntu..."
                    sudo mkdir -p -m 755 /etc/apt/keyrings
                    wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
                    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
                    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
                    sudo apt update
                    sudo apt install -y gh
                    ;;
                fedora|rhel|centos)
                    echo "Installing gh on Fedora/RHEL/CentOS..."
                    sudo dnf install -y 'dnf-command(config-manager)'
                    sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
                    sudo dnf install -y gh
                    ;;
                arch|manjaro)
                    echo "Installing gh on Arch/Manjaro..."
                    sudo pacman -S --noconfirm github-cli
                    ;;
                *)
                    echo "Error: Unsupported Linux distribution: $ID"
                    echo "Please install GitHub CLI manually: https://github.com/cli/cli#installation"
                    exit 1
                    ;;
            esac
        else
            echo "Error: Cannot detect Linux distribution"
            echo "Please install GitHub CLI manually: https://github.com/cli/cli#installation"
            exit 1
        fi
        ;;
    *)
        echo "Error: Unsupported operating system: $OS"
        echo "Please install GitHub CLI manually: https://github.com/cli/cli#installation"
        exit 1
        ;;
esac

# Verify installation
if command -v gh &> /dev/null; then
    echo "GitHub CLI successfully installed: $(gh --version | head -n 1)"
else
    echo "Error: GitHub CLI installation failed"
    exit 1
fi
