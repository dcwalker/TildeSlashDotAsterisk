#!/usr/bin/env python3
"""
List all skills available to the project (current working directory).

Includes skills from the project's .cursor/skills (if present) and from the
home directory (~/.cursor/skills, ~/.cursor/skills-cursor, ~/.claude/skills,
~/.codex/skills). For each skill, shows source (project or home), which agents
have it (cursor, codex, claude), the description, and the "When to Use" trigger
summary. Color is used when output is a TTY and --no-color is not set.

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
COLOR_PROJECT = "\033[32m"
COLOR_HOME = "\033[34m"
COLOR_CURSOR = "\033[36m"
COLOR_CLAUDE = "\033[33m"
COLOR_CODEX = "\033[35m"
COLOR_META = "\033[90m"
COLOR_DESC = "\033[37m"
COLOR_WHEN = "\033[90m"

CURSOR_SUBDIR = ".cursor"


def get_skill_info(skill_dir: Path) -> Optional[Dict[str, str]]:
    """Read name, description, and When to Use from SKILL.md."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    name = skill_dir.name
    description = ""
    when_to_use = ""

    # Parse YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        name_match = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip()
        desc_match = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip()

    # Extract ## When to Use section body
    when_match = re.search(
        r"##\s+When to Use\s*\n(.*)(?=\n##\s|\Z)", text, re.DOTALL
    )
    if when_match:
        raw = when_match.group(1).strip()
        lines = [l.strip().lstrip("-*").strip() for l in raw.splitlines() if l.strip()]
        if lines:
            when_to_use = lines[0]
            if len(lines) > 1:
                when_to_use += "; " + lines[1]

    return {"name": name, "description": description, "when_to_use": when_to_use}


def find_project_skills_root(
    cwd: Optional[Path] = None, home: Optional[Path] = None
) -> Optional[Path]:
    """Walk up from cwd to find a .cursor/skills directory. Never returns home itself."""
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    path = cwd.resolve()
    while path != path.parent:
        if (path / CURSOR_SUBDIR / "skills").is_dir():
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
    return sorted(e.name for e in scripts_dir.iterdir() if e.is_file())


def list_skills_in(skills_dir: Path) -> List[Tuple[str, Path, Dict[str, str]]]:
    """Return (name, path, info) for each skill directory directly inside skills_dir."""
    if not skills_dir.is_dir():
        return []
    result = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        info = get_skill_info(entry)
        if info is not None:
            result.append((info["name"], entry, info))
    return result


def collect_all_skills(
    project_root: Optional[Path],
    home: Path,
) -> List[Tuple[str, str, str, List[str], Dict[str, str]]]:
    """Collect (skill_name, source, agent, scripts, info) for every skill."""
    out: List[Tuple[str, str, str, List[str], Dict[str, str]]] = []

    if project_root is not None:
        for name, path, info in list_skills_in(project_root / CURSOR_SUBDIR / "skills"):
            out.append((name, "project", "cursor", get_skill_scripts(path), info))

    # ~/.cursor/skills (user skills)
    for name, path, info in list_skills_in(home / CURSOR_SUBDIR / "skills"):
        out.append((name, "home", "cursor", get_skill_scripts(path), info))

    # ~/.cursor/skills-cursor (Cursor built-in meta-skills)
    for name, path, info in list_skills_in(home / CURSOR_SUBDIR / "skills-cursor"):
        out.append((name, "home", "cursor-meta", get_skill_scripts(path), info))

    for agent, subdir in [("claude", ".claude"), ("codex", ".codex")]:
        for name, path, info in list_skills_in(home / subdir / "skills"):
            out.append((name, "home", agent, get_skill_scripts(path), info))

    return out


def aggregate_by_skill(
    rows: List[Tuple[str, str, str, List[str], Dict[str, str]]],
) -> List[Tuple[str, List[str], List[str], List[str], Dict[str, str]]]:
    """Group by skill name; return (name, sources, agents, scripts, info)."""
    by_name: Dict[str, Tuple[set, set, set, Dict[str, str]]] = {}
    for name, source, agent, scripts, info in rows:
        if name not in by_name:
            by_name[name] = (set(), set(), set(), info)
        by_name[name][0].add(source)
        by_name[name][1].add(agent)
        by_name[name][2].update(scripts)
    return [
        (name, sorted(sources), sorted(agents), sorted(script_set), info)
        for name, (sources, agents, script_set, info) in sorted(by_name.items())
    ]


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def colorize_source(source: str, use_color: bool) -> str:
    if not use_color:
        return source
    if source == "project":
        return f"{COLOR_PROJECT}project{RESET}"
    return f"{COLOR_HOME}home{RESET}"


def colorize_agent(agent: str, use_color: bool) -> str:
    if not use_color:
        return agent
    if agent == "cursor":
        return f"{COLOR_CURSOR}cursor{RESET}"
    if agent == "cursor-meta":
        return f"{COLOR_META}cursor-meta{RESET}"
    if agent == "claude":
        return f"{COLOR_CLAUDE}claude{RESET}"
    if agent == "codex":
        return f"{COLOR_CODEX}codex{RESET}"
    return agent


def _print_entry(
    name: str,
    src_str: str,
    ag_str: str,
    info: Dict[str, str],
    scripts: List[str],
    use_color: bool,
) -> None:
    name_display = f"{BOLD}{name}{RESET}" if use_color else name
    print(name_display)
    print(f"  Source: {src_str}  |  Agent: {ag_str}")

    desc = info.get("description", "")
    if desc:
        desc_line = truncate(desc, 120)
        print(f"  {COLOR_DESC}{desc_line}{RESET}" if use_color else f"  {desc_line}")

    when = info.get("when_to_use", "")
    if when:
        when_line = f"When to Use: {truncate(when, 120)}"
        print(f"  {COLOR_WHEN}{when_line}{RESET}" if use_color else f"  {when_line}")

    for script in scripts:
        script_line = f"↳  scripts/{script}"
        print(f"  {COLOR_META}{script_line}{RESET}" if use_color else f"  {script_line}")


def run_text(
    aggregated: List[Tuple[str, List[str], List[str], List[str], Dict[str, str]]],
    use_color: bool,
    project_root: Optional[Path],
) -> None:
    for i, (name, sources, agents, scripts, info) in enumerate(aggregated):
        src_str = ", ".join(colorize_source(s, use_color) for s in sources)
        ag_str = ", ".join(colorize_agent(a, use_color) for a in agents)
        _print_entry(name, src_str, ag_str, info, scripts, use_color)
        if i < len(aggregated) - 1:
            print()

    if project_root is not None:
        print()
        print(f"Project root: {project_root}")
    print()


def run_json(
    aggregated: List[Tuple[str, List[str], List[str], List[str], Dict[str, str]]],
    project_root: Optional[Path],
) -> None:
    import json

    data = {
        "project_root": str(project_root) if project_root else None,
        "skills": [
            {
                "name": name,
                "sources": sources,
                "agents": agents,
                "scripts": scripts,
                "description": info.get("description", ""),
                "when_to_use": info.get("when_to_use", ""),
            }
            for name, sources, agents, scripts, info in aggregated
        ],
    }
    print(json.dumps(data, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List skills available to the current project, with description and trigger summary.",
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
