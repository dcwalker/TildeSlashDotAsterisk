#!/usr/bin/env python3
"""
Download a Confluence page and convert it to Markdown.

Downloads the page content, converts HTML to Markdown using html2text,
downloads any file attachments locally, and rewrites attachment links in the
Markdown to point to the local paths.

Authentication uses basic auth via the environment variables:
  ATLASSIAN_USER_EMAIL    Your Atlassian account email
  ATLASSIAN_USER_API_KEY  Your Atlassian API token (https://id.atlassian.com/manage-profile/security/api-tokens)

Documented Confluence URL formats:
  https://confluence.atlassian.com/confkb/the-differences-between-various-url-formats-for-a-confluence-page-278692715.html

Usage:
  confluence-page-to-markdown.py <URL> [--output-dir DIR]

Examples:
  confluence-page-to-markdown.py "https://mysite.atlassian.net/wiki/spaces/ENG/pages/123456/My+Page"
  confluence-page-to-markdown.py "https://mysite.atlassian.net/wiki/spaces/ENG/overview"
  confluence-page-to-markdown.py "https://mysite.atlassian.net/wiki/x/aBcDe" --output-dir ./docs
"""

import argparse
import base64
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
    Whiteboards and live docs do not have a REST API content endpoint and will
    fail at the fetch stage with an HTTP error.
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
    args = parser.parse_args()

    auth = get_auth()
    base_url, page_id = parse_confluence_url(args.url)

    print(f"Fetching page {page_id} from {base_url} ...")
    page = fetch_page(base_url, page_id, auth)

    title = page.get("title", f"page-{page_id}")
    html_body = page.get("body", {}).get("export_view", {}).get("value", "")

    output_dir = Path(args.output_dir if args.output_dir else dir_from_url(args.url))
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching attachments ...")
    attachments = fetch_attachments(base_url, page_id, auth)
    print(f"Found {len(attachments)} attachment(s).")

    downloaded = []
    for att in attachments:
        filename = att["title"]
        print(f"  Downloading attachment: {filename}")
        try:
            download_attachment(base_url, att, output_dir, auth)
            downloaded.append(att)
        except Exception as exc:
            print(f"  Warning: failed to download '{filename}': {exc}", file=sys.stderr)

    print("Converting HTML to Markdown ...")
    markdown = html_to_markdown(html_body)
    markdown = rewrite_attachment_links(markdown, downloaded, base_url)

    # Prepend a title heading
    markdown = f"# {title}\n\n" + markdown

    output_filename = slugify(title) + ".md"
    output_path = output_dir / output_filename
    output_path.write_text(markdown, encoding="utf-8")

    print("\nDone.")
    print(f"  Markdown: {output_path}")
    if downloaded:
        print(f"  Attachments: {output_dir / 'attachments'}/")


if __name__ == "__main__":
    main()
