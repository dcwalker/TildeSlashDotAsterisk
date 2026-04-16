---
name: jira-workitem
description: Create or edit Jira work items using the Atlassian CLI (acli). Use when the user wants to create, file, or update Jira issues (tasks, bugs, stories, etc.), including rich ADF descriptions, custom fields, component, parent, and bulk operations.
metadata:
  status: trial
---

Create or edit Jira work items with acli. Parent, standard/custom components, required fields, bulk move, bulk component edit, and ADF details live in [jira-workitem-fields-and-rest.md](../../references/jira-workitem-fields-and-rest.md). [get-jira-custom-field-details](../get-jira-custom-field-details/SKILL.md) helps resolve `customfield_*` IDs.

## Inputs

- **Create:** project key, issue type, summary; optional description (ADF), assignee, labels, parent, issue links, required custom fields.
- **Edit:** issue key(s), JQL, or filter; field changes or transitions; for comments, exact draft text and explicit approval before posting.
- acli authenticated: `acli jira auth status`. Use `--fields '*all'` (quoted) when inspecting custom fields.

## Required output structure

- **Create:** clickable `https://[SITE].atlassian.net/browse/[KEY]` after user approves a readable draft (not raw JSON).
- **Edit/comment:** confirm what changed; never post comments without showing the full draft and receiving explicit approval.

## Workflow

### Phase 1: Discover

- Read project conventions (AGENTS.md, CONTRIBUTING.md, issue guidelines) when working in a repo.
- If not authenticated: `acli jira auth login --site "..." --email "..." --token` or `--web`.
- For parent, issue links, components, required selects, or bulk operations, open [jira-workitem-fields-and-rest.md](../../references/jira-workitem-fields-and-rest.md).

### Phase 2: Design

- **Create:** Generate template:

```bash
acli jira workitem create --generate-json > /tmp/workitem-template.json
# If custom/required fields are missing:
acli jira workitem create --generate-json --fields '*all' > /tmp/workitem-template.json
```

- Fill JSON. Required custom fields go in **additionalAttributes** (see reference). Do **not** put `components` in create JSON (acli rejects it); set component after create via REST (reference).

#### Discover required fields and valid options before drafting

Do not wait for a failed create to discover required fields. Run createmeta first:

```bash
curl -s -u "${ATLASSIAN_USER_EMAIL}:${ATLASSIAN_USER_API_KEY}" \
  "https://YOUR-SITE.atlassian.net/rest/api/3/issue/createmeta?projectKeys=PROJ&issuetypeNames=IssueType&expand=projects.issuetypes.fields" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for proj in data['projects']:
    for it in proj['issuetypes']:
        for fname, f in it['fields'].items():
            print(fname, '|', f['name'], '| required:', f.get('required'))
            for av in f.get('allowedValues', []):
                print('  id:', av.get('id'), '| value:', av.get('value', av.get('name','')))
"
```

Use this output to:

1. Identify every required field (`required: True`) and its valid option IDs before writing the JSON.
2. Aim to fill in all relevant optional fields too, not just the minimum. A more complete ticket is more useful.
3. For subjective fields like Severity, Priority, and Environment: look at similar existing issues in the same project to find the values most commonly used for comparable work. Use `acli jira workitem search --jql "project = PROJ AND issuetype = IssueType ORDER BY created DESC" --limit 5` to find reference issues, then inspect them for field values.
4. Always confirm Severity, Priority, Environment, and any other field you are not confident about with the user before creating. Present your proposed values explicitly and ask for a yes or correction.

- Minimal ADF `description` shape:

```json
{
  "version": 1,
  "type": "doc",
  "content": [
    {
      "type": "paragraph",
      "content": [{ "type": "text", "text": "Your text here" }]
    }
  ]
}
```

- Full ADF, mentions, links: reference doc and [Atlassian ADF structure](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/).
- Present summary to user; get **yes/no** before create.

### Phase 3: Implement

**Create:**

```bash
acli jira workitem create --from-json "/path/to/workitem.json"
```

Then `PUT /rest/api/3/issue/{key}` with `components` if needed (reference).

**Select targets:** `--key "K1,K2"`, `--jql "..."`, `--filter ID`, or `--from-file` (assign).

**Common edits:**

- Assign: `acli jira workitem assign --key "..." --assignee "user@example.com"` (`@me`, `--remove-assignee`, `--jql`, etc.).
- Transition: `acli jira workitem transition --key "..." --status "Done"` (exact status name).
- Comment: show draft → explicit approval → `acli jira workitem comment create --key "..." --body "..."` or `--body-file` / `--editor` for ADF.
- Fields: `acli jira workitem edit --key "..." --summary "..." --description-file ...` or `--from-json` with `"issues": [...]` (no `--key` with `--from-json`). Custom fields, parent: JSON per reference. Components: REST PUT, not acli edit JSON.
- Links: `acli jira workitem link create --out BLOCKED --in BLOCKER --type "Blocks" --yes` (note: `--in` is the blocker, `--out` is the blocked issue; always verify direction via JSON after creating). See [jira-workitem-fields-and-rest.md](../../references/jira-workitem-fields-and-rest.md) for direction, link types, and when to use links vs the parent field.
- Web links (external URLs): acli has no command for this. Use `POST /rest/api/3/issue/{key}/remotelink` with body `{"object": {"url": "...", "title": "..."}}`. See reference for upsert via `globalId`, other operations, and permissions.

**Issue type / workflow:** If simple edit fails, use bulk move REST (reference).

### Phase 4: Verify

- Re-fetch affected fields after ADF edits if needed.
- On create failure (required fields, invalid ADF): use createmeta / [get-jira-custom-field-details](../get-jira-custom-field-details/SKILL.md); retry after fixing JSON.


## References

- [jira-workitem-fields-and-rest.md](../../references/jira-workitem-fields-and-rest.md) — field reference, components, bulk move, bulk component, ADF reminders, acli links.
- [get-jira-custom-field-details](../get-jira-custom-field-details/SKILL.md)