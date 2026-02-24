#!/usr/bin/env python3
"""
List all skills available to the project (current working directory).

Includes skills from the project's .cursor/skills (if present) and from the
home directory (~/.cursor/skills, ~/.claude/skills, ~/.codex/skills). For each
skill, shows source (project or home) and which agents have it (cursor, codex,
claude). Color is used when output is a TTY and --no-color is not set; source
and agents are always indicated by text labels so output is usable without color.

Usage: skills-list.py [OPTIONS]
Run with -h or --help for full usage information.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ANSI color codes (empty when color disabled)
RESET = "\033[0m"
BOLD = "\033[1m"
# Source colors: project=green, home=blue
COLOR_PROJECT = "\033[32m"
COLOR_HOME = "\033[34m"
# Agent colors (distinct)
COLOR_CURSOR = "\033[36m"
COLOR_CLAUDE = "\033[33m"
COLOR_CODEX = "\033[35m"
# Script lines
COLOR_SCRIPT = "\033[90m"

# Skill directory names (agent config dirs under home)
CURSOR_SUBDIR = ".cursor"


def get_skill_name(skill_dir: Path) -> Optional[str]:
    """Read skill name from SKILL.md frontmatter (name: ...) or use directory name."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^name:\s*(\S.+?)\s*$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return skill_dir.name
    except OSError:
        return skill_dir.name


def find_project_skills_root(cwd: Optional[Path] = None, home: Optional[Path] = None) -> Optional[Path]:
    """Return the directory that contains .cursor/skills when walking up from cwd, or None. Does not treat home itself as project."""
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    path = cwd.resolve()
    while path != path.parent:
        skills_dir = path / CURSOR_SUBDIR / "skills"
        if skills_dir.is_dir():
            if path == home:
                return None
            return path
        path = path.parent
    return None


def get_skill_scripts(skill_dir: Path) -> List[str]:
    """Return sorted list of script filenames in a skill's scripts/ subdirectory."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(entry.name for entry in scripts_dir.iterdir() if entry.is_file())


def list_skill_dirs(base: Path) -> List[Tuple[str, Path]]:
    """List (skill_name, skill_path) for each skill under base/skills (base is e.g. .cursor or .claude)."""
    skills_base = base / "skills"
    if not skills_base.is_dir():
        return []
    result = []
    for entry in sorted(skills_base.iterdir()):
        if not entry.is_dir():
            continue
        name = get_skill_name(entry)
        if name is not None:
            result.append((name, entry))
    return result


def collect_all_skills(
    project_root: Optional[Path],
    home: Path,
) -> List[Tuple[str, str, str, List[str]]]:
    """Collect (skill_name, source, agent, scripts) for every skill. source in ('project', 'home'), agent in ('cursor', 'claude', 'codex')."""
    out: List[Tuple[str, str, str, List[str]]] = []

    if project_root is not None:
        cursor_skills = project_root / CURSOR_SUBDIR
        for name, path in list_skill_dirs(cursor_skills):
            out.append((name, "project", "cursor", get_skill_scripts(path)))

    for agent, subdir in [("cursor", CURSOR_SUBDIR), ("claude", ".claude"), ("codex", ".codex")]:
        base = home / subdir
        for name, path in list_skill_dirs(base):
            out.append((name, "home", agent, get_skill_scripts(path)))

    return out


def aggregate_by_skill(
    rows: List[Tuple[str, str, str, List[str]]],
) -> List[Tuple[str, List[str], List[str], List[str]]]:
    """Group by skill name; return (skill_name, sorted unique sources, sorted unique agents, sorted unique scripts)."""
    by_name: Dict[str, Tuple[set, set, set]] = {}
    for name, source, agent, scripts in rows:
        if name not in by_name:
            by_name[name] = (set(), set(), set())
        by_name[name][0].add(source)
        by_name[name][1].add(agent)
        by_name[name][2].update(scripts)
    return [
        (name, sorted(sources), sorted(agents), sorted(script_set))
        for name, (sources, agents, script_set) in sorted(by_name.items())
    ]


def colorize_source(source: str, use_color: bool) -> str:
    if not use_color:
        return source
    if source == "project":
        return f"{COLOR_PROJECT}project{RESET}"
    return f"{COLOR_HOME}home{RESET}"


def colorize_agents(agents: List[str], use_color: bool) -> str:
    if not use_color:
        return ", ".join(agents)
    parts = []
    for a in agents:
        if a == "cursor":
            parts.append(f"{COLOR_CURSOR}cursor{RESET}")
        elif a == "claude":
            parts.append(f"{COLOR_CLAUDE}claude{RESET}")
        elif a == "codex":
            parts.append(f"{COLOR_CODEX}codex{RESET}")
        else:
            parts.append(a)
    return ", ".join(parts)


def run_text(
    aggregated: List[Tuple[str, List[str], List[str], List[str]]],
    use_color: bool,
    project_root: Optional[Path],
) -> None:
    """Print human-readable table with optional color."""
    sources_label = "Source(s)"
    agents_label = "Agent(s)"
    name_label = "Skill"
    max_name = max(len(name_label), max(len(n) for n, _, _, _ in aggregated)) if aggregated else len(name_label)
    # Pad using plain text length; colored text may be longer
    plain_sources = ", ".join
    plain_agents = ", ".join
    max_sources = max(len(sources_label), 14)  # "project, home"
    max_agents = max(len(agents_label), 22)     # "claude, codex, cursor"

    header = f"  {name_label:<{max_name}}  {sources_label:<{max_sources}}  {agents_label}"
    print(header)
    print("  " + "-" * max_name + "  " + "-" * max_sources + "  " + "-" * max_agents)
    for name, sources, agents, scripts in aggregated:
        if use_color:
            src_str = ", ".join(colorize_source(s, True) for s in sources)
            ag_str = colorize_agents(agents, True)
        else:
            src_str = plain_sources(sources)
            ag_str = plain_agents(agents)
        pad_src_len = max(0, max_sources - len(plain_sources(sources)))
        print(f"  {name:<{max_name}}  {src_str}{' ' * pad_src_len}  {ag_str}")
        for script in scripts:
            if use_color:
                print(f"    {COLOR_SCRIPT}↳  {script}{RESET}")
            else:
                print(f"    ↳  {script}")
    if project_root is not None:
        print()
        print(f"  Project root: {project_root}")
    print()


def run_json(
    aggregated: List[Tuple[str, List[str], List[str], List[str]]],
    project_root: Optional[Path],
) -> None:
    """Output JSON array of skill objects."""
    import json

    data = {
        "project_root": str(project_root) if project_root else None,
        "skills": [
            {"name": name, "sources": sources, "agents": agents, "scripts": scripts}
            for name, sources, agents, scripts in aggregated
        ],
    }
    print(json.dumps(data, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List skills available to the current project (project + home), with source and agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  skills-list.py
  skills-list.py --no-color
  skills-list.py --json
""",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable color output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON only",
    )
    args = parser.parse_args()

    home = Path.home()
    cwd = Path.cwd()
    project_root = find_project_skills_root(cwd, home)
    rows = collect_all_skills(project_root, home)
    aggregated = aggregate_by_skill(rows)

    use_color = not args.no_color and sys.stdout.isatty()
    if args.json:
        run_json(aggregated, project_root)
    else:
        run_text(aggregated, use_color, project_root)


if __name__ == "__main__":
    main()
