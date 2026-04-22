---
name: fix-pr-checks
description: Identify failing PR checks using list-pr-checks.sh, fix the failures locally, and repeat until all checks pass. Use when preparing code for commit or PR.
---

# Fix PR Checks

Use `list-pr-checks.sh` to identify which PR checks are failing and why, then fix the failures locally and repeat until all checks pass.

## When to Use

- Use when you want to fix PR/CI check failures before pushing
- Use when you've made code changes and need to ensure they pass CI
- Use when preparing code for commit or pull request

## Instructions

### Phase 0: Read project conventions

Review AGENTS.md and CONTRIBUTING.md in the project root (if present). Note any rules about testing, linting, build processes, or CI that may affect how to fix failures.

### Phase 1: Check which checks are failing

This skill uses the `list-pr-checks.sh` script. It is available in your PATH as `list-pr-checks.sh`. Use the PATH form for all commands below.

Review the script's help content first:

```bash
list-pr-checks.sh --help
```

Then run it from the repository root to see every check's status and failure details:

```bash
list-pr-checks.sh
```

The script auto-detects the current branch's PR and prints each check with its status, description, and — for failing CI jobs — the full log output. Read the output carefully to identify:

- Which checks are failing (marked 🔴)
- The exact error message or log lines that explain why

If the PR does not exist yet or no checks have run, the script will say so. In that case, push the branch first and wait for checks to start before re-running.

### Phase 2: Fix each failure

Work through the failing checks one at a time. For each failure:

1. **Understand the error** from the log output the script provided. Do not read CI config files to figure out what failed — the script already tells you.

2. **Determine if it can be fixed locally**. Most failures (lint, format, type errors, test failures, coverage gaps) can be reproduced and fixed in the local environment. Skip checks that require CI-only infrastructure (e.g. a SonarQube quality gate that needs cloud secrets to upload) unless the failure is something you can fix in the code (e.g. insufficient test coverage reported by SonarQube).

3. **Reproduce the failure locally** using the relevant package manager script or tool (e.g. `npm run lint:eslint`, `npm run compile`, `npm run test:cov`, `prettier --check`). Derive the command from the error message and the project's `package.json` scripts — do not guess.

4. **Fix the issue** (edit code, tests, or config as appropriate). Prefer auto-fix when available (e.g. `eslint --fix`, `prettier --write`).

5. **Re-run the local check** to confirm the fix works before moving on.

### Phase 3: Push and verify

After fixing all locally-reproducible failures:

1. Commit and push the changes.
2. Run `list-pr-checks.sh` again once checks have completed to confirm everything is now green.
3. If new failures appear (e.g. a check that was previously passing now fails due to your fix), repeat Phase 2 for those.

### Phase 4: Report

- List which checks were fixed and how.
- Note any checks that were skipped and why (e.g. requires cloud secrets, infrastructure-only).
- If a failure cannot be fixed after three attempts, stop and ask the user for guidance.

## Important Notes

- Always use `list-pr-checks.sh` to find out what is failing. Do not infer failures by reading CI config files.
- Run local checks from the correct working directory (usually the package subdirectory, not the repo root, for monorepos).
- If the same failure persists after 3 fix attempts, stop and ask the user rather than looping.
- If the agent platform enforces an iteration or time limit, summarize progress so the user can re-invoke the skill to continue.

## Example flow (illustrative)

```
1. Run list-pr-checks.sh --help to review options.
2. Run list-pr-checks.sh → see SonarQube failing with "56.5% coverage on new code (required >= 80%)".
3. Identify which new source lines lack coverage from the SonarQube log.
4. Add tests locally, run npm run test:cov to confirm coverage improves.
5. Commit and push.
6. Run list-pr-checks.sh again → all checks green.
7. Report: fixed SonarQube coverage gate by adding 2 tests. All 21 checks passing.
```
