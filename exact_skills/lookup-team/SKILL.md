---
name: lookup-team
description: Look up a complete profile for any team by Atlassian team name, GitHub team slug, or Slack channel name. Searches Atlassian (team membership, Compass ownership, Jira activity, reporting chain), GitHub (team slug, repos), and Slack (associated channels) then assembles a unified dossier. Use this skill whenever someone asks about a team — what they own, who's on them, who leads them, how they're named across tools, what they're working on. Trigger on phrases like "who is on X team", "what does X team own", "what is X team called in GitHub", "who does X team report to", "find X team", "tell me about the X team", "X team Atlassian", "X team members", "X team repos".
---

## What this skill does

Builds a unified profile of a team by querying Atlassian, GitHub, and Slack in parallel, then presents a structured summary covering identity, members, ownership, reporting structure, and profile links.

---

## Environment variables

Uses the same env vars as `lookup-person`. None are required — the skill degrades gracefully.

| Variable | Used for |
|---|---|
| `ATLASSIAN_BASE_URL` | Your Atlassian site, e.g. `https://your-org.atlassian.net` |
| `ATLASSIAN_USER_EMAIL` | Basic auth for Atlassian REST/GraphQL APIs |
| `ATLASSIAN_USER_API_KEY` | Basic auth for Atlassian REST/GraphQL APIs |
| `ATLASSIAN_ORG_ID` | Atlassian org ID for the public teams API |
| `BACKSTAGE_URL` | Backstage catalog API base, e.g. `https://backstage.example.com/api/catalog` |

Define this helper early and use it throughout:
```bash
atl_curl() {
  curl -sf -u "${ATLASSIAN_USER_EMAIL}:${ATLASSIAN_USER_API_KEY}" \
    -H "Accept: application/json" "$@"
}
```

Fetch the cloudId UUID once up front — it's needed for GraphQL and the Atlassian profile URL:
```bash
CLOUD_ID=$(atl_curl "${ATLASSIAN_BASE_URL}/_edge/tenant_info" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['cloudId'])")
SITE_ARI="ari:cloud:platform::site/${CLOUD_ID}"
```

---

## TWG CLI (preferred when available)

The `twg` CLI (Atlassian Teamwork Graph) provides a simpler, auth-aware path for team resolution. Check once at the start:

```bash
TWG_AVAILABLE=$(which twg >/dev/null 2>&1 && echo yes || echo no)
```

When `twg` is available, prefer the `twg` paths described in the steps below. When it is not installed, fall through to the curl/MCP paths as usual.

`twg` reads auth from `~/.config/twg/auth.conf` or `TWG_USER` / `TWG_SITE` env vars. If it is installed but not authenticated, it will error — fall back to the curl path and note the gap.

---

## Step 1: Resolve team identity across platforms

Run all three in parallel.

### Atlassian

**Preferred (when twg is available):**
```bash
twg teams query -s {site} -q "{team name}" -o json
```
`twg` handles name-variant matching and auth automatically. Try the input as given first. If it returns no results, also try the stripped name (without `[T]`, `[D]`, `[V]`, or `FedRAMP ` prefixes) and the slug form (lowercase, hyphens). If it returns multiple matches, list them and ask the user to confirm.

**Fallback (when twg is unavailable):** Paginate the entire public teams API and match locally:
```bash
cursor=""
while true; do
  url="https://api.atlassian.com/public/teams/v1/org/${ATLASSIAN_ORG_ID}/teams?size=50"
  [ -n "$cursor" ] && url="${url}&cursor=${cursor}"
  response=$(atl_curl "$url") || break
  echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data.get('entities', []):
    print(t['teamId'] + '|' + t.get('displayName',''))
"
  cursor=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin).get('cursor',''))" 2>/dev/null)
  [ -z "$cursor" ] && break
done
```

**Try all of these search variants against the full team list (case-insensitive substring match):**
1. The exact input as given (e.g., `"Engineering Enablement"`)
2. With common prefixes added: `"[T] Engineering Enablement"`, `"[D] ..."`, `"[V] ..."`, `"FedRAMP ..."`
3. With prefixes stripped: if the input is `"[T] Engineering Enablement"`, also try `"Engineering Enablement"`
4. Slug form: `"engineering-enablement"` (lowercase, hyphens)

Do not give up after the first variant fails. A team named `[T] Engineering Enablement` in the API will not match a bare search for `Engineering Enablement` unless you also check the stripped name. Match on either `teamId` or `displayName`.

If multiple teams match after trying all variants, list them and ask the user to confirm. If curl is unavailable, fall back to `lookupJiraAccountId` with `cloudId: "${ATLASSIAN_BASE_URL}"` and the team name as `searchString`.

### GitHub

