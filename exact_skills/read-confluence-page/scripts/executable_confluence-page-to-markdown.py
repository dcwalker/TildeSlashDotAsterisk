#!/usr/bin/env python3
"""
Download a Confluence page and convert it to Markdown.

Downloads the page content, converts HTML to Markdown using html2text,
downloads any file attachments locally, and rewrites attachment links in the
Markdown to point to the local paths. When a page has comments, a second file
is written with the same basename plus "-with-comments" before ".md": inline
comments are inserted after the highlighted text in the body, wrapped with the
same blank-line / two-dash / blank-line marker before and after the thread; after
the opening marker, a bold ``Comment`` line precedes the API selection shown as a
Markdown blockquote (`>`), then the comment bodies.
Page-level (footer) comments
appear in a "## Comments" section at the end. The primary ".md" file stays
free of comment content, matching the export behavior before comment support.

When REST API v2 lists non-page children (whiteboards, databases, folders,
etc.), the script writes stub Markdown files with YAML metadata and product
links so you can see what exists and open Confluence for full canvas or
database data.

Authentication uses basic auth via the environment variables:
  ATLASSIAN_USER_EMAIL    Your Atlassian account email
  ATLASSIAN_USER_API_KEY  Your Atlassian API token (https://id.atlassian.com/manage-profile/security/api-tokens)

Documented Confluence URL formats:
  https://confluence.atlassian.com/confkb/the-differences-between-various-url-formats-for-a-confluence-page-278692715.html

Usage:
  confluence-page-to-markdown.py <URL> [--output-dir DIR] [--single-page]

By default, child content is fetched recursively; each item is written under its own
folder (root page at the output root, descendants under children/<id>-<slug>/).
Markdown files are named with a zero-padded Confluence nav position prefix when the
REST API v2 exposes it (e.g. 00000057-Page-Title.md) so directory listings match sidebar order.
Pass --single-page to export only the URL target with no child recursion.

Examples:
  confluence-page-to-markdown.py "https://mysite.atlassian.net/wiki/spaces/ENG/pages/123456/My+Page"
  confluence-page-to-markdown.py "https://mysite.atlassian.net/wiki/spaces/ENG/overview"
  confluence-page-to-markdown.py "https://mysite.atlassian.net/wiki/x/aBcDe" --output-dir ./docs
  confluence-page-to-markdown.py "https://..." --single-page
"""

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

try:
    import requests
except ImportError:
    print("Error: 'requests' is not installed. Run: pip3 install --user requests", file=sys.stderr)
    sys.exit(1)

try:
    import html2text
except ImportError:
    print("Error: 'html2text' is not installed. Run: pip3 install --user html2text", file=sys.stderr)
    sys.exit(1)


# Closing fence for ```json blocks appended to Markdown bodies (Sonar S1192).
MD_JSON_FENCE_END = "\n```\n"

# Accept header for Confluence REST v2 JSON responses (Sonar S1192).
HTTP_ACCEPT_JSON = "application/json"

# Wraps each inserted inline thread and separates replies inside it (blank line, --, blank line).
COMMENT_BLOCK_SEPARATOR = "\n\n--\n\n"

# Label after the opening ``--`` and before the quoted selection (Markdown bold).
INLINE_COMMENT_LABEL = "**Comment**"

# v2 API collection segment for GET /wiki/api/v2/{segment}/{id} and .../direct-children
# GET /wiki/rest/api/content/{id}/child/comment — see Confluence REST v1
# "Content - children and descendants".
COMMENT_EXPAND = "body.view,version,history"

V2_COLLECTION_BY_TYPE: dict[str, str] = {
    "page": "pages",
    "whiteboard": "whiteboards",
    "database": "databases",
    "folder": "folders",
    "embed": "embeds",
    "smart_link": "embeds",
}


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


def fetch_space_homepage_id(base_url: str, space_key: str, auth: tuple) -> str:
    """Fetch the homepage ID for a space. Used to resolve space overview URLs."""
    resp = requests.get(
        f"{base_url}/wiki/rest/api/space/{space_key}",
        params={"expand": "homepage"},
        auth=auth,
    )
    resp.raise_for_status()
    data = resp.json()
    homepage = data.get("homepage")
    if not homepage or not homepage.get("id"):
        print(
            f"Error: space '{space_key}' has no homepage or is not accessible.",
            file=sys.stderr,
        )
        sys.exit(1)
    return homepage["id"]


