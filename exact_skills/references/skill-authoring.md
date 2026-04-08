# Skill Authoring Reference

This document is a reusable reference for writing project skills that are safe, concise, and maintainable.

## Core pattern: Skill + References

- Put execution workflow in `skills/<skill-name>/SKILL.md`.
- Put reusable policy/templates/checklists in `references/*.md`.
- Link from `SKILL.md` to references instead of duplicating long guidance.

## Authoring checklist

- Name is explicit and hyphenated (`create-ai-sdlc-skill` style).
- Description is specific and includes trigger language ("Use when...").
- `SKILL.md` stays concise and procedural.
- Inputs and outputs are explicit.
- Workflow has ordered phases and stop conditions.
- Verification criteria are present.
- Links are one level deep and valid.

## Recommended SKILL.md sections

1. Frontmatter (`name`, `description`, optional metadata)
2. Purpose (1-2 lines)
3. Inputs
4. Required output structure
5. Workflow phases (Discover, Design, Implement, Verify)
6. References (links to `references/*.md`)

## Quality gates before finalizing

- No contradictory instructions.
- No hidden assumptions about tooling or environment.
- No unnecessary verbosity.
- No duplicated standards that already exist in references.
- Terminology is consistent end to end.

## Anti-patterns

- Vague names (`helper`, `tooling`, `misc`).
- Long narrative in `SKILL.md` with no actionable steps.
- Embedding policy docs directly in each skill.
- Missing trigger language in description.
- Repeating similar checklists across many skills.
