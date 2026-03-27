---
name: review-readme
description: Thoroughly review and update the README.md document to remove duplicates, verify accuracy against the codebase, and align with documentation guidelines. Use when the user wants to audit, clean up, or improve a README.
---

# Review README

Thoroughly review the README.md, remove duplicate content, verify all content against the codebase, and align the document with the project's documentation guidelines. Make all necessary edits and leave the README accurate, non-redundant, and properly structured.

## When to Use

Use this skill when:
- The user asks to review, audit, clean up, or improve a README
- The README may be out of date with the current codebase
- The README contains duplicate or redundant sections
- The README needs to follow project documentation standards

## Critical Execution Rules

**Every step in this review is mandatory.** Do not skip, combine, or abbreviate any step. After completing each numbered step, output a **Step Summary** to the user before moving on. The step summary must follow this format:

> **Step N — [Step Title]**
> - **Guidelines applied**: [Source of the rules used — e.g., "CONTRIBUTING.md §Documentation", "AGENTS.md", or "Skill defaults (no project guidelines found)"]
> - **What I checked**: [Specific files read, searches performed, comparisons made]
> - **Findings**: [What was found — duplicates, errors, gaps, or "No issues found"]
> - **Actions planned**: [What will be fixed in Phase 3, or "None needed"]

If a step has no findings, you must still output the summary confirming you completed it with "No issues found." This proves the step was executed, not skipped.

## Instructions

### Phase 1: Read the documentation guidelines

Before reviewing the README, read the project's documentation standards so you know what to enforce.

1. **Read AGENTS.md**: Read **AGENTS.md** in the project root, if it exists. Note any rules about documentation: what must be documented, how to format it, what to avoid. If the file does not exist, state that explicitly.

2. **Read CONTRIBUTING.md**: Read the **"Documentation" section of CONTRIBUTING.md** in the project root, if it exists. Note style rules, required sections, layout conventions, heading levels, tone, and any explicit do/don't rules. If the file does not exist, state that explicitly.

3. **Establish baseline**: If neither file exists, proceed with general best-practice documentation standards (clear headings, no duplicate content, accurate commands and paths, consistent formatting). State which standard you are using.

The steps below include sensible defaults for content and structural rules (section length, paragraph density, TOC requirements, etc.). When project documentation guidelines exist, their rules **override** the defaults in this skill. When no project guidelines exist, use the defaults as written.

### Phase 2: Read and audit the README

Read the entire README.md from top to bottom. Complete every step below in order. Output a step summary after each one.

#### Step 1 — Identify duplicate content

Scan the entire README for content that appears more than once. Duplicates include:
- Sections that cover the same topic under different headings
- Paragraphs or sentences that repeat the same information in different words
- Code examples or commands that appear in multiple places
- Instructions that are restated in a different section

For each duplicate found, note: (a) the locations of both instances, (b) which instance is more complete or better placed, and (c) whether to merge, consolidate, or delete the weaker instance.

#### Step 2 — Verify commands and code blocks

For **every** shell command, script path, file path, flag, and code block in the README, verify it against the codebase. This means actually reading the referenced files, checking package.json scripts, and confirming paths exist. Specifically:
- Check that every referenced file and script exists at the stated path. Use Glob to verify.
- Check that commands use the correct package manager (npm vs yarn vs pnpm vs bun), correct script names, and correct flags.
- Check that code examples are syntactically valid and reflect the current API or interface.
- Note every command or path that is stale, incorrect, or no longer applicable.

Do not assume a command is correct because it looks reasonable — verify it.

#### Step 3 — Verify setup and installation sections

For any section covering installation, prerequisites, configuration, or getting started:
- Verify that every listed prerequisite (tool, runtime, package manager, environment variable, etc.) is still required. Check package.json engines, Dockerfiles, CI configs, and install scripts.
- Verify that stated version numbers are current — check against lock files, package.json, .tool-versions, .nvmrc, or equivalent.
- Trace through installation steps in order against the codebase and any install/config scripts. Confirm each step is complete and in the correct sequence.
- Verify that required environment variables, config files, or credentials are fully listed and correctly described. Cross-reference with .env.example, config templates, and application startup code.
- Flag any steps that are missing, out of order, or reference tooling that is no longer used.

