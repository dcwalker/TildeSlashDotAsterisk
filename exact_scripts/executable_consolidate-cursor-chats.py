#!/usr/bin/env python3
"""
Consolidate Cursor chat history from all workspace databases into one target workspace.

Merges:
  - composer.composerData        (the list of all chat sessions)
  - workbench.panel.composerChatViewPane.*  (individual conversation content)
  - aiService.generations / aiService.prompts

Safe to run repeatedly — uses INSERT OR IGNORE for individual chats and
deduplicates by composerId when merging the index.

Requires: Python 3.8+, sqlite3 (stdlib), curses (stdlib), no third-party dependencies.
"""

from __future__ import annotations

import curses
import json
import os
import platform
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPOSER_DATA_SQL = "SELECT value FROM ItemTable WHERE key='composer.composerData'"
COMPOSER_DATA_UPSERT = "INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('composer.composerData', ?)"
COMPOSER_CHAT_PREFIX = "workbench.panel.composerChatViewPane."
MERGE_KEYS = {"aiService.generations", "aiService.prompts"}
STATE_DB_NAME = "state.vscdb"


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def cursor_user_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / "User"
    if system == "Linux":
        return Path.home() / ".config" / "Cursor" / "User"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            sys.exit("Error: APPDATA environment variable not set.")
        return Path(appdata) / "Cursor" / "User"
    sys.exit(f"Error: Unsupported platform '{system}'.")


# ---------------------------------------------------------------------------
# Cursor process detection
# ---------------------------------------------------------------------------

def cursor_is_running() -> bool:
    system = platform.system()
    if system in ("Darwin", "Linux"):
        import subprocess
        result = subprocess.run(["pgrep", "-x", "Cursor"], capture_output=True)
        return result.returncode == 0
    if system == "Windows":
        import subprocess
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Cursor.exe"],
            capture_output=True, text=True,
        )
        return "Cursor.exe" in result.stdout
    return False


# ---------------------------------------------------------------------------
# Workspace discovery
# ---------------------------------------------------------------------------

def workspace_label(ws_dir: Path) -> str:
    wj = ws_dir / "workspace.json"
    if wj.exists():
        try:
            data = json.loads(wj.read_text())
            raw = data.get("folder") or data.get("workspace") or ""
            path = re.sub(r"^file://", "", raw)
            return path or str(ws_dir.name)
        except (json.JSONDecodeError, OSError):
            pass
    return str(ws_dir.name)


def count_sessions_with_content(db_path: Path) -> int:
    """Count composer sessions that have actual conversation content stored locally."""
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = con.execute(
            f"SELECT COUNT(*) FROM ItemTable WHERE key LIKE '{COMPOSER_CHAT_PREFIX}%'"
        ).fetchone()
        con.close()
        return row[0] if row else 0
    except Exception:
        return 0


def _global_session_counts(user_dir: Path) -> dict[str, int]:
    """
    Return a mapping of workspaceIdentifier.id → session count from the global
    composer.composerHeaders index.  Used to surface cloud-only workspaces whose
    local DB has already been cleared.
    """
    global_db = user_dir / "globalStorage" / STATE_DB_NAME
    if not global_db.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
        row = con.execute(GLOBAL_HEADERS_SQL).fetchone()
        con.close()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    counts: dict[str, int] = {}
    for entry in json.loads(row[0]).get("allComposers", []):
        ws_id = entry.get("workspaceIdentifier", {}).get("id", "")
        # Skip ephemeral / empty-window identifiers
        if ws_id and ws_id != "empty-window" and not ws_id.isdigit():
            counts[ws_id] = counts.get(ws_id, 0) + 1
    return counts


