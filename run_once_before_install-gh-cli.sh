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
        # macOS - install directly from GitHub releases
        ARCH="$(uname -m)"
        case "$ARCH" in
            x86_64) GH_ARCH="amd64" ;;
            arm64)  GH_ARCH="arm64" ;;
            *)
                echo "Error: Unsupported architecture: $ARCH"
                exit 1
                ;;
        esac

        # Get latest version from GitHub API
        GH_VERSION=$(curl -sL https://api.github.com/repos/cli/cli/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
        if [ -z "$GH_VERSION" ]; then
            echo "Error: Could not determine latest gh version"
            exit 1
        fi

        echo "Installing gh v${GH_VERSION} for macOS ${GH_ARCH}..."
        TMPDIR_GH="$(mktemp -d)"
        curl -sL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_macOS_${GH_ARCH}.zip" -o "${TMPDIR_GH}/gh.zip"
        unzip -q "${TMPDIR_GH}/gh.zip" -d "${TMPDIR_GH}"
        mkdir -p "$HOME/bin"
        cp "${TMPDIR_GH}/gh_${GH_VERSION}_macOS_${GH_ARCH}/bin/gh" "$HOME/bin/gh"
        chmod +x "$HOME/bin/gh"
        rm -rf "${TMPDIR_GH}"
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
