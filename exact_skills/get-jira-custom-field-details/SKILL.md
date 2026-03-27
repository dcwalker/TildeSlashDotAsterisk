---
name: get-jira-custom-field-details
description: Looks up a Jira custom field by name and returns its ID, field type, and when applicable a list of option values. Use when the user asks for custom field details, field ID for a field name, options for a select/list field, or when preparing acli/API payloads that need customfield_ IDs.
---

# Get Jira Custom Field Details

Returns custom field ID, field type, and (for option-based fields) the list of option values. Input is the field name as shown in Jira.

## When to Use

- User asks for the custom field ID for a field name (e.g. "Severity", "Environment").
- User needs field type or option values for a Jira custom field.
- Preparing `acli jira workitem create --from-json` or REST API payloads that require `customfield_XXXXX` and correct value format.

## Prerequisites

- Jira REST API access. Auth via Basic (email + API token):
  - `ATLASSIAN_USER_EMAIL` – Atlassian account email
  - `ATLASSIAN_USER_API_KEY` – API token ([create at id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens))
- Site: `ATLASSIAN_SITE` – Atlassian site host (e.g. `your-domain.atlassian.net`), or pass `--site` to the script. Required; no default.

## Instructions

1. Get the exact or partial field name from the user (e.g. "Severity", "Environment").
2. Ensure `ATLASSIAN_SITE` is set (or pass `--site`), then run `get-field-details.py` with the field name as the argument.
3. Use the script output:
   - **Field ID**: Use as the key in JSON (e.g. `"customfield_10000": "value"`).
   - **Field type**: Use to choose value format (e.g. option fields need `{"value": "..."}` or `{"id": "..."}`).
   - **Options**: If present, valid values for select/list/radio/checkbox fields; use `value` or `id` in API payloads.

## Output

The script prints:

- **Custom field ID** (e.g. `customfield_10000`)
- **Field type** from Jira schema (e.g. `option`, `array` with `items: option`, or other schema type/custom type)
- **Options** (if the field has option values): list of `id` and `value` per option. If the options endpoint returns 403, the script notes that options require Administer Jira and suggests using issue createmeta for a specific project/issue type to see allowed values.

If no custom field matches the name, the script exits with an error and suggests checking spelling or using the exact name from Jira.

## Alternative Without Script

If the script cannot be run:

1. **Find field ID and type**: `GET /rest/api/3/field` with Basic auth. Search the response for a field whose `name` matches (case-insensitive). Use that object's `id` and `schema` (e.g. `schema.type`, `schema.custom`) as the field type.
2. **Find options** (for select/list-style fields): Either:
   - `GET /rest/api/3/field/{fieldId}/contexts`, then `GET /rest/api/3/field/{fieldId}/context/{contextId}/option` for one context (requires Administer Jira), or
   - `GET /rest/api/3/issue/createmeta?projectKeys=PROJ&expand=projects.issuetypes.fields` and read `allowedValues` for the field in the project/issue type of interest.

## Reference

- [Jira REST API v3 – Get fields](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-fields/#api-rest-api-3-field-get)
- [Get custom field options (context)](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-custom-field-options/#api-rest-api-3-field-fieldid-context-contextid-option-get)