Discover orgs dynamically, then search for a matching team slug:
```bash
gh api /user/orgs --paginate \
  | python3 -c "import json,sys; [print(o['login']) for o in json.load(sys.stdin)]" \
  | while read org; do
    gh api "/orgs/${org}/teams" --paginate 2>/dev/null \
      | python3 -c "
import json, sys, re
inp = '${TEAM_NAME_LOWER}'
for t in json.load(sys.stdin):
    name_lower = t['name'].lower()
    slug = t['slug']
    if inp in name_lower or inp in slug:
        print('${org}' + '/' + slug + '|' + t['name'])
"
  done
```

The GitHub team slug is typically a lowercased, hyphenated version of the name without prefixes. Try both the full name and the stripped name (without `[T] `, `[D] `, etc.).

### Backstage

The Backstage group name matches the GitHub team slug. Fetch the group entity directly:
```bash
curl -sf "${BACKSTAGE_URL}/entities/by-name/group/default/{github-slug}" \
  | python3 -c "
import json, sys
e = json.load(sys.stdin)
meta = e.get('metadata', {})
spec = e.get('spec', {})
print('title:', meta.get('title',''))
print('description:', meta.get('description',''))
for k,v in (meta.get('annotations',{}) or {}).items():
    print('annotation:', k, '=', v)
for link in (meta.get('links') or []):
    print('link:', link.get('title',''), '=', link.get('url',''))
"
```

Also fetch members and owned components:
```bash
# Members
curl -sf "${BACKSTAGE_URL}/entities?filter=kind=user,relations.memberof=group:default/{github-slug}" \
  | python3 -c "
import json,sys
for e in json.load(sys.stdin):
    m = e.get('metadata',{})
    s = e.get('spec',{})
    p = s.get('profile',{}) or {}
    print(m.get('name',''), '|', p.get('displayName',''), '|', p.get('email',''))
"

# Owned components
curl -sf "${BACKSTAGE_URL}/entities?filter=relations.ownedby=group:default/{github-slug}" \
  | python3 -c "
import json,sys
for e in json.load(sys.stdin):
    m = e.get('metadata',{})
    print(e.get('kind',''), '|', m.get('name',''), '|', m.get('description',''))
"
```

Backstage group and component pages use the pattern:
```
https://{backstage-host}/catalog/default/group/{github-slug}
https://{backstage-host}/catalog/default/component/{component-name}
https://{backstage-host}/catalog/default/user/{username}
```
where `backstage-host` is the hostname from `BACKSTAGE_URL`.

If the backstage skill is available, use it instead: `uv run scripts/backstage.py get group default {github-slug}` and `uv run scripts/backstage.py query --filter relations.ownedby=group:default/{github-slug}`.

### Slack

Use `slack_search_channels` with the team name. Also try the stripped name (without prefix). Return any channels whose names or topics reference the team.

---

## Step 2: Fetch full details from each platform

Once you have the team ID and slug, run all data gathering in parallel.

### Atlassian — members, metadata, and profile URL

**Preferred (when twg is available):**
```bash
twg teams get "{team name or ARI}" -s {site} -o json
```
Returns the team with its full member list including `accountId`, `name`, and `accountStatus`. Use this to populate the members table. Still run the `teamsV2` GraphQL query (below) for `extendedProfile` fields (`jobTitle`, `department`) and the Atlassian `profileUrl`, which `twg teams get` may not include.

**Fallback / supplement:** Use the `teamsV2` GraphQL query to get members and team metadata:

```bash
atl_curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-ExperimentalApi: teams-beta,team-members-beta" \
  "${ATLASSIAN_BASE_URL}/gateway/api/graphql" \
  -d "{
    \"query\": \"query TeamsEnrich(\$ids: [ID!]!, \$siteId: String!) { team { teamsV2(ids: \$ids, siteId: \$siteId) @optIn(to: \\\"Team\\\") { id displayName state profileUrl isVerified type { name } creator { ... on AtlassianAccountUser { name } } members(first: 200) @optIn(to: \\\"team-members-beta\\\") { nodes { member { ... on AtlassianAccountUser { accountId name accountStatus extendedProfile { department location jobTitle } } } } } } } }\",
    \"variables\": {\"ids\": [\"ari:cloud:identity::team/${TEAM_ID}\"], \"siteId\": \"${CLOUD_ID}\"}
  }" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
team = ((data.get('data') or {}).get('team') or {}).get('teamsV2', [{}])[0]
print('profileUrl:', team.get('profileUrl',''))
print('state:', team.get('state',''))
print('isVerified:', team.get('isVerified',''))
for m in team.get('members',{}).get('nodes',[]):
    mem = m.get('member',{})
    ext = mem.get('extendedProfile',{}) or {}
    status = mem.get('accountStatus','')
    print('MEMBER', mem.get('accountId',''), '|', mem.get('name',''), '|', ext.get('jobTitle',''), '|', ext.get('department',''), '|', status)
"
```

