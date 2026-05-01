---
name: pr
description: Create or update GitHub pull requests following team standards. Creates new PRs as drafts, links related tickets, checks assignment, and writes concise descriptions readable in under a minute. Use when the user asks to create a PR, open a pull request, update a PR, or submit changes for review.
---

# Manage PR

Creates or updates GitHub pull requests via `gh pr create` or `gh pr edit`.

## Creating a PR

### 1. Gather context

Before writing the description:

- Run `git log origin/HEAD..HEAD --oneline` to list commits on this branch.
- Check for a linked Jira or GitHub issue. Look in: branch name, commit messages, and any context the user provided.
- Run `gh pr view --json assignees,isDraft 2>/dev/null` to check if a PR already exists for this branch.
- Check for a PR template at `.github/pull_request_template.md` (also check `.github/PULL_REQUEST_TEMPLATE.md`).

**If a PR template is found:**
- If it is short (under ~30 lines), show the full template to the user.
- If it is long (30+ lines), summarize its sections briefly.
- Ask: "A PR template was found. Do you want to use it as the base for the description?"
  - If yes: use the template structure, filling in the relevant sections. Keep the final result scannable in under one minute.
  - If no: proceed with the standard description template below.

### 2. Confirm assignment

If no assignee is set, ask: "Should I assign this PR to you?"

- If yes: pass `--assignee @me` when creating.
- If no: omit the flag.

### 3. Write the description

Use the template below. Omit the `tl;dr` section if the description body is short (3 or fewer bullet points).

```
[tl;dr: one sentence summary — omit if body is short]

**Value**: [one sentence — what problem this solves or what benefit it delivers]

## Changes
- [brief note per logical change — keep each to one line]

## Related
- [Ticket title](URL)  ← include one line per ticket; omit section if none
```

**Description rules:**
- The full description must be readable in under one minute.
- Each change bullet is one line — no sub-bullets, no paragraphs.
- Ticket links must be full hyperlinks, not bare IDs. Include all related tickets.
- The value statement answers "why does this matter?" not "what does this do?"

### 4. Create the PR as a draft

```bash
gh pr create \
  --draft \
  --title "<title>" \
  --body "<description>" \
  [--assignee @me]
```

Always use `--draft`. Never create a PR in ready-for-review state.

---

## Updating a PR

### 1. Check current state

```bash
gh pr view --json isDraft,title,body,assignees
```

### 2. Confirm state is still correct

Ask: "This PR is currently a **[draft / ready for review]**. Is that still correct?"

- If the user wants to mark it ready: `gh pr ready`
- If the user wants to convert back to draft: `gh pr convert-to-draft`
- If unchanged: proceed without modification.

### 3. Check assignment

If `assignees` is empty, ask: "This PR has no assignee. Should I assign it to you?"

- If yes: `gh pr edit --add-assignee @me`

### 4. Review the title

Compare the existing title against the updated description. Ask: "The current title is: **[title]**. Does this still accurately describe the change, or should it be updated?"

- If the user confirms it is accurate: keep it.
- If the user provides a new title: use that.
- If the title is clearly stale based on the description content: propose a replacement and ask for approval before applying.

### 5. Apply edits

```bash
gh pr edit \
  --title "<updated title>" \
  --body "<updated description>"
```

Re-apply the same description rules from the creation workflow.

---

## Checklist

Before finishing, confirm:

- [ ] PR was created as draft (or state was explicitly confirmed on update)
- [ ] Title was reviewed and confirmed accurate against the description
- [ ] Assignee was set or user explicitly declined
- [ ] All related tickets are linked as hyperlinks in the description
- [ ] Description has a value statement
- [ ] Description reads in under one minute
- [ ] tl;dr is present if the description is more than 3 bullet points
