---
name: confluence-page
description: >-
  Create or update Confluence Cloud pages using the REST API v2. Use when the
  user wants to create a new Confluence page, update an existing page's content
  or title, or write rich ADF or storage-format content to a Confluence space.
metadata:
  status: trial
---

Create or update Confluence Cloud pages via the Confluence REST API v2. `acli confluence page` only supports reading; all writes use REST directly. For ADF details, errors, and mentions, see [confluence-rest-page-write.md](../../references/confluence-rest-page-write.md).

## Inputs

- Target: create (space, optional parent, title, body) or update (page ID, new title/body/move).
- Credentials: `ATLASSIAN_USER_EMAIL`, `ATLASSIAN_USER_API_KEY`, `ATLASSIAN_BASE_URL` (e.g. `https://mycompany.atlassian.net`).
- User confirmation before any create or update.

## Required output structure

1. Clickable page URL from the API response (`_links.base` + `_links.webui`).
2. For creates/updates: explicit user approval after showing a readable draft (title, space, body summary).

## Workflow

### Phase 1: Discover

- Resolve **space ID** from key: `acli confluence space list --keys SPACE_KEY --json` (use numeric `id`).
- **Create:** optional **parent page ID** via `acli confluence page view --id PAGE_ID --json` or [download-confluence-page](../download-confluence-page/SKILL.md).
- **Update:** page ID and current version: `acli confluence page view --id PAGE_ID --include-version --json` (`version.number`; PUT needs `version.number + 1`). If the page ID is unknown, use [search-confluence](../search-confluence/SKILL.md) or download-confluence-page.

### Phase 2: Design

- **Create:** Build `/tmp/page-create.json` with `spaceId`, `status`, `title`, optional `parentId`, and `body` using `atlas_doc_format`. The `value` field is a **stringified** ADF JSON document (see reference doc for ADF rules).

```json
{
  "spaceId": "SPACE_ID",
  "status": "current",
  "title": "Page Title",
  "parentId": "PARENT_PAGE_ID",
  "body": {
    "representation": "atlas_doc_format",
    "value": "{\"version\":1,\"type\":\"doc\",\"content\":[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"Your content here.\"}]}]}"
  }
}
```

Omit `parentId` for space root. For drafts: `"status": "draft"` (title may be omitted per API rules).

- **Update:** Fetch current body before editing (do not rebuild from memory; you would overwrite concurrent edits):

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  "$ATLASSIAN_BASE_URL/wiki/rest/api/content/PAGE_ID/version/CURRENT_VERSION?expand=content.body.atlas_doc_format" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['content']['body']['atlas_doc_format']['value'])" \
  > /tmp/page-current.json
```

Apply targeted ADF changes. Build `/tmp/page-update.json` with `id`, `status`, `title`, `body` (`atlas_doc_format` stringified), and `version: { "number": CURRENT_VERSION_PLUS_1, "message": "..." }`.

- Present the draft; wait for **yes/no** confirmation.

### Phase 3: Implement

**Create:**

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -X POST "$ATLASSIAN_BASE_URL/wiki/api/v2/pages" \
  -d @/tmp/page-create.json
```

**Update:**

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -X PUT "$ATLASSIAN_BASE_URL/wiki/api/v2/pages/PAGE_ID" \
  -d @/tmp/page-update.json
```

### Phase 4: Verify

- Confirm HTTP success; share the page URL.
- On **409**, re-fetch version and retry (see reference error table).


## Archiving pages

`acli confluence page` has no archive command. Use the v1 REST API (experimental):

```bash
curl -s -X POST \
  "$ATLASSIAN_BASE_URL/wiki/rest/api/content/archive" \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"pages": [{"id": "PAGE_ID_1"}, {"id": "PAGE_ID_2"}]}'
```

Returns `202 Accepted` with a task ID. Poll for completion:

```bash
curl -s \
  "$ATLASSIAN_BASE_URL/wiki/rest/api/longtask/TASK_ID" \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Accept: application/json"
```

Check `finished: true` and `status: "FINISH_SUCCESS"` in the response. Multiple page IDs can be submitted in a single request; they need not belong to the same space.

Pitfalls:
- `PUT /wiki/rest/api/content/{id}` with `"status": "archived"` silently returns "current" without archiving.
- `POST /wiki/api/v2/pages/{id}/archive` returns 404; this endpoint does not exist.

## References

- [confluence-rest-page-write.md](../../references/confluence-rest-page-write.md) — ADF (images, links, mentions), error codes, personal spaces, API links.
- [search-confluence](../search-confluence/SKILL.md), [download-confluence-page](../download-confluence-page/SKILL.md).