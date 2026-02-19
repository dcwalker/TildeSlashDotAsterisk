---
name: plan-from-work-item
description: Read a Jira or GitHub work item and create a plan to address it. Use acli for Jira and gh for GitHub. Use when the user wants to address an issue, plan work from a ticket, or when given a URL or identifier for a Jira issue or GitHub issue.
---

# Plan from Work Item

Create a plan to address a single work item by gathering the item, project context, and producing the next logical step(s). Stop and prompt whenever the next step is unclear or the item is ambiguous.

## 1. Obtain a reference

- If the user provided a URL or ticket identifier (e.g. PROJECT-123, org/repo#42), use it.
- If not, prompt: "Please provide a URL or ticket identifier (e.g. Jira key or GitHub org/repo#number) so I can look up the work item."

Do not guess or invent a reference.

## 2. Look up the work item

- **Jira**: Use the `acli` CLI. Example: `acli jira issue view PROJECT-123` (or equivalent for your setup). Use the cloudId from user or workspace context if one is specified.
- **GitHub**: Use the `gh` CLI. Example: `gh issue view <number> --repo org/repo` or `gh issue view <url>`.

Choose the tool from the reference: Jira keys (e.g. PROJ-123) or atlassian.net URLs → acli; GitHub issue URLs or org/repo#n → gh.

## 3. Review the work item

Capture and use:

- Title and description (problem statement, requirements)
- Type: bug, feature, improvement, task, etc.
- Metadata: creation date, labels, status, assignee, links (e.g. parent, blocks)
- All comments for extra context, repro steps, or decisions

Note anything unclear or contradictory for step 6.

## 4. Review project docs

In the project root, read:

- **AGENTS.md** – planning, autonomy, API usage, memory/state, documentation rules
- **CONTRIBUTING.md** – planning, coding standards, testing, commits, documentation

The plan must align with these (e.g. plan before coding, document in tracking system, no refactor without approval, follow CONTRIBUTING for tests and commits).

## 5. Decide next logical step

- From the item type, description, acceptance criteria, and comments, determine the single next logical step (e.g. "reproduce the bug," "implement endpoint X," "add tests for Y").
- If the next step is not clear (e.g. multiple valid options, missing acceptance criteria, vague scope), do not guess. Prompt the user: "The next step isn't clear because [reason]. What would you like to do next?" and wait for a response before writing the plan.

## 6. Resolve ambiguity before planning

If anything in the work item is unclear or contradictory (e.g. description vs acceptance criteria, conflicting comments), prompt the user for guidance and wait for a response. Do not assume or invent requirements. Only produce the plan once you have enough clarity.

## 7. Build the plan by type

### Bug

- Summarize the issue and any repro steps from the item and comments.
- Plan: (1) Investigate potential causes in the code; (2) If the cause is not obvious, add minimal debugging (e.g. logs, assertions) and describe how to reproduce; (3) Review the code for an obvious fix; (4) Propose fix and tests. Keep debugging and changes minimal until the cause is confirmed.

### Feature or improvement

- Extract and list acceptance criteria and problem statement from the description and comments.
- Plan must address both: each acceptance criterion and the problem statement. If any are missing, ask the user to confirm or add them before finalizing the plan.

### Other (task, chore, etc.)

- Align the plan with the title, description, and any stated success criteria. If none are clear, prompt for clarification.

## 8. Output the plan

Produce a short, actionable plan that:

- States the work item reference and type
- Lists assumptions and any open questions
- Gives ordered next steps (numbered or checklist)
- References AGENTS.md / CONTRIBUTING.md where relevant (e.g. "Add tests per CONTRIBUTING," "Document in tracking system per AGENTS.md")

Keep the plan concise. If the work spans many steps, focus on the immediate next step and note that later steps will follow.
