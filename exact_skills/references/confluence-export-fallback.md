# Confluence Markdown export script (fallback path)

Supporting detail for [download-confluence-page](../download-confluence-page/SKILL.md). Use when the primary `acli` path is not enough (attachments, very long bodies, or Markdown on disk).

## Script location

The script lives at `skills/download-confluence-page/scripts/confluence-page-to-markdown.py` in this repository.

Resolve the skill install path for the current environment (Cursor, Claude Code, Codex, or project-local skills). Do not assume `~/.cursor` or any single path.

From the skill root (`download-confluence-page/`, next to `SKILL.md`):

```bash
python3 scripts/confluence-page-to-markdown.py "https://site.atlassian.net/wiki/..." [--output-dir DIR] [--single-page]
```

Or pass the absolute path to the script.

By default the script recurses through **direct children** returned by Confluence REST API v2 under each exported page. **Pages** get full `export_view` HTML converted to Markdown plus `attachments/`. **Whiteboards, databases, folders, embeds,** and other types get **stub** Markdown files: YAML front matter (ids, title, type, space hints, `confluence_web_url` when the API provides it) plus a short body and, when available, a trimmed JSON dump of the v2 response so you can see what exists and open the product for canvas or database content. Descendants live under `children/<contentId>-<titleSlug>/`. A parent page's Markdown starts with **YAML front matter** (searchable metadata: labels, ancestors, space, version, web URL) and ends with `## Child pages` (page links) and, when needed, `## Other Confluence content` (links to stub files, with the Confluence type in parentheses). Pass `--single-page` to export only the URL target (no recursion). If v2 child listing is unavailable, the script falls back to v1 **child/page** only (pages only; whiteboards and databases will not appear). If you still need live API metadata (labels, operations, etc.) after an export, you can also run `acli confluence page view` as needed.

## Script output

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

## External reference

- Content body representations (REST): https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-body/
