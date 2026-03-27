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

## Skill authoring behavior

- Before creating a new skill, check existing names for near-duplicates.
- If a name does not match this convention, propose a compliant name, and a migration map.
- If renaming an existing skill, update references that point to the old name.