#### Step 4 — Verify visual content

For any diagrams, screenshots, architecture visuals, or directory trees:
- Verify that directory trees match the actual directory structure. Use Glob and ls to confirm.
- Verify that architecture diagrams or flow charts reflect the current system design — check the referenced components, services, and data flows against the codebase.
- Verify that screenshots reflect the current UI state (if verifiable from the codebase).
- Flag any visuals that are outdated, missing referenced files, or inconsistent with the codebase.

If the README contains no visual content, state "No visual content found — step complete."

#### Step 5 — Check structure and layout

Compare the document's structure against the guidelines identified in Phase 1:
- **Heading hierarchy**: Verify correct H1/H2/H3 nesting. Flag any skipped levels (e.g., H1 → H3) or inconsistent usage.
- **Required sections**: Check that all sections required by the documentation guidelines are present (e.g., prerequisites, installation, usage, contributing, license).
- **Prohibited content**: Flag any content that the guidelines say should not be in the README (e.g., implementation details that belong in code comments, internal-only information).
- **Tone and voice**: Check that the writing style matches the guidelines (e.g., second person, active voice, concise).

#### Step 6 — Check section length and readability

Apply the section length and readability rules from the project's documentation guidelines (Phase 1). If the guidelines specify thresholds for section length, paragraph length, or when to extract content to `docs/`, use those thresholds exactly. If no project guidelines exist, use these defaults:
- Flag sections exceeding ~40 lines or ~500 words
- Flag paragraphs longer than ~6 sentences

For every section in the README:
- **Measure against thresholds**: Check each section's length against the guideline thresholds. Flag any section that exceeds them and propose how to split it (subsections with descriptive headings) or extract it (to a `docs/` file with a summary and link in the README).
- **Long paragraphs**: Flag paragraphs that are too dense. Propose breaking them into shorter paragraphs, bullet lists, or tables.
- **Wall-of-text blocks**: Flag areas where multiple consecutive paragraphs have no headings, lists, or code blocks to break up the text. These need structural relief.
- **Table of contents**: If a TOC exists, verify every entry links to a real heading and every heading is represented. If the guidelines require a TOC, check that one exists.

#### Step 7 — Verify internal links and anchors

Check every internal link and cross-reference within the README:
- Verify that anchor links (e.g., `[see Setup](#setup)`) point to headings that actually exist in the document.
- Verify that relative file links (e.g., `[contributing](./CONTRIBUTING.md)`) point to files that exist.
- Verify that any external URLs are correctly formatted (not broken Markdown syntax). Do not attempt to fetch external URLs, but check the Markdown syntax is valid.
- Flag any broken or orphaned links.

If the README contains no internal links, state "No internal links found — step complete."

#### Step 8 — Check formatting consistency

