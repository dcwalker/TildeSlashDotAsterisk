#!/bin/bash
# Clone the personal-ai-and-coding-standards repo to ~/code/ if not already present.
# This repo is monitored by check-package-updates.sh for out-of-date or dirty state
# and notifications are shown when opening a terminal.

set -euo pipefail

REPO_DIR="$HOME/code/personal-ai-and-coding-standards"

if [ -d "$REPO_DIR" ]; then
  echo "personal-ai-and-coding-standards already cloned at $REPO_DIR"
  exit 0
fi

mkdir -p "$HOME/code"

echo "Cloning personal-ai-and-coding-standards to $REPO_DIR..."
git clone https://github.com/dcwalker/personal-ai-and-coding-standards.git "$REPO_DIR"
echo "Done."
