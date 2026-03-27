---
name: validate-skill-naming
description: Validate and normalize skill names to the team naming convention. Use when creating, reviewing, organizing, or renaming skills.
---
# Validate Skill Naming

## Objective

Enforce this naming convention for skill directories:

- Integrations: `{tool}[-{scope}]`
- Action skills: `{intent}-{subject}[-{qualifier}]`
- Intent words should follow established patterns used by other existing skills

## Process

1. Inventory skill directories in the target skills path.
2. Classify each skill as integration or action.
3. Flag names that violate convention:
   - not lowercase kebab-case,
   - mixed naming style for similar intent,
   - ambiguous abbreviations,
   - inconsistent intent words compared with established naming patterns.
4. Produce a rename map with `old -> new`.
5. Apply renames only after explicit confirmation.
6. After renaming, update references that mention old names.

## Output format

Return results in this structure:

```text
Compliant
- skill-a
- skill-b

Needs rename
- old-name -> new-name (reason)
- old-name-2 -> new-name-2 (reason)

Collisions and decisions needed
- proposed-name already exists: old-a, old-b
```

## Guardrails

- Never rename without explicit user approval.
- Prefer minimal rename changes that preserve meaning.
- Keep product slugs consistent across related skills.
