---
name: resolve-sonarqube-issues
description: Review and resolve SonarQube findings including Issues, Security Hotspots, Test Coverage, and Code Duplication. Use when the user wants to address SonarQube findings or improve code quality metrics.
metadata:
  status: trial
---

Review and systematically resolve SonarQube findings (Issues, Security Hotspots, Code Duplication, Test Coverage) for the current PR using `scripts/list-sonar-issues.py` to list findings before fixing.

## Inputs

- Branch/PR context the Sonar script can resolve to SonarQube data
- Optional: `AGENTS.md`, `CONTRIBUTING.md` for repo conventions
- User intent: fix valid findings, document false positives, or suppress (suppression only with explicit user approval)

## Required output structure

1. **Findings summary** (before code changes): counts by category and severity, notable patterns
2. **Grouping plan** (before fixes): commit batches, processing order, per-group approach
3. **Per-group summary** after each batch: fixed vs invalid, commit SHA when applicable
4. **Final report**: Fixed, Invalid/Suppressed, Unresolved, Statistics

## Workflow

### Phase 1: Discover

- Read `AGENTS.md` and `CONTRIBUTING.md` if present.
- Run `python3 scripts/list-sonar-issues.py --help` from this skill's directory (next to `SKILL.md`), or `python3 skills/resolve-sonarqube-issues/scripts/list-sonar-issues.py` from the **cpe-imre** repository root when working there. Then run with **no flags**; **cache** the output (runs may exceed a minute).
- If the script errors, stop and report; do not proceed on assumed-empty results.

### Phase 2: Design

- Produce the findings summary and grouping plan per [resolve-sonarqube-workflow.md](../references/resolve-sonarqube-workflow.md) (Steps 1–2) before editing code.

### Phase 3: Implement

- Process groups in priority order (Security Hotspots, Issues, Code Duplication, Test Coverage). Follow commit-message, invalid-issue comments, and suppression rules in the workflow reference (Step 3).

### Phase 4: Verify

- Deliver the final structured summary (Step 4 in the workflow reference).
- Treat Sonar re-runs on the same PR as **eventually consistent** with pushed commits; see the workflow reference for the verification caveat.

## References

- [resolve-sonarqube-workflow.md](../references/resolve-sonarqube-workflow.md) — script usage, Steps 1–4, commit and suppression rules
- [skill-authoring.md](../references/skill-authoring.md)
- [technical-definition-of-done.md](../references/technical-definition-of-done.md)
