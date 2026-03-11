---
name: resolve-sonarqube-issues
description: Review and resolve SonarQube findings including Issues, Security Hotspots, Test Coverage, and Code Duplication. Use when the user wants to address SonarQube findings or improve code quality metrics.
---

# Resolve SonarQube Issues

Review and systematically resolve SonarQube findings including Issues, Security Hotspots, Test Coverage, and Code Duplication for the current PR.

## When to Use

Use this skill when:

- The user wants to address SonarQube findings
- You need to fix code quality issues
- There are security hotspots to review
- Test coverage or code duplication needs attention

## Instructions

Please start by reviewing the AGENTS.md and CONTRIBUTING.md files in the project (if present). Then run the list-sonar-issues.py script with the `--help` option to understand how the script works. The script is at `scripts/list-sonar-issues.py` relative to this skill's directory (e.g. ~/.cursor/skills/resolve-sonarqube-issues/scripts/list-sonar-issues.py), or may be on PATH if installed to ~/scripts.

Next, run the list-sonar-issues.py script with no flags to show the Issues, Security Hotspots, Test Coverage, and Code Duplication for this PR. Cache the results of the script because it can sometimes take a minute or more to run.

If the script fails or returns an error, stop and report the issue before proceeding.

### Step 1: Report findings breakdown

Before making any fixes, present a findings summary:
- Total count of findings by category (Issues, Security Hotspots, Code Duplication, Test Coverage)
- Breakdown by severity within each category
- Note any patterns (e.g., "12 issues are the same lint rule in different files")

### Step 2: Create a grouping plan

Review all findings holistically and present a grouping plan:
- Which findings will be grouped into a single commit (same rule, same severity/type)
- The processing order, prioritized as:
  1. Security Hotspots (highest severity first)
  2. Issues (highest severity first)
  3. Code Duplication
  4. Test Coverage
- For each group: how many items, the planned fix approach, and whether any appear invalid

Present this plan before starting fixes.

### Step 3: Fix or comment on each group

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

### Step 4: Final report

After fixing all valid issues, provide a structured summary:
1. **Fixed**: Count and list of issues fixed, with commit SHAs
2. **Invalid/Suppressed**: Count and list of issues marked invalid, with reasons
3. **Unresolved**: Any issues that could not be addressed, with the reason
4. **Statistics**: Total findings, total fixed, total invalid, total unresolved

Re-running the list-sonar-issues.py script to verify that the issues have been resolved will not work, as the items won't be updated until the fixes are committed and pushed.
