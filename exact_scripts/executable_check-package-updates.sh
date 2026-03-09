#!/bin/bash
# Check all package managers for available updates and cache the results.
# Invoked by Launch Agent (macOS) or systemd timer (Linux).
# Results displayed on terminal open via shell_update_checks.

set -euo pipefail

CACHE_DIR="$HOME/.cache/shell-startup"
CACHE_FILE="$CACHE_DIR/package-updates"

mkdir -p "$CACHE_DIR"

# Ensure common tools are in PATH
for dir in "$HOME/.local/bin" "$HOME/.dprint/bin" "/usr/local/bin" "$HOME/Library/Python/3.9/bin" "$HOME/bin" "$HOME/scripts"; do
    [ -d "$dir" ] && PATH="$dir:$PATH"
done

# Load NVM if available (needed for npm check)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

export PATH

check_npm() {
    if command -v npm >/dev/null 2>&1; then
        local outdated_global
        outdated_global=$(npm outdated -g --depth=0 2>/dev/null | tail -n +2) || true
        if [ -n "$outdated_global" ]; then
            local count
            count=$(echo "$outdated_global" | wc -l | tr -d ' ')
            echo "📦 $count global npm packages need updating (npm outdated -g; npm update -g)"
        fi
    fi
}

check_pip() {
    if command -v pip >/dev/null 2>&1; then
        local outdated
        outdated=$(pip list --outdated 2>/dev/null) || true
        if [ -n "$outdated" ]; then
            local count
            count=$(echo "$outdated" | wc -l | tr -d ' ')
            echo "🐍 $count Python packages (global) need updating (pip list --outdated | tail -n +3 | cut -d' ' -f1 | xargs pip install --upgrade)"
        fi
    fi
}

check_rpm() {
    if command -v dnf >/dev/null 2>&1; then
        local outdated
        outdated=$(dnf check-update 2>/dev/null | grep -v "^$" | grep -v "Last metadata" | tail -n +2) || true
        if [ -n "$outdated" ]; then
            local count
            count=$(echo "$outdated" | wc -l | tr -d ' ')
            echo "📦 $count DNF packages need updating (sudo dnf upgrade)"
        fi
    elif command -v yum >/dev/null 2>&1; then
        local outdated
        outdated=$(yum check-update 2>/dev/null | tail -n +2 | grep -v "^$") || true
        if [ -n "$outdated" ]; then
            local count
            count=$(echo "$outdated" | wc -l | tr -d ' ')
            echo "📦 $count YUM packages need updating (sudo yum upgrade)"
        fi
    fi
}

check_apt() {
    if command -v apt >/dev/null 2>&1; then
        local outdated
        outdated=$(apt list --upgradable 2>/dev/null | grep -v "^Listing" | grep -v "^$") || true
        if [ -n "$outdated" ]; then
            local count
            count=$(echo "$outdated" | wc -l | tr -d ' ')
            echo "📦 $count APT packages need updating (sudo apt upgrade)"
        fi
    fi
}

check_cargo() {
    if command -v cargo >/dev/null 2>&1 && command -v cargo-install-update >/dev/null 2>&1; then
        local outdated
        outdated=$(cargo install-update --list 2>/dev/null | grep -v "^$" | tail -n +2) || true
        if [ -n "$outdated" ]; then
            local count
            count=$(echo "$outdated" | wc -l | tr -d ' ')
            echo "🦀 $count Cargo packages need updating (cargo install-update --all)"
        fi
    fi
}

check_mas() {
    if command -v mas >/dev/null 2>&1; then
        local outdated
        outdated=$(mas outdated 2>/dev/null) || true
        if [ -n "$outdated" ]; then
            local count
            count=$(echo "$outdated" | wc -l | tr -d ' ')
            echo "🍎 $count Mac App Store apps need updating (mas upgrade)"
        fi
    fi
}

