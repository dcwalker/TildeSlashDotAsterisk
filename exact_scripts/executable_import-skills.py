#!/usr/bin/env python3
"""
Import skills into the chezmoi-managed skills setup.

Scans the home directory and the current working directory for skills
directories (folders containing subdirectories with SKILL.md files).
Lists any skills not already managed by chezmoi and allows interactive
multi-select to import them.

Imported skills are set up following the single-source-of-truth pattern:
  - Source templates stored as .skills-*.md.tmpl and .scripts-*.tmpl
  - Template references created in dot_cursor, dot_claude, and dot_codex
  - Running chezmoi apply deploys identical copies to all three tools

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
from typing import Dict, List, Optional, Set, Tuple

CHEZMOI_DIR = Path.home() / ".local" / "share" / "chezmoi"
TOOLS = ("cursor", "claude", "codex")
SKILL_FILENAME = "SKILL.md"
SCRIPTS_SUBDIR = "scripts"


def get_chezmoi_skill_names() -> Set[str]:
    """Return the set of skill names already managed by chezmoi."""
    skills_dir = CHEZMOI_DIR / "dot_claude" / "exact_skills"
    if not skills_dir.is_dir():
        return set()
    return {
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir() and (entry / f"{SKILL_FILENAME}.tmpl").is_file()
    }


def find_skills_dirs(scan_dirs: List[Path]) -> List[Path]:
    """Find directories that contain skill subdirectories (with SKILL.md)."""
    found: List[Path] = []
    seen: Set[Path] = set()

    for base in scan_dirs:
        if not base.is_dir():
            continue
        # Look for 'skills' directories within the base and one level of tool dirs
        candidates = [base / "skills"]
        for tool_dir in (".cursor", ".claude", ".codex"):
            candidates.append(base / tool_dir / "skills")

        for candidate in candidates:
            if not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            # Verify it contains at least one skill subdirectory
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


def classify_skill_files(
    skill_dir: Path,
) -> Tuple[Path, List[Path], List[Path]]:
    """Classify files in a skill directory.

    Returns:
        (skill_md, extra_mds, scripts)
        - skill_md: the SKILL.md file
        - extra_mds: additional .md files in the skill root
        - scripts: executable files in the scripts/ subdirectory
    """
    skill_md = skill_dir / SKILL_FILENAME
    extra_mds: List[Path] = []
    scripts: List[Path] = []

    for entry in sorted(skill_dir.iterdir()):
        if entry.is_file() and entry.name != SKILL_FILENAME:
            if entry.suffix == ".md":
                extra_mds.append(entry)
            # Other non-md files at the root are treated as extra content
            elif entry.name not in (".DS_Store",):
                extra_mds.append(entry)

    scripts_dir = skill_dir / SCRIPTS_SUBDIR
    if scripts_dir.is_dir():
        for entry in sorted(scripts_dir.iterdir()):
            if entry.is_file() and entry.name not in (".DS_Store",):
                scripts.append(entry)

    return skill_md, extra_mds, scripts


def derive_source_template_name(skill_name: str, filename: str) -> str:
    """Derive the chezmoi source template name for a skill file.

    SKILL.md -> .skills-<skill_name>.md.tmpl
    extra-doc.md -> .skills-<skill_name>-<stem>.md.tmpl
    """
    stem = Path(filename).stem
    suffix = Path(filename).suffix

    if filename == SKILL_FILENAME:
        return f".skills-{skill_name}{suffix}.tmpl"

    return f".skills-{skill_name}-{stem}{suffix}.tmpl"


def derive_script_template_name(filename: str) -> str:
    """Derive the chezmoi source template name for a script file.

    my-script.py -> .scripts-my-script.py.tmpl
    """
    return f".scripts-{filename}.tmpl"


def derive_tool_script_name(filename: str) -> str:
    """Derive the chezmoi tool-directory name for a script.

    my-script.py -> executable_my-script.py.tmpl
    """
    return f"executable_{filename}.tmpl"


def derive_tool_extra_name(filename: str) -> str:
    """Derive the chezmoi tool-directory name for an extra file.

    extra-doc.md -> extra-doc.md.tmpl
    """
    return f"{filename}.tmpl"


def plan_skill_import(
    skill_name: str, skill_dir: Path
) -> List[Tuple[str, Path, Path]]:
    """Plan the import actions for a single skill. Returns a list of actions."""
    skill_md, extra_mds, scripts = classify_skill_files(skill_dir)

    actions: List[Tuple[str, Path, Path]] = []

    # 1. Create source template for SKILL.md
    src_tmpl_name = derive_source_template_name(skill_name, SKILL_FILENAME)
    src_tmpl_path = CHEZMOI_DIR / src_tmpl_name
    actions.append(("source-template", skill_md, src_tmpl_path))

    # 2. Create source templates for extra markdown/content files
    extra_src_names: Dict[str, str] = {}
    for extra in extra_mds:
        src_name = derive_source_template_name(skill_name, extra.name)
        src_path = CHEZMOI_DIR / src_name
        actions.append(("source-template", extra, src_path))
        extra_src_names[extra.name] = src_name

    # 3. Create source templates for scripts
    script_src_names: Dict[str, str] = {}
    for script in scripts:
        src_name = derive_script_template_name(script.name)
        src_path = CHEZMOI_DIR / src_name
        actions.append(("source-template", script, src_path))
        script_src_names[script.name] = src_name

    # 4. Create tool-specific template references for each tool
    for tool in TOOLS:
        tool_skill_dir = (
            CHEZMOI_DIR / f"dot_{tool}" / "exact_skills" / skill_name
        )

        # SKILL.md.tmpl reference
        actions.append((
            "tool-reference",
            Path(src_tmpl_name),
            tool_skill_dir / f"{SKILL_FILENAME}.tmpl",
        ))

        # Extra file references
        for extra in extra_mds:
            actions.append((
                "tool-reference",
                Path(extra_src_names[extra.name]),
                tool_skill_dir / derive_tool_extra_name(extra.name),
            ))

        # Script references
        if scripts:
            for script in scripts:
                actions.append((
                    "tool-reference",
                    Path(script_src_names[script.name]),
                    tool_skill_dir / SCRIPTS_SUBDIR / derive_tool_script_name(script.name),
                ))

    return actions


def print_action_preview(
    skill_name: str, actions: List[Tuple[str, Path, Path]]
) -> None:
    """Print a preview of the planned actions for a skill."""
    print(f"  {skill_name}:")
    for action_type, source, dest in actions:
        dest_rel = str(dest.relative_to(CHEZMOI_DIR))
        if action_type == "source-template":
            print(f"    Copy {source.name} -> {dest_rel}")
        elif action_type == "tool-reference":
            print(f"    Create reference {dest_rel}")


def execute_actions(actions: List[Tuple[str, Path, Path]]) -> None:
    """Execute the planned import actions."""
    for action_type, source, dest in actions:
        if action_type == "source-template":
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        elif action_type == "tool-reference":
            include_name = str(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                f'{{{{ include "{include_name}" }}}}\n',
                encoding="utf-8",
            )


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

    # Directories to scan
    scan_dirs = [home, cwd] + args.scan_dir

    print("Scanning for skills...")
    for d in scan_dirs:
        print(f"  {d}")

    # Find skills directories
    skills_dirs = find_skills_dirs(scan_dirs)

    if not skills_dirs:
        print("\nNo skills directories found.")
        sys.exit(0)

    print("\nFound skills directories:")
    for d in skills_dirs:
        print(f"  {d}")

    # Get existing chezmoi skills
    existing = get_chezmoi_skill_names()

    # Discover importable skills
    importable = discover_importable_skills(skills_dirs, existing)

    if not importable:
        print("\nAll discovered skills are already in chezmoi.")
        sys.exit(0)

    # Interactive selection
    selected = prompt_selection(importable)
    if not selected:
        print("\nNo skills selected.")
        sys.exit(0)

    # Plan all imports
    planned: List[Tuple[str, Path, List[Tuple[str, Path, Path]]]] = []
    for skill_name, skill_dir in selected:
        actions = plan_skill_import(skill_name, skill_dir)
        planned.append((skill_name, skill_dir, actions))

    # Show preview
    print("\nThe following changes will be made:")
    for skill_name, _skill_dir, actions in planned:
        print_action_preview(skill_name, actions)

    # Dry run stops after preview
    if args.dry_run:
        print("\nDry run complete. No changes were made.")
        sys.exit(0)

    # Confirm
    print()
    if not confirm("Proceed with import?"):
        print("Import cancelled.")
        sys.exit(0)

    # Execute
    print()
    for skill_name, _skill_dir, actions in planned:
        print(f"Importing {skill_name}...")
        execute_actions(actions)

    print("\nImport complete.")
    print("Run 'chezmoi apply' to deploy skills to all tools.")


if __name__ == "__main__":
    main()
