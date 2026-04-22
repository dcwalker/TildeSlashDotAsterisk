---
name: get-jira-custom-field-details
description: Looks up a Jira custom field by name and returns its ID, field type, and when applicable a list of option values. Use when the user asks for custom field details, field ID for a field name, options for a select/list field, or when preparing acli/API payloads that need customfield_ IDs.
metadata:
  status: trial
---

Return custom field ID, field type, and (for option fields) allowed values from the field name shown in Jira.

## Inputs

- Field name or partial name (e.g. "Severity", "Environment").
- `ATLASSIAN_BASE_URL` or `--site`: host (e.g. `your-domain.atlassian.net`) or full base URL (e.g. `https://your-domain.atlassian.net`), consistent with `jira-workitem` helpers.
- `ATLASSIAN_USER_EMAIL` and `ATLASSIAN_USER_API_KEY` (Basic auth for REST).

## Required output structure

- **Field ID** (e.g. `customfield_10000`) for JSON keys.
- **Schema / type** to choose payload shape (`option`, arrays, etc.).
- **Options** when available (`id` / `value`); if options fail with 403, note Administer Jira or use createmeta per project/issue type (see reference below).

## Workflow

### Phase 1: Discover

- Confirm site and credentials.
- Script path: `skills/get-jira-custom-field-details/scripts/get-field-details.py` in this repo (or absolute path to your skills install).

### Phase 2: Design

- No separate design step unless the user has multiple similarly named fields; then narrow by project/issue type via createmeta.

### Phase 3: Implement

```bash
python3 scripts/get-field-details.py "Field Name" [--site your-domain.atlassian.net]
```

Run from the `get-jira-custom-field-details/` directory next to `SKILL.md`, or pass the script’s absolute path.

### Phase 4: Verify

- Map output into [jira-workitem](../jira-workitem/SKILL.md) or REST payloads (`additionalAttributes`, `customfield_*` shapes). For complex fields, cross-check [jira-workitem-fields-and-rest.md](../../references/jira-workitem-fields-and-rest.md).

## Without the script

1. `GET /rest/api/3/field` with Basic auth; match `name` (case-insensitive); use `id` and `schema`.
2. Options: `GET /rest/api/3/field/{fieldId}/contexts` then option endpoints (often needs Administer Jira), or `GET /rest/api/3/issue/createmeta?projectKeys=PROJ&expand=projects.issuetypes.fields` for `allowedValues`.

## References

- [Jira REST API v3 – Get fields](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-fields/#api-rest-api-3-field-get)
- [Get custom field options (context)](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-custom-field-options/#api-rest-api-3-field-fieldid-context-contextid-option-get)
- [jira-workitem](../jira-workitem/SKILL.md), [jira-workitem-fields-and-rest.md](../../references/jira-workitem-fields-and-rest.md)