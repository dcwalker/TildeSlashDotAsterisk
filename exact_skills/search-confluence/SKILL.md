---
name: search-confluence
description: Search Confluence pages, blog posts, and attachments using CQL (Confluence Query Language). Returns titles, URLs, spaces, and excerpts. Use when the user wants to find Confluence content, look up documentation, search a space, or locate pages by topic, label, author, or date.
---

# Search Confluence

Search Confluence content using the `confluence-search.py` script, which calls the Confluence Search API with a CQL query and returns formatted results.

## When to Use

- User wants to find Confluence pages, blog posts, or attachments
- User asks to search for documentation or look something up in Confluence
- User provides a topic, keyword, or label to search for
- User wants to see pages modified recently or created by a specific person
- User wants to browse the contents of a space or a section of a page hierarchy

## Prerequisites

Before running the script, check that the required credentials are available:

- `ATLASSIAN_USER_EMAIL` - the user's Atlassian account email
- `ATLASSIAN_USER_API_KEY` - the user's Atlassian API token (https://id.atlassian.com/manage-profile/security/api-tokens)
- `ATLASSIAN_BASE_URL` - the Confluence site URL, e.g. `https://mycompany.atlassian.net`

`ATLASSIAN_USER_EMAIL` and `ATLASSIAN_USER_API_KEY` must be set as environment variables. If they are missing, tell the user which ones are unset and ask them to set them before proceeding.

`ATLASSIAN_BASE_URL` can be provided either as an environment variable or via the `--base-url` flag. If it is not set in the environment, ask the user for their Confluence site URL and pass it with `--base-url` instead of asking them to set the variable.

## Running the script

```bash
confluence-search.py "<CQL query>" [--limit N] [--base-url URL] [--json]
```

Flags:
- `--limit N` - max results to return (default 25)
- `--base-url URL` - Confluence site URL (falls back to `ATLASSIAN_BASE_URL`)
- `--json` - output as JSON (for further processing)

## Building CQL queries

CQL syntax: `field operator value`, combined with `AND`, `OR`, `NOT`, sorted with `ORDER BY`.
All queries are case-insensitive.

### Full-text search

```
text ~ "keyword"
```

`text` is a master field that searches across page title, body content, and labels.
Use `~` (CONTAINS) for full-text; `=` is an exact match and rarely what you want for text.

### Search by title

```
title ~ "runbook"
title = "Exact Page Title"
```

### Filter by content type

```
type = page
type = blogpost
type = attachment
type IN (page, blogpost)
```

Other types: `whiteboard`, `database`, `embed`, `folder`, `comment`.

### Filter by space

```
space = ENG
space IN (ENG, OPS, PLAT)
```

Use space keys (short codes), not display names.

### Filter by label

```
label = "on-call"
label NOT IN (draft, archived)
```

### Filter by date

```
lastmodified >= now("-2w")          modified in the last 2 weeks
lastmodified >= now("-30d")         modified in the last 30 days
created > "2025-01-01"              created after a date
lastmodified >= startOfMonth()      modified since start of this month
```

Date math functions: `now()`, `startOfDay()`, `startOfWeek()`, `startOfMonth()`, `startOfYear()` and their `end*` counterparts.

### Filter by author

```
creator = "accountId"
contributor = "accountId"
```

### Filter by page hierarchy

```
ancestor = 12345      all descendants of a page (recursive)
parent = 12345        direct children of a page only
```

### Sort results

```
ORDER BY lastmodified DESC
ORDER BY created DESC
ORDER BY title ASC
```

### Combining clauses

```
text ~ "incident" AND space = OPS AND type = page
label = "runbook" AND lastmodified >= now("-6m") ORDER BY lastmodified DESC
type = page AND space IN (ENG, PLAT) AND title ~ "architecture"
ancestor = 98765 AND lastmodified >= now("-1w")
```

## Example invocations

```bash
# Find pages containing "deployment pipeline" in the ENG space
confluence-search.py 'text ~ "deployment pipeline" AND space = ENG'

# Find runbooks modified in the last 6 months
confluence-search.py 'label = "runbook" AND lastmodified >= now("-6m")' --limit 10

# Find recently updated pages across two spaces
confluence-search.py 'type = page AND space IN (ENG, OPS) AND lastmodified >= now("-2w")' --limit 20

# Find all descendants of a section by ancestor page ID
confluence-search.py 'ancestor = 12345678 AND type = page'

# Exact title search
confluence-search.py 'title = "On-Call Runbook"'

# Get JSON output for further processing
confluence-search.py 'text ~ "API gateway" AND space = ARCH' --json
```

## Interpreting results

The script outputs one result per entry with:
- Title and content type
- Space name and key
- Last modified date and author
- Direct URL to the page
- A short excerpt with the matching context

If no results are found, try broadening the query (e.g. remove space filter, use `text ~` instead of `title ~`, shorten the search phrase).

To load full page content after you have a URL or page id, use the [read-confluence-page](../read-confluence-page/SKILL.md) skill.

## CQL reference

- Fields: https://developer.atlassian.com/cloud/confluence/cql-fields/
- Operators: https://developer.atlassian.com/cloud/confluence/cql-operators/
- Functions: https://developer.atlassian.com/cloud/confluence/cql-functions/
- Full guide: https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/
