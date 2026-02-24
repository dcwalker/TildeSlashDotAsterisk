#!/usr/bin/env python3
"""
Rank Jira issues matching a JQL query by parent, type, and status category.

Fetches all issues for the base JQL, shows the set and a preview of the new order,
then updates rank via the Jira Software Agile REST API after user confirmation.
Only issues returned by the query are ever updated.

Usage:
    python rank_jira_issues.py [--jql "assignee in (...)" ] [--site-url https://your-domain.atlassian.net]

    If --jql or --site-url are omitted, the script will prompt for them.

Environment variables:
    ATLASSIAN_USER_EMAIL    - Your Atlassian account email
    ATLASSIAN_USER_API_KEY  - Your Atlassian API token
"""

import argparse
import os
import re
import sys
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

import requests

# Constants
URL_HTTPS_PREFIX = "https://"
SEARCH_PAGE_SIZE = 50
RANK_BATCH_SIZE = 50
CONTENT_TYPE_JSON = "application/json"

# Type order: Epic, Bug, Task, Story, other
TYPE_ORDER = {"epic": 0, "bug": 1, "task": 2, "story": 3}

# Status category key -> sort order (done first, then in progress, then to do)
STATUS_CATEGORY_ORDER = {"done": 0, "indeterminate": 1, "new": 2}

# Status category key -> human-readable label for display
STATUS_CATEGORY_LABEL = {"done": "Done", "indeterminate": "In progress", "new": "To do"}


def validate_site_url(site_url: str) -> bool:
    """Return True if input is a valid Atlassian site URL or hostname (*.atlassian.net)."""
    s = (site_url or "").strip()
    if not s:
        return False
    s = s.replace(URL_HTTPS_PREFIX, "").replace("http://", "").split("/")[0].rstrip("/")
    return bool(re.match(r"^[a-zA-Z0-9-]+\.atlassian\.net$", s))


def normalize_site_url(site_url: str) -> str:
    """Derive base URL from site URL or hostname; https, no trailing slash."""
    raw = (site_url or "").strip().replace(URL_HTTPS_PREFIX, "").replace("http://", "").split("/")[0]
    if ".atlassian.net" not in raw:
        raw = f"{raw}.atlassian.net"
    return f"{URL_HTTPS_PREFIX}{raw}"


def prompt_for_site_url() -> str:
    """Prompt for Atlassian site URL with validation; re-prompt until valid."""
    prompt = "Enter your Atlassian site URL (e.g. https://your-domain.atlassian.net or your-domain.atlassian.net): "
    error_msg = "Invalid site URL format. Expected format: your-domain.atlassian.net or https://your-domain.atlassian.net"
    while True:
        value = input(prompt).strip()
        if not value:
            print("Value cannot be empty. Please try again.")
            continue
        if validate_site_url(value):
            return value
        print(error_msg)


def prompt_for_jql() -> str:
    """Prompt for JQL query; re-prompt until non-empty."""
    prompt = "Enter JQL query (e.g. assignee in (currentUser()), parent in (PROJ-123)): "
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("JQL cannot be empty. Please try again.")


# Column widths for table row (key, type, status, parent, summary)
_COL_KEY = 14
_COL_TYPE = 8
_COL_STATUS = 12
_COL_PARENT = 12
_SUMMARY_MAX = 56


@dataclass
class IssueRow:
    """Minimal issue data for sorting and display."""

    key: str
    type_name: str
    status_name: str
    status_category_key: str
    parent_key: str
    summary: str

    def type_order(self) -> int:
        name = (self.type_name or "").strip().lower()
        return TYPE_ORDER.get(name, 4)

    def status_order(self) -> int:
        key = (self.status_category_key or "").strip().lower()
        return STATUS_CATEGORY_ORDER.get(key, 3)

    def parent_sort_key(self) -> str:
        return self.parent_key or ""

    def sort_key(self) -> tuple:
        return (
            self.parent_sort_key(),
            self.type_order(),
            self.status_order(),
        )


