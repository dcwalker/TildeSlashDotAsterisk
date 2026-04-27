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

#### Component pre-fill from catalog-info.yaml

When creating or updating a ticket, check for a `catalog-info.yaml` file in the repo root (or the nearest one to the current working directory). If found, read the `title` attribute from it.

If `title` is present, look up matching components on the target Jira issue or project using the editmeta endpoint:

```bash
curl -s -u "${ATLASSIAN_USER_EMAIL}:${ATLASSIAN_USER_API_KEY}" \
  "https://YOUR-SITE.atlassian.net/rest/api/3/issue/ISSUE-KEY/editmeta" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
target = 'TITLE FROM CATALOG-INFO'
for c in data['fields']['components']['allowedValues']:
    if target.lower() in c['name'].lower():
        print(c['id'], '|', c['name'])
"
```

For new issues (no key yet), substitute any existing issue from the same project to get the allowed values list.

Based on the result, prompt the user with one of these options before proceeding:

- If exactly one match is found: "Found component `[name]` (id: `[id]`) matching the catalog-info title. Set this as the component on the ticket, search by a different name, or leave the component field blank?"
- If multiple matches are found: list each match by name and id, then ask which one to use, whether to search by a different name, or whether to leave the field blank.
- If no match is found: "No component matching `[title]` was found. Enter a different name to search for, or leave the component field blank?"

Do not set the component field until the user confirms. Once confirmed, use `PUT /rest/api/3/issue/{key}` with `{"fields": {"components": [{"id": "COMPONENT_ID"}]}}` (see reference).

#### Team pre-fill from catalog-info.yaml

After resolving the component, also check the `spec.owner` attribute in the same `catalog-info.yaml`. If present, use the value as-is for the initial search. Only if that produces no match, strip a leading `team-` prefix and search again (e.g. fall back from `team-my-team-name` to `my-team-name`).

Search for matching teams by name using the Atlassian public teams API, paginating via `cursor` until all pages are checked:

```bash
cursor=""
while true; do
  url="https://api.atlassian.com/public/teams/v1/org/${ATLASSIAN_ORG_ID}/teams?size=50"
  [ -n "$cursor" ] && url="${url}&cursor=${cursor}"
  response=$(curl -s -u "${ATLASSIAN_USER_EMAIL}:${ATLASSIAN_USER_API_KEY}" "$url")
  echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
target = 'SEARCH TERM HERE'
for t in data.get('entities', []):
    if target.lower() in t['displayName'].lower():
        print(t['teamId'], '|', t['displayName'])
"
  cursor=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cursor',''))")
  [ -z "$cursor" ] && break
done
```

Based on the result, prompt the user with one of these options before proceeding:

- If exactly one match is found: "Found team `[displayName]` (id: `[teamId]`) matching the catalog-info owner. Set this as the team on the ticket, search by a different name, or leave the team field blank?"
- If multiple matches are found: list each by name and id, then ask which one to use, whether to search by a different name, or whether to leave the field blank.
- If no match is found: "No team matching `[search term]` was found. Enter a different name to search for, or leave the team field blank?"

Do not set the team field until the user confirms. Once confirmed, use `PUT /rest/api/3/issue/{key}` with `{"fields": {"customfield_NNNNN": {"id": "TEAM_UUID"}}}`, where `customfield_NNNNN` is the Team field ID discovered via `/rest/api/3/field` or editmeta (see reference).

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

For updates to an existing issue, use `/rest/api/3/issue/{key}/editmeta` to get the full list of editable fields and their allowed values.

#### Prompt the user for every field

After discovering all fields, prompt the user for a value for every field that appears on the screen — not just required ones. For each field:

1. Look at recent similar issues in the project to find the most commonly used values:

```bash
acli jira workitem search --jql "project = PROJ AND issuetype = IssueType ORDER BY created DESC" --limit 10 --fields '*all'
```

2. Use that context, plus anything known from the current conversation or repo (e.g. catalog-info.yaml, AGENTS.md), to form a suggested value.

3. Present the suggestion to the user and ask for confirmation or a correction. The only exception is when you are highly confident the value is correct and unambiguous (e.g. the project key on a create, or a field whose value was explicitly stated by the user). In that case you may state the value you will use and give the user a chance to object before proceeding.

4. For fields with a fixed set of allowed values, always display the options. Never guess a value that is not in the allowed list.

5. Group fields into a single prompt when possible to avoid excessive back-and-forth — for example, present all optional fields together with suggested values and ask the user to confirm, change, or skip each one.

6. Skip fields that are system-managed or clearly not user-facing (e.g. `created`, `updated`, `id`, `self`, `watches`, `votes`).

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