def discover_workspaces(user_dir: Path) -> list[dict]:
    ws_storage = user_dir / "workspaceStorage"
    if not ws_storage.is_dir():
        sys.exit(f"Error: workspaceStorage not found at {ws_storage}")

    global_counts = _global_session_counts(user_dir)

    workspaces = []
    for ws_dir in sorted(ws_storage.iterdir()):
        db = ws_dir / STATE_DB_NAME
        if not db.is_file():
            continue
        local_n = count_sessions_with_content(db)
        global_n = global_counts.get(ws_dir.name, 0)
        # Include workspaces with local content OR sessions in the global index
        if local_n == 0 and global_n == 0:
            continue
        workspaces.append({
            "hash": ws_dir.name,
            "db": db,
            "label": workspace_label(ws_dir),
            # Show local count when available; fall back to global count so
            # cloud-only workspaces still show a meaningful number
            "composers": local_n if local_n > 0 else global_n,
            # Flag used to skip local DB processing for global-only workspaces
            "local_composers": local_n,
        })

    return sorted(workspaces, key=lambda w: w["label"].lower())


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def merge_composer_index(existing_json: str | None, incoming_json: str | None) -> tuple[str, int]:
    """Merge allComposers lists, deduplicating by composerId."""
    if not incoming_json:
        return existing_json or "{}", 0

    incoming_items = json.loads(incoming_json).get("allComposers", [])
    if not incoming_items:
        return existing_json or "{}", 0

    existing = json.loads(existing_json) if existing_json else {}
    composers = existing.setdefault("allComposers", [])
    seen_ids = {item["composerId"] for item in composers if "composerId" in item}

    added = 0
    for item in incoming_items:
        cid = item.get("composerId")
        if cid and cid not in seen_ids:
            composers.append(item)
            seen_ids.add(cid)
            added += 1

    return json.dumps(existing), added


def merge_string_json_list(existing_json: str | None, incoming_json: str | None) -> tuple[str, int]:
    """Merge two flat JSON arrays, deduplicating string entries."""
    if not incoming_json:
        return existing_json or "[]", 0
    incoming = json.loads(incoming_json)
    if not incoming:
        return existing_json or "[]", 0

    existing = json.loads(existing_json) if existing_json else []
    seen = set(existing) if all(isinstance(x, str) for x in existing) else set()
    added = 0
    for item in incoming:
        if isinstance(item, str) and item not in seen:
            existing.append(item)
            seen.add(item)
            added += 1
        elif not isinstance(item, str):
            existing.append(item)
            added += 1
    return json.dumps(existing), added


# ---------------------------------------------------------------------------
# Per-source merge steps
# ---------------------------------------------------------------------------

def _merge_composer_data(
    src_con: sqlite3.Connection,
    target_con: sqlite3.Connection,
    stats: dict,
) -> None:
    src_row = src_con.execute(COMPOSER_DATA_SQL).fetchone()
    if not src_row:
        return
    tgt_row = target_con.execute(COMPOSER_DATA_SQL).fetchone()
    merged_json, added = merge_composer_index(
        tgt_row[0] if tgt_row else None,
        src_row[0],
    )
    stats["composers_added"] += added
    target_con.execute(COMPOSER_DATA_UPSERT, (merged_json,))
    print(f"  Composers merged: +{added}")


def _copy_chat_panes(
    src_con: sqlite3.Connection,
    target_con: sqlite3.Connection,
    stats: dict,
) -> None:
    chat_rows = src_con.execute(
        f"SELECT key, value FROM ItemTable WHERE key LIKE '{COMPOSER_CHAT_PREFIX}%'"
    ).fetchall()
    if not chat_rows:
        return
    target_con.executemany(
        "INSERT OR IGNORE INTO ItemTable (key, value) VALUES (?, ?)",
        chat_rows,
    )
    stats["chats_added"] += len(chat_rows)
    print(f"  Chat panes copied: {len(chat_rows)}")


def _merge_aux_keys(
    src_con: sqlite3.Connection,
    target_con: sqlite3.Connection,
) -> None:
    for merge_key in MERGE_KEYS:
        src_row = src_con.execute(
            "SELECT value FROM ItemTable WHERE key=?", (merge_key,)
        ).fetchone()
        if not src_row:
            continue
        tgt_row = target_con.execute(
            "SELECT value FROM ItemTable WHERE key=?", (merge_key,)
        ).fetchone()
        merged, added = merge_string_json_list(
            tgt_row[0] if tgt_row else None,
            src_row[0],
        )
        if added:
            target_con.execute(
                "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
                (merge_key, merged),
            )


def _clear_source_db(src_db: Path, stats: dict) -> None:
    """Remove all chat sessions from a source DB after they have been merged."""
    try:
        con = sqlite3.connect(str(src_db))
        con.execute(f"DELETE FROM ItemTable WHERE key LIKE '{COMPOSER_CHAT_PREFIX}%'")
        con.execute(COMPOSER_DATA_UPSERT, (json.dumps({"allComposers": []}),))
        for key in MERGE_KEYS:
            con.execute("DELETE FROM ItemTable WHERE key=?", (key,))
        con.commit()
        con.close()
        stats["sources_cleared"] += 1
        print("  Source DB cleared.")
    except sqlite3.Error as e:
        print(f"  Warning: could not clear source DB: {e}")