def _parse_issue(raw: dict) -> Optional[IssueRow]:
    """Build IssueRow from one search result; returns None if key missing."""
    key = (raw.get("key") or "").strip()
    if not key:
        return None
    fields_obj = raw.get("fields") or {}
    it = fields_obj.get("issuetype") or {}
    type_name = str(it.get("name") or "")
    st = fields_obj.get("status") or {}
    status_name = str(st.get("name") or "")
    status_cat = st.get("statusCategory") or {}
    status_category_key = str(status_cat.get("key") or "")
    parent_obj = fields_obj.get("parent") or {}
    parent_key = str(parent_obj.get("key") or "")
    summary_val = fields_obj.get("summary")
    if summary_val is None:
        summary = ""
    elif isinstance(summary_val, str):
        summary = summary_val
    else:
        summary = str(summary_val)
    return IssueRow(
        key=key,
        type_name=type_name,
        status_name=status_name,
        status_category_key=status_category_key,
        parent_key=parent_key,
        summary=summary,
    )


def search_issues(base_url: str, auth: tuple[str, str], jql: str) -> list[IssueRow]:
    """Fetch all issues matching JQL via paginated search (POST /rest/api/3/search/jql). Returns list of IssueRow."""
    url = f"{base_url}/rest/api/3/search/jql"
    headers = {"Accept": CONTENT_TYPE_JSON, "Content-Type": CONTENT_TYPE_JSON}
    fields = ["key", "issuetype", "status", "parent", "summary"]
    issues: list[IssueRow] = []
    next_page_token: Optional[str] = None

    while True:
        payload = {
            "jql": jql,
            "maxResults": SEARCH_PAGE_SIZE,
            "fields": fields,
        }
        if next_page_token is not None:
            payload["nextPageToken"] = next_page_token
        resp = requests.post(url, auth=auth, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_list = data.get("issues") or []

        for raw in raw_list:
            row = _parse_issue(raw)
            if row is not None:
                issues.append(row)

        next_page_token = data.get("nextPageToken")
        if not next_page_token or len(raw_list) == 0:
            break

    return issues


def apply_rank(base_url: str, auth: tuple[str, str], ordered_keys: list[str]) -> tuple[bool, Optional[dict]]:
    """
    Apply rank order via PUT /rest/agile/1.0/issue/rank.
    Order is applied in batches of 50 (rankAfterIssue). Returns (success, error_detail).
    """
    if len(ordered_keys) <= 1:
        return True, None

    url = f"{base_url}/rest/agile/1.0/issue/rank"
    headers = {"Accept": CONTENT_TYPE_JSON, "Content-Type": CONTENT_TYPE_JSON}

    # Rank each batch after the previous anchor: [K1, K2, ... K51] then rank [K2..K51] after K1.
    i = 0
    while i < len(ordered_keys):
        anchor = ordered_keys[i]
        batch = ordered_keys[i + 1 : i + 1 + RANK_BATCH_SIZE]
        if not batch:
            break
        body = {"issues": batch, "rankAfterIssue": anchor}
        resp = requests.put(url, auth=auth, headers=headers, json=body, timeout=60)
        if resp.status_code == 204:
            i += len(batch) + 1
            continue
        if resp.status_code == 207:
            try:
                detail = resp.json()
            except Exception:
                detail = {"body": resp.text}
            return False, detail
        resp.raise_for_status()
        i += len(batch) + 1

    return True, None


def _status_category_display(key: str) -> str:
    """Return human-readable label for Jira status category key."""
    k = (key or "").strip().lower()
    return STATUS_CATEGORY_LABEL.get(k, key or "")


def _order_children_under_parents(sorted_issues: list[IssueRow]) -> list[IssueRow]:
    """Reorder so each issue with a parent in the set appears immediately after that parent.
    Preserves relative order among siblings (type, status). Applied after other sort."""
    if not sorted_issues:
        return []
    keys_set = {row.key for row in sorted_issues}
    children_of: dict[str, list[IssueRow]] = {}
    for row in sorted_issues:
        if row.parent_key and row.parent_key in keys_set:
            children_of.setdefault(row.parent_key, []).append(row)
    top_level = [r for r in sorted_issues if not r.parent_key or r.parent_key not in keys_set]
    result: list[IssueRow] = []
    queue: deque[IssueRow] = deque(top_level)
    while queue:
        row = queue.popleft()
        result.append(row)
        # Prepend children so they are processed immediately after this parent
        for child in reversed(children_of.get(row.key, [])):
            queue.appendleft(child)
    return result


def _truncate_summary(s: str, max_len: int = _SUMMARY_MAX) -> str:
    """Truncate summary with ellipsis if over max_len."""
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _print_issue_list(issues: list[IssueRow], numbered: bool = False) -> None:
    """Print one table row per issue: key, type, status, parent, summary (no created date)."""
    for i, row in enumerate(issues, start=1 if numbered else 0):
        status_display = _status_category_display(row.status_category_key)
        parent_display = row.parent_key if row.parent_key else ""
        summary_display = _truncate_summary(row.summary)
        prefix = f"{i:>3}. " if numbered else "     "
        line = (
            f"{prefix}"
            f"{row.type_name:<{_COL_TYPE}} "
            f"{row.key:<{_COL_KEY}} "
            f"{parent_display:<{_COL_PARENT}} "
            f"{status_display:<{_COL_STATUS}} "
            f"{summary_display}"
        )
        print(line)


def _confirm(prompt: str) -> bool:
    """Return True if user answers y/yes."""
    answer = input(prompt).strip().lower()
    return answer in ("y", "yes")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rank Jira issues by parent, type, and status category."
    )
    parser.add_argument("--jql", help="Base JQL query (e.g. assignee in (...), parent in (KEY))")
    parser.add_argument(
        "--site-url",
        help="Atlassian site URL (e.g. https://your-domain.atlassian.net or your-domain.atlassian.net)",
    )
    args = parser.parse_args()

    user_email = os.environ.get("ATLASSIAN_USER_EMAIL")
    user_api_key = os.environ.get("ATLASSIAN_USER_API_KEY")
    if not user_email or not user_api_key:
        print("Error: ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY must be set.", file=sys.stderr)
        return 1

    site_url_input = (args.site_url or "").strip()
    if site_url_input:
        if not validate_site_url(site_url_input):
            print(
                "Error: Invalid site URL format. Expected format: your-domain.atlassian.net or https://your-domain.atlassian.net",
                file=sys.stderr,
            )
            return 1
    else:
        site_url_input = prompt_for_site_url()

    jql = (args.jql or "").strip()
    if not jql:
        jql = prompt_for_jql()

    base_url = normalize_site_url(site_url_input)
    auth = (user_email, user_api_key)

    print(f"Searching with JQL: {jql}")
    try:
        issues = search_issues(base_url, auth, jql)
    except requests.RequestException as e:
        print(f"Error: Search failed: {e}", file=sys.stderr)
        return 1

    if not issues:
        print("No issues found for this JQL.")
        return 0

    sorted_issues = sorted(issues, key=IssueRow.sort_key)
    sorted_issues = _order_children_under_parents(sorted_issues)
    ordered_keys = [row.key for row in sorted_issues]

    print(f"\nFound {len(issues)} issue(s) (in ranked order):")
    _print_issue_list(sorted_issues)

    if not _confirm("\nSort these issues? (y/n): "):
        print("Aborted.")
        return 0

    print("\nPreview (new rank order):")
    _print_issue_list(sorted_issues, numbered=True)

    if not _confirm("\nApply this rank order? (y/n): "):
        print("Aborted.")
        return 0

    ok, err_detail = apply_rank(base_url, auth, ordered_keys)
    if ok:
        print("Rank updated successfully.")
        return 0
    print("Rank update returned 207 (partial failure). Details:", file=sys.stderr)
    if err_detail:
        import json
        print(json.dumps(err_detail, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
