---
name: confluence-page
description: >-
  Create or update Confluence Cloud pages or blog posts using the REST API v2.
  Use when the user wants to create a new Confluence page or blog post, update
  an existing page's content or title, or write rich ADF or storage-format
  content to a Confluence space.
metadata:
  status: trial
---

Create or update Confluence Cloud pages and blog posts via the Confluence REST API v2. `acli confluence page` only supports reading; all writes use REST directly. For ADF details, errors, and mentions, see [confluence-rest-page-write.md](../../references/confluence-rest-page-write.md).

> **⚠️ Always save as draft — never publish without explicit instruction.**
>
> The Confluence API uses `"status"` to distinguish between saving and publishing:
> - `"status": "draft"` — saves the content privately; no one is notified.
> - `"status": "current"` — publishes the content and **immediately sends @mention notifications** to every tagged user.
>
> Because publishing is irreversible in terms of notifications (mentioned users are notified the moment status becomes `"current"`), always default to `"draft"` and only use `"current"` when the user explicitly says to publish.

## Inputs

- Target: create page (space, optional parent, title, body), create blog post (space, title, body), or update (page/blog post ID, new title/body/move).
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

- **Create page:** Build `/tmp/page-create.json` with `spaceId`, `status`, `title`, optional `parentId`, and `body` using `atlas_doc_format`. The `value` field is a **stringified** ADF JSON document (see reference doc for ADF rules). Default `status` to `"draft"` unless the user explicitly requests publishing.

```json
{
  "spaceId": "SPACE_ID",
  "status": "draft",
  "title": "Page Title",
  "parentId": "PARENT_PAGE_ID",
  "body": {
    "representation": "atlas_doc_format",
    "value": "{\"version\":1,\"type\":\"doc\",\"content\":[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"Your content here.\"}]}]}"
  }
}
```

Omit `parentId` for space root. To publish explicitly: use `"status": "current"` — this triggers @mention notifications immediately and cannot be undone.

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


## Blog posts

Blog posts use a separate endpoint (`/wiki/api/v2/blogposts`) and do not support `parentId`. The same draft-by-default rule applies.

### Phase 1: Discover (blog posts)

- Resolve **space ID** from key: `acli confluence space list --keys SPACE_KEY --json` (use numeric `id`).
- **Update:** find the blog post ID via [search-confluence](../search-confluence/SKILL.md) (use CQL `type = blogpost AND title = "..."`) or `acli confluence page view --id BLOG_POST_ID --json`.

### Phase 2: Design (blog posts)

**Create:** Build `/tmp/blogpost-create.json`. Always use `"status": "draft"` unless the user explicitly requests publishing. Changing to `"current"` triggers @mention notifications immediately and cannot be undone.

```json
{
  "spaceId": "SPACE_ID",
  "status": "draft",
  "title": "Blog Post Title",
  "body": {
    "representation": "atlas_doc_format",
    "value": "{\"version\":1,\"type\":\"doc\",\"content\":[{\"type\":\"paragraph\",\"content\":[{\"type\":\"text\",\"text\":\"Your content here.\"}]}]}"
  }
}
```

**Update:** Fetch the current blog post body and version before editing:

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  "$ATLASSIAN_BASE_URL/wiki/api/v2/blogposts/BLOG_POST_ID?body-format=atlas_doc_format" \
  > /tmp/blogpost-current.json
```

Extract `version.number` and `body.atlas_doc_format.value` from the response. Build `/tmp/blogpost-update.json` with `id`, `status`, `title`, `body`, and `version: { "number": CURRENT_VERSION_PLUS_1, "message": "..." }`.

- Present the draft; wait for **yes/no** confirmation.

### Phase 3: Implement (blog posts)

**Create:**

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -X POST "$ATLASSIAN_BASE_URL/wiki/api/v2/blogposts" \
  -d @/tmp/blogpost-create.json
```

**Update:**

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -X PUT "$ATLASSIAN_BASE_URL/wiki/api/v2/blogposts/BLOG_POST_ID" \
  -d @/tmp/blogpost-update.json
