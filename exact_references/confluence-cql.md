# Confluence CQL (search)

Supporting detail for [search-confluence](../skills/search-confluence/SKILL.md).

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

To load full page content after you have a URL or page id, use the [download-confluence-page](../skills/download-confluence-page/SKILL.md) skill.

## CQL reference (Atlassian)

- Fields: https://developer.atlassian.com/cloud/confluence/cql-fields/
- Operators: https://developer.atlassian.com/cloud/confluence/cql-operators/
- Functions: https://developer.atlassian.com/cloud/confluence/cql-functions/
- Full guide: https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/
