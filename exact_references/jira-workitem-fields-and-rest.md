# Jira work items: fields, bulk operations, and ADF notes

Supporting detail for [jira-workitem](../skills/jira-workitem/SKILL.md). Use this for parent, component, custom fields, bulk move, and ADF reminders; keep the skill file focused on the ordered workflow.

## Field reference (create and edit)

Use this section when setting **Parent**, **Component**, or **custom/required fields** on create or edit. Same formats and discovery steps apply to both.

### Parent (link to Epic or parent issue)

The **parent** field links an issue to an Epic or another parent issue. acli has no `--parent` flag; set it via JSON (create or edit).

- **Format:** `"parent": { "key": "PARENT_ISSUE_KEY" }` in the fields object.
- **Create:** Include in the create JSON. **Edit:** `acli jira workitem edit --key "KEY-1,..." --from-json path/to/edit.json --yes`, or `PUT /rest/api/3/issue/{key}` with body `{"fields": {"parent": {"key": "PARENT_ISSUE_KEY"}}}` for per-issue updates.
- **Discover:** Not all projects or issue types expose parent. Check with `acli jira workitem view PARENT_KEY --json --fields '*all'`; if `parent` is missing, the project may not use parent linking for that type.

### Component (standard components field)

On many Jira Cloud sites the repo's Compass component is linked via the standard **components** field, not a custom field.

- **Discover:** View a reference issue in the same project that already has the desired component: `acli jira workitem view REF_KEY --json --fields components` (or `--fields '*all'`). The API returns an array of component objects with `id` (string, e.g. `"24121"`), `name`, `ari`, `metadata`, etc.
- **Format:** `"components": [ { "id": "<component_id>" } ]`. Use the `id` value from the reference issue.
- **acli limitation:** acli `workitem create` and `workitem edit --from-json` do **not** accept the `components` field; they return "unknown field" if you include it. **Create:** Create the issue first, then set the component via REST: `PUT /rest/api/3/issue/{key}` with body `{"fields": {"components": [{"id": "<component_id>"}]}}`. Use the same auth as acli (e.g. Basic with `ATLASSIAN_USER_EMAIL` and `ATLASSIAN_USER_API_KEY`). **Edit (single/batch):** Use the same PUT request. **Edit (bulk, same component for many issues):** Use the bulk edit API (see "Bulk set Component" below).

### Component (custom field)

If the project uses a **custom** component field (e.g. "Domain Component" or similar):

- **Discover field ID:** Use [get-jira-custom-field-details](../skills/get-jira-custom-field-details/SKILL.md) or run `get-field-details.py` with the field name. The ID is like `customfield_10000`. Or use create metadata: `GET /rest/api/3/issue/createmeta?projectKeys=PROJECT_KEY&issuetypeIds=ISSUE_TYPE_ID&expand=projects.issuetypes.fields` and find the field by name.
- **Discover value:** Use get-compass-component-by-repo skill or `get-component-by-repo.py` with the repo name. Use the component name or ID in the format the field expects.
- **Format:** Typically `"customfield_XXXXX": { "value": "Component Name" }` or `{ "id": "OPTION_ID" }` depending on field type. View an issue that has the field set (`--fields '*all'`) to see the shape.
- **Create:** Include in the create JSON. **Edit:** Include in the edit JSON and apply with `--from-json`.

### Required and custom fields (option IDs)

For **required** or **custom** select/dropdown fields (e.g. Environment, Severity), you need valid option IDs. Same process for create and for bulk move (when the target issue type has required fields).

