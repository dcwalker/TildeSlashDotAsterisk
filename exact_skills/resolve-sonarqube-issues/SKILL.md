---
name: resolve-sonarqube-issues
description: Review and resolve SonarQube findings including Issues, Security Hotspots, Test Coverage, and Code Duplication. Use when the user wants to address SonarQube findings or improve code quality metrics.
metadata:
  status: trial
---

Review and systematically resolve SonarQube findings (Issues, Security Hotspots, Code Duplication, Test Coverage) using a scan-fix loop driven by `scripts/list-sonar-issues.py`. The loop runs until the server confirms zero issues on the latest scan.

## Inputs

- Branch/PR context the Sonar script can resolve to SonarQube data
- Optional: `AGENTS.md`, `CONTRIBUTING.md` for repo conventions
- User intent: fix valid findings, document false positives, or suppress (suppression only with explicit user approval)
- Environment variables: `SONAR_HOST_URL`, `SONAR_TOKEN` (required for both the script and `sonar-scanner`)

## Required output structure

1. **Initial server check**: report current issue counts from the server before any scan
2. **Per-loop header**: "Loop N — running sonar-scanner…"
3. **Scan wait confirmation**: confirm when the new analysis is published on the server
4. **Findings summary** (after each scan): counts by category and severity, notable patterns
5. **Grouping plan** (before fixes): commit batches, processing order, per-group approach
6. **Per-group summary** after each batch: fixed vs invalid, commit SHA when applicable
7. **Loop result**: issues remaining after fixes, or "✅ No issues found — loop complete."
8. **Final report** (when loop ends): Fixed, Invalid/Suppressed, Unresolved, Statistics

## Workflow

### Phase 0: Setup

- Read `AGENTS.md` and `CONTRIBUTING.md` if present.
- Run `python3 skills/resolve-sonarqube-issues/scripts/list-sonar-issues.py --help` from the repo root to confirm the script is available.

### Phase 1: Check server for existing issues

- Run `python3 skills/resolve-sonarqube-issues/scripts/list-sonar-issues.py --summary` and **cache** the output.
- If the script errors, stop and report; do not proceed on assumed-empty results.
- Report the current issue and hotspot counts to the user.
- If issues already exist on the server, skip to **Phase 3: Fix** — do not run a redundant scan first.
- If no issues exist, proceed to **Phase 2: Scan**.

### Phase 2: Scan

- Run `sonar-scanner` from the project root and wait for it to finish.
- After `sonar-scanner` exits, **poll the server** until the new analysis is published before reading results.

  **Polling strategy** — use the SonarQube API to detect the new analysis:

  ```bash
  # Capture the latest analysis date before the scan (store during Phase 1 check)
  BEFORE_DATE=$(python3 -c "
  import urllib.request, base64, json, os
  host = os.environ['SONAR_HOST_URL'].rstrip('/')
  token = os.environ['SONAR_TOKEN']
  auth = base64.b64encode(f'{token}:'.encode()).decode()
  req = urllib.request.Request(
      f'{host}/api/project_analyses/search?project=YOUR_PROJECT_KEY&ps=1',
      headers={'Authorization': f'Basic {auth}'}
  )
  data = json.loads(urllib.request.urlopen(req).read())
  analyses = data.get('analyses', [])
  print(analyses[0]['date'] if analyses else '')
  ")

  # Poll until a newer analysis appears (timeout after 10 minutes)
  TIMEOUT=600
  ELAPSED=0
  while [ $ELAPSED -lt $TIMEOUT ]; do
    AFTER_DATE=$(python3 -c "
  import urllib.request, base64, json, os
  host = os.environ['SONAR_HOST_URL'].rstrip('/')
  token = os.environ['SONAR_TOKEN']
  auth = base64.b64encode(f'{token}:'.encode()).decode()
  req = urllib.request.Request(
      f'{host}/api/project_analyses/search?project=YOUR_PROJECT_KEY&ps=1',
      headers={'Authorization': f'Basic {auth}'}
  )
  data = json.loads(urllib.request.urlopen(req).read())
  analyses = data.get('analyses', [])
  print(analyses[0]['date'] if analyses else '')
  ")
    if [ "$AFTER_DATE" != "$BEFORE_DATE" ] && [ -n "$AFTER_DATE" ]; then
      echo "New analysis published: $AFTER_DATE"
      break
    fi
    sleep 15
    ELAPSED=$((ELAPSED + 15))
  done

  if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: Timed out waiting for SonarQube to publish analysis results."
    exit 1
  fi
  ```

  Replace `YOUR_PROJECT_KEY` with the value from `sonar-project.properties` (`sonar.projectKey`).

- Once the new analysis is confirmed published, run the full issue fetch and **cache** the output:

  ```bash
  python3 skills/resolve-sonarqube-issues/scripts/list-sonar-issues.py
  ```

- If the script errors after the scan, stop and report.

### Phase 3: Evaluate

- Produce the **findings summary**: counts by category and severity, notable patterns.
- **If zero issues and zero hotspots**: report `✅ No issues found — loop complete.` and stop. Do not re-scan.
- **If issues exist**: proceed to Phase 4.

### Phase 4: Fix

- Produce the **grouping plan** per [resolve-sonarqube-workflow.md](../../references/resolve-sonarqube-workflow.md) (Steps 1–2) before editing code.
- Process groups in priority order: Security Hotspots → Issues → Code Duplication → Test Coverage.
- Follow commit-message, invalid-issue comments, and suppression rules in the workflow reference (Step 3).
- Deliver the **per-group summary** after each batch.

### Phase 5: Loop

- After all fix batches are committed and pushed, return to **Phase 2: Scan**.
- Repeat until Phase 3 confirms zero issues.
- Track loop count and surface it in each loop header: "Loop N — running sonar-scanner…"

### Phase 6: Final report

- Deliver the structured final report (Step 4 in the workflow reference): Fixed, Invalid/Suppressed, Unresolved, Statistics.
- State total loops run and total issues resolved.

## Important constraints

- **Never report "no issues" from a cached or pre-scan result.** The clean bill of health must come from a fresh server analysis published after the most recent code changes.
- **Do not stack scans.** Wait for each `sonar-scanner` run to complete and the analysis to be published before starting the next one.
- **Suppression requires explicit user approval** before applying any `// NOSONAR` or suppression annotation.
- **Cache all script output** — runs may exceed a minute. Do not re-run the script for the same analysis unless the loop has iterated.

## References

- [resolve-sonarqube-workflow.md](../../references/resolve-sonarqube-workflow.md) — script usage, Steps 1–4, commit and suppression rules