def _process_source(
    source: dict,
    target_con: sqlite3.Connection,
    stats: dict,
    delete_sources: bool = False,
) -> None:
    print(f"\nProcessing: {source['label']} ({source['composers']} sessions)")
    try:
        src_con = sqlite3.connect(f"file:{source['db']}?mode=ro", uri=True)
    except sqlite3.Error as e:
        print(f"  Skipping — could not open DB: {e}")
        return
    _merge_composer_data(src_con, target_con, stats)
    _copy_chat_panes(src_con, target_con, stats)
    _merge_aux_keys(src_con, target_con)
    src_con.close()
    stats["sources_processed"] += 1
    if delete_sources:
        _clear_source_db(source["db"], stats)


# ---------------------------------------------------------------------------
# Global index (composer.composerHeaders in globalStorage)
# ---------------------------------------------------------------------------

GLOBAL_HEADERS_SQL = "SELECT value FROM ItemTable WHERE key='composer.composerHeaders'"

_STUB_COMPOSER_FIELDS = {
    "type": "head",
    "unifiedMode": "agent",
    "hasUnreadMessages": False,
    "totalLinesAdded": 0,
    "totalLinesRemoved": 0,
    "hasBlockingPendingActions": False,
    "isArchived": False,
    "isDraft": False,
    "isWorktree": False,
    "isSpec": False,
    "isProject": False,
    "isBestOfNSubcomposer": False,
    "numSubComposers": 0,
    "referencedPlans": [],
    "trackedGitRepos": [],
}


def _build_workspace_identifier(ws: dict) -> dict:
    """Build a workspaceIdentifier object from a workspace dict."""
    label = ws["label"]
    uri_obj = {
        "$mid": 1,
        "fsPath": label,
        "external": f"file://{label}",
        "path": label,
        "scheme": "file",
    }
    if label.endswith(".code-workspace"):
        return {"id": ws["hash"], "configPath": uri_obj}
    return {"id": ws["hash"], "uri": uri_obj}


def _load_global_headers(global_db: Path) -> tuple[dict, dict]:
    """Return (index_data, id_to_entry) from global composer.composerHeaders."""
    try:
        con = sqlite3.connect(f"file:{global_db}?mode=ro", uri=True)
        row = con.execute(GLOBAL_HEADERS_SQL).fetchone()
        con.close()
    except sqlite3.Error:
        return {"allComposers": []}, {}
    if not row:
        return {"allComposers": []}, {}
    data = json.loads(row[0])
    by_id = {c["composerId"]: c for c in data.get("allComposers", []) if "composerId" in c}
    return data, by_id


def _update_global_headers(
    global_db: Path,
    source_hashes: set[str],
    target_ws_id: dict,
    merged_local_entries: list[dict],
    stats: dict,
) -> None:
    """
    1. Reassign workspaceIdentifier for any global session that belongs to a source workspace.
    2. Add local-only sessions (pre-Cursor 3.0, not yet in global index) so they
       appear in the Agents Window under the target workspace.
    """
    try:
        con = sqlite3.connect(global_db)
        row = con.execute(GLOBAL_HEADERS_SQL).fetchone()
        data = json.loads(row[0]) if row else {"allComposers": []}
        composers = data.get("allComposers", [])

        # Step 1: reassign existing global sessions from source workspaces
        global_ids = {c["composerId"] for c in composers if "composerId" in c}
        reassigned = 0
        for entry in composers:
            ws_id = entry.get("workspaceIdentifier", {}).get("id")
            if ws_id in source_hashes:
                entry["workspaceIdentifier"] = target_ws_id
                reassigned += 1

        # Step 2: inject local-only sessions into the global index
        added_to_global = 0
        for entry in merged_local_entries:
            cid = entry.get("composerId")
            if not cid or cid in global_ids:
                continue
            new_entry = dict(entry)
            new_entry["workspaceIdentifier"] = target_ws_id
            composers.append(new_entry)
            global_ids.add(cid)
            added_to_global += 1

        data["allComposers"] = composers
        con.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('composer.composerHeaders', ?)",
            (json.dumps(data),),
        )
        con.commit()
        con.close()

        stats["global_reassigned"] = reassigned
        stats["global_injected"] = added_to_global
        print(f"\nGlobal index: reassigned {reassigned}, injected {added_to_global} local-only session(s).")
    except sqlite3.Error as e:
        print(f"\nWarning: could not update global index: {e}")


