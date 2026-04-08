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

## Core Rule: Never Pin Transitive Dependencies Directly

This is the single most important constraint. Do not add transitive packages as direct dependencies in `dependencies`, `devDependencies`, or `resolutions`. The only correct approach is to update the direct dependency that brings in the transitive package, to a version that naturally resolves to the target transitive version.

Adding a transitive package directly will:
- Cause `knip` and similar unused-dependency checks to fail
- Bloat the package surface area
- Not reliably override all copies in the dependency tree

## Instructions

Please start by reviewing the AGENTS.md and CONTRIBUTING.md files.

**Finding the script:** Look for `list-dependabot-prs.sh` in the repository (for example under `scripts/` or the project root). If it is not present in the repo, try running it by name (e.g. `list-dependabot-prs.sh`) in case it is installed on the user's PATH. Do not assume a fixed path; paths vary by environment.

Once located, run the script with `--help` to understand how it works (e.g. `scripts/list-dependabot-prs.sh --help` or `list-dependabot-prs.sh --help`).

Next, run the script with no options to list all of the open PRs in this repo from Dependabot.

If the script cannot be found or returns an error, stop and report the issue before proceeding.

If there are no open Dependabot PRs, report that to the user.

Review the Dependabot PRs and follow this workflow:

### Step 1: Classify each Dependabot PR

For each PR, determine whether it targets a direct or transitive dependency.

**Direct dependency:** the package is already listed in a `package.json` in this repo. Update its version in `package.json`. This is straightforward.

**Transitive dependency:** the package is not listed in any `package.json` in this repo. It is pulled in as a dependency of a dependency. Do not add it to `package.json`. Instead, follow the transitive resolution process in Step 2.

### Step 2: Resolve transitive dependencies through their parent

For each transitive dependency PR:

1. Run `yarn why <package>` to find which direct dependency (or chain of dependencies) brings it in.

2. Identify the top-level direct dependency in the chain that is listed in this repo's `package.json`.

3. Check whether a newer version of that direct dependency already depends on the required (fixed) version of the transitive package:
   ```
   npm info <direct-package>@<newer-version> dependencies
   ```
   or inspect the changelog/release notes for the direct package.

4. If a newer version of the direct dependency resolves the transitive package to the target version or higher, update the direct dependency in `package.json` to that version. No other change is needed.

5. If the current plan already includes an update for that direct dependency, verify that the planned target version pulls in the correct transitive version before finalizing the plan.

6. If no available version of the direct dependency resolves the transitive package to the required version, note this as a limitation in the plan and flag it for the user.

### Step 3: Create and present a plan

Group all updates and create a plan before touching any files:

- List all `package.json` files that need updates.
- List all direct dependencies to be updated with their current and target versions.
- For each transitive dependency, show the full chain: Dependabot PR → transitive package → direct parent dependency → planned update. Include the `yarn why` output or `npm info` evidence that confirms the parent update will pull in the correct version.
- Flag any transitive dependencies that cannot be resolved through a parent update.

Present the plan to the user for review. Do not proceed to Step 4 until the user explicitly approves.

### Step 4: Apply the updates

Update each `package.json` as described in the approved plan:
- Change version strings for direct dependencies only.
- Do not add new entries for transitive packages under `dependencies`, `devDependencies`, or `resolutions`.

### Step 5: Update the lock file and verify

Run `yarn install` (or the appropriate package manager) to update the lock file.

After install, verify that the transitive dependency versions in the lock file match what was expected. For each transitive dependency in the plan, confirm the resolved version in `yarn.lock` by searching for the package entry.

If the lock file does not resolve a transitive dependency to the expected version after updating the parent, investigate why before continuing. Do not add the transitive package directly as a workaround.

### Step 6: Run tests and linters

Run tests and linters to ensure the updates do not break anything. If the project uses `knip` or a similar unused-dependency check, run it as well.

If there are failures, report them and ask how to proceed. Do not bypass pre-commit hooks.

### Step 7: Commit

Follow the commit skill workflow. The commit message should reference all Dependabot PR numbers and titles that this bulk update supersedes.

### Step 8: Final report

After committing, provide a structured summary:
- Updated: each dependency updated with old version, new version, and which Dependabot PR(s) it supersedes
- Transitive resolutions: each transitive package, which parent was updated, and the resolved version confirmed in yarn.lock
- Test and lint results: whether all checks passed, and any failures encountered
- Superseded PRs: full list of Dependabot PR numbers that can now be closed
- Issues: any problems encountered or dependencies that could not be updated

## Example Scenario

Dependabot PR updates `flatted` from 3.3.3 to 3.4.2 (not in package.json):
- `yarn why flatted` shows: `eslint` → `file-entry-cache` → `flat-cache` → `flatted`
- `npm info eslint@10.0.3 dependencies` shows it still uses `flat-cache` which depends on `flatted@^3.2.9`
- `npm info flat-cache@latest dependencies` shows `flatted@^3.4.0`
- `eslint` is already being updated to `^10.0.3` in this bulk update
- After running `yarn install`, confirm `flatted@3.4.2` appears in `yarn.lock`
- No entry for `flatted` is added to `package.json`

Dependabot PR updates `lodash` from 4.17.20 to 4.17.21 (direct dependency):
- `lodash` is in `package.json`; update its version entry directly.
