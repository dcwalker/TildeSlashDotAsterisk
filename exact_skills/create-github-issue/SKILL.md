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

Before creating an issue, review the following project documentation if available:
- AGENTS.md - Project-specific guidance for AI agents
- CONTRIBUTING.md - Contribution guidelines and standards
- ISSUE_TEMPLATE.md / `.github/ISSUE_TEMPLATE/*` - Preferred issue format
- ISSUE_REPORTING_GUIDELINES.md (or similar) - Reporting expectations

These documents provide important context about required issue details and formatting.

### Step 2: Verify Authentication

Check if `gh` is authenticated:

```bash
gh auth status
```

If not authenticated, prompt the user to authenticate first:

```bash
gh auth login
```

### Step 3: Gather Required Information

The following fields are required to create an issue. If any are missing, stop and ask the user:

1. Repository (for example, `"owner/repo"` or use current repo)
2. Title

Optional but recommended:
- Body/description (Markdown supported)
- Labels (comma-separated)
- Assignees (comma-separated GitHub usernames)
- Milestone
- Project

### Step 4: Build Issue Body Draft

Read and apply the repository issue guidance before drafting:
- `ISSUE_REPORTING_GUIDELINES.md` (or linked equivalent)
- `.github/ISSUE_TEMPLATE/*` if present

Then create a concise Markdown draft in `/tmp/github-issue-body.md` that matches the required sections for the specific issue type (bug, enhancement, task, etc.), without copying full guideline text into the issue.

Example command:

```bash
cat > /tmp/github-issue-body.md <<'EOF'
[Issue body draft aligned to repository guidelines]
EOF
```

### Step 5: Present Draft to User

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

Important:
- Present the issue body as readable Markdown text, not just a file path.
- Do not create the issue until explicit approval is received.

Ask the user: "Would you like to proceed with creating this issue? (yes/no)"

If the user requests changes, update the draft and present again.

If anything in the description or requirements is unclear, stop and ask for clarification before proceeding.

### Step 6: Create the Issue

Once approved, create the issue with `gh issue create`:

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

Capture the output URL (for example, `https://github.com/owner/repo/issues/123`).

### Step 7: Share the Result

Share the created issue as a clickable link:

```
Issue created successfully: [#123](https://github.com/owner/repo/issues/123)
```

If possible, include both issue number and URL.

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

## Important Notes

- Always validate required information before attempting to create the issue
- Always show a draft and get explicit approval before creating
- If issue details are ambiguous, stop and ask for clarification
- Keep temporary files in `/tmp` (or user-specified location)
- Clean up temporary files after successful creation when practical
- If no repository is provided, infer from local git remote and confirm with the user

## Related Documentation

- GitHub CLI auth: https://cli.github.com/manual/gh_auth_status
- GitHub CLI issue create: https://cli.github.com/manual/gh_issue_create
- Issue reporting guidelines: https://github.com/dcwalker/personal-ai-and-coding-standards/blob/main/ISSUE_REPORTING_GUIDELINES.md