# ---------------------------------------------------------------------------
# Index repair — synthesize allComposers entries for orphaned chat panes
# ---------------------------------------------------------------------------

def _make_stub_entry(composer_id: str, global_by_id: dict, db_mtime_ms: int) -> dict:
    """
    Return a full composer entry for an orphaned session.
    Uses global index data when available; falls back to db mtime for createdAt.
    """
    if composer_id in global_by_id:
        return dict(global_by_id[composer_id])
    return {**_STUB_COMPOSER_FIELDS, "composerId": composer_id, "createdAt": db_mtime_ms}


def _repair_orphaned_index_entries(
    target_con: sqlite3.Connection,
    target_db: Path,
    global_by_id: dict,
    stats: dict,
) -> None:
    """Add allComposers entries for any chat pane rows missing from the local index."""
    pane_keys = target_con.execute(
        f"SELECT key FROM ItemTable WHERE key LIKE '{COMPOSER_CHAT_PREFIX}%'"
    ).fetchall()
    pane_ids = {row[0][len(COMPOSER_CHAT_PREFIX):] for row in pane_keys}
    if not pane_ids:
        return

    index_row = target_con.execute(COMPOSER_DATA_SQL).fetchone()
    index_data = json.loads(index_row[0]) if index_row else {"allComposers": []}
    indexed_ids = {c["composerId"] for c in index_data.get("allComposers", []) if "composerId" in c}

    orphans = pane_ids - indexed_ids
    if not orphans:
        return

    db_mtime_ms = int(target_db.stat().st_mtime * 1000)
    for composer_id in orphans:
        index_data.setdefault("allComposers", []).append(
            _make_stub_entry(composer_id, global_by_id, db_mtime_ms)
        )

    target_con.execute(COMPOSER_DATA_UPSERT, (json.dumps(index_data),))
    stats["orphans_repaired"] = len(orphans)
    print(f"\nRepaired {len(orphans)} orphaned chat session(s).")


# ---------------------------------------------------------------------------
# Core consolidation
# ---------------------------------------------------------------------------

def consolidate(sources: list[dict], target: dict, user_dir: Path, delete_sources: bool = False) -> dict:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_db = target["db"]
    global_db = user_dir / "globalStorage" / STATE_DB_NAME

    # Backup both databases
    shutil.copy2(target_db, target_db.with_suffix(f".backup-{ts}"))
    print("\nBacked up target workspace DB.")
    if global_db.exists():
        shutil.copy2(global_db, global_db.with_suffix(f".backup-{ts}"))
        print("Backed up global DB.")

    stats = {
        "composers_added": 0,
        "chats_added": 0,
        "sources_processed": 0,
        "sources_cleared": 0,
        "orphans_repaired": 0,
        "global_reassigned": 0,
        "global_injected": 0,
        "transcripts_copied": 0,
        "transcripts_deleted": 0,
        "transcripts_injected": 0,
        "projects_removed": 0,
    }

    # Load global index for metadata lookups during orphan repair
    _, global_by_id = _load_global_headers(global_db)

    # Merge local workspace databases (skip global-only workspaces — no local DB to merge)
    target_con = sqlite3.connect(target_db)
    for source in sources:
        if source["hash"] == target["hash"]:
            continue
        if source.get("local_composers", source["composers"]) == 0:
            # Global-only workspace: nothing in the local DB to copy; the global
            # reassignment step below will move its cloud sessions to the target.
            print(f"\nSkipping local DB for {source['label']} (cloud sessions only)")
            stats["sources_processed"] += 1
            continue
        _process_source(source, target_con, stats, delete_sources=delete_sources)
    _repair_orphaned_index_entries(target_con, target_db, global_by_id, stats)
    target_con.commit()

    # Read the fully merged local index to inject into global
    merged_row = target_con.execute(COMPOSER_DATA_SQL).fetchone()
    merged_local_entries = json.loads(merged_row[0]).get("allComposers", []) if merged_row else []
    target_con.close()

    # Update global index: reassign existing sessions + inject local-only ones
    if global_db.exists():
        source_hashes = {s["hash"] for s in sources}
        target_ws_id = _build_workspace_identifier(target)
        _update_global_headers(global_db, source_hashes, target_ws_id, merged_local_entries, stats)

    # Copy cloud agent transcripts from source project dirs into the target project dir
    cursor_projects = Path.home() / ".cursor" / "projects"
    _merge_transcripts(sources, target, cursor_projects, stats, delete_sources=delete_sources)

    # Inject any transcript-only sessions (not yet in global index) into the global index
    all_workspaces = sources + [target]
    if global_db.exists():
        _inject_transcript_only_sessions(global_db, cursor_projects, all_workspaces, stats)

    return stats


