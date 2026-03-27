# Skill and Rule Naming Convention

Use these names when creating or renaming skills and rules.

## Skill names

- Integrations: `{tool}[-{scope}]`
  - Examples: `github`, `jira`, `syslog`
- Action skills: `{intent}-{subject}[-{qualifier}]`
  - Examples: `review-code`, `fix-bug`, `create-plan`, `validate-config`

## Naming rules

- Use lowercase letters, numbers, and hyphens only.
- Use singular nouns unless plural is required for meaning.
- Prefer explicit words over abbreviations, unless the abbreviation is the common product name.
- Keep names concise, predictable, and searchable.
- Do not mix styles for similar skills, and choose one canonical product slug.

## Intent consistency guidance

Keep intent words consistent with established patterns in existing skill names.

- For similar workflows, reuse the same intent word used by established skills.
- Avoid introducing synonym drift, for example mixing `address`, `fix`, and `resolve` for the same intent.
- If inconsistency already exists, propose renames that converge on the dominant existing pattern.
- Treat the current skill set as the source of truth, and update names over time to improve consistency.

## Skill authoring behavior

- Before creating a new skill, check existing names for near-duplicates.
- If a name does not match this convention, propose a compliant name, and a migration map.
- If renaming an existing skill, update references that point to the old name.
