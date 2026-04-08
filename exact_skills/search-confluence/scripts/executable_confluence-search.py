#!/usr/bin/env python3
"""
Search Confluence using CQL (Confluence Query Language).

Authentication uses basic auth via the environment variables:
  ATLASSIAN_USER_EMAIL    Your Atlassian account email
  ATLASSIAN_USER_API_KEY  Your Atlassian API token (https://id.atlassian.com/manage-profile/security/api-tokens)
  ATLASSIAN_BASE_URL      Your Confluence base URL (e.g. https://mycompany.atlassian.net)

CQL reference:
  https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/
  https://developer.atlassian.com/cloud/confluence/cql-fields/

Usage:
  confluence-search.py "<CQL>" [options]

Examples:
  confluence-search.py 'text ~ "deployment pipeline" AND space = ENG'
  confluence-search.py 'title ~ "runbook"' --limit 10
  confluence-search.py 'type = page AND space = ENG AND lastmodified >= now("-2w")'
  confluence-search.py 'label = "on-call"' --json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' is not installed. Run: pip3 install --user requests", file=sys.stderr)
    sys.exit(1)

# Seconds; avoids hanging agents on stalled Confluence connections.
REQUEST_TIMEOUT = 60.0


def get_auth() -> tuple:
    """Return (email, api_key) from environment, or exit with an error."""
    email = os.environ.get("ATLASSIAN_USER_EMAIL")
    token = os.environ.get("ATLASSIAN_USER_API_KEY")
    missing = []
    if not email:
        missing.append("ATLASSIAN_USER_EMAIL")
    if not token:
        missing.append("ATLASSIAN_USER_API_KEY")
    if missing:
        print(
            f"Error: required environment variable(s) not set: {', '.join(missing)}",
            file=sys.stderr,
        )
        print(
            "Set them before running this script:\n"
            "  export ATLASSIAN_USER_EMAIL=you@example.com\n"
            "  export ATLASSIAN_USER_API_KEY=your-api-token",
            file=sys.stderr,
        )
        sys.exit(1)
    return (email, token)


def get_base_url(override: Optional[str]) -> str:
    """Return Confluence base URL from argument or environment, or exit."""
    raw_url = override if override is not None else os.environ.get("ATLASSIAN_BASE_URL", "")
    url = raw_url.strip().rstrip("/")
    if not url:
        print(
            "Error: required environment variable not set: ATLASSIAN_BASE_URL\n"
            "  Set it before running this script:\n"
            "    export ATLASSIAN_BASE_URL=https://mycompany.atlassian.net\n"
            "  or pass it directly:\n"
            "    --base-url https://mycompany.atlassian.net",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def _handle_search_error(resp) -> None:
    """Print a useful message for a 400 CQL rejection and exit."""
    try:
        err = resp.json()
        message = err.get("message") or err.get("errorMessages") or resp.text
    except Exception:
        message = resp.text
    print(f"Error: CQL query rejected by Confluence: {message}", file=sys.stderr)
    sys.exit(1)


def _extract_cursor(next_url: str) -> Optional[str]:
    """Return the cursor value from a pagination next-link, or None."""
    for part in next_url.split("&"):
        if part.startswith("cursor=") or "?cursor=" in part:
            return part.split("cursor=")[-1]
    return None


def search(base_url: str, cql: str, limit: int, auth: tuple) -> list:
    """Run a CQL search and return all result objects up to limit."""
    results = []
    cursor = None

    while len(results) < limit:
        batch = min(limit - len(results), 50)
        params: dict = {
            "cql": cql,
            "limit": batch,
            "excerpt": "highlight",
            "expand": "metadata.labels,space,version",
        }
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(
            f"{base_url}/wiki/rest/api/search",
            params=params,
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 400:
            _handle_search_error(resp)

        resp.raise_for_status()
        data = resp.json()
        batch_results = data.get("results", [])
        results.extend(batch_results)

        links = data.get("_links", {})
        if not links.get("next") or len(batch_results) < batch:
            break

        cursor = _extract_cursor(links["next"])
        if cursor is None:
            break

    return results


def format_date(iso: Optional[str]) -> str:
    """Shorten an ISO 8601 timestamp to a readable date."""
    if not iso:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def _build_meta_parts(space: str, space_name: str, last_modified: str, modified_by_name: str) -> list:
    """Return a list of metadata strings for the result header line."""
    parts = []
    if space_name:
        parts.append(f"Space: {space_name} ({space})" if space_name != space else f"Space: {space}")
    if last_modified and last_modified != "unknown":
        mod = f"Last modified: {last_modified}"
        if modified_by_name:
            mod += f" by {modified_by_name}"
        parts.append(mod)
    return parts


def _format_excerpt(raw: str, max_len: int = 200) -> str:
    """Strip highlight markers and truncate an excerpt."""
    text = raw.replace("@@@hl@@@", "").replace("@@@endhl@@@", "").strip()
    if len(text) > max_len:
        return text[:max_len].rstrip() + "..."
    return text


def format_result(index: int, result: dict, base_url: str) -> str:
    """Format a single search result as human-readable text."""
    content = result.get("content", {})
    title = content.get("title") or result.get("title", "(untitled)")
    content_type = content.get("type", "")
    space = (content.get("space") or {}).get("key", "")
    space_name = (content.get("space") or {}).get("name", space)

    web_link = (content.get("_links") or {}).get("webui", "")
    url = f"{base_url}/wiki{web_link}" if web_link.startswith("/") else web_link

    last_modified = format_date(result.get("lastModified"))
    modified_by_name = ((content.get("version") or {}).get("by") or {}).get("displayName", "")
    excerpt = _format_excerpt(result.get("excerpt", ""))

    lines = [f"{index}. {title} [{content_type}]"]
    meta_parts = _build_meta_parts(space, space_name, last_modified, modified_by_name)
    if meta_parts:
        lines.append(f"   {' | '.join(meta_parts)}")
    if url:
        lines.append(f"   URL: {url}")
    if excerpt:
        lines.append(f"   Excerpt: ...{excerpt}...")

    return "\n".join(lines)


def run_text(results: list, cql: str, base_url: str) -> None:
    shown = len(results)
    print(f"Found {shown} result(s) for: {cql}\n")
    for i, result in enumerate(results, start=1):
        print(format_result(i, result, base_url))
        if i < shown:
            print()


def run_json_output(results: list, cql: str, base_url: str) -> None:
    output = []
    for result in results:
        content = result.get("content", {})
        web_link = (content.get("_links") or {}).get("webui", "")
        url = f"{base_url}/wiki{web_link}" if web_link.startswith("/") else web_link
        excerpt = result.get("excerpt", "").replace("@@@hl@@@", "").replace("@@@endhl@@@", "")
        output.append({
            "title": content.get("title") or result.get("title", ""),
            "type": content.get("type", ""),
            "id": content.get("id", ""),
            "space": (content.get("space") or {}).get("key", ""),
            "space_name": (content.get("space") or {}).get("name", ""),
            "url": url,
            "last_modified": result.get("lastModified", ""),
            "excerpt": excerpt.strip(),
        })
    print(json.dumps({"cql": cql, "total": len(results), "results": output}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Confluence using CQL.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  ATLASSIAN_USER_EMAIL    Your Atlassian account email (required)
  ATLASSIAN_USER_API_KEY  Your Atlassian API token (required)
  ATLASSIAN_BASE_URL      Your Confluence base URL (optional if --base-url is passed)

CQL quick reference:
  text ~ "keyword"                    full-text search across title, body, labels
  title ~ "keyword"                   search by title
  title = "Exact Title"               exact title match
  type = page                         filter by type (page, blogpost, attachment, ...)
  space = ENG                         filter by space key
  space IN (ENG, OPS)                 multiple spaces
  label = "on-call"                   filter by label
  lastmodified >= now("-2w")          modified in last 2 weeks
  created > 2025-01-01                created after a date
  ancestor = 12345                    all descendants of a page
  parent = 12345                      direct children of a page

Operators: = != ~ !~ > >= < <= IN NOT IN AND OR NOT
Order by:  ORDER BY lastmodified DESC / created DESC / title ASC

CQL reference: https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/
""",
    )
    parser.add_argument("cql", help="CQL query string")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Confluence base URL. Falls back to ATLASSIAN_BASE_URL env var.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of results to return (default: 25).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON.",
    )
    args = parser.parse_args()

    auth = get_auth()
    base_url = get_base_url(args.base_url)
    results = search(base_url, args.cql, args.limit, auth)

    if not results:
        print(f"No results found for: {args.cql}")
        return

    if args.output_json:
        run_json_output(results, args.cql, base_url)
    else:
        run_text(results, args.cql, base_url)


if __name__ == "__main__":
    main()