def search_page_by_title(
    base_url: str, space_key: str, title: str, auth: tuple
) -> str:
    """Search for a page by space key and title; return the page ID."""
    resp = requests.get(
        f"{base_url}/wiki/rest/api/content",
        params={"spaceKey": space_key, "title": title, "type": "page"},
        auth=auth,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        print(
            f"Error: no page found in space '{space_key}' with title '{title}'.",
            file=sys.stderr,
        )
        sys.exit(1)
    return results[0]["id"]


def parse_confluence_url(url: str) -> tuple:
    """Return (base_url, page_id) from a Confluence page URL.

    Documented Confluence URL formats:
    https://confluence.atlassian.com/confkb/the-differences-between-various-url-formats-for-a-confluence-page-278692715.html

    Supported:
      Modern Cloud pages:
        https://site.atlassian.net/wiki/spaces/SPACE/pages/12345/Title
      Blog posts:
        https://site.atlassian.net/wiki/spaces/SPACE/blog/YYYY/MM/DD/12345/Title
      Space overview (resolves to the space homepage):
        https://site.atlassian.net/wiki/spaces/SPACE/overview
      PageId format:
        https://site.atlassian.net/wiki/pages/viewpage.action?pageId=12345
      Pretty (display) format:
        https://site.atlassian.net/wiki/display/SPACE/Title
      Tiny link:
        https://site.atlassian.net/wiki/x/aBcDe

    Blog posts and whiteboard/live-doc pages (non-page content types) that
    share the modern Cloud URL structure are handled by the same regex.
    Non-page types may fail v1 content fetch; use stubs or fix the URL.
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    auth = get_auth()

    # Modern Cloud pages and blog posts:
    #   /wiki/spaces/{spaceKey}/pages/{pageId}[/Title]
    #   /wiki/spaces/{spaceKey}/blog/{YYYY}/{MM}/{DD}/{pageId}[/Title]
    match = re.search(
        r"/wiki/spaces/[^/]+/(?:pages|blog)/(?:\d{4}/\d{2}/\d{2}/)?(\d+)",
        parsed.path,
    )
    if match:
        return base_url, match.group(1)

    # PageId format: /wiki/pages/viewpage.action?pageId=...
    if "viewpage.action" in parsed.path:
        params = parse_qs(parsed.query)
        if "pageId" in params:
            return base_url, params["pageId"][0]

    # Pretty (display) format: /wiki/display/{spaceKey}/Page+Title
    match = re.search(r"/wiki/display/([^/]+)/(.+)", parsed.path)
    if match:
        space_key = match.group(1)
        title = unquote(match.group(2)).replace("+", " ")
        return base_url, search_page_by_title(base_url, space_key, title, auth)

    # Space overview: /wiki/spaces/{spaceKey}/overview -> resolves to the space homepage
    match = re.search(r"/wiki/spaces/([^/]+)/overview", parsed.path)
    if match:
        space_key = match.group(1)
        return base_url, fetch_space_homepage_id(base_url, space_key, auth)

    # Tiny link: /wiki/x/{base64encodedPageId}
    # Encoding spec: https://confluence.atlassian.com/confkb/how-to-programmatically-generate-the-tiny-link-of-a-confluence-page-956713432.html
    match = re.search(r"/wiki/x/([A-Za-z0-9+/=_-]+)$", parsed.path)
    if match:
        try:
            raw = base64.b64decode(match.group(1) + "==")  # padding tolerance
            page_id = str(int.from_bytes(raw, byteorder="big"))
            return base_url, page_id
        except Exception:
            pass

    print(f"Error: unrecognised Confluence URL format: {url}", file=sys.stderr)
    print("Supported formats:", file=sys.stderr)
    print(
        "  https://site.atlassian.net/wiki/spaces/SPACE/pages/12345/Title   (modern Cloud)",
        file=sys.stderr,
    )
    print(
        "  https://site.atlassian.net/wiki/spaces/SPACE/overview            (space homepage)",
        file=sys.stderr,
    )
    print(
        "  https://site.atlassian.net/wiki/spaces/SPACE/blog/YYYY/MM/DD/12345/Title  (blog post)",
        file=sys.stderr,
    )
    print(
        "  https://site.atlassian.net/wiki/pages/viewpage.action?pageId=12345",
        file=sys.stderr,
    )
    print(
        "  https://site.atlassian.net/wiki/display/SPACE/Title",
        file=sys.stderr,
    )
    print(
        "  https://site.atlassian.net/wiki/x/aBcDe                         (tiny link)",
        file=sys.stderr,
    )
    sys.exit(1)


def absolute_webui_url(base_url: str, webui: Optional[str]) -> Optional[str]:
    """Turn a Confluence _links.webui path into an absolute URL."""
    if not webui:
        return None
    if webui.startswith("http://") or webui.startswith("https://"):
        return webui
    path = webui if webui.startswith("/") else f"/{webui}"
    return f"{base_url.rstrip('/')}{path}"


def _fmt_yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    s = str(v)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _yaml_lines_for_value(key: str, v) -> list[str]:
    """Return YAML lines for one front matter key (Sonar: lowers format_yaml_frontmatter complexity)."""
    if v is None:
        return []
    key = str(key)
    if isinstance(v, list):
        lines = [f"{key}:"]
        lines.extend(f"  - {_fmt_yaml_scalar(item)}" for item in v)
        return lines
    if isinstance(v, dict):
        lines = [f"{key}:"]
        for sk, sv in v.items():
            if sv is None:
                continue
            lines.append(f"  {sk}: {_fmt_yaml_scalar(sv)}")
        return lines
    return [f"{key}: {_fmt_yaml_scalar(v)}"]


def format_yaml_frontmatter(data: dict) -> str:
    """Serialise a flat dict (scalars and lists of scalars) to YAML front matter."""
    lines = ["---"]
    for k, v in data.items():
        lines.extend(_yaml_lines_for_value(k, v))
    lines.append("---")
    return "\n".join(lines) + "\n"


def markdown_json_block(
    heading: str, obj: dict, max_chars: int, *, section_lead: str = "\n"
) -> str:
    """Append a ## heading plus fenced JSON dump (truncated) to Markdown."""
    return (
        f"{section_lead}## {heading}\n\n```json\n"
        + json.dumps(obj, indent=2, ensure_ascii=False, default=str)[:max_chars]
        + MD_JSON_FENCE_END
    )


def _page_space_fields(space: dict) -> dict:
    out: dict = {}
    if space.get("key"):
        out["space_key"] = space["key"]
    if space.get("name"):
        out["space_name"] = space["name"]
    return out


def _page_sorted_labels(page: dict) -> list[str]:
    labels: list[str] = []
    meta = page.get("metadata") or {}
    for lbl in (meta.get("labels") or {}).get("results", []) or []:
        name = lbl.get("label")
        if name:
            labels.append(str(name))
    return sorted(set(labels)) if labels else []


def _page_ancestor_fields(ancestors: list) -> dict:
    if not ancestors:
        return {}
    return {
        "ancestor_ids": [str(a.get("id", "")) for a in ancestors if a.get("id")],
        "ancestor_titles": [str(a.get("title", "")) for a in ancestors],
    }


def _page_version_fields(ver: dict) -> dict:
    out: dict = {}
    if ver.get("number") is not None:
        num = ver["number"]
        out["version_number"] = int(num) if str(num).isdigit() else num
    if ver.get("when"):
        out["version_when"] = str(ver["when"])
    if ver.get("message"):
        out["version_message"] = str(ver["message"])
    return out


def build_page_frontmatter(page: dict, base_url: str) -> dict:
    """Extract searchable metadata from a v1 content JSON payload (page or blog)."""
    fm: dict = {
        "confluence_content_type": str(page.get("type", "page")),
        "confluence_content_id": str(page.get("id", "")),
        "title": page.get("title") or "",
    }
    fm.update(_page_space_fields(page.get("space") or {}))
    labels = _page_sorted_labels(page)
    if labels:
        fm["labels"] = labels
    fm.update(_page_ancestor_fields(page.get("ancestors") or []))
    fm.update(_page_version_fields(page.get("version") or {}))
    links = page.get("_links") or {}
    web = absolute_webui_url(base_url, links.get("webui"))
    if web:
        fm["confluence_web_url"] = web
    status = page.get("status")
    if status:
        fm["status"] = str(status)
    return fm


def frontmatter_from_v2_object(
    base_url: str, obj: dict, content_type: str
) -> dict:
    """Build front matter fields from a typical v2 JSON object (page, folder, etc.)."""
    fm: dict = {
        "confluence_content_type": content_type,
        "confluence_content_id": str(obj.get("id", "")),
        "title": str(obj.get("title", "")),
    }
    if obj.get("parentId") is not None:
        fm["parent_id"] = str(obj["parentId"])
    if obj.get("parentType"):
        fm["parent_type"] = str(obj["parentType"])
    if obj.get("spaceId"):
        fm["space_id"] = str(obj["spaceId"])
    if obj.get("status"):
        fm["status"] = str(obj["status"])
    pos = obj.get("position")
    if pos is not None:
        try:
            fm["position"] = int(pos)
        except (TypeError, ValueError):
            fm["position"] = str(pos)
    ver = obj.get("version") or {}
    if ver.get("number") is not None:
        fm["version_number"] = ver["number"]
    if ver.get("message"):
        fm["version_message"] = str(ver["message"])
    created = ver.get("createdAt")
    if created:
        fm["created_at"] = str(created)
    authored = ver.get("authorId")
    if authored:
        fm["author_id"] = str(authored)
    links = obj.get("_links") or {}
    web = absolute_webui_url(base_url, links.get("webui"))
    if web:
        fm["confluence_web_url"] = web
    return fm


def fetch_page(base_url: str, page_id: str, auth: tuple) -> dict:
    """Fetch page metadata and export_view HTML body.

    export_view returns rendered HTML with absolute URLs (rather than the raw
    Confluence XML storage format). This means macros, code blocks, panels, and
    other structured content are already expanded into HTML that html2text can
    convert cleanly, instead of appearing as raw XML tags.

    API reference:
      https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-body/
    """
    resp = requests.get(
        f"{base_url}/wiki/rest/api/content/{page_id}",
        params={"expand": "body.export_view,metadata.labels,space,ancestors,title"},
        auth=auth,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_page_nav_position_v2(base_url: str, page_id: str, auth: tuple) -> Optional[int]:
    """Return this page's sibling order (position) from REST v2, or None if unavailable."""
    detail = fetch_v2_by_id(base_url, "pages", page_id, auth)
    if not detail:
        return None
    raw = detail.get("position")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def fetch_v2_by_id(
    base_url: str, collection: str, content_id: str, auth: tuple
) -> Optional[dict]:
    """GET /wiki/api/v2/{collection}/{id}. Returns None on non-success."""
    resp = requests.get(
        f"{base_url}/wiki/api/v2/{collection}/{content_id}",
        auth=auth,
        headers={"Accept": HTTP_ACCEPT_JSON},
    )
    if not resp.ok:
        return None
    return resp.json()


def fetch_direct_children_v2(
    base_url: str, collection: str, content_id: str, auth: tuple
) -> Optional[list]:
    """Paginate GET /wiki/api/v2/{collection}/{id}/direct-children. None if unusable."""
    results: list = []
    next_url: Optional[str] = (
        f"{base_url}/wiki/api/v2/{collection}/{content_id}/direct-children"
    )
    params: Optional[dict] = {"limit": 50}
    while next_url:
        resp = requests.get(
            next_url,
            params=params,
            auth=auth,
            headers={"Accept": HTTP_ACCEPT_JSON},
        )
        if resp.status_code in (401, 403, 404):
            return None
        if not resp.ok:
            print(
                f"  Warning: v2 direct-children failed for {collection}/{content_id}: "
                f"HTTP {resp.status_code}",
                file=sys.stderr,
            )
            return None
        data = resp.json()
        results.extend(data.get("results", []))
        nxt = data.get("_links", {}).get("next")
        if nxt:
            next_url = nxt if nxt.startswith("http") else f"{base_url.rstrip('/')}{nxt}"
            params = None
        else:
            next_url = None
            params = None
    return results


def fetch_child_pages(base_url: str, page_id: str, auth: tuple) -> list:
    """List direct child pages (type page) for pagination. Empty if none or not applicable."""
    results = []
    start = 0
    limit = 50
    while True:
        resp = requests.get(
            f"{base_url}/wiki/rest/api/content/{page_id}/child/page",
            params={"start": start, "limit": limit},
            auth=auth,
        )
        if resp.status_code in (400, 404):
            return []
        if not resp.ok:
            print(
                f"  Warning: could not list child pages for {page_id}: "
                f"HTTP {resp.status_code}",
                file=sys.stderr,
            )
            return []
        data = resp.json()
        page = data.get("results", [])
        results.extend(page)
        if len(page) < limit:
            break
        start += limit
    return results


def fetch_attachments(base_url: str, page_id: str, auth: tuple) -> list:
    """Fetch list of file attachments for a page."""
    results = []
    start = 0
    limit = 50
    while True:
        resp = requests.get(
            f"{base_url}/wiki/rest/api/content/{page_id}/child/attachment",
            params={"start": start, "limit": limit, "expand": "metadata.mediaType"},
            auth=auth,
        )
        resp.raise_for_status()
        data = resp.json()
        page = data.get("results", [])
        results.extend(page)
        if len(page) < limit:
            break
        start += limit
    return results


def safe_fetch_attachments(base_url: str, content_id: str, auth: tuple) -> list:
    """Like fetch_attachments but does not abort the export on HTTP errors."""
    try:
        return fetch_attachments(base_url, content_id, auth)
    except requests.RequestException as exc:
        print(
            f"  Warning: could not list attachments for {content_id}: {exc}",
            file=sys.stderr,
        )
        return []


def fetch_comment_content_v1(base_url: str, comment_id: str, auth: tuple) -> dict:
    """GET v1 comment content with rendered body (for v2 comment ids and reply trees)."""
    resp = requests.get(
        f"{base_url}/wiki/rest/api/content/{comment_id}",
        params={"expand": "body.view,version,history"},
        auth=auth,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_v2_page_comment_list(base_url: str, page_id: str, kind: str, auth: tuple) -> list:
    """GET /wiki/api/v2/pages/{id}/{kind} with pagination; kind is inline-comments or footer-comments.

    See Confluence REST API v2 Comment group:
    https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comment/
    """
    url = f"{base_url.rstrip('/')}/wiki/api/v2/pages/{page_id}/{kind}"
    results: list = []
    first = True
    while url:
        resp = requests.get(
            url,
            params={"limit": 50} if first else None,
            auth=auth,
            headers={"Accept": HTTP_ACCEPT_JSON},
        )
        first = False
        if resp.status_code in (400, 404):
            return []
        if not resp.ok:
            print(
                f"  Warning: v2 pages/{page_id}/{kind} failed: HTTP {resp.status_code}",
                file=sys.stderr,
            )
            return []
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = (data.get("_links") or {}).get("next")
        if next_url:
            url = (
                next_url
                if next_url.startswith("http")
                else f"{base_url.rstrip('/')}{next_url}"
            )
        else:
            url = None
    return results


def safe_fetch_v2_page_comment_list(
    base_url: str, page_id: str, kind: str, auth: tuple
) -> list:
    try:
        return fetch_v2_page_comment_list(base_url, page_id, kind, auth)
    except requests.RequestException as exc:
        print(
            f"  Warning: could not list v2 {kind} for page {page_id}: {exc}",
            file=sys.stderr,
        )
        return []


def inline_anchor_text(v2_comment: dict) -> str:
    """Text span in the page that the inline comment attaches to (for Markdown search)."""
    props = v2_comment.get("properties") or {}
    s = (props.get("inlineOriginalSelection") or "").strip()
    if s:
        return s
    icp = props.get("inlineCommentProperties") or {}
    if isinstance(icp, dict):
        return (icp.get("textSelection") or "").strip()
    return ""


def inline_match_index(v2_comment: dict) -> int:
    """Which occurrence of the anchor text to use (0-based), if the API provides it."""
    props = v2_comment.get("properties") or {}
    icp = props.get("inlineCommentProperties") or {}
    for obj in (icp, props):
        if not isinstance(obj, dict):
            continue
        for key in ("textSelectionMatchIndex",):
            raw = obj.get(key)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass
    return 0


def inline_marker_ref(v2_comment: dict) -> str:
    """UUID linking the comment to ``<span class=\"inline-comment-marker\" data-ref=\"...\">`` in export_view."""
    props = v2_comment.get("properties") or {}
    ref = props.get("inlineMarkerRef") or props.get("inline-marker-ref")
    return str(ref).strip() if ref else ""


def markdown_selection_as_blockquote(selection: str) -> str:
    """Render Confluence inline selection as a Markdown blockquote (common for quoted excerpts)."""
    if not selection or not selection.strip():
        return ""
    return "\n".join(f"> {line}" for line in selection.splitlines())


def _find_nth_occurrence(haystack: str, needle: str, n: int) -> int:
    """Index of the n-th occurrence of needle (0-based n), or -1."""
    if not needle:
        return -1
    start = 0
    for i in range(n + 1):
        idx = haystack.find(needle, start)
        if idx < 0:
            return -1
        if i == n:
            return idx
        start = idx + max(len(needle), 1)
    return -1


def _ellipsis_truncated_prefix(anchor: str) -> Optional[str]:
    """When the v2 selection ends with an ellipsis, the API often truncates; Markdown has full text."""
    s = anchor.rstrip()
    if len(s) >= 3 and s.endswith("..."):
        p = s[:-3].rstrip()
        return p if p else None
    if s.endswith("\u2026"):
        p = s[:-1].rstrip()
        return p if p else None
    return None


def _insertion_index_after_anchor(markdown: str, anchor: str, match_index: int) -> int:
    """Character offset after the highlighted span in Markdown, or -1 if not found."""
    if not anchor:
        return -1
    idx = _find_nth_occurrence(markdown, anchor, match_index)
    if idx >= 0:
        return idx + len(anchor)
    prefix = _ellipsis_truncated_prefix(anchor)
    if prefix is None:
        return -1
    idx = _find_nth_occurrence(markdown, prefix, match_index)
    if idx >= 0:
        return idx + len(prefix)
    return -1


def markdown_basename_with_comments_suffix(md_name: str) -> str:
    """e.g. 00000057-Page.md -> 00000057-Page-with-comments.md"""
    if md_name.endswith(".md"):
        return md_name[:-3] + "-with-comments.md"
    return md_name + "-with-comments.md"


def comment_tree_from_v1_root(base_url: str, root_v1: dict, auth: tuple) -> dict:
    """Nested {comment, replies} from a v1 comment object (recursive replies)."""
    cid = str(root_v1["id"])
    children = safe_fetch_comment_children(base_url, cid, auth)
    return {
        "comment": root_v1,
        "replies": [comment_tree_from_v1_root(base_url, ch, auth) for ch in children],
    }


def format_comment_block_md(
    base_url: str,
    c_v1: dict,
    downloaded_attachments: list,
) -> str:
    """One comment as Markdown: author, time, body (attachment links rewritten)."""
    author = comment_author_display(c_v1)
    when = comment_timestamp(c_v1)
    html = comment_body_html(c_v1)
    body = html_to_markdown(html)
    body = rewrite_attachment_links(body, downloaded_attachments, base_url)
    return f"**{author}** ({when})\n\n{body.strip()}"


def render_inline_thread_flat(
    tree: dict,
    base_url: str,
    downloaded_attachments: list,
    *,
    highlight_text: str = "",
) -> str:
    """Depth-first thread; ``INLINE_COMMENT_LABEL``, optional blockquote, then COMMENT_BLOCK_SEPARATOR between replies."""
    parts: list[str] = []

    def walk(node: dict) -> None:
        parts.append(format_comment_block_md(base_url, node["comment"], downloaded_attachments))
        for r in node.get("replies") or []:
            walk(r)

    walk(tree)
    thread_md = COMMENT_BLOCK_SEPARATOR.join(parts)
    highlight = markdown_selection_as_blockquote(highlight_text)
    if highlight:
        return f"{INLINE_COMMENT_LABEL}\n\n{highlight}\n\n{thread_md}"
    return f"{INLINE_COMMENT_LABEL}\n\n{thread_md}"


def insert_inline_comments_into_markdown(
    markdown: str,
    inline_v2_list: list,
    base_url: str,
    auth: tuple,
    downloaded_attachments: list,
    page_export_html: Optional[str] = None,
) -> str:
    """Insert each inline thread after its anchor text; unanchored threads go at EOF.

    If ``page_export_html`` is set, the full highlight is taken from the inline
    comment marker span (see ``inlineMarkerRef``) so placement matches the same
    ``html_to_markdown`` output as the page body. Otherwise the v2 selection
    string is used; if it ends with ``...`` (truncation), matching falls back to
    a prefix (see ``_insertion_index_after_anchor``).
    """
    placements: list[tuple[int, str]] = []
    for ic in inline_v2_list:
        cid = str(ic.get("id", ""))
        if not cid:
            continue
        placement_anchor, highlight_text = _placement_anchor_and_highlight_for_inline(
            ic, page_export_html
        )
        try:
            root_v1 = fetch_comment_content_v1(base_url, cid, auth)
        except requests.RequestException:
            continue
        tree = comment_tree_from_v1_root(base_url, root_v1, auth)
        block = render_inline_thread_flat(
            tree,
            base_url,
            downloaded_attachments,
            highlight_text=highlight_text,
        )
        if not block.strip():
            continue
        suffix = COMMENT_BLOCK_SEPARATOR + block + COMMENT_BLOCK_SEPARATOR
        if not placement_anchor:
            placements.append((len(markdown), suffix))
            continue
        end = _insertion_index_after_anchor(
            markdown, placement_anchor, inline_match_index(ic)
        )
        if end < 0:
            placements.append((len(markdown), suffix))
            continue
        placements.append((end, suffix))
    # Insert from the end so indices stay valid; merge same insertion points in order.
    by_end: dict[int, list[str]] = {}
    for end, txt in placements:
        by_end.setdefault(end, []).append(txt)
    for end in sorted(by_end.keys(), reverse=True):
        merged = "".join(by_end[end])
        markdown = markdown[:end] + merged + markdown[end:]
    return markdown


def fetch_comment_children(base_url: str, parent_id: str, auth: tuple) -> list:
    """Fetch all direct child comments for a page or comment (paginated)."""
    results: list = []
    start = 0
    limit = 50
    while True:
        resp = requests.get(
            f"{base_url}/wiki/rest/api/content/{parent_id}/child/comment",
            params={
                "start": start,
                "limit": limit,
                "expand": COMMENT_EXPAND,
            },
            auth=auth,
        )
        resp.raise_for_status()
        data = resp.json()
        page = data.get("results", [])
        results.extend(page)
        if len(page) < limit:
            break
        start += limit
    return results


def safe_fetch_comment_children(base_url: str, parent_id: str, auth: tuple) -> list:
    """Like fetch_comment_children but does not abort the export on HTTP errors."""
    try:
        return fetch_comment_children(base_url, parent_id, auth)
    except requests.RequestException as exc:
        print(
            f"  Warning: could not list comments for {parent_id}: {exc}",
            file=sys.stderr,
        )
        return []


def comment_body_html(comment: dict) -> str:
    """Prefer rendered HTML for comment bodies (same idea as export_view for pages)."""
    body = comment.get("body") or {}
    for key in ("export_view", "view", "storage"):
        part = body.get(key)
        if isinstance(part, dict) and part.get("value"):
            return str(part["value"])
    return ""


def comment_author_display(comment: dict) -> str:
    hist = comment.get("history") or {}
    created = hist.get("createdBy")
    if isinstance(created, dict):
        return (
            created.get("displayName")
            or created.get("publicName")
            or created.get("email")
            or created.get("username")
            or "Unknown"
        )
    return "Unknown"


def comment_timestamp(comment: dict) -> str:
    ver = comment.get("version") or {}
    when = ver.get("when")
    if when:
        return str(when)
    hist = comment.get("history") or {}
    if hist.get("createdDate"):
        return str(hist["createdDate"])
    return ""


def _heading_for_depth(depth: int) -> str:
    level = min(2 + depth, 6)
    return "#" * level


def render_comment_tree_markdown(
    tree: list,
    base_url: str,
    downloaded_attachments: list,
    depth: int,
    *,
    attachment_rel_prefix: str = "",
) -> str:
    """Render nested comments as Markdown with increasing heading depth."""
    parts: list[str] = []
    for node in tree:
        c = node["comment"]
        replies = node.get("replies") or []
        hid = _heading_for_depth(depth)
        title = (c.get("title") or "").strip() or f"Comment {c.get('id', '')}"
        author = comment_author_display(c)
        when = comment_timestamp(c)
        html = comment_body_html(c)
        md = html_to_markdown(html)
        md = rewrite_attachment_links(
            md,
            downloaded_attachments,
            base_url,
            attachment_rel_prefix=attachment_rel_prefix,
        )
        meta_lines = [f"**Author:** {author}"]
        if when:
            meta_lines.append(f"**When:** {when}")
        meta_block = "  \n".join(meta_lines)
        parts.append(f"\n{hid} {title}\n\n{meta_block}\n\n{md.strip()}\n")
        if replies:
            parts.append(
                render_comment_tree_markdown(
                    replies,
                    base_url,
                    downloaded_attachments,
                    depth + 1,
                    attachment_rel_prefix=attachment_rel_prefix,
                )
            )
    return "".join(parts)


def render_footer_comments_section_markdown(
    footer_v2_list: list,
    base_url: str,
    auth: tuple,
    downloaded_attachments: list,
) -> str:
    """## Comments plus threaded footer comments (headings start at ###)."""
    if not footer_v2_list:
        return ""
    parts: list[str] = ["\n\n## Comments\n\n"]
    for fc in footer_v2_list:
        cid = str(fc.get("id", ""))
        if not cid:
            continue
        try:
            root_v1 = fetch_comment_content_v1(base_url, cid, auth)
        except requests.RequestException:
            continue
        tree = comment_tree_from_v1_root(base_url, root_v1, auth)
        parts.append(
            render_comment_tree_markdown(
                [tree],
                base_url,
                downloaded_attachments,
                1,
                attachment_rel_prefix="",
            )
        )
    return "".join(parts)


def maybe_write_markdown_with_comments(
    base_url: str,
    content_id: str,
    output_dir: Path,
    md_name: str,
    header: str,
    title: str,
    markdown_body: str,
    child_section: str,
    downloaded_attachments: list,
    auth: tuple,
    page_export_html: Optional[str] = None,
) -> None:
    """If v2 reports inline or footer comments, write *-with-comments.md next to the base file."""
    inline_list = safe_fetch_v2_page_comment_list(
        base_url, content_id, "inline-comments", auth
    )
    footer_list = safe_fetch_v2_page_comment_list(
        base_url, content_id, "footer-comments", auth
    )
    if not inline_list and not footer_list:
        return
    print("  Building -with-comments variant (v2 inline/footer) ...")
    md_with = insert_inline_comments_into_markdown(
        markdown_body,
        inline_list,
        base_url,
        auth,
        downloaded_attachments,
        page_export_html=page_export_html,
    )
    md_with = md_with + child_section
    md_with += render_footer_comments_section_markdown(
        footer_list, base_url, auth, downloaded_attachments
    )
    out_path = output_dir / markdown_basename_with_comments_suffix(md_name)
    out_path.write_text(header + f"# {title}\n\n" + md_with, encoding="utf-8")
    print(f"  Wrote {out_path}")


def download_attachment(base_url: str, attachment: dict, output_dir: Path, auth: tuple) -> Path:
    """Download a single attachment and return its local path."""
    filename = attachment["title"]
    download_path = attachment["_links"]["download"]
    url = f"{base_url}/wiki{download_path}" if download_path.startswith("/") else download_path

    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    local_path = attachments_dir / filename

    resp = requests.get(url, auth=auth, stream=True)
    resp.raise_for_status()
    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return local_path


def html_to_markdown(html: str) -> str:
    """Convert HTML string to Markdown using html2text."""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.body_width = 0  # no line wrapping
    converter.protect_links = True
    converter.wrap_links = False
    return converter.handle(html)


def _span_inner_html_balanced(html: str, start: int) -> Optional[str]:
    """Return inner HTML of a ``<span>`` opened just before ``start``, handling nested spans."""
    depth = 1
    i = start
    while i < len(html) and depth:
        nxt = html.find("<", i)
        if nxt < 0:
            return None
        if html[nxt : nxt + 7].lower() == "</span>":
            depth -= 1
            if depth == 0:
                return html[start:nxt]
            i = nxt + 7
            continue
        if re.match(r"<span\b", html[nxt:], re.I):
            depth += 1
        i = nxt + 1
    return None


def _inner_html_span_inline_marker(export_html: str, marker_ref: str) -> Optional[str]:
    """Inner HTML for ``export_view`` inline comment markers (rendered ``span``)."""
    for m in re.finditer(r"<span\b[^>]*>", export_html, re.I):
        tag = m.group(0)
        if "inline-comment-marker" not in tag.lower():
            continue
        if not re.search(
            r"data-ref\s*=\s*['\"]" + re.escape(marker_ref) + r"['\"]",
            tag,
        ):
            continue
        return _span_inner_html_balanced(export_html, m.end())
    return None


def _inner_html_ac_inline_marker(export_html: str, marker_ref: str) -> Optional[str]:
    """Inner HTML for storage-style ``ac:inline-comment-marker`` (if present in HTML)."""
    m = re.search(
        r"<ac:inline-comment-marker\b[^>]*\bac:ref\s*=\s*['\"]"
        + re.escape(marker_ref)
        + r"['\"][^>]*>",
        export_html,
        re.I,
    )
    if not m:
        return None
    start = m.end()
    lower = export_html.lower()
    close = "</ac:inline-comment-marker>"
    end = lower.find(close, start)
    if end < 0:
        return None
    return export_html[start:end]


def selection_markdown_from_page_export_html(export_html: str, marker_ref: str) -> Optional[str]:
    """Convert the marked highlight in page HTML to Markdown (same pipeline as the full page)."""
    if not export_html or not marker_ref:
        return None
    inner = _inner_html_span_inline_marker(export_html, marker_ref)
    if inner is None:
        inner = _inner_html_ac_inline_marker(export_html, marker_ref)
    if inner is None:
        return None
    md = html_to_markdown(inner).strip()
    return md if md else None


def _placement_anchor_and_highlight_for_inline(
    ic: dict,
    page_export_html: Optional[str],
) -> tuple[str, str]:
    """Prefer full highlight from export_view HTML (``inlineMarkerRef``); else v2 selection string."""
    anchor_api = inline_anchor_text(ic)
    placement = anchor_api
    highlight = anchor_api
    if not page_export_html:
        return placement, highlight
    marker_ref = inline_marker_ref(ic)
    if not marker_ref:
        return placement, highlight
    full_sel = selection_markdown_from_page_export_html(page_export_html, marker_ref)
    if full_sel:
        placement = full_sel
        highlight = full_sel
    return placement, highlight


def rewrite_attachment_links(
    markdown: str,
    attachments: list,
    base_url: str,
    *,
    attachment_rel_prefix: str = "",
) -> str:
    """Replace Confluence attachment URLs in Markdown with relative local paths.

    attachment_rel_prefix is prepended before attachments/ (e.g. "../" from a
    subdirectory).
    """
    for attachment in attachments:
        filename = attachment["title"]
        download_path = attachment["_links"]["download"]
        # Match both the full URL and the relative /wiki/... path
        patterns = [
            re.escape(f"{base_url}/wiki{download_path}"),
            re.escape(f"/wiki{download_path}"),
            re.escape(download_path),
        ]
        local_rel = f"{attachment_rel_prefix}attachments/{filename}"
        for pattern in patterns:
            markdown = re.sub(pattern, local_rel, markdown)
    return markdown


def slugify(title: str) -> str:
    """Convert a page title to a safe filename."""
    slug = re.sub(r"[^\w\s-]", "", title).strip()
    slug = re.sub(r"[\s]+", "-", slug)
    return slug[:80]


def dir_from_url(url: str) -> str:
    """Derive a directory name from the URL path by replacing slashes with hyphens.

    Example:
      https://mysite.atlassian.net/wiki/spaces/ENG/pages/123456/My+Page
      -> wiki-spaces-ENG-pages-123456-My+Page
    """
    path = urlparse(url).path.strip("/")
    return path.replace("/", "-")


def child_folder_name(page_id: str, title: str) -> str:
    """Unique directory name for a child export (id first, then slug)."""
    s = slugify(title)
    name = f"{page_id}-{s}" if s else f"{page_id}"
    return name[:120]


def coalesce_child_position(child: dict) -> Optional[int]:
    """Read sibling rank from a v2 child payload, if present."""
    for key in ("childPosition", "position"):
        raw = child.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return None


def nav_position_for_page(
    position_cache: dict[str, Optional[int]],
    base_url: str,
    page_id: str,
    auth: tuple,
    sibling_position: Optional[int],
) -> Optional[int]:
    """Resolve nav position: explicit from parent list, else cache, else GET v2 page."""
    if sibling_position is not None:
        return sibling_position
    if page_id in position_cache:
        return position_cache[page_id]
    pos = fetch_page_nav_position_v2(base_url, page_id, auth)
    position_cache[page_id] = pos
    return pos


def markdown_basename(nav_position: Optional[int], title: str) -> str:
    """Markdown filename; zero-padded position prefix for lexical sort like the site tree."""
    slug = slugify(title) or "page"
    if nav_position is not None:
        return f"{nav_position:08d}-{slug}.md"
    return f"{slug}.md"


def _child_sort_tuple(child: dict) -> tuple:
    pos = coalesce_child_position(child)
    title_key = (child.get("title") or "").lower()
    cid = str(child.get("id", ""))
    if pos is not None:
        return (0, pos, title_key, cid)
    return (1, 0, title_key, cid)


def v2_type_to_collection(content_type: str) -> Optional[str]:
    """Map v2 child type string to API collection name."""
    t = str(content_type or "").lower().strip()
    return V2_COLLECTION_BY_TYPE.get(t)


def download_attachments_for_page(
    base_url: str,
    attachments: list,
    output_dir: Path,
    auth: tuple,
) -> list:
    """Download each attachment; return metadata entries that were saved successfully."""
    downloaded = []
    for att in attachments:
        filename = att["title"]
        print(f"  Downloading attachment: {filename}")
        try:
            download_attachment(base_url, att, output_dir, auth)
            downloaded.append(att)
        except Exception as exc:
            print(f"  Warning: failed to download '{filename}': {exc}", file=sys.stderr)
    return downloaded


def sorted_direct_children(base_url: str, page_id: str, auth: tuple) -> list:
    """Direct children of a page via v2 (all types returned by the API), sorted by position.

    Falls back to v1 child/page only (pages) when v2 is unavailable; whiteboards and
    databases will not appear in that fallback.
    """
    v2 = fetch_direct_children_v2(base_url, "pages", page_id, auth)
    if v2 is not None:
        children = list(v2)
        children.sort(key=_child_sort_tuple)
        return children
    raw = fetch_child_pages(base_url, page_id, auth)
    children = [c for c in raw if c.get("type") == "page"]
    children.sort(key=lambda c: (c.get("title") or "").lower())
    return children


def markdown_section_child_links(
    position_cache: dict[str, Optional[int]],
    base_url: str,
    auth: tuple,
    children: list,
) -> str:
    """Appendix linking to child Markdown files: pages vs other Confluence types."""
    if not children:
        return ""
    pages = [c for c in children if str(c.get("type", "")).lower() == "page"]
    others = [c for c in children if str(c.get("type", "")).lower() != "page"]
    parts: list[str] = []

    if pages:
        parts.append("\n\n## Child pages\n\n")
        for c in pages:
            cid = str(c["id"])
            ctitle = c.get("title", cid)
            sub = child_folder_name(cid, ctitle)
            pos = coalesce_child_position(c)
            resolved = nav_position_for_page(position_cache, base_url, cid, auth, pos)
            md_name = markdown_basename(resolved, ctitle)
            rel = f"children/{sub}/{md_name}"
            parts.append(f"- [{ctitle}]({rel})\n")

    if others:
        parts.append("\n\n## Other Confluence content\n\n")
        parts.append(
            "The items below are not full page exports. "
            "Open the product URL in metadata (or in Confluence) for whiteboards, "
            "databases, and similar tools.\n\n"
        )
        for c in others:
            cid = str(c["id"])
            ctitle = c.get("title", cid)
            ctype = str(c.get("type", "unknown"))
            sub = child_folder_name(cid, ctitle)
            pos = coalesce_child_position(c)
            coll = v2_type_to_collection(ctype)
            if coll == "pages":
                resolved = nav_position_for_page(position_cache, base_url, cid, auth, pos)
            else:
                resolved = pos
            md_name = markdown_basename(resolved, ctitle)
            rel = f"children/{sub}/{md_name}"
            parts.append(f"- [{ctitle}]({rel}) ({ctype})\n")

    return "".join(parts)


def stack_key_for_child(child: dict) -> str:
    """Unique key for cycle detection (type + id)."""
    cid = str(child.get("id", ""))
    ctype = str(child.get("type", "")).lower() or "unknown"
    return f"{ctype}:{cid}"


def recurse_export_children(
    base_url: str,
    children: list,
    output_dir: Path,
    auth: tuple,
    path_stack: list[str],
    position_cache: dict[str, Optional[int]],
) -> None:
    """Export each direct child (page, folder, whiteboard, database, etc.)."""
    for c in children:
        cid = str(c["id"])
        ctitle = c.get("title", cid)
        ctype = str(c.get("type", "")).lower() or "page"
        sub = child_folder_name(cid, ctitle)
        child_dir = output_dir / "children" / sub
        sibling_pos = coalesce_child_position(c)
        if ctype == "page":
            process_page(
                base_url,
                cid,
                child_dir,
                auth,
                recurse_children=True,
                path_stack=path_stack,
                position_cache=position_cache,
                sibling_position=sibling_pos,
            )
        elif ctype == "folder":
            process_folder(
                base_url,
                cid,
                child_dir,
                auth,
                recurse_children=True,
                path_stack=path_stack,
                position_cache=position_cache,
                sibling_position=sibling_pos,
            )
        elif ctype in ("whiteboard", "database"):
            export_v2_leaf_stub(
                base_url,
                ctype,
                cid,
                ctitle,
                child_dir,
                auth,
                path_stack,
                position_cache,
                sibling_pos,
            )
        else:
            export_generic_child_stub(
                base_url,
                c,
                child_dir,
                path_stack,
                sibling_pos,
            )


def export_generic_child_stub(
    base_url: str,
    child: dict,
    output_dir: Path,
    path_stack: list[str],
    sibling_position: Optional[int],
) -> None:
    """Stub for embeds and other v2 types when we only have the parent listing."""
    cid = str(child["id"])
    key = stack_key_for_child(child)
    if key in path_stack:
        print(
            f"  Skipping {key} (would form a cycle in the parent chain).",
            file=sys.stderr,
        )
        return
    path_stack.append(key)
    try:
        ctype = str(child.get("type", "unknown"))
        title = child.get("title", cid)
        output_dir.mkdir(parents=True, exist_ok=True)
        fm: dict = {
            "confluence_content_type": ctype,
            "confluence_content_id": cid,
            "title": str(title),
            "export_note": (
                "Stub from parent direct-children listing only. "
                "No type-specific v2 GET was used; open Confluence for full content."
            ),
        }
        pos = sibling_position if sibling_position is not None else coalesce_child_position(child)
        if pos is not None:
            fm["position"] = pos
        for optional in ("parentId", "parentType", "spaceId", "status"):
            if child.get(optional) is not None:
                fm[f"v2_{optional}"] = str(child[optional])
        links = child.get("_links") or {}
        web = absolute_webui_url(base_url, links.get("webui"))
        if web:
            fm["confluence_web_url"] = web
        body = (
            f"# {title}\n\n"
            f"This export is a placeholder for Confluence content of type `{ctype}`. "
            "The REST export does not include the full interactive representation. "
        )
        if web:
            body += f"Open in Confluence: {web}\n"
        else:
            body += "Open this item in the Confluence space tree.\n"
        raw_preview = {k: child[k] for k in child if k != "body"}
        fm["listing_json"] = json.dumps(raw_preview, ensure_ascii=False, default=str)[:4000]
        nav_pos = pos
        out_path = output_dir / markdown_basename(nav_pos, str(title))
        out_path.write_text(format_yaml_frontmatter(fm) + "\n" + body, encoding="utf-8")
        print(f"  Wrote stub {out_path}")
    finally:
        path_stack.pop()


def _v2_leaf_collection(content_type: str) -> str:
    coll = v2_type_to_collection(content_type)
    return coll if coll else "pages"


def _v2_leaf_frontmatter_and_title(
    base_url: str,
    content_type: str,
    content_id: str,
    title_hint: str,
    detail: Optional[dict],
    coll: str,
) -> tuple[dict, str]:
    if detail:
        title = str(detail.get("title") or title_hint)
        fm = frontmatter_from_v2_object(base_url, detail, content_type)
    else:
        title = str(title_hint)
        fm = {
            "confluence_content_type": content_type,
            "confluence_content_id": str(content_id),
            "title": title,
            "export_note": f"v2 GET {coll}/{content_id} failed; metadata may be incomplete.",
        }
    suffix = (
        " Canvas, database rows, and live widgets are not available via this export; use the product URL."
    )
    fm["export_note"] = (fm.get("export_note", "") + suffix).strip()
    return fm, title


def _v2_leaf_nav_position(
    sibling_position: Optional[int], detail: Optional[dict]
) -> Optional[int]:
    if sibling_position is not None:
        return sibling_position
    if not detail or detail.get("position") is None:
        return None
    try:
        return int(detail.get("position"))
    except (TypeError, ValueError):
        return None


def _v2_leaf_intro_body(
    title: str, content_type: str, content_id: str, fm: dict, detail: Optional[dict]
) -> str:
    body = f"# {title}\n\n"
    body += (
        f"Confluence **{content_type}** (id `{content_id}`). "
        "Full canvas or table data is not exported here; use the link below if present.\n\n"
    )
    web = fm.get("confluence_web_url")
    if web:
        body += f"- [Open in Confluence]({web})\n"
    if detail:
        body += markdown_json_block("API metadata (summary)", detail, 12000)
    return body


def _v2_leaf_nested_children(
    base_url: str,
    coll: str,
    content_id: str,
    auth: tuple,
    position_cache: dict[str, Optional[int]],
    body: str,
) -> tuple[str, list]:
    if coll not in ("whiteboards", "databases"):
        return body, []
    nested = fetch_direct_children_v2(base_url, coll, content_id, auth)
    if not nested:
        return body, []
    nested_children = list(nested)
    nested_children.sort(key=_child_sort_tuple)
    body += markdown_section_child_links(
        position_cache, base_url, auth, nested_children
    )
    return body, nested_children


def export_v2_leaf_stub(
    base_url: str,
    content_type: str,
    content_id: str,
    title_hint: str,
    output_dir: Path,
    auth: tuple,
    path_stack: list[str],
    position_cache: dict[str, Optional[int]],
    sibling_position: Optional[int],
) -> None:
    """Fetch v2 metadata for whiteboard or database and write a stub Markdown file."""
    key = f"{content_type}:{content_id}"
    if key in path_stack:
        print(
            f"  Skipping {key} (would form a cycle in the parent chain).",
            file=sys.stderr,
        )
        return
    path_stack.append(key)
    try:
        coll = _v2_leaf_collection(content_type)
        detail = fetch_v2_by_id(base_url, coll, content_id, auth)
        output_dir.mkdir(parents=True, exist_ok=True)
        fm, title = _v2_leaf_frontmatter_and_title(
            base_url, content_type, content_id, title_hint, detail, coll
        )
        atts = safe_fetch_attachments(base_url, content_id, auth)
        if atts:
            print(f"  Found {len(atts)} attachment(s) for {content_type} {content_id}.")
            download_attachments_for_page(base_url, atts, output_dir, auth)
        nav_pos = _v2_leaf_nav_position(sibling_position, detail)
        md_name = markdown_basename(nav_pos, title)
        body = _v2_leaf_intro_body(title, content_type, content_id, fm, detail)
        body, nested_children = _v2_leaf_nested_children(
            base_url, coll, content_id, auth, position_cache, body
        )
        out_path = output_dir / md_name
        out_path.write_text(format_yaml_frontmatter(fm) + "\n" + body, encoding="utf-8")
        print(f"  Wrote {out_path}")
        if nested_children:
            recurse_export_children(
                base_url, nested_children, output_dir, auth, path_stack, position_cache
            )
    finally:
        path_stack.pop()


def _folder_title_and_frontmatter(
    base_url: str, folder_id: str, detail: Optional[dict]
) -> tuple[str, dict]:
    title = str(detail.get("title", folder_id)) if detail else folder_id
    if detail:
        fm = frontmatter_from_v2_object(base_url, detail, "folder")
    else:
        fm = {
            "confluence_content_type": "folder",
            "confluence_content_id": folder_id,
            "title": title,
            "export_note": "v2 GET folders/{id} failed; listing children may still work.",
        }
    note_suffix = (
        " Folder exports depend on v2 direct-children; some child types may only appear in the product."
    )
    fm["export_note"] = (str(fm.get("export_note", "")) + note_suffix).strip()
    return title, fm


def _folder_nav_position(
    sibling_position: Optional[int], detail: Optional[dict]
) -> Optional[int]:
    if sibling_position is not None:
        return sibling_position
    if not detail or detail.get("position") is None:
        return None
    try:
        return int(detail["position"])
    except (TypeError, ValueError):
        return None


def _folder_body_markdown(
    title: str,
    recurse_children: bool,
    children: list,
    detail: Optional[dict],
    position_cache: dict[str, Optional[int]],
    base_url: str,
    auth: tuple,
) -> str:
    if not recurse_children:
        return f"# {title}\n\n"
    body = f"# {title}\n\n"
    body += markdown_section_child_links(position_cache, base_url, auth, children)
    if detail:
        body += markdown_json_block(
            "Folder API metadata (summary)", detail, 8000, section_lead="\n\n"
        )
    return body


def process_folder(
    base_url: str,
    folder_id: str,
    output_dir: Path,
    auth: tuple,
    *,
    recurse_children: bool,
    path_stack: list[str],
    position_cache: dict[str, Optional[int]],
    sibling_position: Optional[int] = None,
) -> None:
    """Export a folder: metadata stub, optional attachments, recurse into v2 children."""
    folder_id = str(folder_id)
    key = f"folder:{folder_id}"
    if key in path_stack:
        print(
            f"  Skipping folder {folder_id} (would form a cycle in the parent chain).",
            file=sys.stderr,
        )
        return
    path_stack.append(key)
    try:
        print(f"Fetching folder {folder_id} from {base_url} ...")
        detail = fetch_v2_by_id(base_url, "folders", folder_id, auth)
        output_dir.mkdir(parents=True, exist_ok=True)
        title, fm = _folder_title_and_frontmatter(base_url, folder_id, detail)
        atts = safe_fetch_attachments(base_url, folder_id, auth)
        if atts:
            print(f"Found {len(atts)} attachment(s).")
            download_attachments_for_page(base_url, atts, output_dir, auth)
        nav_pos = _folder_nav_position(sibling_position, detail)
        md_name = markdown_basename(nav_pos, title)
        children: list = []
        if recurse_children:
            children = fetch_direct_children_v2(base_url, "folders", folder_id, auth) or []
            children.sort(key=_child_sort_tuple)
        body = _folder_body_markdown(
            title, recurse_children, children, detail, position_cache, base_url, auth
        )
        out_path = output_dir / md_name
        out_path.write_text(format_yaml_frontmatter(fm) + "\n" + body, encoding="utf-8")
        print(f"  Wrote {out_path}")
        if recurse_children and children:
            recurse_export_children(
                base_url, children, output_dir, auth, path_stack, position_cache
            )
    finally:
        path_stack.pop()


def _write_page_v1_fetch_error_stub(
    base_url: str,
    page_id: str,
    exc: requests.HTTPError,
    output_dir: Path,
    auth: tuple,
    position_cache: dict[str, Optional[int]],
    sibling_position: Optional[int],
) -> None:
    """Write Markdown when v1 content GET fails (permissions, wrong type, etc.)."""
    print(
        f"  Warning: v1 content fetch failed for page {page_id}: {exc}. "
        "Writing error stub (no body export).",
        file=sys.stderr,
    )
    v2p = fetch_v2_by_id(base_url, "pages", page_id, auth)
    title = str(v2p.get("title", page_id)) if v2p else f"page-{page_id}"
    fm: dict = {
        "confluence_content_type": "page",
        "confluence_content_id": page_id,
        "title": title,
        "export_error": str(exc),
        "export_note": (
            "v1 export_view fetch failed. This id may be a blog post, whiteboard, "
            "or other type. Open Confluence or use v2 metadata below."
        ),
    }
    if v2p:
        fm.update(frontmatter_from_v2_object(base_url, v2p, "page"))
    body = (
        f"# {title}\n\n"
        f"**Export failed:** `{exc}`\n\n"
        "If this is a normal page, check permissions and API token scopes. "
        "Otherwise open the item in Confluence.\n"
    )
    if v2p:
        body += markdown_json_block("Page API metadata (v2)", v2p, 8000)
    nav_pos = nav_position_for_page(
        position_cache, base_url, page_id, auth, sibling_position
    )
    out_path = output_dir / markdown_basename(nav_pos, title)
    out_path.write_text(format_yaml_frontmatter(fm) + "\n" + body, encoding="utf-8")
    print(f"  Wrote error stub {out_path}")


def _process_page_success_export(
    base_url: str,
    page_id: str,
    page: dict,
    output_dir: Path,
    auth: tuple,
    recurse_children: bool,
    path_stack: list[str],
    position_cache: dict[str, Optional[int]],
    sibling_position: Optional[int],
) -> None:
    """Convert a fetched v1 page dict to Markdown, attachments, and child exports."""
    title = page.get("title", f"page-{page_id}")
    nav_pos = nav_position_for_page(
        position_cache, base_url, page_id, auth, sibling_position
    )
    md_name = markdown_basename(nav_pos, title)
    html_body = page.get("body", {}).get("export_view", {}).get("value", "")
    fm_page = build_page_frontmatter(page, base_url)
    print("Fetching attachments ...")
    attachments = safe_fetch_attachments(base_url, page_id, auth)
    print(f"Found {len(attachments)} attachment(s).")
    downloaded = download_attachments_for_page(base_url, attachments, output_dir, auth)
    print("Converting HTML to Markdown ...")
    markdown_body = html_to_markdown(html_body)
    markdown_body = rewrite_attachment_links(markdown_body, downloaded, base_url)
    child_section = ""
    children = []
    if recurse_children:
        children = sorted_direct_children(base_url, page_id, auth)
        child_section = markdown_section_child_links(
            position_cache, base_url, auth, children
        )
    output_path = output_dir / md_name
    header = format_yaml_frontmatter(fm_page)
    output_path.write_text(
        header + f"# {title}\n\n" + markdown_body + child_section, encoding="utf-8"
    )
    print(f"  Wrote {output_path}")
    maybe_write_markdown_with_comments(
        base_url,
        page_id,
        output_dir,
        md_name,
        header,
        title,
        markdown_body,
        child_section,
        downloaded,
        auth,
        html_body,
    )
    if children:
        recurse_export_children(
            base_url, children, output_dir, auth, path_stack, position_cache
        )


def process_page(
    base_url: str,
    page_id: str,
    output_dir: Path,
    auth: tuple,
    *,
    recurse_children: bool,
    path_stack: list[str],
    position_cache: dict[str, Optional[int]],
    sibling_position: Optional[int] = None,
) -> None:
    """Fetch one page, write Markdown and attachments, optionally recurse into children."""
    page_id = str(page_id)
    key = f"page:{page_id}"
    if key in path_stack:
        print(
            f"  Skipping page {page_id} (would form a cycle in the parent chain).",
            file=sys.stderr,
        )
        return
    path_stack.append(key)
    try:
        print(f"Fetching page {page_id} from {base_url} ...")
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            page = fetch_page(base_url, page_id, auth)
        except requests.HTTPError as exc:
            _write_page_v1_fetch_error_stub(
                base_url,
                page_id,
                exc,
                output_dir,
                auth,
                position_cache,
                sibling_position,
            )
            return
        _process_page_success_export(
            base_url,
            page_id,
            page,
            output_dir,
            auth,
            recurse_children,
            path_stack,
            position_cache,
            sibling_position,
        )
    finally:
        path_stack.pop()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download a Confluence page and convert it to Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  ATLASSIAN_USER_EMAIL    Your Atlassian account email
  ATLASSIAN_USER_API_KEY  Your Atlassian API token

Supported URL formats:
  https://site.atlassian.net/wiki/spaces/SPACE/pages/12345/Title   (modern Cloud)
  https://site.atlassian.net/wiki/spaces/SPACE/overview            (space homepage)
  https://site.atlassian.net/wiki/spaces/SPACE/blog/YYYY/MM/DD/12345/Title
  https://site.atlassian.net/wiki/pages/viewpage.action?pageId=12345
  https://site.atlassian.net/wiki/display/SPACE/Title
  https://site.atlassian.net/wiki/x/aBcDe                         (tiny link)

Output directory:
  When --output-dir is not given, a directory is created in the current
  working directory named from the URL path with slashes replaced by hyphens.
  Example: wiki-spaces-ENG-pages-123456-My+Page

Markdown filenames:
  When Confluence REST API v2 returns a sibling position, files are named like
  00000057-Page-Title.md (eight-digit zero-padded rank) so sorted directory listings
  match the space sidebar order. If v2 metadata is missing, the script falls back
  to Page-Title.md only.

Recursion (default):
  Child content is written under children/<contentId>-<titleSlug>/ with the same
  layout (Markdown file, attachments/, nested children/). Pages with v2 inline or
  footer comments also get a sibling *-with-comments.md. Each exported file starts
  with YAML front matter (ids, title, space, labels, links, etc.) for searching.
  Child pages are linked under ## Child pages; whiteboards, databases, folders,
  and other types appear under ## Other Confluence content with stub files.

  Use --single-page to export only the page from the URL with no descendants.
""",
    )
    parser.add_argument("url", help="Confluence page URL")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Directory to write output files. "
            "Defaults to a name derived from the URL path "
            "(e.g. wiki-spaces-ENG-pages-123456-My+Page)."
        ),
    )
    parser.add_argument(
        "--single-page",
        action="store_true",
        help="Export only the given page; do not download child pages recursively.",
    )
    args = parser.parse_args()

    auth = get_auth()
    base_url, page_id = parse_confluence_url(args.url)

    output_dir = Path(args.output_dir if args.output_dir else dir_from_url(args.url))
    path_stack: list[str] = []
    position_cache: dict[str, Optional[int]] = {}
    process_page(
        base_url,
        page_id,
        output_dir,
        auth,
        recurse_children=not args.single_page,
        path_stack=path_stack,
        position_cache=position_cache,
        sibling_position=None,
    )

    print("\nDone.")
    print(f"  Root directory: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
