---
name: read-confluence-page
description: >-
  Reads Confluence Cloud pages and blog posts for agents: prefers Atlassian CLI
  (acli) with direct child pages included, and falls back to a bundled script
  that exports Markdown plus downloaded attachments when the page is very long
  or attachments matter. Use when the user wants full page content, not search
  excerpts, or after search-confluence returns URLs to open.
---

# Read Confluence page

Load the full content of a Confluence Cloud page or blog post. Prefer `acli` first. Use the script in `scripts/` when you need local Markdown, downloaded attachments, or a very large body is easier to read from files than from one JSON blob.

Pair with [search-confluence](../search-confluence/SKILL.md) to find URLs or page IDs, then follow this skill to read a specific result.

## Prerequisites

- `acli` installed and authenticated for Confluence. Check with `acli confluence auth status` (or `acli jira auth status` if Confluence uses the same profile; log in with `acli confluence auth login` if needed).

For the fallback script only:

- `ATLASSIAN_USER_EMAIL` and `ATLASSIAN_USER_API_KEY` (same as search-confluence).
- `pip3 install --user requests html2text`

## Resolve page ID

`acli confluence page view` requires `--id`.

- From a URL like `.../wiki/spaces/SPACE/pages/12345/Title`, the numeric segment is the page ID.
- From `.../pages/viewpage.action?pageId=12345`, use that `pageId`.
- From search results or CQL JSON, use the content id field.
- If only a title or keyword is known, run [search-confluence](../search-confluence/SKILL.md) first to get an id or URL.

Blog posts use a post id from URLs under `.../blog/.../12345/...` with `acli confluence blog view`.

## Primary path: acli (always include child pages for pages)

For every Confluence page read, include direct child pages in the same call so the agent sees local structure (sibling docs, sub-runbooks, etc.).

```bash
acli confluence page view --id PAGE_ID --include-direct-children --json
```

Optional flags when useful:

- `--body-format storage` or `atlas_doc_format` or `view` if the default body shape is hard to use.
- `--include-labels`, `--include-version`, or other `acli confluence page view --help` flags for extra metadata.

Blog posts do not use `--include-direct-children` (not available on `blog view`). Use:

```bash
acli confluence blog view --id POST_ID -j
```

Interpret the JSON for the user task. Child page summaries in the page response are part of the context you should use (titles, ids, links).

## Fallback: Markdown export and attachments

Use the bundled script when:

- The page has non-trivial attachments or embedded files you must open locally, or
- The page body is very long and unwieldy inside a single `acli` JSON payload, or
- You want a `.md` file and `attachments/` on disk for the workspace.

### Running the export script

The script lives at `scripts/confluence-page-to-markdown.py` next to this skill’s `SKILL.md`.

Use the same convention as [search-confluence](../search-confluence/SKILL.md): examples use the script name and a relative `scripts/` path. Before running, resolve where this skill is installed for the current environment (Cursor, Claude Code, Codex, or a project-local skills tree). Do not assume `~/.cursor` or any single path.

- From the skill root (`read-confluence-page/`, next to `SKILL.md`), run:

```bash
python3 scripts/confluence-page-to-markdown.py "https://site.atlassian.net/wiki/..." [--output-dir DIR] [--single-page]
```

- Or pass the absolute path to the script (substitute the real location on disk):

```bash
python3 /path/to/read-confluence-page/scripts/confluence-page-to-markdown.py "https://site.atlassian.net/wiki/..." [--output-dir DIR] [--single-page]
```

By default the script recurses through **direct children** returned by Confluence REST API v2 under each exported page. **Pages** get full `export_view` HTML converted to Markdown plus `attachments/`. **Whiteboards, databases, folders, embeds,** and other types get **stub** Markdown files: YAML front matter (ids, title, type, space hints, `confluence_web_url` when the API provides it) plus a short body and, when available, a trimmed JSON dump of the v2 response so you can see what exists and open the product for canvas or database content. Descendants live under `children/<contentId>-<titleSlug>/`. A parent page’s Markdown starts with **YAML front matter** (searchable metadata: labels, ancestors, space, version, web URL) and ends with `## Child pages` (page links) and, when needed, `## Other Confluence content` (links to stub files, with the Confluence type in parentheses). Pass `--single-page` to export only the URL target (no recursion). If v2 child listing is unavailable, the script falls back to v1 **child/page** only (pages only; whiteboards and databases will not appear). If you still need live API metadata (labels, operations, etc.) after an export, you can also run `acli confluence page view` as needed.

## Workflow summary

1. Ensure `acli` Confluence auth works.
2. Obtain `PAGE_ID` (or blog `POST_ID`) from the URL or search.
3. For pages: `acli confluence page view --id ... --include-direct-children --json` (always include children).
4. If step 3 is not enough (attachments, length, Markdown on disk): run `scripts/confluence-page-to-markdown.py` from this skill’s directory (or with an absolute path to that script) and the page URL (it recurses by default; use `--single-page` if you only want one file).
5. Answer using the page body, metadata, child list, and any generated files.

## Script output (fallback only)

- Each exported `.md` file begins with **YAML front matter** (`---` … `---`) containing Confluence metadata (content id, type, title, space, labels, ancestors, version timestamps, `confluence_web_url` when present, and export notes). This helps search and tooling that index front matter.
- **Pages:** front matter, then `# title`, then body Markdown from `export_view`, plus `attachments/` when present.
- **Folders:** metadata stub, optional attachments, `## Child pages` / `## Other Confluence content`, then recursion via v2 `folders/{id}/direct-children` (API behaviour for mixed child types can be limited; see Atlassian docs and release notes).
- **Whiteboards / databases:** stub files with v2 metadata and a note that canvas or row data is not exported; product URL when available. If v2 exposes `direct-children` for that whiteboard or database, those children are linked and exported the same way as under a page.
- When REST API v2 exposes sibling `position` / `childPosition`, filenames use an eight-digit zero-padded prefix (e.g. `00000057-Page-Title.md`) so lexical sort matches the Confluence tree order; otherwise the name is `Page-Title.md` only.
- Default recursion: under `children/<contentId>-<slug>/`, the same layout repeats; parents link to child files under `## Child pages` and `## Other Confluence content` as applicable.
- If v1 `content/{id}` fails (wrong type or permissions), the script writes an **error stub** with whatever v2 page metadata it can load instead of aborting.
- `--single-page`: only the requested page, no `children/` tree.

## Limitations

- `acli` and the script target Confluence Cloud. Whiteboards, databases, and live widgets are not fully exportable via REST; stubs and URLs are intentional.
- v2 **direct-children** under folders (and some parent types) may not return every child type in one call; rely on Confluence for authoritative structure when the export looks incomplete.
- `acli` does not download all attachments to a folder; use the script for that.
- HTML to Markdown in the script is lossy for complex layouts.

## References

- Content body representations (REST): https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-body/
