---
name: triage-work-items
description: >
  Triage and review Trello cards or Jira work items to ensure all metadata is
  complete, titles are outcome-focused, related items are linked or merged, and
  stale work is unblocked. Use when the user wants to audit a card, ticket, board,
  or project backlog for completeness and actionability. Also triggers for: "can
  you look at this card/ticket", "review my backlog", "clean up my board", "this
  issue has been sitting for a while", "help me triage".
---

# Triage Work Item

Review and enrich one or more work items so that each has clear, actionable
metadata and a well-formed next step. The depth and language of the review should
match the nature and size of the work — a quick personal chore needs very
different treatment than a complex engineering feature. Draw on GTD (capture,
clarify, organize, reflect, engage), Kanban (flow, WIP), and LEAN (eliminate
waste, maximize value) principles throughout.

---

## Step 0: Establish Scope

If the user did not specify what to review, ask:

> "What would you like to triage? You can share a card URL, issue key, board
> name, project key, or just describe what you're working on."

Do not proceed until scope is clear. Accept any of:

- A Trello card URL or short link (e.g. `https://trello.com/c/abc123`)
- A Trello board name or board ID
- A Jira issue key (e.g. `PROJ-123`) or URL
- A Jira project key or JQL filter

**Capability discovery:** Before fetching, survey what is available in the
current session — check which MCP tools are loaded, which skills are available,
and which CLI tools respond to `command -v <tool>`. Use the best available
option for the platform implied by the scope. If the platform is ambiguous, ask.

---

## Step 1: Fetch the Item(s)

Use the best available tool for the platform. In order of preference:

1. **MCP** — if an MCP for the platform is loaded in this session, use it.
   Common examples: Atlassian MCP for Jira/Confluence, a Trello MCP if present.
2. **Skill** — if a relevant skill is available (e.g. `twg` for Jira project
   or backlog scans), load and invoke it.
3. **CLI** — if a CLI for the platform is installed (`command -v <tool>`),
   invoke it. Pass flags to request all fields.
4. **REST / WebFetch** — fall back to a direct API call if nothing else is
   available. Jira: `GET /rest/api/3/issue/{key}?fields=*all`. Trello:
   `GET https://api.trello.com/1/cards/{id}?fields=all&actions=all`.

For broader project or backlog scans, load the `twg` skill if available.

**Capture for each item:** title, description, type, status/list, assignee(s),
labels/tags, due date, start date, priority, effort estimate, linked items,
attachments, embedded URLs, comments (with dates), external links, creation date,
and last-updated date.

---

## Step 2: Read Context and Size

Before auditing anything, make two quick assessments. These shape every
suggestion you make for the rest of the triage.

### 2a. Work context

| Context | Signals |
|---|---|
| **Personal** | Personal board, no team members, items like "buy groceries", "plan trip", "call dentist" |
| **Professional** | Team board/project, issue types like Bug/Story/Epic, sprint context, business terminology |
| **Mixed** | Personal productivity board used for work tasks, or a team board with personal to-dos mixed in |

### 2b. Task size

| Size | Signals |
|---|---|
| **Small** | Single clear action, completable in under a day, no dependencies, obvious done state |
| **Medium** | Multiple steps or sub-tasks, 1–5 days of effort, may have a dependency or two |
| **Large / Project** | Multi-week or multi-phase effort, has sub-tasks or should have them, involves multiple people or systems |

### 2c. Select enrichment tier

Use the context and size to select the right enrichment level. The goal is
*just enough structure to move the item forward* — no more.

| Tier | When | What to enrich |
|---|---|---|
| **1 — Lightweight** | Personal + Small, or any pure personal quick-task | Title clarity, assignee (if shared), due date (if time-sensitive), maybe a brief note |
| **2 — Standard** | Professional + Small/Medium, or Personal + Medium/Large | Title, description outcome, labels, assignee, priority, due date |
| **3 — Full** | Professional + Large, or any item that is clearly a project or initiative | Everything in Tier 2, plus phases/sub-tasks, external links, and effort estimate |

When in doubt, start at a lower tier. It is always better to under-enrich and
ask than to impose structure the user didn't want.

---

## Step 3: Scan for Similar and Related Items

Before auditing the individual item, look for duplicates and candidates to
link or merge. This step matters most for professional boards/projects.

For personal boards with small tasks, skip this step unless the user has
asked you to look for duplicates.

Use the same tool hierarchy from Step 1. Search for items that share key terms
from the title and description. For Jira, scope the search to the same project
with `statusCategory != Done`. For Trello, scope to the same board. Limit
results to 20 and request at minimum: title/summary, status, and assignee.

| Relationship | Action |
|---|---|
| Direct overlap (same work) | Present as probable duplicate; ask whether to merge, close one, or link |
| Partial overlap (related work) | Suggest linking ("Relates to" or "Blocks/Blocked by") |
| Sequential dependency | Suggest ordering in the backlog |
| No overlap | Proceed silently |

Confirm every proposed link or merge before applying.

---