Review the README for consistent formatting throughout:
- **Bullet style**: Check that the same bullet character (`-` or `*`) is used consistently.
- **Code fences**: Check that fenced code blocks include a language identifier (e.g., ` ```bash `, ` ```json `). Flag any bare ` ``` ` fences.
- **Inline code**: Check that file names, commands, paths, variable names, and flags are wrapped in backtick inline code.
- **Bold/italic usage**: Check for consistent emphasis patterns.
- **List indentation**: Check that nested lists use consistent indentation.

#### Step 9 — Identify documentation gaps

Examine the codebase for features, configuration, commands, or behaviors that exist but are not documented in the README. Specifically:
- Check package.json scripts — are all user-facing scripts documented?
- Check CLI entry points and flags — are all options described?
- Check config files and environment variables — are all options listed?
- Check major features and modules — does the README mention all of them?
- Check recent git history for newly added features that may not yet be documented.

List every gap found with the source in the codebase and what content needs to be added.

#### Step 10 — Identify unlinked documentation

Check for documentation files that exist but are not linked from the README:
- List all Markdown files (`.md`) in the project root that are peers of the README (e.g., `CONTRIBUTING.md`, `CHANGELOG.md`, `ARCHITECTURE.md`).
- List all files in the `docs/` directory, if one exists.
- For each file found, check whether the README contains a link to it. Flag any that are missing a link.

#### Step 11 — Compile findings

Before making any changes, compile and present a complete findings summary organized by category:
- **Duplicates**: List all duplicate content with locations
- **Inaccuracies**: List all incorrect commands, paths, versions, or descriptions
- **Structural issues**: List all heading, layout, and guideline violations
- **Readability issues**: List all sections that are too long, paragraphs that need breaking up, and areas needing structural relief
- **Broken links**: List all broken internal links and anchors
- **Formatting inconsistencies**: List all formatting issues
- **Gaps**: List all undocumented features, commands, or configuration
- **Unlinked docs**: List all documentation files not linked from the README
- **Other issues**: Any additional findings

If any category has no findings, include it with "None found."

### Phase 3: Update the README

Apply all necessary changes. Address every finding from Phase 2.

1. **Remove duplicates**: Delete or consolidate repeated content. Prefer keeping the more complete or better-placed instance.

2. **Fix inaccurate content**: Update stale commands, paths, flags, versions, and descriptions to match the current codebase.

3. **Update visuals**: Correct any diagrams, directory trees, or visual content that no longer accurately reflects the codebase.

4. **Fix structure**: Reorder, add, or remove sections to match the layout and style required by the documentation guidelines.

5. **Break up long sections**: Split or extract sections that exceed the thresholds defined in the project's documentation guidelines. Break long paragraphs into shorter ones, bullet lists, or tables. Add structural relief (headings, lists, code blocks) to wall-of-text areas. If guidelines specify when to extract to `docs/`, follow those rules.

6. **Fix links and anchors**: Repair or remove any broken internal links. Update anchor references to match actual heading text.

7. **Fix formatting**: Apply consistent bullet style, add language identifiers to code fences, wrap technical terms in inline code, and fix any other formatting inconsistencies.

8. **Add missing content**: Document anything that exists in the codebase but is absent from the README. Every feature, command, configuration option, or behavior that a user needs to know about must be documented. Only add content that is verifiably true based on the codebase — do not add speculative content, general advice, or padding.

9. **Link unlinked documentation**: Add links in the README to any Markdown files in the project root or `docs/` directory that are not already linked. Place each link in the most contextually relevant section; if no section is a clear fit, add or use a "Documentation" section.

10. **Update table of contents**: If a TOC exists, update it to reflect all current headings. If the project guidelines require a TOC, add one if missing.

### Phase 4: Report changes

After updating, provide a structured summary:

1. **Changes made**: List each change with its category (duplicate removal, accuracy fix, structural change, readability improvement, link fix, formatting fix, new content, new link) and a brief explanation of why it was made.

2. **Issues not fixed**: List any issues found but not fixed, with the reason (e.g., "Diagram in §2 appears outdated but the correct state could not be determined from the codebase alone — flagged for manual review").

3. **Statistics**: Report the count of changes by category (e.g., "3 duplicates removed, 5 commands updated, 2 sections split for readability, 1 missing feature documented").

4. If no changes were needed, say so explicitly.

## Quality Rules

- Do not assume content is accurate — verify everything against the codebase.
- Add content that is missing but verifiably present in the codebase. Omissions are bugs, not safe defaults.
- Preserve the author's tone and writing style when rewriting for accuracy.
- Ask the user for guidance if you find an issue that cannot be resolved from the codebase alone.
- Every step must produce a visible summary — no silent completions.
- Do not batch or combine steps. Complete and report each step individually before moving to the next.
