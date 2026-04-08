# Resolve SonarQube: detailed workflow

Supporting detail for [resolve-sonarqube-issues](../resolve-sonarqube-issues/SKILL.md). Use this for script usage, grouping rules, fix batches, commit/comment conventions, and the final report shape.

## Script: `list-sonar-issues.py`

- **Personal skills tree:** `scripts/list-sonar-issues.py` next to `SKILL.md` under `resolve-sonarqube-issues/`.
- **cpe-imre repo:** `skills/resolve-sonarqube-issues/scripts/list-sonar-issues.py` from the repository root.
- Or on `PATH` if installed elsewhere (e.g. `~/scripts`).
- Run with `--help` first to learn flags and output shape.
- Run with **no flags** to list Issues, Security Hotspots, Test Coverage, and Code Duplication for the current PR (or context the script resolves).
- **Cache** the output; a run can take a minute or more.
- If the script fails or returns an error, **stop** and report before editing code.

## Step 1: Report findings breakdown

Before making any fixes, present a findings summary:

- Total count of findings by category (Issues, Security Hotspots, Code Duplication, Test Coverage)
- Breakdown by severity within each category
- Note any patterns (e.g., "12 issues are the same lint rule in different files")

## Step 2: Create a grouping plan

Review all findings holistically and present a grouping plan:

- Which findings will be grouped into a single commit (same rule, same severity/type)
- The processing order, prioritized as:
  1. Security Hotspots (highest severity first)
  2. Issues (highest severity first)
  3. Code Duplication
  4. Test Coverage
- For each group: how many items, the planned fix approach, and whether any appear invalid

Present this plan before starting fixes.

## Step 3: Fix or comment on each group

Work through each group following this workflow:

1. Review the issue(s) and confirm whether they are valid.

2. If the issue(s) are valid:
   - Fix the issue(s) in the code.
   - Group similar issues into a single commit when appropriate.
   - The commit message should include:
     - A clear description of what was fixed.
     - The SonarQube issue type, message, and severity.
     - The SonarQube issue URL(s).

3. If an issue is not valid:
   - Add a code comment explaining why it is not valid.
   - Include the SonarQube issue type, severity, and URL in the comment.
   - Do not suppress the issue without approval.
   - Suppressing SonarQube items requires user approval. Propose why suppression is appropriate and wait for confirmation before proceeding.

After processing each group, output a brief summary of what was done (issues fixed, issues marked invalid, commit SHA if applicable) before moving to the next group.

## Step 4: Final report

After fixing all valid issues, provide a structured summary:

1. **Fixed**: Count and list of issues fixed, with commit SHAs
2. **Invalid/Suppressed**: Count and list of issues marked invalid, with reasons
3. **Unresolved**: Any issues that could not be addressed, with the reason
4. **Statistics**: Total findings, total fixed, total invalid, total unresolved

### Verification caveat

Re-running `list-sonar-issues.py` on the same PR to confirm resolution often does **not** reflect fixes immediately; SonarQube analysis updates after commits are pushed and processed. Plan verification accordingly (e.g., follow-up CI, or a later re-run).
