# Confluence REST: page body, errors, and edge cases

Supporting detail for [confluence-page](../confluence-page/SKILL.md). Keep the skill file procedural; use this for ADF shape, errors, and personal spaces.

## Body format: ADF

Always use `atlas_doc_format`. The `value` field must be a JSON string (the ADF document serialized with `JSON.stringify` or equivalent).

The ADF document structure matches Jira's: a root `doc` node containing block nodes (`paragraph`, `heading`, `bulletList`, `codeBlock`, `table`, etc.) and inline nodes with marks. See the [ADF document structure spec](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/) for the full node and mark reference.

Minimal ADF document (before stringifying):

```json
{
  "version": 1,
  "type": "doc",
  "content": [
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "Hello, Confluence." }]
    }
  ]
}
```

Stringify this object before placing it in the `"value"` field of the request body.

### Images and accessibility

Every embedded image must include a caption describing its content. Use the native `caption` child node inside `mediaSingle` rather than a separate paragraph below the image:

```json
{
  "type": "mediaSingle",
  "attrs": { "layout": "center" },
  "content": [
    {
      "type": "media",
      "attrs": {
        "id": "FILE_ID",
        "type": "file",
        "collection": "contentId-PAGE_ID"
      }
    },
    {
      "type": "caption",
      "content": [{ "type": "text", "text": "Description of the image content." }]
    }
  ]
}
```

The caption node renders as Confluence's built-in styled caption below the image. A plain paragraph below the image is not the same and does not use the caption style. Write captions that describe the image content accurately enough for someone who cannot see the image to understand what it shows.

### Clickable links

A plain text URL in an ADF body (e.g. `{ "type": "text", "text": "https://example.com" }`) is NOT automatically hyperlinked; it renders as unclickable text.

The default link style is `inlineCard`. Use an `inlineCard` node for all URLs unless the user explicitly requests plain hyperlink text:

```json
{
  "type": "paragraph",
  "content": [
    { "type": "text", "text": "Reference: " },
    { "type": "inlineCard", "attrs": { "url": "https://procoretech.atlassian.net/browse/PI-12345" } }
  ]
}
```

Confluence renders `inlineCard` as a smart link; for Jira URLs this shows the issue title and status; for other URLs it shows a preview card. The `inlineCard` node is valid inside `paragraph` and `heading` content.

Use a text node with a `link` mark only when the user explicitly asks for custom display text (e.g. `"text": "see ticket"` instead of showing the full card):

```json
{
  "type": "text",
  "text": "see ticket",
  "marks": [{ "type": "link", "attrs": { "href": "https://procoretech.atlassian.net/browse/PI-12345" } }]
}
```

### Mentions (@mentioning users)

Confluence pages support user mentions via the ADF `mention` inline node. The node requires the user's `accountId` in `attrs`:

```json
{
  "type": "mention",
  "attrs": {
    "id": "ACCOUNT_ID",
    "text": "@Display Name",
    "accessLevel": ""
  }
}
```

To look up an `accountId` from a display name or email, use the Confluence user search REST API (same auth as all other requests):

```bash
curl -s \
  -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  "$ATLASSIAN_BASE_URL/wiki/rest/api/user/search?query=SEARCH_TERM"
```

The response is an array of user objects; extract `accountId` from the matching result. Alternatively, the `atlassian_user_search.py` script in [jira-workitem](../jira-workitem/scripts/atlassian_user_search.py) uses `/rest/api/3/user/search`, which resolves the same `accountId` values and can be reused.

Plain text `@Display Name` in the page body does not create a real mention or trigger a notification. Always use the ADF `mention` node with the correct `accountId` when a mention must notify the user.

## Error handling

| Status | Likely cause |
|--------|-------------|
| 400 | Missing required field, invalid body format, or title conflict in the space |
| 401 | Auth credentials missing or expired |
| 403 | User lacks write permission for the space |
| 404 | Space ID or parent page ID not found |
| 409 | Version conflict on update: re-fetch the version number and retry |

On 409, re-run `acli confluence page view --id PAGE_ID --include-version --json` to get the latest version number, increment it, and retry.

## Operational notes

- Keep JSON payloads in `/tmp/`; clean up after use.
- Always show the user a clear draft and get explicit confirmation before creating or updating.
- To create a page as a child of another page, both must be in the same space.
- The `title` must be unique within the space for published pages.

### Personal spaces

Personal spaces are identifiable and writable via the same API. Use `--type personal` to filter them:

```bash
acli confluence space list --type personal --json
```

The response includes the numeric `id` needed for `spaceId` in create/update requests. [Inference] Personal space keys often follow a `~accountId` format (e.g. `~712020:abc123`), which makes them distinguishable in the `key` field even without the type filter. Once you have the space ID, creating or updating pages in a personal space works identically to any other space. By default only the space owner has write access, so the authenticated user must be the owner or must have been granted explicit write permission.

## External links

- [REST API v2: Create page](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/#api-pages-post)
- [REST API v2: Update page](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/#api-pages-id-put)
- [ADF document structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)

## Related skills

- [download-confluence-page](../download-confluence-page/SKILL.md): read page content and metadata before updating.
- [search-confluence](../search-confluence/SKILL.md): find page IDs by keyword or CQL.
