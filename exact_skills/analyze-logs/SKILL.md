---
name: analyze-logs
description: Read application logs, identify errors, group similar errors by impact and volume, and share findings. Use when the user wants to analyze logs, review errors, troubleshoot failures, or understand log patterns.
---

# Analyze Logs

Read application logs, identify errors, group similar errors with codebase context, prioritize by impact and volume, and share findings. Works with any project; log location and access details come from the project's Operations documentation.

## Prerequisites

1. Review AGENTS.md and CONTRIBUTING.md in the project root (if present) for context and standards.
2. Read the Operations section of the project README. The Logs subsection (or equivalent) defines where logs are written, how to access them, required tools, log message structure, file layout, and filtering examples. Use this as the source of truth for all log-related technical details.

## Time Range

Unless the user specifies otherwise, analyze the last 24 hours of log data. Use whatever time parameters the project's log tooling supports (e.g., `--since`, `-s`, date ranges).

## Instructions

### Step 1: Fetch Logs

Using the commands, tools, and paths documented in the project README Operations section, fetch logs for the configured time range. Follow the project's instructions for environment selection, output redirection, and any required authentication.

If the fetch fails, report the error and stop.

### Step 2: Identify Errors

Filter for ERROR and FATAL levels. Include WARN when relevant to failures or unusual behavior. Use the log structure and filtering examples from the Operations section to locate error entries. Search for error messages, stack traces, and common failure patterns (e.g., "Failed", "Error", "Exception", "timeout", HTTP error codes).

### Step 3: Group Similar Errors

Group errors that share the same root cause or message pattern. Normalize variable parts (IDs, timestamps, URLs) to compare messages.

### Step 4: Context and Prioritization

For each error group:

1. Search the codebase for the error message or related identifiers to locate the source.
2. Determine impact: user-facing, job failure, background task, single feature, or system-wide.
3. Count occurrences per group.

Prioritize groups by:

1. Impact (higher severity first: system-wide, job failure, user-facing, then background)
2. Volume (more occurrences within same impact tier)

### Step 5: Share Findings

Report findings in this structure:

```markdown
# Log Analysis Report
**Time range:** [e.g., last 24 hours]
**Source:** [how logs were obtained, per project docs]

## Executive Summary
[One-paragraph overview of key findings and top priorities]

## Error Groups (by priority)

### Group 1: [Brief description]
- **Count:** [number]
- **Impact:** [description]
- **Source:** [file(s) and function/area]
- **Sample message:** [one representative log line]
- **Context:** [what the code does, why it fails]

### Group 2: ...
[Repeat for each group]

## Recommendations
[Actionable next steps, if any]
```

## Notes

- If the user specifies a different time range or environment, use those values instead of the defaults.
- If the project README has no Operations or Logs section, ask the user where logs are located and how to access them.
