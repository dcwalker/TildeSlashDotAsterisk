#!/usr/bin/env python3
"""
Script to list GitHub Advanced Security (GHAS) issues for the repository it is run in.

Fetches open Dependabot, code scanning, and secret scanning alerts from the GitHub API.
Repo is detected from the current directory's git remote, or from GITHUB_REPOSITORY / --repo.

Usage: ./list-ghas-issues.py [OPTIONS]
Run with -h or --help for full usage information.

Environment variables:
    GITHUB_TOKEN   - GitHub personal access token or gh CLI auth (optional if gh is logged in)
    GITHUB_REPOSITORY - Override repo (owner/repo) when not running from a git repo
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def get_terminal_width() -> int:
    """Get terminal width, default to 80 if not available."""
    try:
        return shutil.get_terminal_size().columns
    except OSError:
        return 80


def _na(val: Any) -> str:
    """Format value for display; use N/A for empty/None."""
    if val is None or val == "":
        return "N/A"
    return str(val).strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]*>", "", text)


GITHUB_API_BASE = "https://api.github.com"
ACCEPT_HEADER = "application/vnd.github+json"
API_VERSION = "2022-11-28"
USER_AGENT = "list-ghas-issues/1.0"
PER_PAGE = 100

# Alert type -> API path segment (GHAS app pattern)
ALERT_PATHS = {
    "dependabot": "dependabot",
    "code_scanning": "code-scanning",
    "secret_scanning": "secret-scanning",
}

# Common field labels for detail output
_LABEL_NUMBER = "Number:"
_LABEL_STATE = "State:"
_LABEL_CREATED_AT = "Created at:"


def get_repo_from_git() -> Optional[str]:
    """Get owner/repo from current directory's git remote origin."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        url = result.stdout.strip()
        # Match https://github.com/owner/repo or git@github.com:owner/repo
        m = re.match(r"(?:https?://github\.com/|git@github\.com:)([^/]+)/([^\s/]+?)(?:\.git)?$", url)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def get_token() -> Optional[str]:
    """Get GitHub token from GITHUB_TOKEN or gh auth token."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def parse_link_header(link: Optional[str]) -> Optional[str]:
    """Extract next page URL from Link header. Returns None if no next."""
    if not link:
        return None
    # Match <url>; rel="next"
    m = re.search(r'<([^>]+)>;\s*rel="next"', link, re.IGNORECASE)
    return m.group(1) if m else None


def _parse_alert_response(resp: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Read response body and Link header; return (alerts list, next_url)."""
    data = json.loads(resp.read().decode())
    alerts = data if isinstance(data, list) else []
    next_url = parse_link_header(resp.headers.get("Link"))
    return (alerts, next_url)


def _handle_alert_http_error(
    e: urllib.error.HTTPError,
    repo: str,
    path_segment: str,
) -> None:
    """Handle HTTPError from alerts API (caller handles 404). Exits with message."""
    body = e.read().decode() if e.fp else ""
    if e.code == 403 and (
        e.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in body.lower()
    ):
        sys.exit(
            "Error: GitHub API rate limit exceeded. Set GITHUB_TOKEN or run again later."
        )
    try:
        err = json.loads(body)
        msg = err.get("message", body)
    except ValueError:
        msg = body or str(e)
    sys.exit(f"Error: GitHub API {e.code} for {repo}/{path_segment}: {msg}")