check_chezmoi() {
    if command -v chezmoi >/dev/null 2>&1; then
        local chezmoi_status
        chezmoi_status=$(chezmoi status 2>/dev/null) || true
        if [ -n "$chezmoi_status" ]; then
            local count
            count=$(echo "$chezmoi_status" | wc -l | tr -d ' ')
            echo "🏠 $count chezmoi dotfile changes pending (chezmoi apply --interactive)"
        fi

        local source_dir
        source_dir="$(chezmoi source-path 2>/dev/null)" || true
        if [ -n "$source_dir" ] && [ -d "$source_dir/.git" ]; then
            git -C "$source_dir" fetch --quiet 2>/dev/null || true
            local behind
            behind=$(git -C "$source_dir" rev-list --count HEAD..@{u} 2>/dev/null) || true
            if [ -n "$behind" ] && [ "$behind" -gt 0 ]; then
                echo "🏠 chezmoi repo is $behind commit(s) behind remote (chezmoi git pull && chezmoi apply --interactive)"
            fi
        fi
    fi
}

check_rustup() {
    if command -v rustup >/dev/null 2>&1; then
        local check_output
        check_output=$(rustup check 2>/dev/null) || true
        if echo "$check_output" | grep -q "Update available"; then
            echo "🦀 rustup updates available (rustup update)"
        fi
    fi
}

check_acli() {
    if command -v acli >/dev/null 2>&1; then
        local version_output
        version_output=$(acli --version 2>/dev/null) || true
        if echo "$version_output" | grep -q "outdated version"; then
            local current latest
            current=$(echo "$version_output" | grep "outdated version" | sed -n 's/.*outdated version \([0-9.-]*[a-z]*\)\..*/\1/p')
            latest=$(echo "$version_output" | grep "outdated version" | sed -n 's/.*latest version \([0-9.-]*[a-z]*\)\..*/\1/p')
            echo "⚡ acli update available: $current → $latest (see https://developer.atlassian.com/cloud/acli/guides/install-acli/)"
        fi
    fi
}

check_dprint() {
    if command -v dprint >/dev/null 2>&1 && command -v chezmoi >/dev/null 2>&1; then
        local current
        current=$(dprint --version 2>/dev/null | awk '{print $2}') || true
        if [ -n "$current" ]; then
            local latest
            latest=$(chezmoi execute-template '{{ (gitHubLatestRelease "dprint/dprint").TagName }}' 2>/dev/null) || true
            if [ -n "$latest" ] && [ "$current" != "$latest" ]; then
                echo "📝 dprint update available: $current → $latest (curl -fsSL https://dprint.dev/install.sh | sh)"
            fi
        fi
    fi
}

check_external_repos() {
    local repos=(
        "$HOME/code/trello-tools"
        "$HOME/.local/share/trello-tools"
        "$HOME/code/personal-ai-and-coding-standards"
    )

    for repo in "${repos[@]}"; do
        [ -d "$repo/.git" ] || continue
        local name
        name=$(basename "$repo")

        # Check for uncommitted changes
        local dirty
        dirty=$(git -C "$repo" status --porcelain 2>/dev/null) || true
        if [ -n "$dirty" ]; then
            local count
            count=$(echo "$dirty" | wc -l | tr -d ' ')
            echo "📂 $name has $count uncommitted change(s) (cd $repo && git status)"
        fi

        # Check if behind remote
        git -C "$repo" fetch --quiet 2>/dev/null || true
        local behind
        behind=$(git -C "$repo" rev-list --count HEAD..@{u} 2>/dev/null) || true
        if [ -n "$behind" ] && [ "$behind" -gt 0 ]; then
            echo "📂 $name is $behind commit(s) behind remote (cd $repo && git pull)"
        fi

        # Check if ahead of remote (unpushed commits)
        local ahead
        ahead=$(git -C "$repo" rev-list --count @{u}..HEAD 2>/dev/null) || true
        if [ -n "$ahead" ] && [ "$ahead" -gt 0 ]; then
            echo "📂 $name has $ahead unpushed commit(s) (cd $repo && git push)"
        fi
    done
}

# Run all checks, write to temp file, then atomically move into place
{
    check_npm
    check_pip
    check_rpm
    check_apt
    check_cargo
    check_mas
    check_chezmoi
    check_external_repos
    check_rustup
    check_acli
    check_dprint
} > "$CACHE_FILE.tmp" 2>/dev/null

mv "$CACHE_FILE.tmp" "$CACHE_FILE"
