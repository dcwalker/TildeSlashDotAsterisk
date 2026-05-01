---
name: create-github-issue
description: Create a GitHub issue using the GitHub CLI (gh) with a clear, reviewable draft workflow. Use when the user wants to create, file, or submit a GitHub issue.
---

# Create GitHub Issue

Create a GitHub issue using the GitHub CLI (`gh`) with a draft-and-approve workflow before submission.

## When to Use

Use this skill when:
- The user wants to create a new GitHub issue
- The user asks to file, create, or submit an issue on GitHub
- The user wants help drafting an issue with structured content
- The user wants to use the `gh` command line tool for issue creation

## Prerequisites

This skill requires:
- GitHub CLI (`gh`) installed
- `gh` authenticated for the target host/account
- Target repository known (or discoverable from current git remote)

## Instructions

### Step 1: Review Project Documentation

Before creating an issue, read the following if available:
- `AGENTS.md` — Project-specific guidance for AI agents
- `CONTRIBUTING.md` — Contribution guidelines and standards
- `.github/ISSUE_TEMPLATE/*` or `ISSUE_TEMPLATE.md` — Preferred issue format
- `ISSUE_REPORTING_GUIDELINES.md` (or similar) — Reporting expectations
- `docs/glossary.md` — Project terminology and definitions

#### Glossary from docs/glossary.md

If `docs/glossary.md` exists, read it before drafting any field values.

Use glossary terms and definitions when:
- Writing the issue title or body
- Selecting labels, milestones, or projects where a glossary term maps to an option
- Describing steps to reproduce, expected behavior, or acceptance criteria

Prefer exact glossary terms over synonyms or informal language when they apply to the issue being filed.

### Step 2: Verify Authentication

```bash
gh auth status
```

If not authenticated, prompt the user to authenticate first:

```bash
gh auth login
```

### Step 3: Discover Available Values

Before prompting the user for field values, discover what is available in the target repository:

```bash
# Labels
gh label list --repo "OWNER/REPO" --limit 100

# Milestones
gh milestone list --repo "OWNER/REPO"

# Projects
gh project list --owner "OWNER"
```

Also fetch recent similar issues for context and to inform suggested values:

```bash
gh issue list --repo "OWNER/REPO" --limit 10 --state all --json title,labels,milestone,assignees,body
```

Use this context to form suggested values for each field.

### Step 4: Gather and Suggest Field Values

Prompt the user for a value for every available field. For each field:

1. Use the discovered values (labels, milestones, projects) and recent issues to form a suggested value.
2. Present the suggestion and ask for confirmation or a correction.
3. For fields with a fixed set of allowed values (labels, milestones), always display the options. Never suggest a value not in the list.
4. Group fields into a single prompt where possible to reduce back-and-forth — present all optional fields together with suggested values and ask the user to confirm, change, or skip each one.
5. The only exception is when you are highly confident a value is correct and unambiguous (for example, the repository when it is clear from the git remote). In that case, state the value you will use and give the user a chance to object before proceeding.

Required:
1. Repository (infer from git remote and confirm, or ask)
2. Title

Optional but recommended:
- Body/description
- Labels
- Assignees
- Milestone
- Project

### Step 5: Build Issue Body Draft

Apply the repository issue guidance from Step 1 when drafting:
- Match the structure from `.github/ISSUE_TEMPLATE/*` if present
- Use exact terms from `docs/glossary.md` where applicable

Write the draft to `/tmp/github-issue-body.md`:

```bash
cat > /tmp/github-issue-body.md <<'EOF'
[Issue body draft aligned to repository guidelines]
EOF
```

### Step 6: Present Draft to User

Before creating the issue, present a clear summary:

```
GitHub Issue Draft:
- Repository: [OWNER/REPO]
- Labels: [LABELS or "None"]
- Assignees: [ASSIGNEES or "None"]
- Milestone: [MILESTONE or "None"]
- Project: [PROJECT or "None"]

Title:
[TITLE]

Body:
[RENDERED_MARKDOWN_BODY]
```

- Present the body as readable Markdown text, not a file path.
- Do not create the issue until explicit approval is received.

Ask: "Would you like to proceed with creating this issue? (yes/no)"

If the user requests changes, update the draft and present again. If anything is unclear, stop and ask before proceeding.

### Step 7: Create the Issue

Once approved:

```bash
gh issue create \
  --repo "OWNER/REPO" \
  --title "ISSUE TITLE" \
  --body-file "/tmp/github-issue-body.md"
```

Add optional flags only when provided:
- `--label "bug"` (repeat for multiple labels)
- `--assignee "username"` (repeat for multiple assignees)
- `--milestone "MILESTONE"`
- `--project "PROJECT"`

### Step 8: Share the Result

Share the created issue as a clickable link:

```
Issue created: [#123](https://github.com/owner/repo/issues/123)
```

Clean up `/tmp/github-issue-body.md` after successful creation.

## Error Handling

If issue creation fails:
1. Check the `gh` error message
2. Common issues:
   - Authentication expired or insufficient scopes
   - Missing repository access permissions
   - Invalid label, assignee, milestone, or project name
   - Repository does not exist or was mistyped
3. Display the error to the user and suggest corrective action
4. Offer to retry after fixing the issue

## Related Documentation

- GitHub CLI auth: https://cli.github.com/manual/gh_auth_status
- GitHub CLI issue create: https://cli.github.com/manual/gh_issue_create
- Issue reporting guidelines: https://github.com/dcwalker/personal-ai-and-coding-standards/blob/main/ISSUE_REPORTING_GUIDELINES.md