# ---------------------------------------------------------------------------
# Cloud agent transcript consolidation
# ---------------------------------------------------------------------------

def _slug_from_label(label: str) -> str:
    """Convert a workspace path to the slugified project directory name Cursor uses."""
    clean = label.rstrip("/").lstrip("/")
    return clean.replace("/", "-").replace(" ", "-").replace(".", "-")


def _find_transcript_dir(label: str, cursor_projects: Path) -> Path | None:
    """Find the ~/.cursor/projects/<slug>/agent-transcripts dir for a workspace label."""
    slug = _slug_from_label(label)
    candidate = cursor_projects / slug / "agent-transcripts"
    if candidate.is_dir():
        return candidate
    # Fallback: case-insensitive search
    for d in cursor_projects.iterdir():
        if d.name.lower() == slug.lower():
            t = d / "agent-transcripts"
            if t.is_dir():
                return t
    return None


def _extract_session_name(jsonl_path: Path) -> str | None:
    """Extract a session name from the first <user_query> tag in a transcript file."""
    try:
        with open(jsonl_path) as f:
            first_line = f.readline()
        first = json.loads(first_line)
        content = first.get("message", {}).get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    m = re.search(r"<user_query>(.*?)</user_query>", block.get("text", ""), re.DOTALL)
                    if m:
                        return m.group(1).strip()[:80]
        elif isinstance(content, str):
            m = re.search(r"<user_query>(.*?)</user_query>", content, re.DOTALL)
            if m:
                return m.group(1).strip()[:80]
    except Exception:
        pass
    return None


def _build_slug_map(workspaces: list[dict], composers: list[dict]) -> dict[str, dict]:
    """Build a slug → workspaceIdentifier map from known workspaces + global index."""
    slug_to_ws_id: dict[str, dict] = {}
    for ws in workspaces:
        slug_to_ws_id[_slug_from_label(ws["label"])] = _build_workspace_identifier(ws)
    for entry in composers:
        ws_id = entry.get("workspaceIdentifier", {})
        path = (ws_id.get("uri") or ws_id.get("configPath") or {}).get("fsPath", "")
        if path:
            slug_to_ws_id.setdefault(_slug_from_label(path), ws_id)
    return slug_to_ws_id


def _new_entries_for_project(
    project_dir: Path,
    existing_ids: set[str],
    slug_to_ws_id: dict[str, dict],
) -> list[dict]:
    """Return global-index entries for transcript sessions not yet in the index."""
    slug = project_dir.name
    transcripts_dir = project_dir / "agent-transcripts"
    if not transcripts_dir.is_dir():
        return []
    ws_id = slug_to_ws_id.get(slug, {"id": slug[:32]})
    entries = []
    for session_dir in transcripts_dir.iterdir():
        composer_id = session_dir.name
        if composer_id in existing_ids:
            continue
        jsonl_files = list(session_dir.glob("*.jsonl"))
        if not jsonl_files:
            continue
        jf = jsonl_files[0]
        entries.append({
            **_STUB_COMPOSER_FIELDS,
            "composerId": composer_id,
            "createdAt": int(jf.stat().st_mtime * 1000),
            "name": _extract_session_name(jf) or "Untitled session",
            "workspaceIdentifier": ws_id,
        })
    return entries


