# TildeSlashDotAsterisk

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).

This repo originated in January 2010 and was migrated to chezmoi on February 5, 2026.

## Documentation

- [chezmoi homepage](https://www.chezmoi.io/)
- [chezmoi user guide](https://www.chezmoi.io/user-guide/command-overview/)
- [chezmoi reference](https://www.chezmoi.io/reference/)

## Quick Reference

### Keep a host up to date

Pull the latest changes from the repo and apply them:

```sh
chezmoi update
```

This runs `git pull` in the source directory and then applies any changes.

### Update chezmoi after editing a managed file directly

If you've edited a dotfile in your home directory (e.g. `~/.zshrc`) and want to
capture those changes back into chezmoi:

```sh
chezmoi re-add
```

Or for a specific file:

```sh
chezmoi add ~/.zshrc
```

### Review pending changes before applying

To see what chezmoi would change based on the local source directory:

```sh
chezmoi diff
```

To include the latest remote changes in the diff, pull first:

```sh
chezmoi git pull && chezmoi diff
```

### Set up a new host (fresh install)

Install chezmoi and initialize it with this repo in one command:

```sh
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply dcwalker/TildeSlashDotAsterisk
```

This installs chezmoi, clones the repo, and applies all configs. You will be
prompted to provide values for any template variables (name, email, etc.).

### Set up a new host without overwriting existing configs

If the host already has dotfiles you want to review before overwriting, initialize
without applying:

```sh
sh -c "$(curl -fsLS get.chezmoi.io)" -- init dcwalker/TildeSlashDotAsterisk
```

Then compare what chezmoi would change:

```sh
chezmoi diff
```

Review individual files:

```sh
chezmoi diff ~/.zshrc
chezmoi diff ~/.gitconfig
```

Merge changes interactively where needed:

```sh
chezmoi merge ~/.zshrc
```

Once satisfied, apply everything:

```sh
chezmoi apply
```

Or apply one file at a time:

```sh
chezmoi apply ~/.zshrc
```
