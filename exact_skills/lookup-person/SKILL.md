---
name: lookup-person
description: Look up a complete profile for any person by name, email, Slack handle, or GitHub username. Searches Slack (profile, title, department, timezone, manager), Atlassian/Jira (account, active projects, Atlassian team memberships), and GitHub (profile, org team memberships) then assembles a unified dossier. Use this skill whenever someone asks to look up a person, find a coworker's contact info, check who someone's manager is, find what teams or projects someone is on, or get any organizational info about a colleague — even if they don't say "look up" or "profile." Trigger on phrases like "who is X", "find X", "what team is X on", "X's manager", "tell me about X".
---

## What this skill does

Builds a unified profile of a person by querying Slack, Atlassian, and GitHub in parallel, then presents a structured summary.

---

## Environment variables

This skill uses the following env vars when available. None are required — the skill degrades gracefully when they aren't set.

| Variable | Used for |
|---|---|
| `ATLASSIAN_BASE_URL` | Your Atlassian site, e.g. `https://your-org.atlassian.net` |
| `ATLASSIAN_USER_EMAIL` | Basic auth for Atlassian REST/GraphQL APIs |
| `ATLASSIAN_USER_API_KEY` | Basic auth for Atlassian REST/GraphQL APIs |
| `ATLASSIAN_ORG_ID` | Atlassian org ID for the public teams API |
| `TWG_USER` | TWG CLI — Atlassian account email (alternative to `ATLASSIAN_USER_EMAIL`) |
| `TWG_SITE` | TWG CLI — default site prefix or domain |
| `TWG_TOKEN` | TWG CLI — API token |

Define this helper early and use it throughout:
```bash
atl_curl() {
  curl -sf -u "${ATLASSIAN_USER_EMAIL}:${ATLASSIAN_USER_API_KEY}" \
    -H "Accept: application/json" "$@"
}
```

If the vars aren't set, `curl -sf` fails silently. Fall back to MCP tools for that section and collect the gap for the closing note.

At the end of every profile, include a **"What's missing"** note — list only sections that couldn't be populated and the simplest way to unlock each:
- Atlassian Teams / Reporting line → set up TWG CLI or set `ATLASSIAN_USER_EMAIL`, `ATLASSIAN_USER_API_KEY`, `ATLASSIAN_ORG_ID`
- GitHub teams → `gh auth login`
- Jira activity → check Atlassian MCP connection

---

## TWG CLI (prefer when available)

