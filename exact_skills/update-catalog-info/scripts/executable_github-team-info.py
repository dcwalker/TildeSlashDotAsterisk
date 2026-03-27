#!/usr/bin/env python3
"""
Fetch and print GitHub team metadata and membership.

Uses the gh CLI when available, otherwise falls back to the GitHub REST API
with GITHUB_TOKEN from the environment.

Usage:
    python3 github-team-info.py --org ORG --team-slug TEAM_SLUG
    python3 github-team-info.py --help

If --org or --team-slug is omitted, the script will prompt for the value.

Environment variables:
    GITHUB_TOKEN    - GitHub personal access token (used when gh CLI is unavailable)
                      Requires read:org scope for team endpoints.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Optional, Union

# Optional: use requests when gh CLI is not available
try:
    import requests
except ImportError:
    requests = None

# Optional: use questionary for interactive prompts
try:
    import questionary
except ImportError:
    questionary = None

GITHUB_API_BASE = "https://api.github.com"
RATE_LIMIT_MAX_RETRIES = 5
RATE_LIMIT_DEFAULT_WAIT_SEC = 60
RATE_LIMIT_MSG = "rate limit"


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _is_rate_limit_error(stderr: str) -> bool:
    """Check if gh stderr indicates a rate limit error."""
    err = stderr.lower()
    return "403" in err or "429" in err or RATE_LIMIT_MSG in err


def _fetch_via_gh(endpoint: str, paginate: bool = False) -> Optional[Union[dict, list]]:
    """Fetch from GitHub API using gh CLI. Returns parsed JSON or None on failure."""
    cmd = ["gh", "api", endpoint]
    if paginate:
        cmd.append("--paginate")
    for attempt in range(RATE_LIMIT_MAX_RETRIES):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            if _is_rate_limit_error(result.stderr) and attempt < RATE_LIMIT_MAX_RETRIES - 1:
                wait = RATE_LIMIT_DEFAULT_WAIT_SEC
                print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"gh api error: {result.stderr}", file=sys.stderr)
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return None
    return None


def _is_rate_limit_response(response: "requests.Response") -> bool:
    """Check if response indicates a rate limit error."""
    try:
        body = response.json()
        msg = (body.get("message") or "").lower()
    except Exception:
        return False
    return RATE_LIMIT_MSG in msg or "secondary " + RATE_LIMIT_MSG in msg


def _rate_limit_wait(response: "requests.Response") -> int:
    """Return seconds to wait based on rate limit response headers."""
    retry_after = response.headers.get("Retry-After")
    if retry_after and retry_after.isdigit():
        return int(retry_after)
    if response.headers.get("X-RateLimit-Remaining") == "0":
        reset = response.headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            return max(1, int(reset) - int(time.time()))
    return RATE_LIMIT_DEFAULT_WAIT_SEC


def _sleep_and_retry_rate_limit(response: "requests.Response", attempt: int) -> bool:
    """If rate limited and retries left, sleep and return True. Else return False."""
    if response.status_code not in (403, 429):
        return False
    if not _is_rate_limit_response(response):
        return False
    if attempt >= RATE_LIMIT_MAX_RETRIES - 1:
        return False
    wait = _rate_limit_wait(response)
    print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
    time.sleep(wait)
    return True


def _process_response(
    response: "requests.Response", paginate: bool, all_items: list
) -> tuple[Optional[Union[dict, list]], Optional[str]]:
    """Process response. Returns (result, next_url). result is final data if done, None if more pages."""
    response.raise_for_status()
    data = response.json()
    if paginate and isinstance(data, list):
        all_items.extend(data)
        next_url = _next_page_url(response.headers.get("Link") or "")
        return (all_items, None) if not next_url else (None, next_url)
    return (data, None)


def _fetch_pages(
    url: str, headers: dict, paginate: bool, attempt: int
) -> Optional[Union[dict, list]]:
    """Fetch URL and follow pagination. Returns data or None on rate limit retry."""
    all_items: list = []
    try:
        while url:
            response = requests.get(url, headers=headers, timeout=60)
            if _sleep_and_retry_rate_limit(response, attempt):
                return None
            result, next_url = _process_response(response, paginate, all_items)
            if result is not None:
                return result
            url = next_url
        return None
    except requests.HTTPError as e:
        if e.response is not None and _sleep_and_retry_rate_limit(e.response, attempt):
            return None
        raise


def _fetch_via_requests(
    endpoint: str, token: str, paginate: bool = False
) -> Optional[Union[dict, list]]:
    """Fetch from GitHub API using requests. Returns parsed JSON or None on failure."""
    if requests is None:
        print("Error: requests package required when gh CLI is not available", file=sys.stderr)
        return None

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API_BASE}/{endpoint}"

    for attempt in range(RATE_LIMIT_MAX_RETRIES):
        result = _fetch_pages(url, headers, paginate, attempt)
        if result is not None:
            return result
    return None


def _prompt(value: Optional[str], prompt_text: str) -> str:
    """Return value if set, otherwise prompt the user."""
    if value:
        return value.strip()
    if questionary:
        result = questionary.text(prompt_text).ask()
        return (result or "").strip()
    return input(prompt_text).strip()


def _next_page_url(link_header: str) -> Optional[str]:
    """Extract next page URL from GitHub Link header."""
    for part in link_header.split(","):
        part = part.strip()
        if part.endswith('rel="next"'):
            url = part.split(";")[0].strip(" <>")
            return url
    return None


def fetch_team(org: str, team_slug: str, use_gh: bool, token: Optional[str]) -> Optional[dict]:
    endpoint = f"orgs/{org}/teams/{team_slug}"
    if use_gh:
        return _fetch_via_gh(endpoint)
    if token:
        return _fetch_via_requests(endpoint, token)
    return None


def fetch_members(
    org: str, team_slug: str, use_gh: bool, token: Optional[str]
) -> Optional[list]:
    endpoint = f"orgs/{org}/teams/{team_slug}/members"
    if use_gh:
        return _fetch_via_gh(endpoint, paginate=True)
    if token:
        return _fetch_via_requests(endpoint, token, paginate=True)
    return None


def fetch_user(login: str, use_gh: bool, token: Optional[str]) -> Optional[dict]:
    """Fetch full user profile from GET /users/{login}."""
    endpoint = f"users/{login}"
    if use_gh:
        return _fetch_via_gh(endpoint)
    if token:
        return _fetch_via_requests(endpoint, token)
    return None


def fetch_team_membership(
    org: str, team_slug: str, login: str, use_gh: bool, token: Optional[str]
) -> Optional[dict]:
    """Fetch team membership (role, state) for a user."""
    endpoint = f"orgs/{org}/teams/{team_slug}/memberships/{login}"
    if use_gh:
        return _fetch_via_gh(endpoint)
    if token:
        return _fetch_via_requests(endpoint, token)
    return None


def enrich_members(
    org: str,
    team_slug: str,
    members: list,
    use_gh: bool,
    token: Optional[str],
) -> list:
    """Enrich each member with full user profile and team role."""
    enriched = []
    for i, member in enumerate(members):
        login = member.get("login")
        if not login:
            enriched.append(member)
            continue
        user = fetch_user(login, use_gh, token)
        membership = fetch_team_membership(org, team_slug, login, use_gh, token)
        if user:
            record = dict(user)
        else:
            record = dict(member)
        if membership:
            record["team_role"] = membership.get("role")
            record["team_state"] = membership.get("state")
        enriched.append(record)
    return enriched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and print GitHub team metadata and membership.",
        epilog="Uses gh CLI when available, otherwise GITHUB_TOKEN.",
    )
    parser.add_argument("--org", help="GitHub organization name")
    parser.add_argument("--team-slug", dest="team_slug", help="Team slug (e.g. team-engineering-enablement)")
    args = parser.parse_args()

    org = _prompt(args.org, "Organization name: ")
    team_slug = _prompt(args.team_slug, "Team slug: ")
    if not org or not team_slug:
        print("Error: org and team slug are required.", file=sys.stderr)
        return 1

    use_gh = _gh_available()
    token = os.environ.get("GITHUB_TOKEN")

    if not use_gh and not token:
        print(
            "Error: gh CLI not found and GITHUB_TOKEN not set. Install gh or set GITHUB_TOKEN.",
            file=sys.stderr,
        )
        return 1

    try:
        team = fetch_team(org, team_slug, use_gh, token)
        if team is None:
            print(
                f"Error: No team found for org '{org}' and team slug '{team_slug}'.",
                file=sys.stderr,
            )
            return 1

        members = fetch_members(org, team_slug, use_gh, token)
        if members is None:
            return 1

        members = enrich_members(org, team_slug, members, use_gh, token)

        output = {
            "team": team,
            "members": members,
            "members_count": len(members),
        }

        print(json.dumps(output, indent=2))
        return 0
    except Exception as e:
        if requests is not None and isinstance(e, requests.RequestException):
            print(f"API error: {e}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
