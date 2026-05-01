---
name: review-code
description: Reviews local code or a pull request against repository-specific guidelines. Loads CONTRIBUTING.md as the primary standard, supplements with AGENTS.md and any tool-specific instruction files found in the repo. For PRs, auto-detects the open PR, reviews the actual diff, and can post a native GitHub review with inline comments. Use when asked to review a PR, review code changes, or do a code review.
---

# Code Review

Reviews code against repository-specific guidelines with the thoroughness of an experienced software tester.

## Step 1: Ask the user

Before doing anything, ask:

> "Would you like to review your **local code** or a **pull request**?"

**If PR:** check for an open PR on the current branch:
```bash
gh pr view --json number,title,url 2>/dev/null
```
If one is found, ask: "I found PR #N: _title_. Review that, or a different one?"

Then ask: "Should I **post the review directly to GitHub** (native PR review with inline comments) or **display it here as text**?"

## Step 2: Load guidelines

**Primary** — read the first one found:
- `CONTRIBUTING.md`
- `CONTRIBUTING.rst`
- `docs/CONTRIBUTING.md`
- `.github/CONTRIBUTING.md`

**Neutral AI instructions** — read if found:
- `AGENTS.md`

**Tool-specific** — scan and read any that exist:
- `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursorrules`, `.cursor/rules/*.mdc` (use Glob), `.windsurfrules`, `.clinerules`, `DEVIN.md`

Track which sources were loaded — include them in the output.

If nothing is found, skip the review and emit the **no-guidelines output** from Step 5.

## Step 3: Get the code to review

**Local mode:** Read files from disk with `Read`, `Glob`, `Grep`.

**PR mode:** Do NOT assume local files match the PR. Get the diff and metadata:
```bash
gh pr diff <number>
gh pr view <number> --json title,body,headRefName,baseRefName,author,additions,deletions,changedFiles,commits,headRefOid
```
Read each changed file in full using `Read`. If the local file does not match the PR's head (e.g. a different branch is checked out), fetch from the PR's head ref:
```bash
gh api repos/{owner}/{repo}/contents/{path}?ref={headRefOid} --jq '.content' | base64 -d
```

## Step 4: Review

**Thoroughness over speed.** Read every changed file in full — do not rely solely on the diff. Trace logic across the codebase: follow function calls, check callers, examine related files not in the diff but affected by the changes.

Question every implementation decision with a tester's mindset:
- What assumptions does this code make? Are they documented or enforced?
- What happens at boundary conditions — empty input, nulls, max values, concurrent access?
- How does it behave in failure modes — network failures, slow DB, unexpected upstream data?
- Is the happy path tested? Are the unhappy paths tested?
- Does the change introduce or leave open any security surface (input validation, auth checks, data exposure)?
- Are there race conditions, missing locks, or shared mutable state?
- Is the abstraction right — is this code doing too much or too little?

Use `Grep` to understand how changed code is used elsewhere before deciding whether to flag something.

Assign a risk score 0–100 based on the most serious issue found:

| Score | Risk | Meaning |
|-------|------|---------|
| 0–19 | 🟢 None | No issues |
| 20–39 | 🟢 Low | Minor style or convention issues |
| 40–59 | 🟡 Medium | Missing best practices, incomplete work |
| 60–79 | 🔴 High | Correctness concerns, unsafe patterns |
| 80–100 | 🔴 Critical | Will break in production, security vulnerabilities |

## Step 5: Output

### Text output

Use this format for local reviews and for PRs when the user chose text output:

```
=== Code Review ===

Repository:    owner/repo
Branch:        feature/my-changes        (PR mode only)
PR:            #42 — My PR title         (PR mode only)
Guidelines:    CONTRIBUTING.md, AGENTS.md
Risk Score:    35/100 🟡 Medium

=== Issues ===

Found 3 issues

File: src/api.ts
---
Line:          42
Risk:          🔴 High (60)
Issue:
| Missing null check before accessing user.id. This will throw a TypeError
| if user is undefined — possible when the session expires mid-request.
| Suggestion: const id = user?.id ?? throwError('No user in session')

File: src/service.ts
---
Risk:          🟡 Medium (40)
Issue:
| Error handling is missing from the catch block per CONTRIBUTING.md §4.
| Silently swallowing errors here makes failures invisible in production.

PR Level
---
Risk:          🟢 Low (0)
Note:
| Guidelines loaded: CONTRIBUTING.md, AGENTS.md

=== Summary ===

Risk Score:    35/100
Issues:        3
  🔴 High:     1
  🟡 Medium:   1
  🟢 Low:      1
```

Wrap issue text at ~80 characters and prefix each line with `| ` (matching the sonar script style). Risk emoji: 🔴 for score ≥ 60, 🟡 for 40–59, 🟢 for < 40.

### GitHub PR review

**Requires explicit user confirmation before posting.**

Construct the review body and post using the GitHub API:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews \
  --method POST \
  --input - <<'EOF'
{
  "body": "overall summary comment",
  "event": "COMMENT",
  "comments": [
    {
      "path": "src/api.ts",
      "line": 42,
      "side": "RIGHT",
      "body": "comment text"
    }
  ]
}
EOF
```

- Use `event=COMMENT` for informational reviews, `event=REQUEST_CHANGES` if the PR should not merge as-is
- `side=RIGHT` for comments on new/changed lines (the usual case)
- For multi-line comments add `start_line` alongside `line`
- Only post inline comments on lines present in the PR diff — PR-level observations go in `body` only
- After posting, output the review URL

### No guidelines found

```
=== Code Review ===

No review guidelines found in this repository.

To enable guided code review, add a CONTRIBUTING.md with your team's coding
standards and review expectations. Optionally add an AGENTS.md for
AI-specific review instructions.
```

## Rules

- Always ask the user before starting (Step 1)
- In PR mode, verify you are reviewing the correct code using the PR diff — do not assume local state matches
- Require explicit user confirmation before posting to GitHub
- Do not use the `Write` tool
- Allowed tools: `Read`, `Glob`, `Grep`, `Bash` (for `gh` commands only)