- **Create metadata API:** `GET /rest/api/3/issue/createmeta?projectKeys=PROJECT_KEY&issuetypeIds=ISSUE_TYPE_ID&expand=projects.issuetypes.fields`. In the response, find the issue type and inspect each required field's `schema` and `allowedValues`; use the option `id` (not the display value). Omit `issuetypeIds` to see all issue types; use the type's `id` (e.g. `1` for Bug) in the URL if needed.
- **Create JSON (acli):** Required custom fields are not top-level keys. Put them in **additionalAttributes**: `"additionalAttributes": { "customfield_XXXXX": { "id": "OPTION_ID" } }`. Single-select option: `{ "id": "OPTION_ID" }`. Multi-select: array of `{ "id": "OPTION_ID" }`. The generated template (`acli jira workitem create --generate-json`) does not list every required field; if create fails with e.g. "Severity is required., Environment is required.", use the create metadata API to find those fields and add them to additionalAttributes.
- **Bulk move (targetMandatoryFields):** When changing issue type via bulk move, if the target type has required fields, set `inferFieldDefaults: false` and send `targetMandatoryFields` with `"customfield_XXXXX": { "value": ["OPTION_ID"] }` (option id as string in a one-element array). Get field IDs and option IDs from the same create metadata API above.

If the schema or value shape is unclear, prompt the user for the correct value.

## Issue links vs the parent field

These are two distinct Jira concepts. Use the right one for the relationship you want to express.

### When to use each

| Situation | Use |
|---|---|
| Grouping work under an Epic, Story, or parent Task (work breakdown) | Parent field |
| Expressing a dependency, blocker, duplicate, or any cross-issue relationship | Issue link |
| A sub-task belongs inside a parent issue | Parent field |
| One issue cannot proceed until another is resolved | Issue link (Blocks) |
| Two issues track the same problem | Issue link (Duplicate) |
| Relating issues across different projects or epics | Issue link |

The parent field is structural: it places an issue inside a hierarchy in the backlog. Only one parent is allowed. Issue links are relational: they describe relationships between issues without affecting hierarchy. Multiple links of different types can exist on one issue.

### Creating links with acli

```bash
# List available link types (shows outward descriptions)
acli jira workitem link type

# Create a link
acli jira workitem link create --out KEY-A --in KEY-B --type "Blocks" --yes

# List links on an issue
acli jira workitem link list --key KEY-123
```

### Inward vs outward direction

**Always confirm direction after creating a link** by running `acli jira workitem view KEY --json --fields issuelinks` and checking the JSON. The direction is correct when the issue that should be the blocker has `outwardIssue` pointing to the blocked issue.

How to read the JSON result:

- `outwardIssue: Y` on issue X → X "blocks" Y (X is the blocker, Y is blocked)
- `inwardIssue: Y` on issue X → X "is blocked by" Y (Y is the blocker, X is blocked)

**acli flag behavior (counterintuitive):** The `--out` and `--in` flags do NOT match outward/inward semantics. Empirically, `--out` is the BLOCKED issue and `--in` is the BLOCKER. To make A block B:

```bash
# A blocks B: use --out B --in A (reversed from what the flag names suggest)
acli jira workitem link create --out B --in A --type "Blocks" --yes
```

Always verify the JSON after creating to confirm the direction before moving on. If it is reversed, delete the link and recreate with the flags swapped.

Examples using the types available in this workspace:

| Goal | --in (the blocker) | --out (the blocked) |
|---|---|---|
| A blocks B | A | B |
| A depends on B | B | A |
| A duplicates B | B | A |

When in doubt, ask the user to confirm which issue should be the blocker before creating the link.

### Deleting links

```bash
acli jira workitem link delete --help
```

Find the link ID first with `acli jira workitem link list --key KEY-123`, then delete by ID.

## Changing issue type when workflows differ (status mapping)

If the target issue type uses a different workflow (e.g. Task "To Do" vs Bug "Backlog"), simple edit fails with "The issue type selected is invalid". Use the **Bulk move** API instead.

**Check first:** Get issue status and project: `acli jira workitem view KEY --json --fields status,project`. Get target workflow statuses: `GET /rest/api/3/project/{projectIdOrKey}/statuses`. If the target issue type's statuses do not include the issue's current status id, use bulk move.

