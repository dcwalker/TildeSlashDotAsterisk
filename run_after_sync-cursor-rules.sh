#!/bin/bash
# Sync personal rules into local repos for Cursor.
# - Copies ~/rules/* into each ~/code/*/.cursor/rules/
# - Tracks synced files in .git/info/exclude using a managed block
# - Removes stale synced files that were previously managed

set -euo pipefail

RULES_DIR="$HOME/rules"
CODE_DIR="$HOME/code"
BLOCK_START="# >>> cursor-rules (managed by chezmoi) >>>"
BLOCK_END="# <<< cursor-rules (managed by chezmoi) <<<"

if [ ! -d "$CODE_DIR" ]; then
    echo "code directory not found at $CODE_DIR, skipping"
    exit 0
fi

if [ ! -d "$RULES_DIR" ]; then
    echo "rules directory not found at $RULES_DIR, skipping"
    exit 0
fi

get_rule_files() {
    find "$RULES_DIR" -type f \( -name "*.md" -o -name "*.mdc" \) -print
}

get_managed_block_paths() {
    local exclude_file="$1"
    [ -f "$exclude_file" ] || return 0

    awk -v start="$BLOCK_START" -v end="$BLOCK_END" '
        $0 == start { in_block = 1; next }
        $0 == end { in_block = 0; next }
        in_block && NF > 0 { print }
    ' "$exclude_file"
}

rewrite_exclude_with_block() {
    local exclude_file="$1"
    shift
    local new_paths=("$@")
    local tmp
    tmp="$(mktemp)"

    if [ -f "$exclude_file" ]; then
        awk -v start="$BLOCK_START" -v end="$BLOCK_END" '
            $0 == start { in_block = 1; next }
            $0 == end { in_block = 0; next }
            !in_block { print }
        ' "$exclude_file" > "$tmp"
    fi

    if [ "${#new_paths[@]}" -gt 0 ]; then
        {
            [ -s "$tmp" ] && [ "$(tail -n 1 "$tmp" 2>/dev/null || true)" != "" ] && echo ""
            echo "$BLOCK_START"
            printf "%s\n" "${new_paths[@]}" | LC_ALL=C sort -u
            echo "$BLOCK_END"
        } >> "$tmp"
    fi

    mkdir -p "$(dirname "$exclude_file")"
    mv "$tmp" "$exclude_file"
}

prune_empty_rule_dirs() {
    local repo_root="$1"
    local dir="$2"
    while [ "$dir" != "$repo_root" ] && [ "$dir" != "/" ]; do
        rmdir "$dir" 2>/dev/null || break
        dir="$(dirname "$dir")"
    done
}

sync_repo_rules() {
    local repo="$1"
    local rules_target="$repo/.cursor/rules"
    local exclude_file="$repo/.git/info/exclude"
    local src rel dest old
    local -a new_paths=()
    local -a old_paths=()

    mkdir -p "$rules_target"

    while IFS= read -r old; do
        [ -n "$old" ] || continue
        old_paths+=("$old")
    done < <(get_managed_block_paths "$exclude_file" || true)

    while IFS= read -r src; do
        [ -n "$src" ] || continue
        rel="${src#$RULES_DIR/}"
        dest="$rules_target/$rel"
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        new_paths+=(".cursor/rules/$rel")
    done < <(get_rule_files)

    # Remove stale files that were managed before but are not managed now.
    for old in "${old_paths[@]-}"; do
        local keep=false
        for rel in "${new_paths[@]-}"; do
            if [ "$old" = "$rel" ]; then
                keep=true
                break
            fi
        done
        if [ "$keep" = false ] && [ -f "$repo/$old" ]; then
            rm -f "$repo/$old"
            prune_empty_rule_dirs "$repo" "$(dirname "$repo/$old")"
        fi
    done

    rewrite_exclude_with_block "$exclude_file" "${new_paths[@]}"
}

for repo in "$CODE_DIR"/*; do
    [ -d "$repo" ] || continue
    [ -d "$repo/.git" ] || continue
    sync_repo_rules "$repo"
done

