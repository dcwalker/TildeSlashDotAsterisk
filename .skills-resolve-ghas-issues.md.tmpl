---
name: resolve-ghas-issues
description: Review and resolve GitHub Advanced Security (GHAS) findings including Dependabot, code scanning, and secret scanning alerts. Use when the user wants to address GHAS findings or fix security alerts.
---

# Resolve GHAS Issues

Review and systematically resolve GitHub Advanced Security findings including Dependabot alerts, code scanning alerts, and secret scanning alerts for the current repository.

## When to Use

Use this skill when:

- The user wants to address GHAS or GitHub Advanced Security findings
- You need to fix Dependabot, code scanning, or secret scanning alerts
- The user asks to resolve security alerts from GitHub

## Instructions

Please start by reviewing the AGENTS.md and CONTRIBUTING.md files in the project (if present). Then run the list-ghas-issues.py script with the `--help` option to understand how the script works. The script is at `scripts/list-ghas-issues.py` relative to this skill's directory (e.g. ~/.cursor/skills/resolve-ghas-issues/scripts/list-ghas-issues.py), or on PATH if skill script dirs are on PATH.

Next, run the list-ghas-issues.py script with no flags to show all open GHAS alerts (Dependabot, code scanning, secret scanning) for this repo. Cache the results of the script because it can take a minute or more to run.

If the script fails or returns an error (e.g. missing GITHUB_TOKEN or gh auth), stop and report the issue before proceeding.

### Step 1: Report findings breakdown

Before making any fixes, present a findings summary:
- Total count of alerts by category (Secret scanning, Code scanning, Dependabot)
- Breakdown by severity within each category
- Note any patterns (e.g., "5 Dependabot alerts are all for the same transitive dependency")

### Step 2: Create a grouping plan

Review all findings holistically and present a grouping plan:
- Which alerts will be grouped into a single commit (same type, related dependencies)
- The processing order, prioritized as:
  1. Secret scanning alerts (exposed secrets; highest risk)
  2. Code scanning alerts (by severity: critical, high, then medium/low)
  3. Dependabot alerts (by severity, or by dependency if batching updates)
- For each group: how many items, the planned fix approach, and whether any appear invalid

Present this plan before starting fixes.

### Step 3: Fix or dismiss each group

Work through each group following this workflow:

1. Review the alert(s) and confirm whether they are valid and should be fixed.

2. If the alert(s) are valid:
   - Fix the issue(s) in the code or configuration (e.g. upgrade dependency, fix code that triggers a code scanning rule, rotate and remove an exposed secret).
   - Group similar fixes into a single commit when appropriate.
   - The commit message should include:
     - A clear description of what was fixed.
     - The alert type (Dependabot, code scanning, or secret scanning) and any relevant identifiers or URLs.

3. If an alert is not valid or should be dismissed:
   - Prefer fixing or mitigating where possible. If dismissal is appropriate (e.g. false positive, accepted risk), use the GitHub UI or API to dismiss with a reason, or add a code comment explaining why the finding is not addressed.
   - Do not dismiss or suppress without user approval. Propose why dismissal is appropriate and wait for confirmation before proceeding.

After processing each group, output a brief summary of what was done (alerts fixed, alerts dismissed, commit SHA if applicable) before moving to the next group.

### Step 4: Final report

After fixing all valid issues, provide a structured summary:
1. **Fixed**: Count and list of alerts fixed, with commit SHAs
2. **Dismissed**: Count and list of alerts dismissed, with reasons
3. **Unresolved**: Any alerts that could not be addressed, with the reason
4. **Statistics**: Total alerts, total fixed, total dismissed, total unresolved

Re-running the list-ghas-issues.py script to verify that alerts have been resolved may show updated state only after changes are committed and pushed, and after GitHub has re-run checks where applicable.