def fetch_alerts(
    repo: str,
    path_segment: str,
    token: str,
) -> List[Dict[str, Any]]:
    """
    Fetch all open alerts for one type. Uses Link header pagination.
    See: https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
    """
    out: List[Dict[str, Any]] = []
    url: Optional[str] = (
        f"{GITHUB_API_BASE}/repos/{repo}/{path_segment}/alerts"
        f"?state=open&per_page={PER_PAGE}"
    )
    while url:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": ACCEPT_HEADER,
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data, url = _parse_alert_response(resp)
                out.extend(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return out
            _handle_alert_http_error(e, repo, path_segment)
        except urllib.error.URLError as e:
            sys.exit(f"Error: Request failed: {e.reason}")
    return out


class OutputFormatter:
    """Handles console output with pipe-prefixed wrapped text (SonarQube-style)."""

    def __init__(self) -> None:
        self._width = max(40, get_terminal_width() - 3)

    def wrap_with_pipe(self, text: str) -> str:
        """Wrap text at word boundaries and prefix each line with | """
        if not text:
            return "|"
        lines_out: List[str] = []
        for line in text.splitlines():
            if line.strip():
                wrapped = textwrap.fill(
                    line,
                    width=self._width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                for w in wrapped.splitlines():
                    lines_out.append("| " + w)
            else:
                lines_out.append("|")
        return "\n".join(lines_out)

    def _line(self, label: str, value: Any) -> str:
        """Single key-value line with aligned label (16 chars)."""
        return f"{label:<16} {_na(value)}"


def _dependabot_cvss_patch_lines(
    adv: Dict[str, Any], vuln: Dict[str, Any], fmt: OutputFormatter
) -> List[str]:
    """CVSS, first patched, and vulnerable range lines for Dependabot."""
    lines: List[str] = []
    cvss = adv.get("cvss") if isinstance(adv.get("cvss"), dict) else {}
    if cvss:
        lines.append(fmt._line("CVSS score:", cvss.get("score")))
        lines.append(fmt._line("CVSS vector:", cvss.get("vector_string")))
    first_patched = vuln.get("first_patched_version")
    if isinstance(first_patched, dict) and first_patched.get("identifier"):
        lines.append(fmt._line("First patched:", first_patched.get("identifier")))
    elif isinstance(first_patched, str):
        lines.append(fmt._line("First patched:", first_patched))
    lines.append(fmt._line("Vulnerable range:", vuln.get("vulnerable_version_range")))
    return lines


def _dependabot_advisory_blocks(adv: Dict[str, Any], fmt: OutputFormatter) -> List[str]:
    """Summary, description, and CWE blocks for Dependabot advisory."""
    blocks: List[str] = []
    if adv.get("summary"):
        blocks.extend(["", "Summary:", "", fmt.wrap_with_pipe(adv["summary"]), ""])
    if adv.get("description"):
        blocks.extend(["Description:", "", fmt.wrap_with_pipe(_strip_html(adv["description"])), ""])
    cwes = adv.get("cwes") or []
    if cwes:
        cwe_parts = [f"{c.get('cwe_id', '')}: {c.get('name', '')}" for c in cwes if isinstance(c, dict)]
        blocks.extend(["CWEs:", "", fmt.wrap_with_pipe(", ".join(cwe_parts)), ""])
    return blocks


def _format_one_dependabot_detail(alert: Dict[str, Any], fmt: OutputFormatter) -> List[str]:
    """Return list of output lines for one Dependabot alert (full detail)."""
    number = alert.get("number") or alert.get("id") or "?"
    url = alert.get("html_url") or alert.get("url") or ""
    dep = alert.get("dependency") or {}
    pkg = dep.get("package") or {}
    adv = alert.get("security_advisory") or {}
    vuln = alert.get("security_vulnerability") or {}
    vuln_pkg = vuln.get("package") or {}

    out = [
        f"Dependabot Alert #{number}",
        "---",
        fmt._line(_LABEL_NUMBER, alert.get("number") or alert.get("id")),
        fmt._line(_LABEL_STATE, alert.get("state")),
        fmt._line("Package:", vuln_pkg.get("name") or pkg.get("name")),
        fmt._line("Ecosystem:", vuln_pkg.get("ecosystem") or pkg.get("ecosystem")),
        fmt._line("Manifest path:", dep.get("manifest_path")),
        fmt._line("Scope:", dep.get("scope")),
        fmt._line("Relationship:", dep.get("relationship")),
        fmt._line("Severity:", adv.get("severity") or vuln.get("severity")),
        fmt._line("GHSA ID:", adv.get("ghsa_id")),
        fmt._line("CVE ID:", adv.get("cve_id")),
        fmt._line(_LABEL_CREATED_AT, alert.get("created_at")),
        fmt._line("Updated at:", alert.get("updated_at")),
    ]
    out.extend(_dependabot_cvss_patch_lines(adv, vuln, fmt))
    out.extend(_dependabot_advisory_blocks(adv, fmt))
    out.append(fmt._line("URL:", url))
    out.append("")
    return out


def _code_scanning_rule_desc_lines(rule_dict: Dict[str, Any], fmt: OutputFormatter) -> List[str]:
    """Rule description block for code scanning."""
    rule_desc = rule_dict.get("description") or rule_dict.get("full_description")
    if isinstance(rule_desc, str):
        return ["Rule description:", "", fmt.wrap_with_pipe(_strip_html(rule_desc)), ""]
    if isinstance(rule_desc, dict):
        full = rule_desc.get("text") or rule_desc.get("description") or ""
        if full:
            return ["Rule description:", "", fmt.wrap_with_pipe(_strip_html(full)), ""]
    return []


def _code_scanning_location_lines(loc: Dict[str, Any]) -> List[str]:
    """Location block for code scanning (path/line/column from most_recent_instance.location)."""
    lines = [
        "Location:",
        f"  Path:        {_na(loc.get('path'))}",
        f"  Start line:  {_na(loc.get('start_line'))}",
        f"  End line:    {_na(loc.get('end_line'))}",
    ]
    if loc.get("start_column") is not None or loc.get("end_column") is not None:
        lines.append(f"  Start col:   {_na(loc.get('start_column'))}")
        lines.append(f"  End col:     {_na(loc.get('end_column'))}")
    lines.append("")
    return lines


def _format_one_code_scanning_detail(alert: Dict[str, Any], fmt: OutputFormatter) -> List[str]:
    """Return list of output lines for one code scanning alert (full detail)."""
    number = alert.get("number") or alert.get("id") or "?"
    url = alert.get("html_url") or alert.get("url") or ""
    rule = alert.get("rule")
    rule_dict = rule if isinstance(rule, dict) else {}

    out = [
        f"Code Scanning Alert #{number}",
        "---",
        fmt._line(_LABEL_NUMBER, alert.get("number") or alert.get("id")),
        fmt._line(_LABEL_STATE, alert.get("state")),
        fmt._line("Rule ID:", rule_dict.get("id")),
        fmt._line("Rule name:", rule_dict.get("name")),
        fmt._line("Severity:", rule_dict.get("security_severity_level")),
        fmt._line(_LABEL_CREATED_AT, alert.get("created_at")),
        fmt._line("Closed at:", alert.get("closed_at")),
        fmt._line("Dismissed at:", alert.get("dismissed_at")),
    ]
    tool = alert.get("tool") if isinstance(alert.get("tool"), dict) else {}
    if tool:
        out.append(fmt._line("Tool:", tool.get("name")))
        out.append(fmt._line("Tool version:", tool.get("version")))
    if alert.get("message"):
        out.extend(["Message:", "", fmt.wrap_with_pipe(alert["message"]), ""])
    out.extend(_code_scanning_rule_desc_lines(rule_dict, fmt))
    # Path/line live under most_recent_instance.location (GitHub API schema)
    instance = alert.get("most_recent_instance")
    loc = instance.get("location") if isinstance(instance, dict) else None
    if not loc and isinstance(alert.get("location"), dict):
        loc = alert.get("location")
    if isinstance(loc, dict):
        out.extend(_code_scanning_location_lines(loc))
    out.append(fmt._line("URL:", url))
    out.append("")
    return out


def _format_one_secret_scanning_detail(alert: Dict[str, Any], fmt: OutputFormatter) -> List[str]:
    """Return list of output lines for one secret scanning alert (full detail)."""
    number = alert.get("number") or alert.get("id") or "?"
    url = alert.get("html_url") or alert.get("url") or ""

    out = [
        f"Secret Scanning Alert #{number}",
        "---",
        fmt._line(_LABEL_NUMBER, alert.get("number") or alert.get("id")),
        fmt._line(_LABEL_STATE, alert.get("state")),
        fmt._line("Secret type:", alert.get("secret_type_display_name") or alert.get("secret_type")),
        fmt._line(_LABEL_CREATED_AT, alert.get("created_at")),
        fmt._line("Resolved at:", alert.get("resolved_at")),
        fmt._line("Resolved by:", alert.get("resolved_by")),
        fmt._line("Resolution:", alert.get("resolution")),
    ]
    locs = alert.get("locations")
    if isinstance(locs, list) and locs:
        out.append("Locations:")
        for i, loc in enumerate(locs[:5]):
            if isinstance(loc, dict):
                out.append(f"  [{i + 1}] Path: {_na(loc.get('path'))}  Line: {_na(loc.get('start_line'))}")
        if len(locs) > 5:
            out.append(f"  ... and {len(locs) - 5} more")
        out.append("")
    out.append(fmt._line("URL:", url))
    out.append("")
    return out


_DETAIL_FORMATTERS = {
    "dependabot": _format_one_dependabot_detail,
    "code_scanning": _format_one_code_scanning_detail,
    "secret_scanning": _format_one_secret_scanning_detail,
}


def _summary_dependabot(alert: Dict[str, Any], number: Any, url: str) -> str:
    adv = alert.get("security_advisory") or {}
    vuln = alert.get("security_vulnerability") or {}
    vuln_pkg = vuln.get("package") if isinstance(vuln.get("package"), dict) else {}
    dep = alert.get("dependency") or {}
    dep_pkg = dep.get("package") if isinstance(dep.get("package"), dict) else {}
    sec = adv.get("severity") or vuln.get("severity") or "?"
    pkg_name = (vuln_pkg.get("name") if vuln_pkg else None) or (dep_pkg.get("name") if dep_pkg else None) or "?"
    return f"  #{number}  {(str(sec).upper()):8}  {_na(pkg_name)}  {url}"


def _summary_code_scanning(alert: Dict[str, Any], number: Any, url: str) -> str:
    rule = alert.get("rule")
    if isinstance(rule, dict):
        rule_id = rule.get("id") or rule.get("name") or "?"
        sec = rule.get("security_severity_level") or "?"
    else:
        rule_id = str(rule) if rule else "?"
        sec = "?"
    return f"  #{number}  {_na(sec):8}  {rule_id}  {url}"


def _summary_secret_scanning(alert: Dict[str, Any], number: Any, url: str) -> str:
    kind = alert.get("secret_type_display_name") or alert.get("secret_type") or "?"
    return f"  #{number}  {kind}  {url}"


_SUMMARY_FORMATTERS = {
    "dependabot": _summary_dependabot,
    "code_scanning": _summary_code_scanning,
    "secret_scanning": _summary_secret_scanning,
}


def _format_alert_summary(alert: Dict[str, Any], alert_type: str) -> str:
    """One-line summary for --summary output."""
    number = alert.get("number") or alert.get("id") or "?"
    url = alert.get("html_url") or alert.get("url") or ""
    fn = _SUMMARY_FORMATTERS.get(alert_type)
    return fn(alert, number, url) if fn else f"  #{number}  {url}"


def _resolve_repo(args: argparse.Namespace) -> str:
    """Resolve repo from args or env or git. Exits on failure."""
    repo = (args.repo or os.environ.get("GITHUB_REPOSITORY", "").strip()) or get_repo_from_git()
    if not repo:
        sys.exit(
            "Error: Could not detect repository. Run from a git repo, set GITHUB_REPOSITORY, or use --repo owner/repo"
        )
    return repo


def _fetch_all_alerts(
    repo: str, types_to_fetch: List[str], token: str
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch alerts for each type; return dict of type -> list of alerts."""
    results: Dict[str, List[Dict[str, Any]]] = {}
    for alert_type in types_to_fetch:
        results[alert_type] = fetch_alerts(repo, ALERT_PATHS[alert_type], token)
    return results


def _print_alert_section(
    alert_type: str,
    alerts: List[Dict[str, Any]],
    summary_only: bool,
    fmt: OutputFormatter,
) -> None:
    """Print one section (e.g. Dependabot (N)) with its alerts."""
    label = alert_type.replace("_", " ").title()
    count = len(alerts)
    print(f"=== {label} ({count}) ===")
    print()
    if not alerts:
        print("No alerts found.")
        print()
        return
    if summary_only:
        for a in alerts:
            print(_format_alert_summary(a, alert_type))
        return
    print(f"Found {count} alert{'s' if count != 1 else ''}")
    print()
    detail_fn = _DETAIL_FORMATTERS.get(alert_type)
    for a in alerts:
        if detail_fn:
            for line in detail_fn(a, fmt):
                print(line)
        else:
            print(f"  Alert #{a.get('number') or a.get('id') or '?'}")
            print("---")
            print(f"  URL: {a.get('html_url') or a.get('url') or 'N/A'}")
            print()


def _print_human_output(
    repo: str,
    types_to_fetch: List[str],
    all_results: Dict[str, List[Dict[str, Any]]],
    summary_only: bool,
) -> None:
    """Print human-readable sections (full detail or --summary)."""
    print(f"Repository: {repo}")
    print()
    total = 0
    fmt = OutputFormatter()
    for alert_type in types_to_fetch:
        alerts = all_results[alert_type]
        total += len(alerts)
        _print_alert_section(alert_type, alerts, summary_only, fmt)
    print(f"Total open GHAS issues: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List GitHub Advanced Security (GHAS) issues for the current repo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --json
  %(prog)s --repo owner/repo
  %(prog)s --type dependabot
""",
    )
    parser.add_argument(
        "--repo",
        metavar="OWNER/REPO",
        help="Repository in owner/repo form (default: from git remote or GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--type",
        choices=list(ALERT_PATHS.keys()),
        help="Only fetch this alert type (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON only",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Output one-line summary per alert only (default: full detail)",
    )
    args = parser.parse_args()

    repo = _resolve_repo(args)
    token = get_token()
    if not token:
        sys.exit("Error: No GitHub token. Set GITHUB_TOKEN or run 'gh auth login'.")

    types_to_fetch = [args.type] if args.type else list(ALERT_PATHS.keys())
    all_results = _fetch_all_alerts(repo, types_to_fetch, token)

    if args.json:
        print(json.dumps(all_results, indent=2))
        return
    _print_human_output(repo, types_to_fetch, all_results, args.summary)


if __name__ == "__main__":
    main()
