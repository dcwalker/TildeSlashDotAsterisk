#!/usr/bin/env python3
"""
Import skills into the chezmoi-managed skills setup.

Scans the home directory and the current working directory for skills
directories (folders containing subdirectories with SKILL.md files).
Lists any skills not already managed by chezmoi and allows interactive
multi-select to import them.

Imported skills are copied directly into exact_skills/<name>/ in the
chezmoi source directory. Symlinks from ~/.claude/skills, ~/.cursor/skills,
and ~/.codex/skills all point to ~/skills/, so a single copy serves all
three tools.

Usage:
  import-skills.py [OPTIONS]

Examples:
  import-skills.py
  import-skills.py --scan-dir /path/to/project
  import-skills.py --dry-run
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

CHEZMOI_DIR = Path.home() / ".local" / "share" / "chezmoi"
SKILLS_DIR = CHEZMOI_DIR / "exact_skills"
SKILL_FILENAME = "SKILL.md"
SCRIPTS_SUBDIR = "scripts"


def get_chezmoi_skill_names() -> Set[str]:
    """Return the set of skill names already managed by chezmoi."""
    if not SKILLS_DIR.is_dir():
        return set()
    return {
        entry.name
        for entry in SKILLS_DIR.iterdir()
        if entry.is_dir() and (entry / SKILL_FILENAME).is_file()
    }


def find_skills_dirs(scan_dirs: List[Path]) -> List[Path]:
    """Find directories that contain skill subdirectories (with SKILL.md)."""
    found: List[Path] = []
    seen: Set[Path] = set()

    for base in scan_dirs:
        if not base.is_dir():
            continue
        candidates = [base / "skills"]
        for tool_dir in (".cursor", ".claude", ".codex"):
            candidates.append(base / tool_dir / "skills")

        for candidate in candidates:
            if not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            has_skill = any(
                (entry / SKILL_FILENAME).is_file()
                for entry in candidate.iterdir()
                if entry.is_dir()
            )
            if has_skill:
                seen.add(resolved)
                found.append(candidate)

    return found


def discover_importable_skills(
    skills_dirs: List[Path], existing: Set[str]
) -> List[Tuple[str, Path]]:
    """Find skills in discovered directories that are not already in chezmoi."""
    importable: Dict[str, Path] = {}
    for skills_dir in skills_dirs:
        for entry in sorted(skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / SKILL_FILENAME).is_file():
                continue
            name = entry.name
            if name in existing:
                continue
            if name not in importable:
                importable[name] = entry
    return sorted(importable.items())


def get_skill_description(skill_dir: Path) -> str:
    """Extract the description from a SKILL.md frontmatter."""
    skill_md = skill_dir / SKILL_FILENAME
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        desc_match = re.search(
            r"^description:\s*(.+)$", fm_match.group(1), re.MULTILINE
        )
        if desc_match:
            desc = desc_match.group(1).strip()
            if len(desc) > 100:
                return desc[:97] + "..."
            return desc
    return ""


def prompt_selection(
    skills: List[Tuple[str, Path]],
) -> List[Tuple[str, Path]]:
    """Present an interactive multi-select prompt and return chosen skills."""
    print("\nSkills available to import:")
    for i, (name, path) in enumerate(skills, 1):
        desc = get_skill_description(path)
        source = f" ({path.parent})"
        if desc:
            print(f"{i}. {name}{source} - {desc}")
        else:
            print(f"{i}. {name}{source}")

    print(f"\nYou can select multiple items by entering numbers separated by commas or spaces.")
    print(f"Examples: '1,3,5' or '1 3 5' or '1-3' for ranges")
    print(f"Enter 'all' to select all items, or press Ctrl+C to cancel.")

    while True:
        try:
            choice = input("Enter selection: ").strip().lower()

            if not choice:
                return []

            if choice == "all":
                return list(skills)

            selected: List[Tuple[str, Path]] = []
            parts = choice.replace(",", " ").split()

            for part in parts:
                part = part.strip()
                if "-" in part:
                    try:
                        start, end = map(int, part.split("-"))
                        if start > end:
                            start, end = end, start
                        for i in range(start, end + 1):
                            index = i - 1
                            if 0 <= index < len(skills):
                                if skills[index] not in selected:
                                    selected.append(skills[index])
                            else:
                                print(f"Invalid choice: {i} (must be between 1 and {len(skills)})")
                    except ValueError:
                        print(f"Invalid range format: {part}")
                        continue
                else:
                    try:
                        index = int(part) - 1
                        if 0 <= index < len(skills):
                            if skills[index] not in selected:
                                selected.append(skills[index])
                        else:
                            print(f"Invalid choice: {part} (must be between 1 and {len(skills)})")
                    except ValueError:
                        print(f"Invalid input: {part}")
                        continue

            if selected:
                return selected

            print("No valid selections made. Please try again.")

        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(1)


def plan_skill_import(
    skill_name: str, skill_dir: Path
) -> List[Tuple[str, Path, Path]]:
    """Plan the import actions for a single skill.

    Returns a list of (action_type, source_path, dest_path) tuples.
    Files are copied directly into exact_skills/<name>/.
    Scripts get the executable_ prefix for chezmoi.
    """
    actions: List[Tuple[str, Path, Path]] = []
    dest_base = SKILLS_DIR / skill_name

    for entry in sorted(skill_dir.rglob("*")):
        if not entry.is_file():
            continue
        if entry.name in (".DS_Store",):
            continue

        rel = entry.relative_to(skill_dir)

        # Scripts need the executable_ prefix for chezmoi
        if rel.parts[0] == SCRIPTS_SUBDIR and len(rel.parts) == 2:
            script_name = rel.parts[1]
            if not script_name.startswith("executable_"):
                dest = dest_base / SCRIPTS_SUBDIR / f"executable_{script_name}"
            else:
                dest = dest_base / rel
        else:
            dest = dest_base / rel

        actions.append(("copy", entry, dest))

    return actions


def print_action_preview(
    skill_name: str, actions: List[Tuple[str, Path, Path]]
) -> None:
    """Print a preview of the planned actions for a skill."""
    print(f"  {skill_name}:")
    for action_type, source, dest in actions:
        dest_rel = str(dest.relative_to(CHEZMOI_DIR))
        print(f"    Copy {source.name} -> {dest_rel}")


def execute_actions(actions: List[Tuple[str, Path, Path]]) -> None:
    """Execute the planned import actions."""
    for action_type, source, dest in actions:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)


def confirm(prompt: str) -> bool:
    """Prompt the user for yes/no confirmation."""
    while True:
        try:
            choice = input(f"{prompt} (y/n): ").strip().lower()
            if choice in ("y", "yes"):
                return True
            if choice in ("n", "no"):
                return False
            print("Please enter 'y' or 'n'.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import skills into chezmoi for deployment to Cursor, Claude, "
            "and Codex."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scans for skills directories in:
  - Home directory (~/.cursor/skills, ~/.claude/skills, ~/.codex/skills)
  - Current working directory and its tool subdirectories

Examples:
  import-skills.py
  import-skills.py --scan-dir /path/to/project
  import-skills.py --dry-run
""",
    )
    parser.add_argument(
        "--scan-dir",
        action="append",
        default=[],
        type=Path,
        help="Additional directory to scan for skills (can be repeated)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    home = Path.home()
    cwd = Path.cwd()

    scan_dirs = [home, cwd] + args.scan_dir

    print("Scanning for skills...")
    for d in scan_dirs:
        print(f"  {d}")

    skills_dirs = find_skills_dirs(scan_dirs)

    if not skills_dirs:
        print("\nNo skills directories found.")
        sys.exit(0)

    print("\nFound skills directories:")
    for d in skills_dirs:
        print(f"  {d}")

    existing = get_chezmoi_skill_names()

    importable = discover_importable_skills(skills_dirs, existing)

    if not importable:
        print("\nAll discovered skills are already in chezmoi.")
        sys.exit(0)

    selected = prompt_selection(importable)
    if not selected:
        print("\nNo skills selected.")
        sys.exit(0)

    planned: List[Tuple[str, Path, List[Tuple[str, Path, Path]]]] = []
    for skill_name, skill_dir in selected:
        actions = plan_skill_import(skill_name, skill_dir)
        planned.append((skill_name, skill_dir, actions))

    print("\nThe following changes will be made:")
    for skill_name, _skill_dir, actions in planned:
        print_action_preview(skill_name, actions)

    if args.dry_run:
        print("\nDry run complete. No changes were made.")
        sys.exit(0)

    print()
    if not confirm("Proceed with import?"):
        print("Import cancelled.")
        sys.exit(0)

    print()
    for skill_name, _skill_dir, actions in planned:
        print(f"Importing {skill_name}...")
        execute_actions(actions)

    print("\nImport complete.")
    print("Run 'chezmoi apply' to deploy skills to all tools.")


if __name__ == "__main__":
    main()
