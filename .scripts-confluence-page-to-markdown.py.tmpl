#!/usr/bin/env python3
"""
Download a Confluence page and convert it to Markdown.

Downloads the page content, converts HTML to Markdown using html2text,
downloads any file attachments locally, and rewrites attachment links in the
Markdown to point to the local paths.

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
import json
import os
import re
import sys
from pathlib import Path
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

# v2 API collection segment for GET /wiki/api/v2/{segment}/{id} and .../direct-children
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


def absolute_webui_url(base_url: str, webui: str | None) -> str | None:
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


def fetch_page_nav_position_v2(base_url: str, page_id: str, auth: tuple) -> int | None:
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
) -> dict | None:
    """GET /wiki/api/v2/{collection}/{id}. Returns None on non-success."""
    resp = requests.get(
        f"{base_url}/wiki/api/v2/{collection}/{content_id}",
        auth=auth,
        headers={"Accept": "application/json"},
    )
    if not resp.ok:
        return None
    return resp.json()


def fetch_direct_children_v2(
    base_url: str, collection: str, content_id: str, auth: tuple
) -> list | None:
    """Paginate GET /wiki/api/v2/{collection}/{id}/direct-children. None if unusable."""
    results: list = []
    next_url: str | None = (
        f"{base_url}/wiki/api/v2/{collection}/{content_id}/direct-children"
    )
    params: dict | None = {"limit": 50}
    while next_url:
        resp = requests.get(
            next_url,
            params=params,
            auth=auth,
            headers={"Accept": "application/json"},
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


def rewrite_attachment_links(
    markdown: str,
    attachments: list,
    base_url: str,
) -> str:
    """Replace Confluence attachment URLs in Markdown with relative local paths."""
    for attachment in attachments:
        filename = attachment["title"]
        download_path = attachment["_links"]["download"]
        # Match both the full URL and the relative /wiki/... path
        patterns = [
            re.escape(f"{base_url}/wiki{download_path}"),
            re.escape(f"/wiki{download_path}"),
            re.escape(download_path),
        ]
        local_rel = f"attachments/{filename}"
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


def coalesce_child_position(child: dict) -> int | None:
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
    position_cache: dict[str, int | None],
    base_url: str,
    page_id: str,
    auth: tuple,
    sibling_position: int | None,
) -> int | None:
    """Resolve nav position: explicit from parent list, else cache, else GET v2 page."""
    if sibling_position is not None:
        return sibling_position
    if page_id in position_cache:
        return position_cache[page_id]
    pos = fetch_page_nav_position_v2(base_url, page_id, auth)
    position_cache[page_id] = pos
    return pos


def markdown_basename(nav_position: int | None, title: str) -> str:
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


def v2_type_to_collection(content_type: str) -> str | None:
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
    position_cache: dict[str, int | None],
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
    position_cache: dict[str, int | None],
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
    sibling_position: int | None,
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
    detail: dict | None,
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
    sibling_position: int | None, detail: dict | None
) -> int | None:
    if sibling_position is not None:
        return sibling_position
    if not detail or detail.get("position") is None:
        return None
    try:
        return int(detail.get("position"))
    except (TypeError, ValueError):
        return None


def _v2_leaf_intro_body(
    title: str, content_type: str, content_id: str, fm: dict, detail: dict | None
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
    position_cache: dict[str, int | None],
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
    position_cache: dict[str, int | None],
    sibling_position: int | None,
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
        body = _v2_leaf_intro_body(title, content_type, content_id, fm, detail)
        body, nested_children = _v2_leaf_nested_children(
            base_url, coll, content_id, auth, position_cache, body
        )
        out_path = output_dir / markdown_basename(nav_pos, title)
        out_path.write_text(format_yaml_frontmatter(fm) + "\n" + body, encoding="utf-8")
        print(f"  Wrote {out_path}")
        if nested_children:
            recurse_export_children(
                base_url, nested_children, output_dir, auth, path_stack, position_cache
            )
    finally:
        path_stack.pop()


def _folder_title_and_frontmatter(
    base_url: str, folder_id: str, detail: dict | None
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
    sibling_position: int | None, detail: dict | None
) -> int | None:
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
    detail: dict | None,
    position_cache: dict[str, int | None],
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
    position_cache: dict[str, int | None],
    sibling_position: int | None = None,
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
        children: list = []
        if recurse_children:
            children = fetch_direct_children_v2(base_url, "folders", folder_id, auth) or []
            children.sort(key=_child_sort_tuple)
        body = _folder_body_markdown(
            title, recurse_children, children, detail, position_cache, base_url, auth
        )
        out_path = output_dir / markdown_basename(nav_pos, title)
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
    position_cache: dict[str, int | None],
    sibling_position: int | None,
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
    position_cache: dict[str, int | None],
    sibling_position: int | None,
) -> None:
    """Convert a fetched v1 page dict to Markdown, attachments, and child exports."""
    title = page.get("title", f"page-{page_id}")
    html_body = page.get("body", {}).get("export_view", {}).get("value", "")
    fm_page = build_page_frontmatter(page, base_url)
    print("Fetching attachments ...")
    attachments = safe_fetch_attachments(base_url, page_id, auth)
    print(f"Found {len(attachments)} attachment(s).")
    downloaded = download_attachments_for_page(base_url, attachments, output_dir, auth)
    print("Converting HTML to Markdown ...")
    markdown = html_to_markdown(html_body)
    markdown = rewrite_attachment_links(markdown, downloaded, base_url)
    children = []
    if recurse_children:
        children = sorted_direct_children(base_url, page_id, auth)
        markdown += markdown_section_child_links(
            position_cache, base_url, auth, children
        )
    nav_pos = nav_position_for_page(
        position_cache, base_url, page_id, auth, sibling_position
    )
    output_path = output_dir / markdown_basename(nav_pos, title)
    header = format_yaml_frontmatter(fm_page)
    output_path.write_text(header + f"# {title}\n\n" + markdown, encoding="utf-8")
    print(f"  Wrote {output_path}")
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
    position_cache: dict[str, int | None],
    sibling_position: int | None = None,
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
  layout (Markdown file, attachments/, nested children/). Each exported file starts
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
    position_cache: dict[str, int | None] = {}
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