def _inject_transcript_only_sessions(
    global_db: Path,
    cursor_projects: Path,
    workspaces: list[dict],
    stats: dict,
) -> None:
    """
    Scan all agent-transcript directories and inject sessions that are missing
    from composer.composerHeaders into the global index, so they appear in the
    Agents Window.
    """
    if not cursor_projects.is_dir() or not global_db.exists():
        return

    con = sqlite3.connect(global_db)
    row = con.execute(GLOBAL_HEADERS_SQL).fetchone()
    data = json.loads(row[0]) if row else {"allComposers": []}
    composers = data.get("allComposers", [])
    existing_ids = {c["composerId"] for c in composers if "composerId" in c}
    slug_to_ws_id = _build_slug_map(workspaces, composers)

    new_entries: list[dict] = []
    for project_dir in cursor_projects.iterdir():
        if project_dir.name.isdigit():
            continue
        new_entries.extend(
            _new_entries_for_project(project_dir, existing_ids, slug_to_ws_id)
        )

    if new_entries:
        composers.extend(new_entries)
        data["allComposers"] = composers
        con.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('composer.composerHeaders', ?)",
            (json.dumps(data),),
        )
        con.commit()
        print(f"\nInjected {len(new_entries)} transcript-only session(s) into global index.")
    con.close()
    stats["transcripts_injected"] = len(new_entries)


def _sync_source_transcripts(
    src_transcripts: Path,
    target_transcripts: Path,
    delete_sources: bool,
) -> tuple[int, int]:
    """Copy sessions from src to target; optionally delete from src. Returns (copied, deleted)."""
    copied = 0
    deleted = 0
    for session_dir in src_transcripts.iterdir():
        dest = target_transcripts / session_dir.name
        if not dest.exists():
            shutil.copytree(session_dir, dest)
            copied += 1
        if delete_sources:
            shutil.rmtree(session_dir)
            deleted += 1
    return copied, deleted


def _cleanup_project_dir(project_dir: Path) -> bool:
    """
    Remove an empty agent-transcripts directory and, if the project directory
    contains nothing else of substance, remove it too.
    Returns True if the project directory was removed.
    """
    transcripts_dir = project_dir / "agent-transcripts"
    if transcripts_dir.is_dir() and not any(transcripts_dir.iterdir()):
        transcripts_dir.rmdir()

    # Remove the project dir only if it's now completely empty
    if project_dir.is_dir() and not any(project_dir.iterdir()):
        project_dir.rmdir()
        return True
    return False


def _merge_transcripts(
    sources: list[dict],
    target: dict,
    cursor_projects: Path,
    stats: dict,
    delete_sources: bool = False,
) -> None:
    """Copy cloud agent transcript directories from source projects into the target project."""
    if not cursor_projects.is_dir():
        return

    target_transcripts = _find_transcript_dir(target["label"], cursor_projects)
    if not target_transcripts:
        print("\nWarning: could not find target transcript directory — skipping transcript merge.")
        return

    total_copied = 0
    total_deleted = 0
    projects_removed = 0
    for source in sources:
        if source["hash"] == target["hash"]:
            continue
        src_transcripts = _find_transcript_dir(source["label"], cursor_projects)
        if not src_transcripts:
            continue
        copied, deleted = _sync_source_transcripts(src_transcripts, target_transcripts, delete_sources)
        total_copied += copied
        total_deleted += deleted
        if delete_sources and _cleanup_project_dir(src_transcripts.parent):
            projects_removed += 1

    if total_copied:
        stats["transcripts_copied"] = total_copied
        print(f"\nTranscripts: copied {total_copied} session(s) into target project directory.")
    if total_deleted:
        stats["transcripts_deleted"] = total_deleted
        print(f"Transcripts: deleted {total_deleted} session(s) from source project directories.")
    if projects_removed:
        stats["projects_removed"] = projects_removed
        print(f"Transcripts: removed {projects_removed} now-empty project director(ies).")


# ---------------------------------------------------------------------------
# TUI — shared curses helpers
# ---------------------------------------------------------------------------

def _init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)   # selected row
    curses.init_pair(2, curses.COLOR_GREEN, -1)                   # checkmark
    curses.init_pair(3, curses.COLOR_CYAN, -1)                    # dim info


def _clamp_scroll(cursor: int, scroll: int, visible: int) -> int:
    if cursor < scroll:
        return cursor
    if cursor >= scroll + visible:
        return cursor - visible + 1
    return scroll


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


# ---------------------------------------------------------------------------
# TUI — single-select (arrow key, Enter to confirm)
# ---------------------------------------------------------------------------