## Step 4: Audit Metadata

Audit the fields appropriate to the item's tier. For each missing or unclear
field, apply this decision rule:

| Confidence | Action |
|---|---|
| High — obvious from context | State the intended value; give the user a chance to object |
| Medium — reasonable inference | Suggest the value and ask for confirmation |
| Low — genuinely unclear | Ask before proposing anything |

### Title

A good title is action-oriented and specific enough to act on without reading
the description. Calibrate the phrasing to the context:

- **Personal task:** Use natural language. "Book flights for Austin trip" is
  better than "Flight booking" or "Book flights (acceptance criteria: ...)".
- **Professional task/bug:** Lead with the outcome. "Fix unexpected logout after
  30 min inactivity on mobile" beats "auth bug".
- **Project/initiative:** State the end goal. "Launch self-serve billing portal
  for SMB customers" beats "billing portal".

If the title is a noun phrase, a question, or too vague to act on, propose a
rewrite and confirm before changing it. **Only propose the title once** — in the
final change summary (Step 8), not earlier.

For personal items with no description to draw from, ask a brief question
rather than guessing: "What destination or timeframe did you have in mind?" is
more useful than a generic rewrite like "Plan and book summer vacation."

### Description

A description should answer: what needs to be done, why it matters, what done
looks like, and any constraints. Calibrate to the context:

- **Personal small task:** A single sentence is often enough. No need for formal
  sections or headers.
- **Personal project:** Key details relevant to the domain. For a trip, that
  means destination, dates, budget, who's going. For a home project, scope,
  materials, and timeline. Write as plain prose — no section headers.
