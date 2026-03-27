#!/bin/bash

# Install dprint - a fast, pluggable code formatter written in Rust.
# Handles JSON, YAML, Markdown, and more without requiring Node.js.
# https://dprint.dev/

# Only install if not already present
if command -v dprint &> /dev/null; then
    echo "dprint is already installed."
    exit 0
fi

# Install dprint via the official install script.
# This places the binary in ~/.dprint/bin/dprint.
echo "Installing dprint..."
curl -fsSL https://dprint.dev/install.sh | sh
echo "dprint installed successfully!"