Extract:
- `profileUrl` — this is the direct Atlassian team profile URL (e.g., `https://team.atlassian.com/...`)
- Team state, type, verified status, creator
- Full member list: `accountId`, `name`, `jobTitle`, `department`, `accountStatus`

### Backstage — team description and owned entities

Run in parallel with the Atlassian calls. The `relations.ownedby` query returns all Backstage entities owned by the team — components, APIs, systems, resources. This often provides richer descriptions and repo links than Compass alone.

```bash
curl -sf "${BACKSTAGE_URL}/entities?filter=relations.ownedby=group:default/{github-slug}&limit=200" \
  | python3 -c "
import json, sys
for e in json.load(sys.stdin):
    m = e.get('metadata', {})
    links = [l.get('url','') for l in (m.get('links') or [])]
    anns = m.get('annotations',{}) or {}
    repo = anns.get('github.com/project-slug','') or anns.get('backstage.io/source-location','')
    print(e.get('kind',''), '|', m.get('name',''), '|', m.get('description',''), '|', repo)
"
```

Cross-reference with Compass: components should appear in both. If a component is in Backstage but not Compass, note it. If Compass shows more, use Compass as authoritative for ownership.

### Atlassian — Compass components owned by the team

```bash
atl_curl -X POST \
  -H "Content-Type: application/json" \
  "${ATLASSIAN_BASE_URL}/gateway/api/graphql" \
  -d "{
    \"query\": \"query CompassComponents(\$cloudId: String!, \$ownerARI: String!) { compass { searchComponents(cloudId: \$cloudId, query: { fieldFilters: [{ name: \\\"ownerId\\\", filter: { eq: \$ownerARI } }] }) { ... on CompassSearchComponentConnection { totalCount nodes { component { id name type { name } links { url type } } } } ... on QueryError { message } } } }\",
    \"variables\": {\"cloudId\": \"${CLOUD_ID}\", \"ownerARI\": \"ari:cloud:identity::team/${TEAM_ID}\"}
  }" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
result = (data.get('data') or {}).get('compass',{}).get('searchComponents',{})
print('total:', result.get('totalCount', 0))
for n in result.get('nodes', []):
    c = n.get('component', {})
    ctype = (c.get('type') or {}).get('name', '')
    links = [l['url'] for l in c.get('links', []) if l.get('url')]
    print(c.get('name',''), '|', ctype, '|', links[0] if links else '')
"
```

Alternatively use the `getCompassComponents` MCP tool with the team's owner ARI.

### Atlassian — Jira activity

Find active Jira projects by querying recent issues assigned to team members:
```
searchJiraIssuesUsingJql
  cloudId: "${ATLASSIAN_BASE_URL}"
  jql: "assignee in ({accountId1},{accountId2},...) ORDER BY updated DESC"
  fields: ["summary", "project", "status", "updated", "assignee"]
  maxResults: 30
```

Extract unique project keys/names. This gives a picture of what the team is actively working on.

Alternatively, Jira has a team-scoped query: `team = "{teamId}" AND updated >= -90d` — try this first since it's more direct.

### Atlassian — reporting chain for each member

Run the reporting chain query for each active member. This is the same call as `lookup-person`:

```bash
# For each member accountId:
ACCOUNT_ARI="ari:cloud:identity::user/${ACCOUNT_ID}"
atl_curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-ExperimentalApi: TeamworkGraphContextAPIs" \
  -H "X-Query-Context: ${SITE_ARI}" \
  "${ATLASSIAN_BASE_URL}/gateway/api/graphql" \
  -d "{\"query\": \"query ReportChain(\$userId: ID!) { teamworkGraph_userReportChain(userId: \$userId) @optIn(to: \\\"TeamworkGraphContextAPIs\\\") { edges { node { columns { key value { ... on GraphStoreCypherQueryV2AriNode { id } } } } } } }\", \"variables\": {\"userId\": \"${ACCOUNT_ARI}\"}}" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
edges = (data.get('data') or {}).get('teamworkGraph_userReportChain', {}).get('edges', [])

# Parse all chains (_parse_all_chains logic from atlassian_teams_report.py)
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

Collect chains for all active members, then find the majority manager:

```python
from collections import Counter

# chains = {accountId: [level1ManagerId, level2ManagerId, ...]}
# Find the most common direct manager (level1):
direct_managers = [chain[0] for chain in chains.values() if chain]
majority_direct = Counter(direct_managers).most_common(1)[0] if direct_managers else None

