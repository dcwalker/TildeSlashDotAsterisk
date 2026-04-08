---
name: search-confluence
description: Search Confluence pages, blog posts, and attachments using CQL (Confluence Query Language). Returns titles, URLs, spaces, and excerpts. Use when the user wants to find Confluence content, look up documentation, search a space, or locate pages by topic, label, author, or date.
metadata:
  status: trial
---

Search Confluence using `scripts/confluence-search.py` (Confluence Search API + CQL). For query patterns, examples, and CQL field docs, see [confluence-cql.md](../references/confluence-cql.md).

## Inputs

- Search intent (topic, space, author, date range, hierarchy).
- Credentials: `ATLASSIAN_USER_EMAIL` and `ATLASSIAN_USER_API_KEY` as environment variables (required). `ATLASSIAN_BASE_URL` as env var or `--base-url` (if missing, ask for the site URL and pass `--base-url`).

## Required output structure

- Human-readable results: title, type, space, modified, URL, excerpt; or `--json` when the agent needs structured output.
- If zero results: suggest broader CQL (see reference).

## Workflow

### Phase 1: Discover

- Confirm env vars; if `ATLASSIAN_BASE_URL` is unset, obtain the Confluence site URL for `--base-url`.
- Resolve script path: `skills/search-confluence/scripts/confluence-search.py` in this repo (or the absolute path for your skills install).

### Phase 2: Design

- Build a CQL string. Start from the reference examples or Atlassian field docs linked in [confluence-cql.md](../references/confluence-cql.md).

### Phase 3: Implement

```bash
python3 scripts/confluence-search.py "<CQL query>" [--limit N] [--base-url URL] [--json]
```

Flags: `--limit N` (default 25), `--base-url URL`, `--json`.

Run from the `search-confluence/` directory next to `SKILL.md`, or pass the script’s absolute path.

### Phase 4: Verify

- If the user needs full page text, follow [download-confluence-page](../download-confluence-page/SKILL.md) with a result URL or ID.

## References

- [confluence-cql.md](../references/confluence-cql.md) — CQL clauses, examples, Atlassian CQL links.
- [download-confluence-page](../download-confluence-page/SKILL.md) — full page content after search.
- [skill-authoring.md](../references/skill-authoring.md), [technical-definition-of-done.md](../references/technical-definition-of-done.md).
