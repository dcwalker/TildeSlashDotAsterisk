---
name: download-confluence-page
description: >-
  Downloads the full content of Confluence Cloud pages and blog posts for
  agents: prefers Atlassian CLI (acli) with direct child pages included, and
  falls back to a bundled script that exports Markdown plus downloaded
  attachments when the page is very long or attachments matter. Use when the
  user wants full page content, not search excerpts, or after
  search-confluence returns URLs to open.
metadata:
  status: trial
---

Load full Confluence page or blog post content. Prefer `acli` first; use the Markdown export script when attachments, length, or on-disk files matter. Pair with [search-confluence](../search-confluence/SKILL.md) to resolve IDs or URLs. Script behavior, output layout, and limits: [confluence-export-fallback.md](../references/confluence-export-fallback.md).

## Inputs

- Page or blog URL, or content ID (from search/CQL).
- **Primary path:** `acli` with Confluence auth (`acli confluence auth status`; login if needed).
- **Fallback script:** `ATLASSIAN_USER_EMAIL`, `ATLASSIAN_USER_API_KEY`; `pip3 install --user requests html2text`.

## Required output structure

- For pages: JSON from `acli` including **direct children** when using the primary path.
- For fallback: Markdown tree and optional `attachments/` under the chosen output directory.

## Workflow

### Phase 1: Discover

- Extract **page ID** from the URL (`.../pages/12345/...` or `pageId=12345`) or obtain ID from [search-confluence](../search-confluence/SKILL.md). Blog posts: post ID from `.../blog/...` URLs.

### Phase 2: Design

- Choose primary (`acli` only) vs fallback (script) using the criteria in [confluence-export-fallback.md](../references/confluence-export-fallback.md).

### Phase 3: Implement

**Pages (always include direct children):**

```bash
acli confluence page view --id PAGE_ID --include-direct-children --json
```

Optional: `--body-format storage|atlas_doc_format|view`, `--include-labels`, `--include-version` (see `acli confluence page view --help`).

**Blog posts:**

```bash
acli confluence blog view --id POST_ID -j
```

**Fallback export** (path to script in this repo: `skills/download-confluence-page/scripts/confluence-page-to-markdown.py`):

```bash
python3 scripts/confluence-page-to-markdown.py "https://site.atlassian.net/wiki/..." [--output-dir DIR] [--single-page]
```

Resolve the skill directory for your environment; do not assume a single global path.

### Phase 4: Verify

- Answer using body, metadata, child summaries, and any files produced.
- If structure looks incomplete (folders, mixed child types), see limitations in the reference doc.

## References

- [confluence-export-fallback.md](../references/confluence-export-fallback.md) — script recursion, YAML front matter, stubs, limitations.
- [search-confluence](../search-confluence/SKILL.md).
- Content body (REST): https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-body/
- [skill-authoring.md](../references/skill-authoring.md), [technical-definition-of-done.md](../references/technical-definition-of-done.md).
