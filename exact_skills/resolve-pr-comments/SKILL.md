---
name: resolve-pr-comments
description: Review and address all unresolved GitHub PR comments for the current branch. Fixes issues, responds to comments, and resolves them appropriately. Use when the user wants to handle PR feedback or resolve PR comments.
---

# Resolve PR Comments

Review and systematically address all unresolved GitHub PR comments for the current branch's pull request. For each comment, either fix the issue, acknowledge it was already fixed, or explain why it's not valid.

## When to Use

Use this skill when:
- The user wants to address or resolve PR comments
- There is feedback on a pull request that needs handling
- You need to respond to code review comments
- The user mentions PR feedback, comments, or reviews

## Execution Rules

After processing each comment, output a **Comment Summary** before moving to the next:

> **Comment [ID] — [brief description]**
> - **Action taken**: [Fixed / Already fixed / Invalid — with brief explanation]
> - **Commit**: [SHA if applicable, or "N/A"]
> - **Reply**: [What was posted as the reply]

After all comments are processed, output a **Final Report** (see below).

## Instructions

Please start by reviewing the AGENTS.md and CONTRIBUTING.md files for project conventions.

This skill uses the `list-pr-comments.sh` script. It lives at:

```
~/.cursor/skills/resolve-pr-comments/scripts/list-pr-comments.sh
```

It is also available in your PATH as `list-pr-comments.sh`. Use the PATH form for all commands below.

Review the script's help content first:

```bash
list-pr-comments.sh --help
```

Then, use the script to fetch and review all unresolved GitHub PR comments for this branch's PR:

```bash
list-pr-comments.sh
```

Before processing, list all unresolved comments with a brief summary of each and your planned action (fix, already fixed, or invalid). Then process each comment following the appropriate workflow below:

### Workflow 1: Valid Comment Requiring a Fix

If the comment identifies a valid issue that needs to be addressed:

1. Fix the issue in the code.

2. Commit the fix following project standards:
   - Create a comprehensive commit message that describes all high-level changes.
   - Include a link to the PR comment in the commit message body.
   - Do NOT use the `--no-verify` flag to bypass pre-commit hooks.
   - Follow the commit skill workflow for proper commit message formatting.

3. Note the short commit SHA from the commit.

4. Reply to the PR comment with "Addressed in [SHA]." using:
   ```bash
   list-pr-comments.sh --reply <comment-id> "Addressed in [SHA]."
   ```

5. Resolve the comment using:
   ```bash
   list-pr-comments.sh --resolve <comment-id>
   ```

### Workflow 2: Issue Already Fixed

If the issue was previously addressed:

1. Review the git history to identify when and how the issue was fixed.

2. Find the commit SHA where the fix was made.

3. Reply to the PR comment with "Addressed in [SHA]." using:
   ```bash
   list-pr-comments.sh --reply <comment-id> "Addressed in [SHA]."
   ```

4. Resolve the comment using:
   ```bash
   list-pr-comments.sh --resolve <comment-id>
   ```

### Workflow 3: Invalid or Not Applicable Comment

If the comment is not valid or not applicable:

1. Draft a brief, polite, and professional explanation of why the comment is not valid or applicable. This response will be public.

2. Reply to the PR comment with your explanation using:
   ```bash
   list-pr-comments.sh --reply <comment-id> "Your explanation here"
   ```

3. Resolve the comment using:
   ```bash
   list-pr-comments.sh --resolve <comment-id>
   ```

## Final Report

After processing all comments, provide a structured summary:

1. **Comments processed**: Total count
2. **Breakdown**: How many fixed, how many already fixed, how many marked invalid
3. **Commits created**: List each commit SHA with a brief description
4. **Unresolved**: Any comments that could not be addressed, with the reason

## Important Notes

- Always review the script help content first to understand current options and usage.
- Each fix should be a separate, well-documented commit unless multiple comments relate to the same logical change.
- Pre-commit hooks must not be bypassed unless explicitly approved by the user.
- All responses to PR comments are public and should be professional and constructive.
- Group related fixes into a single commit when appropriate, but ensure the commit message references all relevant PR comments.