**Bulk move:** `POST /rest/api/3/bulk/issues/move` with `targetToSourcesMapping`. Key format: `PROJECT_KEY,TARGET_ISSUE_TYPE_ID` (comma, not colon). For each target specify `issueIdsOrKeys`, and either `inferStatusDefaults: true` (and optionally `targetMandatoryFields` for required fields) or explicit `targetStatus` mapping. If the target type has required fields (e.g. Bug with Environment, Severity), set `inferFieldDefaults: false` and provide `targetMandatoryFields` (see Required and custom fields above for option ID format). acli does not expose bulk move; use REST with the same auth. Docs: [Bulk move issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-bulk-operations/#api-rest-api-3-bulk-issues-move-post), [Bulk operation FAQs](https://developer.atlassian.com/cloud/jira/platform/bulk-operation-additional-examples-and-faqs/).

**Status mapping tip:** When the target type has required fields, using `inferStatusDefaults: true`, omitting `targetStatus`, and supplying `targetMandatoryFields` often works; Jira infers status (e.g. To Do to Backlog). Use explicit `targetStatus` only when you need a specific mapping.

## Bulk set Component (standard components field)

To set the same component on many issues in one call: `POST /rest/api/3/bulk/issues/fields` with body:

```json
{
  "sendBulkNotification": false,
  "selectedIssueIdsOrKeys": ["KEY-1", "KEY-2", "..."],
  "selectedActions": ["components"],
  "editedFieldsInput": {
    "multiselectComponents": {
      "fieldId": "components",
      "bulkEditMultiSelectFieldOption": "REPLACE",
      "components": [{ "componentId": "<component_id>" }]
    }
  }
}
```

`componentId` is numeric (from reference issue or project components). Poll `GET /rest/api/3/bulk/queue/{taskId}` until status is COMPLETE.

## Bulk summary changes (per-issue different value)

acli `workitem edit --summary "X"` sets the same summary for all keys. To change summary per issue (e.g. strip a prefix), use one `PUT /rest/api/3/issue/{key}` per issue with body `{"fields": {"summary": "new summary"}}`. Fetch current summary first with `GET /rest/api/3/issue/{key}?fields=summary`, compute the new value, then PUT.

## Example: Convert multiple issues to Bug and set Component

1. Determine where component is stored: view a reference issue with the repo's Compass component (`acli jira workitem view REF_KEY --json --fields '*all'`). If it's the **components** field (array with `id`, `name`, `ari`), use that; otherwise find the custom field name.
2. Standard **components** field: get component id from reference. For many issues use bulk edit API (above) with numeric `componentId`. For one or a few issues use REST: `PUT /rest/api/3/issue/{key}` with body `{"fields": {"components": [{"id": "<component_id>"}]}}`. Do not use acli edit with `"components"` in the JSON; acli does not support it.
3. Custom component field: get field ID (e.g. `get-field-details.py "Component"`) and value format; get component name (e.g. `get-component-by-repo.py`). Edit JSON: `{ "issues": ["KEY-1"], "customfield_12345": { "value": "Name" } }` and apply with `acli jira workitem edit --from-json edit.json --yes`.
4. For acli edit with JSON, the file must contain the `issues` array; acli does not allow both `--key` and `--from-json`. Run `acli jira workitem edit --from-json edit.json --yes`. Use `--ignore-errors` to continue when some keys fail.

## ADF formatting examples (create)

**Bold:** `"marks": [{"type": "strong"}]` on text. **Code block:** `"type": "codeBlock", "attrs": { "language": "javascript" }, "content": [{ "type": "text", "text": "..." }]`. **Link:** `"marks": [{ "type": "link", "attrs": { "href": "https://example.com" } }]`.

**Canonical ADF specification:** [Atlassian Document Format – Document structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/) is the source of truth for Jira Cloud rich text JSON: the root `doc` node, block and inline nodes (for example `paragraph`, `heading`, `bulletList`, `codeBlock`, `mention`, `inlineCard`, `media`), and marks (for example `link`, `strong`, `code`). That page links to a JSON schema and lists each node and mark. It also states that issue comments and **`textarea` custom fields** store content as ADF; use the same reference when shaping descriptions, comments, or those fields.

### Rich text (ADF): reminders

- **Do not re-spec nodes here.** For `mention`, `inlineCard`, tables, panels, and all other supported shapes, read the node pages under the structure guide above.
- **Mentions:** `mention` requires the correct user `accountId` in attrs. Discover it with `GET /rest/api/3/user/search` (same auth as acli), by inspecting existing ADF on an issue (`acli jira workitem view ISSUE-KEY --json --fields description,comment` and any relevant `customfield_*`), or with the helper script. acli has no `jira user search` (or similar) command; user lookup is REST or the script. Plain text in `--body` / `--description` with `@Display Name` often does **not** produce a real mention or notification; use the Jira UI or ADF JSON via `--body-file` / `--description-file` when mentions must be correct.
- **Helper script:** From the jira-workitem skill directory: `python3 scripts/atlassian_user_search.py -s https://your-domain.atlassian.net 'search-string'` — uses `/rest/api/3/user/search` only (fast); default `--max-results` is 10 (override with `--max-results N`, combine with `--all-pages` for more). Add `--verbose` to also call `/user` (with expand) and `/user/groups` per match (slower). JSON output includes `elapsed_seconds` for that run (search plus any verbose calls).
- **Clickable links:** A plain text URL in an ADF body (e.g. `{ "type": "text", "text": "https://example.com" }`) is NOT automatically hyperlinked; it renders as unclickable text. Always use the inline `link` mark for URLs unless the user explicitly requests a different style or the existing content uses one. Apply the mark to the text node:

  ```json
  {
    "type": "paragraph",
    "content": [
      { "type": "text", "text": "Branch created: " },
      {
        "type": "text",
        "text": "https://github.com/org/repo/tree/my-branch",
        "marks": [{ "type": "link", "attrs": { "href": "https://github.com/org/repo/tree/my-branch" } }]
      }
    ]
  }
  ```

  The `text` value can differ from the `href` (e.g. `"text": "View branch"`) to use custom display text.

- **Smart links vs link marks:** Pasting URLs can yield `inlineCard` nodes; a closing `)` glued to the URL can be stored inside `attrs.url` and break navigation; prefer spacing, a clean `link` mark `href`, or the issue picker (see `inlineCard` and `link` in the structure guide).
- **Verify:** After saving, re-fetch the fields you edited and inspect the returned ADF.

## Web links (remote links)

The "Add web link" UI option maps to the **Issue remote links** REST API. Issue linking must be enabled in the Jira site settings. Requires the `Link issues` project permission and the `write:jira-work` OAuth scope (granular: `write:issue.remote-link:jira`).

### Create a web link

```bash
curl -u "$ATLASSIAN_USER_EMAIL:$ATLASSIAN_USER_API_KEY" \
  -X POST "https://your-domain.atlassian.net/rest/api/3/issue/KEY-123/remotelink" \
  -H "Content-Type: application/json" \
  -d '{
    "object": {
      "url": "https://example.com",
      "title": "Link display title"
    },
    "relationship": "mentioned in"
  }'
```

Only `object.url` and `object.title` are required. `relationship` is optional (shows as a label in the UI).

Supply a `globalId` string to make the call idempotent: if a remote link with that `globalId` already exists it is updated rather than duplicated.

### Other operations

| Goal | Method | Path |
|---|---|---|
| List all web links on an issue | GET | `/rest/api/3/issue/{key}/remotelink` |
| Create or upsert (by globalId) | POST | `/rest/api/3/issue/{key}/remotelink` |
| Get one by link ID | GET | `/rest/api/3/issue/{key}/remotelink/{linkId}` |
| Replace one by link ID | PUT | `/rest/api/3/issue/{key}/remotelink/{linkId}` |
| Delete by link ID | DELETE | `/rest/api/3/issue/{key}/remotelink/{linkId}` |
| Delete by globalId | DELETE | `/rest/api/3/issue/{key}/remotelink?globalId=...` |

Docs: [Issue remote links – REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-remote-links/)

## External links

- Atlassian CLI: https://developer.atlassian.com/cloud/acli/guides/how-to-get-started/
- [ADF document structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
- acli: [workitem edit](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-edit/), [assign](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-assign/), [transition](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-transition/), [comment](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-comment/) (use the `create` subcommand), [view](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-view/).