- **Professional task or bug (Tier 2):** A short paragraph covering what needs
  doing, why it matters, and what a completed state looks like — written as
  prose, not as named sections. Only use structured headers (e.g. "Acceptance
  criteria") for Tier 3 items where the complexity genuinely warrants them.
- **Professional initiative/epic (Tier 3):** Full context including stakeholders,
  success metrics, and known constraints. Structured sections are appropriate here.

If key parts are missing, suggest additions in plain language that fits the
context. Confirm before adding anything.

### Labels / Tags

Propose labels that will help find the item later. Calibrate to context:

- **Personal:** Simple tags like "travel", "home", "health", "finance"
- **Professional:** Domain ("auth", "billing"), type ("bug", "feature",
  "tech-debt"), and specifics ("mobile", "ios", "android") — prefer specific
  over generic when both apply

Always present suggested labels and ask for confirmation. Never add without
approval.

### Assignee

If unassigned and the item is active, ask who should own it. For personal
boards where the user is the only member, skip this.

### Due Date

If no due date is set and the item is active (not backlog/icebox), ask whether
there is a target date. Do not invent a date.

### Priority (Professional items only)

If not set, suggest a priority based on the description, labels, and any
blocking relationships. Confirm before applying. Skip for personal tasks —
priority on a personal board is usually managed by list position.

### Effort / Story Points (Tier 3 professional items only)

If the project uses estimation and the item is unestimated, ask for an estimate
or suggest one based on comparable items. Confirm before applying.

---

## Step 5: Gather Context from Existing Links

Before searching for new content, extract and follow every URL already embedded
in the item — description, comments, attachments, and web links. These are the
most direct source of context and should inform every suggestion you make
downstream (title rewrites, description drafts, label choices, status comments).

### 5a. Extract URLs

Collect all URLs from:
- Description body (inline links, bare URLs, and Markdown links)
- Each comment
- Attachments list
- Remote/web links already attached to the item

### 5b. Fetch each URL

For each URL, attempt access in this order:

1. **WebFetch first** — try a plain HTTP fetch. If it returns useful content,
   read it and move on.
2. **MCP fallback** — if WebFetch fails or returns an auth/login wall, use the
   appropriate authenticated tool based on the URL domain:

| Domain | Tool |
|---|---|
| `*.atlassian.net/wiki` / Confluence | `getConfluencePage` (Atlassian MCP) |
| `*.atlassian.net/browse` / Jira | `getJiraIssue` (Atlassian MCP) |
| `docs.google.com` / `drive.google.com` | `read_file_content` or `download_file_content` (Google Drive MCP) |
| `github.com/*/pull/*` | `gh pr view <url>` |
| `github.com/*/issues/*` | `gh issue view <url>` |
| `app.slack.com` / Slack message links | `slack_read_thread` or `slack_read_channel` (Slack MCP) |
| `mail.google.com` / Gmail | `get_thread` (Gmail MCP) |

If no MCP is available for a domain and WebFetch fails, note the URL as
unresolved and flag it for the user.

### 5c. Check local references directories

Look for a `references/` directory in two locations:

```bash
ls ./references/    # project root (current working directory)
ls ~/references/    # home directory
```

If either exists, scan the filenames for anything relevant to the item being
triaged — matching the domain, component, team, or keywords from the title and
description. Read any relevant files and carry their content forward as
background context, the same way you would use content fetched from a URL.

Common things to look for: glossaries, naming conventions, architecture notes,
team ownership docs, workflow guides, decision records, or any domain reference
that would inform your suggestions.

### 5d. Use what you find

Integrate all gathered context — from URLs and local references — into your
triage. Specifically:

- Use it to improve the title rewrite (does the linked doc name the real outcome?)
- Use it to fill description gaps (does a linked spec answer what/why/done?)
- Use it to suggest labels (does a linked PR or reference doc name a component or team?)
- Use it to draft a status comment (does a linked PR or doc show recent progress?)
- Note any context that changes your read of the item's priority or staleness

---

## Step 6: Search for Additional External Content

For **Tier 2 and Tier 3** items, also search for relevant content not yet
linked. Skip for Tier 1 personal tasks.

**Search in this order:**

1. **Slack** — conversations mentioning the item title, issue key, or key terms
2. **GitHub** — PRs, issues, or commits that reference the item
   ```bash
   gh search prs "KEYWORD or issue key" --state all --limit 10
   ```
3. **Google Drive / Docs** — documents matching the item or linked from its description
4. **Email / Gmail** — threads related to the item title or key
5. **Confluence / wiki** — pages that reference the item (use `search-confluence` skill)

For every item found, propose adding it as a link. Confirm before adding.

---

## Step 7: Staleness Check

Calculate the number of days since the last activity (comment, field update,
status change). Items in a "Done" or equivalent closed status are exempt.

| Age with no activity | Action |
|---|---|
| 3–7 days | Note it; no action required |
| 8–21 days | Ask: "No updates in N days — want me to draft a status comment?" |
| 22+ days | Ask the same; if no clear progress, also offer the stall interview (Step 7b) |

### Step 7a: Draft a Status Comment

Search recent activity on the item and any linked content (PRs, docs, Slack)
to find what has actually happened. Draft a comment that:

- States current status factually
- Notes any blockers or dependencies
- Proposes a specific next action

Show the full draft and get explicit approval before posting.

Use the best available tool to post the comment (MCP → skill → CLI → REST),
following the same hierarchy as Step 1. For Jira, if posting via REST, use
ADF format (not plain text):

```bash
curl -s -X POST \
  -u "${ATLASSIAN_USER_EMAIL}:${ATLASSIAN_USER_API_KEY}" \
  -H "Content-Type: application/json" \
  "https://YOUR-SITE.atlassian.net/rest/api/3/issue/{key}/comment" \
  -d '{"body": <ADF doc>}'
```

---

## Step 7b: Stall Interview (30+ Days, No Progress)

If an item has been open for more than 30 days with no meaningful progress,
and the user wants to unblock it, initiate a structured interview using the
`conduct-interview` skill. The goal is one immediately actionable next step.

Frame the interview around:

1. What was the original intent of this item?
2. What has been tried? What was the result?
3. What is blocking progress right now?
4. Can this be broken into smaller pieces? What would the first piece be?
5. Is this still valuable, or should it be closed/deferred?

Apply LEAN thinking: if the item has no owner, no recent interest, and no
dependency, closing or deferring it is often the right answer.

After the interview, produce:

- A rewritten title if needed
- Child tasks or subtasks for each phase
- A recommended status or list assignment for the parent
- A comment summarizing the review

Confirm all changes before applying.

---

## Step 8: Present Proposed Changes and Apply

Collect all proposals into a single summary. Present it once, then ask for
confirmation. Do not present the same change in multiple places.

```
Proposed changes for [ITEM TITLE] ([KEY or URL]):

Title:        [old] → [new]
Description:  [what you'd add or change]
Labels:       add [x, y]; remove [z]
Assignee:     [name]
Due date:     [date]
Priority:     [value]
Links:        add "[item title]" ([source])
Comment:      [preview]
Sub-tasks:    [list]
```

Ask: "Shall I apply these?" Wait for an affirmative before writing anything.

Apply in this order:

1. Title / summary
2. Description additions
3. Labels, priority, assignee, due date
4. Issue links and web links
5. Child tasks / subtasks
6. Status comment

After applying, re-fetch the item and confirm the changes landed.

---

## Methodology Notes

**GTD** — Every item needs a clear next action. If you cannot state one, the
item is not ready to be in an active status. Pull it back to inbox/backlog.

**Kanban** — An item in an active column with no assignee, no due date, and no
recent activity is unmanaged WIP. Assign it and move it forward, or pull it out
of the active flow.

**LEAN** — Don't create more structure than the work justifies. A two-minute
task does not need a scope document. Impose just enough process to keep things
moving, and no more.

---

## Quality Rules

- Never apply a change without explicit user confirmation.
- Never invent facts, dates, names, or descriptions. Ask if unknown.
- Always show the full draft of any comment before posting.
- Preserve the user's voice in any drafted text.
- One question at a time during the stall interview.
- Propose each change once — in the final Step 7 summary, not earlier.
- If scope is ambiguous, stop and ask before proceeding.

---

## References

- [Trello REST API](https://developer.atlassian.com/cloud/trello/rest/)
- [Jira REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
