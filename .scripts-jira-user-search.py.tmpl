#!/usr/bin/env python3
"""Query Jira Cloud users via /user/search (default: fast JSON only from that endpoint).

By default each result includes accountId, the raw user_search object from Jira, and
mention_hint. Use --verbose to also call GET /user (with expand) and /user/groups per
match (slow for many hits; parallelized with --workers).

Default --max-results is 10 users per /user/search request; pass --max-results N to change it,
and --all-pages to keep requesting until a short page.

Uses GET /rest/api/3/user/search (see User search API). With --verbose, for each accountId:
  - GET /rest/api/3/user?expand=groups,applicationRoles
  - GET /rest/api/3/user/groups?accountId=...

Auth: HTTP Basic with email + API token (same pattern as Atlassian docs).

Environment (optional if flags are set):
  ATLASSIAN_SITE — site base URL, e.g. https://your-domain.atlassian.net
  ATLASSIAN_USER_EMAIL — Atlassian account email
  ATLASSIAN_USER_API_KEY — API token

Output JSON includes elapsed_seconds: wall time in seconds for /user/search (all pages) plus
optional --verbose enrichment, after arguments are validated.

Docs:
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-user-search/#api-rest-api-3-user-search-get
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-users/#api-rest-api-3-user-get
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

ACCEPT_JSON = "application/json"


def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def _normalize_site(url: str) -> str:
    u = url.strip().rstrip("/")
    if not u.startswith("http://") and not u.startswith("https://"):
        u = "https://" + u
    return u


def _basic_auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _request_json(
    url: str,
    *,
    headers: dict[str, str],
    method: str = "GET",
    data: bytes | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any | None, str]:
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            status = resp.getcode() or 200
            if not body.strip():
                return status, None, body
            try:
                return status, json.loads(body), body
            except json.JSONDecodeError:
                return status, None, body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        try:
            parsed = json.loads(err_body) if err_body.strip() else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, parsed, err_body


def _search_users(
    site: str,
    *,
    query: str,
    start_at: int,
    max_results: int,
    account_id: str | None,
    username: str | None,
    user_property: str | None,
    auth_header: str,
) -> tuple[int, list[dict[str, Any]], str | None]:
    params: dict[str, str | int] = {
        "query": query,
        "startAt": start_at,
        "maxResults": max_results,
    }
    if account_id:
        params["accountId"] = account_id
    if username:
        params["username"] = username
    if user_property:
        params["property"] = user_property
    qs = urllib.parse.urlencode(params)
    url = f"{site}/rest/api/3/user/search?{qs}"
    headers = {"Accept": ACCEPT_JSON, "Authorization": auth_header}
    status, payload, raw = _request_json(url, headers=headers)
    if status != 200:
        return status, [], raw
    if not isinstance(payload, list):
        return status, [], raw
    return status, payload, None


def _get_user_profile(
    site: str,
    account_id: str,
    *,
    expand: str,
    auth_header: str,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({"accountId": account_id, "expand": expand})
    url = f"{site}/rest/api/3/user?{params}"
    headers = {"Accept": ACCEPT_JSON, "Authorization": auth_header}
    status, payload, raw = _request_json(url, headers=headers)
    return _wrap_json_response(status, payload, raw)


def _wrap_json_response(status: int, payload: Any, raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {"http_status": status}
    if isinstance(payload, (dict, list)):
        out["body"] = payload
    else:
        out["body"] = None
        out["raw"] = raw[:2000] if raw else None
    return out


def _get_user_groups(
    site: str,
    account_id: str,
    *,
    auth_header: str,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({"accountId": account_id})
    url = f"{site}/rest/api/3/user/groups?{params}"
    headers = {"Accept": ACCEPT_JSON, "Authorization": auth_header}
    status, payload, raw = _request_json(url, headers=headers)
    return _wrap_json_response(status, payload, raw)


def _gather_search_results(
    site: str,
    *,
    query: str,
    start_at: int,
    max_results: int,
    all_pages: bool,
    account_id: str | None,
    username: str | None,
    user_property: str | None,
    auth_header: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], int]:
    collected: list[dict[str, Any]] = []
    start = start_at
    page = 0
    while True:
        status, users, raw = _search_users(
            site,
            query=query,
            start_at=start,
            max_results=max_results,
            account_id=account_id,
            username=username,
            user_property=user_property,
            auth_header=auth_header,
        )
        if status != 200:
            return {"http_status": status, "response": raw}, [], page
        collected.extend(users)
        page += 1
        if not all_pages or len(users) < max_results:
            break
        start += max_results
    return None, collected, page


def _dedupe_account_ids(users: list[dict[str, Any]]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for u in users:
        aid = u.get("accountId")
        if not isinstance(aid, str) or not aid:
            continue
        if aid not in by_id:
            by_id[aid] = u
            order.append(aid)
    return order, by_id


def _mention_hint(account_id: str, search_row: dict[str, Any]) -> dict[str, Any] | None:
    display = search_row.get("displayName")
    if isinstance(display, str):
        return {"adf_mention_attrs": {"id": account_id, "text": f"@{display}"}}
    return None


def _enrich_one_user(
    site: str,
    aid: str,
    search_row: dict[str, Any],
    *,
    search_only: bool,
    expand: str,
    skip_groups: bool,
    auth_header: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "accountId": aid,
        "user_search": search_row,
        "mention_hint": _mention_hint(aid, search_row),
    }
    if search_only:
        return row

    row["user"] = _get_user_profile(site, aid, expand=expand, auth_header=auth_header)
    if not skip_groups:
        row["user_groups"] = _get_user_groups(site, aid, auth_header=auth_header)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Search Jira Cloud users: default outputs /user/search fields plus mention_hint; "
            "--verbose adds GET /user and /user/groups per hit."
        ),
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search string (display name, email fragment, etc.).",
    )
    parser.add_argument(
        "-q",
        "--query",
        dest="query_opt",
        default=None,
        help="Same as positional query.",
    )
    parser.add_argument(
        "-s",
        "--site",
        default=_env("ATLASSIAN_SITE"),
        help="Site base URL (or ATLASSIAN_SITE).",
    )
    parser.add_argument(
        "--email",
        default=_env("ATLASSIAN_USER_EMAIL"),
        help="Atlassian account email (or ATLASSIAN_USER_EMAIL).",
    )
    parser.add_argument(
        "--token",
        default=_env("ATLASSIAN_USER_API_KEY"),
        help="API token (or ATLASSIAN_USER_API_KEY).",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Max users returned per /user/search request (default 10). Use --all-pages to fetch more pages at this size.",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=0,
        help="Starting index for first /user/search page.",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Follow pagination until a page returns fewer than max-results hits.",
    )
    parser.add_argument(
        "--account-id",
        default=None,
        help="Optional accountId filter passed to /user/search.",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Optional username parameter (deprecated in Cloud; rarely useful).",
    )
    parser.add_argument(
        "--property",
        default=None,
        dest="user_property",
        help="Optional user property filter for /user/search.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="After search, fetch GET /user (expand) and /user/groups per match (slower).",
    )
    parser.add_argument(
        "--expand",
        default="groups,applicationRoles",
        help="expand= value for GET /rest/api/3/user (default groups,applicationRoles).",
    )
    parser.add_argument(
        "--skip-groups-endpoint",
        action="store_true",
        help="Do not call GET /rest/api/3/user/groups (groups may still appear via --expand).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        metavar="N",
        help="Parallel threads for per-user enrichment when --verbose (default 8). Use 1 for sequential.",
    )
    args = parser.parse_args()
    q = args.query or args.query_opt
    if not q:
        parser.error("query is required (positional or -q).")
    if not args.site:
        parser.error("site is required (-s or ATLASSIAN_SITE).")
    if not args.email or not args.token:
        parser.error(
            "email and token are required (--email/--token or env "
            "ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY).",
        )

    site = _normalize_site(args.site)
    auth = _basic_auth_header(args.email, args.token)

    t0 = time.perf_counter()
    search_err, collected, pages_fetched = _gather_search_results(
        site,
        query=q,
        start_at=args.start_at,
        max_results=args.max_results,
        all_pages=args.all_pages,
        account_id=args.account_id,
        username=args.username,
        user_property=args.user_property,
        auth_header=auth,
    )
    if search_err is not None:
        elapsed = round(time.perf_counter() - t0, 3)
        json.dump(
            {"error": "user_search_failed", "elapsed_seconds": elapsed, **search_err},
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1

    order, by_id = _dedupe_account_ids(collected)
    search_only = not args.verbose

    def enrich_aid(aid: str) -> dict[str, Any]:
        return _enrich_one_user(
            site,
            aid,
            by_id[aid],
            search_only=search_only,
            expand=args.expand,
            skip_groups=args.skip_groups_endpoint,
            auth_header=auth,
        )

    if search_only or args.workers <= 1 or len(order) <= 1:
        results = [enrich_aid(aid) for aid in order]
    else:
        workers = min(max(1, args.workers), len(order))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(enrich_aid, order))

    elapsed = round(time.perf_counter() - t0, 3)
    out = {
        "site": site,
        "query": q,
        "elapsed_seconds": elapsed,
        "pages_fetched": pages_fetched,
        "total_unique_users": len(results),
        "users": results,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
