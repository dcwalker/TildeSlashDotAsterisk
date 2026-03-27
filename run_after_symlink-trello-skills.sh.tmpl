#!/bin/bash
# Symlink trello-tools skills into all three AI agent skills directories
# and ensure the package is installed.
# Runs after chezmoi apply so symlinks are recreated after exact_ cleanup.

set -euo pipefail

DEV_REPO="$HOME/code/trello-tools"
SHARE_REPO="$HOME/.local/share/trello-tools"

if [ -d "$DEV_REPO" ]; then
    TRELLO_REPO="$DEV_REPO"
    PIP_FLAGS="-e"
    # Clean up the shared clone if the dev repo is now present
    if [ -d "$SHARE_REPO" ]; then
        rm -rf "$SHARE_REPO"
    fi
else
    TRELLO_REPO="$SHARE_REPO"
    PIP_FLAGS=""
fi

TRELLO_SKILLS="$TRELLO_REPO/skills"
SKILLS_DIRS=(
    "$HOME/skills"
)

if [ ! -d "$TRELLO_SKILLS" ]; then
    echo "trello-tools skills not found at $TRELLO_SKILLS, skipping"
    exit 0
fi

# Check if all symlinks already exist — exit early if nothing to do
NEEDS_UPDATE=false
for skills_dir in "${SKILLS_DIRS[@]}"; do
    for skill in "$TRELLO_SKILLS"/*/; do
        skill_name="$(basename "$skill")"
        target="$skills_dir/$skill_name"
        if [ ! -L "$target" ] && [ ! -d "$target" ]; then
            NEEDS_UPDATE=true
            break 2
        fi
    done
done

# Also check if the pip package is installed
if ! python3 -c "import trello_tools" 2>/dev/null; then
    NEEDS_UPDATE=true
fi

if [ "$NEEDS_UPDATE" = false ]; then
    exit 0
fi

# Symlink each skill into all three directories
for skills_dir in "${SKILLS_DIRS[@]}"; do
    mkdir -p "$skills_dir"
    for skill in "$TRELLO_SKILLS"/*/; do
        skill_name="$(basename "$skill")"
        target="$skills_dir/$skill_name"
        # Remove stale symlink or skip if a real directory exists
        if [ -L "$target" ]; then
            rm "$target"
        elif [ -d "$target" ]; then
            continue
        fi
        ln -s "$skill" "$target"
    done
done

# Use a venv on externally-managed Python environments (PEP 668, e.g. Debian Bookworm)
STDLIB_DIR="$(python3 -c 'import sysconfig; print(sysconfig.get_path("stdlib"))' 2>/dev/null)"
if [ -f "${STDLIB_DIR}/EXTERNALLY-MANAGED" ] 2>/dev/null; then
    VENV_DIR="$HOME/.local/share/trello-tools-venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    "$VENV_DIR/bin/pip" install $PIP_FLAGS "$TRELLO_REPO" --quiet
    # Symlink CLI entry points into ~/.local/bin so they're on PATH
    mkdir -p "$HOME/.local/bin"
    for bin_file in "$VENV_DIR/bin"/trello-*; do
        [ -e "$bin_file" ] && ln -sf "$bin_file" "$HOME/.local/bin/$(basename "$bin_file")"
    done
else
    pip install $PIP_FLAGS "$TRELLO_REPO" --quiet
fi