def _run_single_select(stdscr: curses.window, items: list[dict], title: str) -> int:
    curses.curs_set(0)
    _init_colors()
    cursor = 0
    scroll = 0

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        header_rows = 3
        visible = max(1, height - header_rows - 1)

        stdscr.addstr(0, 0, _truncate(title, width))
        stdscr.addstr(1, 0, _truncate("↑/↓  navigate    Enter  confirm    Ctrl+C  cancel", width),
                      curses.color_pair(3))
        stdscr.addstr(2, 0, "─" * (width - 1), curses.color_pair(3))

        scroll = _clamp_scroll(cursor, scroll, visible)

        for i in range(scroll, min(scroll + visible, len(items))):
            row = header_rows + (i - scroll)
            ws = items[i]
            info = f"  {ws['composers']} sessions"
            is_active = i == cursor

            if is_active:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(row, 0, " " * (width - 1))
                stdscr.addstr(row, 0, f"▶ {ws['label']}"[: width - len(info) - 2])
                stdscr.addstr(row, width - len(info) - 1, info)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(row, 0, f"  {ws['label']}"[: width - len(info) - 2])
                stdscr.addstr(row, width - len(info) - 1, info, curses.color_pair(3))

        key = stdscr.getch()
        if key == curses.KEY_UP and cursor > 0:
            cursor -= 1
        elif key == curses.KEY_DOWN and cursor < len(items) - 1:
            cursor += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            return cursor
        elif key == 3:  # Ctrl+C
            raise KeyboardInterrupt

    return cursor


def single_select(items: list[dict], title: str) -> dict:
    idx = curses.wrapper(_run_single_select, items, title)
    return items[idx]


# ---------------------------------------------------------------------------
# TUI — multi-select (arrow key, Space to toggle, Enter to confirm)
#        all items start checked
# ---------------------------------------------------------------------------

def _draw_multi_select_row(
    stdscr: curses.window,
    row: int,
    width: int,
    ws: dict,
    is_checked: bool,
    is_active: bool,
) -> None:
    check = "x" if is_checked else " "
    info = f"  {ws['composers']} sessions"
    label_width = width - len(info) - 2

    if is_active:
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(row, 0, " " * (width - 1))
        stdscr.addstr(row, 0, f" [{check}] {ws['label']}"[:label_width])
        stdscr.addstr(row, width - len(info) - 1, info)
        stdscr.attroff(curses.color_pair(1))
    else:
        stdscr.addstr(row, 0, f" [{check}] {ws['label']}"[:label_width])
        if is_checked:
            stdscr.addstr(row, 2, "x", curses.color_pair(2))
        stdscr.addstr(row, width - len(info) - 1, info, curses.color_pair(3))


def _handle_multi_select_key(
    key: int,
    cursor: int,
    checked: list[bool],
    items: list[dict],
) -> tuple[int, list[bool], bool]:
    """Process a keypress. Returns (new_cursor, new_checked, should_confirm)."""
    if key == curses.KEY_UP and cursor > 0:
        return cursor - 1, checked, False
    if key == curses.KEY_DOWN and cursor < len(items) - 1:
        return cursor + 1, checked, False
    if key == ord(" "):
        checked[cursor] = not checked[cursor]
        return cursor, checked, False
    if key in (ord("a"), ord("A")):
        new_state = not all(checked)
        return cursor, [new_state] * len(items), False
    if key in (curses.KEY_ENTER, 10, 13):
        return cursor, checked, True
    if key == 3:  # Ctrl+C
        raise KeyboardInterrupt
    return cursor, checked, False


def _run_multi_select(stdscr: curses.window, items: list[dict], title: str) -> list[bool]:
    curses.curs_set(0)
    _init_colors()
    cursor = 0
    scroll = 0
    checked = [True] * len(items)

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        header_rows = 4
        visible = max(1, height - header_rows - 1)

        stdscr.addstr(0, 0, _truncate(title, width))
        stdscr.addstr(1, 0, _truncate(
            "↑/↓  navigate    Space  toggle    A  toggle all    Enter  confirm    Ctrl+C  cancel",
            width,
        ), curses.color_pair(3))
        stdscr.addstr(2, 0, _truncate(f"{sum(checked)}/{len(items)} selected", width), curses.color_pair(3))
        stdscr.addstr(3, 0, "─" * (width - 1), curses.color_pair(3))

        scroll = _clamp_scroll(cursor, scroll, visible)

        for i in range(scroll, min(scroll + visible, len(items))):
            _draw_multi_select_row(
                stdscr,
                row=header_rows + (i - scroll),
                width=width,
                ws=items[i],
                is_checked=checked[i],
                is_active=(i == cursor),
            )

        cursor, checked, confirm = _handle_multi_select_key(stdscr.getch(), cursor, checked, items)
        if confirm:
            return checked