```

### Phase 4: Verify (blog posts)

- Confirm HTTP success; share the blog post URL from `_links.base` + `_links.webui`.
- On **409**, re-fetch version and retry.

**Key differences from pages:**

| | Pages | Blog posts |
|---|---|---|
| Create endpoint | `POST /wiki/api/v2/pages` | `POST /wiki/api/v2/blogposts` |
| Update endpoint | `PUT /wiki/api/v2/pages/{id}` | `PUT /wiki/api/v2/blogposts/{id}` |
| `parentId` | Optional | Not supported |
| Default status | `"draft"` | `"draft"` |
| Publish status | `"current"` | `"current"` |


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

## Setting an emoji icon

Page and blog post icons (the emoji shown before the title in the sidebar) are set via content properties using the v1 REST API. This is an **undocumented but working** approach confirmed by inspecting live Confluence pages.

**Property keys:**
- `emoji-title-draft` — controls the icon while the content is a draft
- `emoji-title-published` — controls the icon once published

**Value format:** Unicode codepoint as a lowercase string, without the `U+` prefix (e.g., `"1f680"` for 🚀, `"1f9ea"` for 🧪).

**Create (POST) the property** — use this when the property doesn't exist yet:

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -X POST "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/property" \
  -d '{"key": "emoji-title-draft", "value": "1f680"}'
```

**Update (PUT) the property** — use this when the property already exists (requires `version.number` incremented by 1):

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -X PUT "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/property/emoji-title-draft" \
  -d '{"key": "emoji-title-draft", "value": "1f680", "version": {"number": 2}}'
```

**Common codepoints:**

| Emoji | Codepoint |
|-------|-----------|
| 🚀 | `1f680` |
| 📝 | `1f4dd` |
| 📣 | `1f4e3` |
| ✅ | `2705` |
| ⚠️ | `26a0` |
| 🧪 | `1f9ea` |
| 💡 | `1f4a1` |
| 🔧 | `1f527` |

**Notes:**
- Set `emoji-title-draft` immediately after creating a draft — it controls what appears in the sidebar while unpublished.
- When publishing (status → `"current"`), also set `emoji-title-published` so the icon persists after publish.
- To find any emoji's codepoint: search [emojipedia.org](https://emojipedia.org) and look for the "Codepoints" field (e.g., `U+1F680` → use `1f680`).

## Access controls (restrictions)

Page and blog post access is controlled via the **Content Restrictions API** (v1 only — no v2 equivalent). Restrictions layer on top of space permissions; if no restriction is set, space permissions apply.

**Two operations can be restricted:**

| Operation | Controls |
|-----------|----------|
| `read` | Who can view the content |
| `update` | Who can edit the content |

Each operation can be restricted to specific users (by `accountId`) and/or groups (by `groupId`).

### Get current restrictions

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/restriction"
```

### Set restrictions (replaces all existing)

`PUT` is destructive — it replaces all restrictions. Always include yourself in both `read` and `update` or the API returns `400`.

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -X PUT "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/restriction" \
  -d '[
    {
      "operation": "read",
      "restrictions": {
        "user": { "results": [{ "type": "known", "accountId": "YOUR_ACCOUNT_ID" }] },
        "group": { "results": [{ "type": "group", "name": "GROUP_NAME", "id": "GROUP_ID" }] }
      }
    },
    {
      "operation": "update",
      "restrictions": {
        "user": { "results": [{ "type": "known", "accountId": "YOUR_ACCOUNT_ID" }] }
      }
    }
  ]'
```

### Add a single user to a restriction

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -X PUT "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/restriction/byOperation/read/user?accountId=ACCOUNT_ID"
```

### Add a single group to a restriction

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -X PUT "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/restriction/byOperation/read/byGroupId/GROUP_ID"
```

### Remove a single user or group

Replace `PUT` with `DELETE` on either of the above endpoints.

### Remove all restrictions (open to space permissions)

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -X DELETE "$ATLASSIAN_BASE_URL/wiki/rest/api/content/CONTENT_ID/restriction"
```

### Pitfalls

- **Cannot lock yourself out.** A `PUT` that would remove your own `read` or `update` access returns `400`: *"Must include yourself in 'user' sections for READ and/or UPDATE when restricting those operations."*
- **Inherited restrictions are not returned.** `GET` only shows restrictions set explicitly on that content. To find effective permissions you must walk up the page ancestry manually.
- **v1 only.** There is no restrictions endpoint in the v2 API.

## References

- [confluence-rest-page-write.md](../../references/confluence-rest-page-write.md) — ADF (images, links, mentions), error codes, personal spaces, API links.
- [search-confluence](../search-confluence/SKILL.md), [download-confluence-page](../download-confluence-page/SKILL.md).