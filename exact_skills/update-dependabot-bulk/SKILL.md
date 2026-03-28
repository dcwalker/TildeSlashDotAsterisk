---
name: update-dependabot-bulk
description: Process multiple open Dependabot PRs by creating a bulk update to package.json that supersedes individual PRs. Use when the user wants to batch update dependencies or handle multiple Dependabot PRs at once.
---

# Update Dependabot Bulk

Process multiple open Dependabot PRs by creating a bulk update to package.json that supersedes individual PRs, which is faster than approving and merging each PR individually.

## When to Use

Use this skill when the user wants to:
- Handle multiple open Dependabot PRs at once
- Batch update dependencies
- Consolidate dependency updates into a single commit

## Instructions

Please start by reviewing the AGENTS.md and CONTRIBUTING.md files.

**Finding the script:** Look for `list-dependabot-prs.sh` in the repository (for example under `scripts/` or the project root). If it is not present in the repo, try running it by name (e.g. `list-dependabot-prs.sh`) in case it is installed on the user's PATH. Do not assume a fixed path; paths vary by environment.

Once located, run the script with `--help` to understand how it works (e.g. `scripts/list-dependabot-prs.sh --help` or `list-dependabot-prs.sh --help`).

Next, run the script with no options to list all of the open PRs in this repo from Dependabot.

If the script cannot be found or returns an error, stop and report the issue before proceeding.

If there are no open Dependabot PRs, report that to the user.

Review the Dependabot PRs and follow this workflow:

1. For each Dependabot PR, identify what needs to be updated (see CONTRIBUTING.md "Dependencies" for how to handle direct vs transitive updates):
   - If the PR updates a direct dependency (listed in package.json), note the package name and target version.
   - If the PR updates an indirect dependency (transitive dependency not in package.json), identify which direct dependency in package.json needs to be updated to bring in the newer transitive version.

2. Group all updates and create a plan:
   - List all package.json files that need updates.
   - List all direct dependencies to be updated with their current and target versions.
   - For transitive dependency updates, show the chain: which Dependabot PR, which transitive dependency, which direct dependency needs updating, and how you determined this (e.g., output of `npm ls <package>` or `yarn why <package>`).
   - Present the plan to the user for review. **Do not proceed to step 3 until the user explicitly approves the plan.**

3. After plan approval, update the package.json file(s):
   - Update each direct dependency to the appropriate version; do not add new direct dependencies.
   - The goal is to create a bulk update that supersedes multiple individual Dependabot PRs, which is faster than approving and merging each PR individually.

4. Run `yarn install` (or the appropriate package manager command) to update the lock file.

5. Verify the updates:
   - Run tests and linters to ensure the updates don't break anything.
   - If there are breaking changes or test failures, report them and ask how to proceed.

6. Commit the changes. Follow the commit workflow in the commit skill, ensuring the commit message includes all Dependabot PR numbers/titles that will be resolved.

7. **Final report**: After committing, provide a structured summary:
   - **Updated**: List each dependency updated with old version, new version, and which Dependabot PR(s) it supersedes
   - **Test/lint results**: Whether all checks passed, and any failures encountered
   - **Superseded PRs**: Full list of Dependabot PR numbers that can now be closed
   - **Issues**: Any problems encountered or dependencies that could not be updated

## Example Scenario

- Dependabot PR updates `lodash` from 4.17.20 to 4.17.21 (direct dependency) → Update `lodash` in package.json
- Dependabot PR updates `@types/node` from 16.0.0 to 16.1.0 (dependency of `typescript`) → Update `typescript` in package.json to a version that requires the newer `@types/node`