def multi_select(items: list[dict], title: str) -> list[dict]:
    checked = curses.wrapper(_run_multi_select, items, title)
    return [item for item, selected in zip(items, checked) if selected]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _run_repair(user_dir: Path) -> None:
    """
    Standalone repair mode: scan all agent-transcript directories and inject
    any sessions missing from composer.composerHeaders into the global index.
    Safe to run anytime after Cursor has fully quit.
    """
    global_db = user_dir / "globalStorage" / STATE_DB_NAME
    cursor_projects = Path.home() / ".cursor" / "projects"

    print("\nScanning workspaces for known workspace identifiers…")
    workspaces = discover_workspaces(user_dir)

    stats: dict = {"transcripts_injected": 0}
    _inject_transcript_only_sessions(global_db, cursor_projects, workspaces, stats)

    injected = stats["transcripts_injected"]
    if injected:
        print(f"\nDone. Injected {injected} transcript-only session(s) into the global index.")
        print("Start Cursor to see the sessions in the Agents Window.")
    else:
        print("\nDone. All transcript sessions are already in the global index — nothing to do.")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Consolidate Cursor chat history across workspaces.",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "Repair mode: scan all agent-transcript directories and inject any "
            "sessions missing from the global index (composer.composerHeaders). "
            "Use this to make transcript-only sessions appear in the Agents Window "
            "without doing a full consolidation."
        ),
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Cursor Chat Consolidation Tool")
    print("=" * 60)

    if cursor_is_running():
        sys.exit(
            "\nError: Cursor is currently running.\n"
            "Please quit Cursor completely before running this tool."
        )

    user_dir = cursor_user_dir()
    print(f"\nCursor user directory: {user_dir}")

    if args.repair:
        _run_repair(user_dir)
        return

    print("Scanning workspaces…")
    workspaces = discover_workspaces(user_dir)

    if not workspaces:
        sys.exit("No workspaces with chat history found.")

    total = sum(w["composers"] for w in workspaces)
    print(f"Found {len(workspaces)} workspace(s) with {total} total composer session(s).")
    input("\nPress Enter to begin…")

    # Step 1: pick target
    try:
        target = single_select(workspaces, "Step 1 of 2 — Which workspace should receive all chats?")
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

    print(f"\nTarget: {target['label']}")

    # Step 2: pick sources (exclude target, all checked by default)
    candidates = [w for w in workspaces if w["hash"] != target["hash"]]
    try:
        sources = multi_select(
            candidates,
            "Step 2 of 2 — Which workspaces should be merged into the target?\n"
            "  (all selected by default — Space to deselect)",
        )
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

    if not sources:
        print("\nNo source workspaces selected. Nothing to do.")
        sys.exit(0)

    # Confirm — and ask whether to delete sessions from sources after merging
    print(f"\nWill merge {len(sources)} workspace(s) → {target['label']}")
    delete_sources = input(
        "Delete sessions from source workspaces after merging? [Y/n] "
    ).strip().lower()
    delete_sources_flag = delete_sources != "n"

    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # Consolidate
    stats = consolidate(sources, target, user_dir, delete_sources=delete_sources_flag)

    print("\n" + "=" * 60)
    print("  Done.")
    print(f"  Sources processed    : {stats['sources_processed']}")
    print(f"  Composers added      : {stats['composers_added']}")
    print(f"  Chat panes copied    : {stats['chats_added']}")
    print(f"  Orphans repaired     : {stats['orphans_repaired']}")
    print(f"  Sources cleared      : {stats['sources_cleared']}")
    print(f"  Global reassigned    : {stats['global_reassigned']}")
    print(f"  Global injected      : {stats['global_injected']}")
    print(f"  Transcripts copied   : {stats['transcripts_copied']}")
    print(f"  Transcripts deleted  : {stats['transcripts_deleted']}")
    print(f"  Transcripts injected : {stats['transcripts_injected']}")
    print(f"  Project dirs removed : {stats['projects_removed']}")
    print("=" * 60)
    print("\nStart Cursor to see all chats in the Agents Window.")


if __name__ == "__main__":
    main()