# Resolve the majority manager's name and their own reporting chain
# to show org hierarchy above the team
```

Resolve each unique manager account ID to a display name:
```bash
atl_curl "${ATLASSIAN_BASE_URL}/rest/api/3/user?accountId={ACCOUNT_ID}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('displayName',''), '|', d.get('title',''))"
```

### GitHub — repos owned by the team

```bash
gh api "/orgs/{org}/teams/{slug}/repos" --paginate 2>/dev/null \
  | python3 -c "
import json, sys
for r in json.load(sys.stdin):
    print(r['name'] + '|' + r.get('description','') + '|' + r.get('html_url','') + '|' + r.get('visibility',''))
"
```

---

## Step 3: Present the unified profile

If the user asked a specific question ("what repos do they own?", "who's their manager?"), answer it directly and concisely **before** the full profile.

Then assemble everything using this format (omit sections with no data):

```
# [Team Display Name]
*([T] / [D] / [V] prefix stripped name, if applicable)*

## Platform Identity
- **Atlassian People:** [Team Name](https://home.atlassian.com/o/{ATLASSIAN_ORG_ID}/people/team/{teamId}?cloudId={cloudId}) (ID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- **Compass:** [Team page](https://{ATLASSIAN_BASE_URL}/compass/people/team/{teamId})
- **Backstage:** [Catalog entry](https://{backstage-host}/catalog/default/group/{github-slug})
- **GitHub:** [@org/slug](https://github.com/orgs/{org}/teams/{slug})
- **Slack:** #channel-name

## Members ({N} active)
| Name | Title | Department | Links |
|---|---|---|---|
| Jane Smith | Senior Engineer | Platform Infra | [Slack](slack://user?team=T...&id=U...) · [GitHub](https://github.com/jsmith) · [Atlassian](https://home.atlassian.com/o/{ATLASSIAN_ORG_ID}/people/{accountId}?cloudId={cloudId}) |
...

## Reporting Structure
Most members ({N}/{total}) report to: **[Manager Name]** — [Title]

[Manager Name] — [Title]
↑ [Skip-level] — [Title]
↑ [VP/Director] — [Title]
↑ [C-level] — [Title]
*(reporting chain above majority manager)*

## What the Team Owns

### Compass Components ({N})
- [Component Name](link) — Type
- [Component Name](link) — Type

### GitHub Repos
- [repo-name](url) — description (visibility)

### Active Jira Projects
- Project Name (KEY) — based on recent activity

## Team Details
- **State:** Active / Inactive
- **Verified:** Yes / No
- **Type:** ...
- **Created by:** Name

---
*What's missing: [list sections that couldn't be populated and how to unlock them]*
```

---

## Cross-referencing tips

- Team names in Atlassian often have `[T]`, `[D]`, `[V]`, or `FedRAMP` prefixes — strip these when matching to GitHub slugs or Slack channels.
- If the GitHub team slug doesn't directly match, try replacing spaces with hyphens and lowercasing the stripped name.
- The Atlassian `profileUrl` from the `teamsV2` GraphQL response is the canonical team URL — use it directly rather than constructing one.
- When the majority manager can't be determined (e.g., all members have different managers, or chains are empty), note this explicitly — it may indicate a cross-functional team.
- Compass component count from GraphQL and the MCP tool `getCompassComponents` should agree; use whichever is available.

## Profile link construction

**Atlassian People team page** — construct from the team ID:
```
https://home.atlassian.com/o/{ATLASSIAN_ORG_ID}/people/team/{teamId}?cloudId={cloudId}
```
`ATLASSIAN_ORG_ID` is the env var. `cloudId` is the UUID from `/_edge/tenant_info`. `teamId` is the raw team ID (the `og-` or UUID value from the public teams API — strip any `ari:cloud:identity::team/` prefix if present).

**Compass team page** — construct from the team ID and base URL:
```
https://{ATLASSIAN_BASE_URL}/compass/people/team/{teamId}
```

The `profileUrl` from the `teamsV2` GraphQL response may also be available — use it if present, but prefer the explicitly constructed URLs above since they are more reliable.

**Backstage team page** — uses the GitHub team slug:
```
https://{backstage-host}/catalog/default/group/{github-slug}
```
where `backstage-host` is the hostname from `BACKSTAGE_URL` (strip `/api/catalog`).

**GitHub team**:
```
https://github.com/orgs/{org}/teams/{slug}
```

**Slack channel** — from `slack_search_channels` results; use the `#channel-name` format with the channel URL if available.

**Member individual profiles** — use the same link patterns as `lookup-person`:
- Slack: `slack://user?team={teamId}&id={userId}` (opens in desktop app)
- GitHub: `https://github.com/{username}`
- Atlassian: `https://home.atlassian.com/o/{ATLASSIAN_ORG_ID}/people/{accountId}?cloudId={cloudId}`
- Backstage: `https://{backstage-host}/catalog/default/user/{username}`