The [TWG CLI](https://developer.atlassian.com/cloud/twg-cli/) (Atlassian Teamwork Graph) provides authenticated access to org data including reporting chains and team memberships. Check availability once at the start:

```bash
TWG_AVAILABLE=$(twg doctor >/dev/null 2>&1 && echo yes || echo no)
```

When `TWG_AVAILABLE=yes`, use `twg help` to discover the right subcommands for user search, manager/reporting chain, and team membership queries. The command structure is discoverable at runtime — always use `twg help <topic>` rather than guessing syntax. When `TWG_AVAILABLE=no`, fall through to the curl/MCP paths.

---

## Step 1: Resolve identity across platforms

Use the identifier(s) the user provided to find the person in each system. Run all three lookups in parallel.

### Slack
Use `slack_search_users` with the identifier. Try the full name first; if results are ambiguous, add an email domain or job title qualifier.

### Atlassian

**When TWG is available:** use `twg help` to find the user-search subcommand, then search by name or email. This returns an `accountId` and display name.

**Fallback:** use `lookupJiraAccountId` with `cloudId: "${ATLASSIAN_BASE_URL}"` and the person's name or email as `searchString`. This returns an `accountId`.

If you need the cloudId as a UUID (required for GraphQL calls and the Atlassian People profile URL):
```bash
atl_curl "${ATLASSIAN_BASE_URL}/_edge/tenant_info" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['cloudId'])"
```

### GitHub
- If a GitHub username was given: `gh api /users/{username}` directly.
- If you have the person's email: try `gh api "/search/users?q={email}+in:email"` — note this usually fails for work emails since most people don't expose them publicly on GitHub. Name + location confirmation is more reliable.
- If only a name: `gh api "/search/users?q={name}"` then narrow with location or org if needed.

If a search returns multiple close matches, list them and ask the user to confirm before fetching full profiles.

---

## Step 2: Fetch full details from each platform

Once you have user IDs, run the following in parallel.

### Slack
Call `slack_read_user_profile` with the Slack user ID. Extract:
- Real name, display name, title, department
- Email, phone
- Timezone and locale
- Manager (custom field, if populated)
- Any other custom fields (start date, pronouns, location, GitHub handle)
- Workspace/team ID (the `team` field, starts with `T`) — used to construct the Slack deep link

**Note:** Slack profiles sometimes contain a GitHub username in a custom field. Check all custom fields for anything that looks like a GitHub handle — this can short-circuit a GitHub search.

### Atlassian — user details, teams, and reporting chain

With the `accountId` from Step 1, run these in parallel:

**1. Recent Jira activity** — infers squad/project context:
```
searchJiraIssuesUsingJql
  cloudId: "${ATLASSIAN_BASE_URL}"
  jql: "assignee = \"{accountId}\" ORDER BY updated DESC"
  fields: ["summary", "project", "status", "updated"]
  maxResults: 15
```
Extract unique project keys and names.

**2. Atlassian team memberships** — finds which formal Atlassian teams the person is on.

Paginate all org teams and check each for the person's `accountId` in their member list using the Teams GraphQL API (`teamsV2` query, `@optIn(to: "Team")`, `members @optIn(to: "team-members-beta")`):

```bash
# Paginate the public teams API and collect all teamIds
cursor=""
while true; do
  url="https://api.atlassian.com/public/teams/v1/org/${ATLASSIAN_ORG_ID}/teams?size=50"
  [ -n "$cursor" ] && url="${url}&cursor=${cursor}"
  response=$(atl_curl "$url") || break
  echo "$response" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data.get('entities',[]): print(t['teamId'],'|',t['displayName'])
"
  cursor=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cursor',''))" 2>/dev/null)
  [ -z "$cursor" ] && break
done
# Then use the teamsV2 GraphQL query to get members for each batch of teamIds
# and check if the person's accountId appears in the member list
```

**3. Full reporting line** — walk every level from direct manager to org root.

**When TWG is available:** use `twg help` to find the reporting-chain or manager subcommand for a given `accountId`. TWG handles auth and returns the chain directly.

**Fallback:** use the GraphQL `teamworkGraph_userReportChain` query:

```bash
ACCOUNT_ARI="ari:cloud:identity::user/{accountId}"
atl_curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-ExperimentalApi: TeamworkGraphContextAPIs" \
  "${ATLASSIAN_BASE_URL}/gateway/api/graphql" \
  -d "{\"query\": \"query ReportChain(\$userId: ID!) { teamworkGraph_userReportChain(userId: \$userId) @optIn(to: \\\"TeamworkGraphContextAPIs\\\") { edges { node { columns { key value { ... on GraphStoreCypherQueryV2AriNode { id } } } } } } }\", \"variables\": {\"userId\": \"${ACCOUNT_ARI}\"}}" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
edges = (data.get('data') or {}).get('teamworkGraph_userReportChain', {}).get('edges', [])

# Each edge has columns keyed level1Manager...level10Manager
# level1Manager = direct manager, level2Manager = skip-level, etc.
# Pick the longest chain across all edges
best = []
for edge in edges:
    levels = {}
    for col in edge.get('node', {}).get('columns', []):
        key = col.get('key', '')
        if key.startswith('level') and key.endswith('Manager'):
            try:
                n = int(key[5:-7])
            except ValueError:
                continue
            ari = (col.get('value') or {}).get('id', '')
            if n > 0 and ari:
                levels[n] = ari
    chain = []
    for i in range(1, 11):
        if i in levels:
            chain.append(levels[i])
        else:
            break
    if len(chain) > len(best):
        best = chain

for ari in best:
    print(ari.removeprefix('ari:cloud:identity::user/'))
"
```

This prints one account ID per line, direct manager first. Resolve each to name and title:
```bash
atl_curl "${ATLASSIAN_BASE_URL}/rest/api/3/user?accountId={ACCOUNT_ID}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('displayName',''), '|', d.get('title',''))"
```

**If curl is unavailable:** Check the Slack profile manager field, or use `lookupJiraAccountId` with the manager's account ID as `searchString`. Without curl you can get at most the direct manager's name — note the gap in "What's missing".

### GitHub

Run in parallel once the username is known:

1. Profile: `gh api /users/{username}` — name, company, location, bio

2. Discover which orgs the authenticated user belongs to, then scan each for the person's team memberships:
   ```bash
   # List orgs the GitHub auth token can see
   gh api /user/orgs --paginate | python3 -c "
   import json,sys; [print(o['login']) for o in json.load(sys.stdin)]
   "
   ```
   For each org, do a **full membership scan** — the GraphQL `userLogins` filter only returns direct memberships and misses inherited/parent-team memberships, so the REST scan is more complete:
   ```bash
   # For each org:
   gh api /orgs/{org}/teams --paginate 2>/dev/null \
     | python3 -c "
   import json, sys
   for t in json.load(sys.stdin):
       print(t['slug'] + '|' + t['name'])
   " | while IFS='|' read slug name; do
       status=$(gh api "/orgs/{org}/teams/${slug}/memberships/{username}" 2>/dev/null \
         | python3 -c "import json,sys; print(json.load(sys.stdin).get('state',''))" 2>/dev/null)
       [ "$status" = "active" ] && echo "  - $name"
     done
   ```
   Run org scans concurrently with `&` / `wait` if checking multiple orgs. For very large orgs (hundreds of teams), fall back to the GraphQL filter and note it may be incomplete.

---

## Step 3: Present the unified profile

If the user asked a specific question ("what team are they on?", "who's their manager?"), answer it directly and concisely **before** the full profile.

Then assemble everything using this format (omit sections with no data):

```
# [Full Name]

## Contact & Identity
- **Email:** ...
- **Slack:** @displayname (ID: UXXXXXXXX) — [Open profile](slack://user?team=TXXXXXXXX&id=UXXXXXXXX)
- **GitHub:** [@username](https://github.com/username)
- **Atlassian:** [People profile](https://home.atlassian.com/o/{ATLASSIAN_ORG_ID}/people/{accountId}?cloudId={cloudId})
- **Phone:** ... (if present)

## Location & Timezone
- **Location:** City, State/Country
- **Timezone:** Region/City (abbreviation, UTC offset)

## Role & Organization
- **Title:** ...
- **Department:** ...
- **Start Date:** ... (if available)

## Reporting Line
[C-level] — [Title]
↓ 
[VP / Director] — [Title]
↓ 
[Skip-level] — [Title]
↓ 
[Direct Manager] — [Title]
↓ 
[Person Name] — [Title]
*(from Atlassian reporting chain; level1Manager = direct manager)*

## Atlassian Teams
- Team Name
- Team Name

## Atlassian / Jira Activity
- **Account ID:** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- **Active Projects:** Project Name (KEY), ...
  *(based on recent assignments)*

## GitHub Teams
**{org} org:**
- Team Name

## Slack Status
- **Status:** [emoji] Text
- **Availability:** Active / Away

---
*What's missing: [list sections that couldn't be populated and how to unlock them]*
```

---

## Cross-referencing tips

- If the Slack profile has a custom field with a GitHub-looking value, use it directly rather than searching.
- Cross-check the name returned from GitHub against the Slack name to confirm identity before presenting results.
- For common names, confirm via email match across platforms before treating them as the same person.

## Profile link construction

**Slack deep link** (opens in the desktop app):
```
slack://user?team={teamId}&id={userId}
```
`teamId` is the workspace ID from `slack_read_user_profile` (starts with `T`). There is no reliable web URL equivalent without a workspace slug that the MCP tools don't expose.

**GitHub profile**:
```
https://github.com/{username}
```

**Atlassian People profile**:
```
https://home.atlassian.com/o/{ATLASSIAN_ORG_ID}/people/{accountId}?cloudId={cloudId}
```
`cloudId` is the UUID from `/_edge/tenant_info`. `ATLASSIAN_ORG_ID` is the env var. `accountId` is the Jira/Atlassian account ID. Omit the link if any of the three values are unavailable.
