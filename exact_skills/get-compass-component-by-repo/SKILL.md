---
name: get-compass-component-by-repo
description: Looks up a Compass component by repository name using the repo as the external alias and the Compass GraphQL API. Returns component name, type, URL, Jira project URL, and links grouped by link type. Use when the user asks for Compass component details for a repo, or for the component's Jira project or links.
---

# Get Compass Component Details by Repo Name

Fetches a Compass component by searching with the repository name as the external alias (e.g. `my-service` or `org/my-repo`). Outputs component name, component type, component URL, Jira project URL (if any), and links grouped by link type.

## When to Use

- User asks for Compass component info for a repo or "this repo".
- User needs the component's Jira project URL or links by type.
- Preparing or checking Compass metadata tied to a repository.

## Prerequisites

- Atlassian GraphQL Gateway access with Basic auth:
  - `ATLASSIAN_USER_EMAIL` – Atlassian account email
  - `ATLASSIAN_USER_API_KEY` – API token
- Site: `ATLASSIAN_SITE` – Atlassian site host (e.g. `your-domain.atlassian.net`), or pass `--site` to the script. Required; no default.

## Instructions

1. Determine the repo name from the git repo (e.g. from `git remote -v` or the current directory name). Use the format your Compass site expects (e.g. `repo-name` or `owner/repo`). Only ask the user if it cannot be determined.
2. Ensure the site is available: use `ATLASSIAN_SITE` or `--site` if set. If neither is set and the value is not obvious (e.g. from project config), ask the user. Then run `get-component-by-repo.py` with the repo name as the argument.
3. Use the script output: component name, type, URL, Jira project URL, and links by type.

## Output

The script prints:

- **Component name**: Compass component name
- **Component type**: Type label (e.g. Service, Application)
- **URL**: Component URL in Compass (if set)
- **Jira project URL**: First link with type `PROJECT` or URL containing `/browse/` or `/projects/` (if any)
- **Links by type**: All links grouped by `type`, each with name and URL

If no component is found for the given repo name (trying external sources `atl_gh` and `github`), the script exits with an error. Repo name is used as the external alias ID; use the exact alias format your Compass site uses (e.g. `repo` or `owner/repo`).

## How It Works

The script calls the Atlassian GraphQL Gateway at `https://{site}/gateway/api/graphql` with the `compass-beta` experimental API. It uses `getComponentByExternalAlias(cloudId, externalSource, externalId)` with the repo name as `externalId`, trying external sources `atl_gh` and `github`. Cloud ID is resolved from the site via `/_edge/tenant_info`.

## Reference

- [Compass GraphQL API toolkit](https://developer.atlassian.com/cloud/compass/forge-graphql-toolkit/)
- [GetComponentByExternalAliasInput](https://developer.atlassian.com/cloud/compass/forge-graphql-toolkit/Interfaces/GetComponentByExternalAliasInput)
