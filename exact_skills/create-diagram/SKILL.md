---
name: create-diagram
description: Create and update technical diagrams (Graphviz, Mermaid, or custom diagram code) with companion documentation. Covers when to use Graphviz vs Mermaid vs a custom script or library, inline vs embedded image delivery, and design rules (line styles, colors, line numbers, sources). Use when the user asks to create or update a diagram, document a data flow or architecture, or produce diagram plus narrative.
---

# Create Diagram

Create and update diagrams (Graphviz, Mermaid, or custom diagram code) with companion markdown or prose. Follow the design rules below; the user may override any default.

**Reference:** [design-guidelines-and-rules.md](design-guidelines-and-rules.md) adds context and examples for the design rules. [choosing-diagram-tools-and-format.md](choosing-diagram-tools-and-format.md) explains when to choose diagram tools and when to use inline vs a separate file (embedded). Do not duplicate that content here; link to these files when the user needs more detail.

## When to Use This Skill

- Creating or updating a technical diagram (data flow, architecture, process).
- Producing diagram plus narrative so the content is searchable and consumable in more than one form.
- User asks for a diagram plus narrative or documentation.

## Workflow

After each step, summarize what was decided and how it fits the larger picture so the user can review and give feedback.

**When updating an existing diagram:** Read the top of the source file for audience and usage comments. If they exist, confirm with the user that they are still accurate. If yes, skip or shorten steps 1 and 2 and go to data gathering and layout. If the user wants to change audience or usage, update the comments and proceed.

**Step 1: Audience**  
Identify who will read or use the diagram (e.g. executives, engineers, customers, mixed). That drives terminology (avoid or define jargon; use terms the audience knows) and technical depth (high-level boxes and flows vs field names, APIs, or schema details). When using diagram-as-code, add a comment at the top of the file (e.g. `// Audience: internal engineers`) so future editors know the context.

**Step 2: Usage**  
Clarify where the diagram will live (slide deck, README, Confluence/GitHub/Notion page, standalone webpage, PDF) and any size or aspect constraints (e.g. must fit on one slide). Decide whether it will be updated over time: if yes, prefer diagram-as-code so changes are made in source and output is regenerated; one-off diagrams can be a single PNG if the user prefers. Usage and maintenance inform whether to use inline vs embedded and Mermaid vs Graphviz (e.g. "Inline in README, rarely updated" → Mermaid in Markdown; "Confluence page, will be updated, complex flow" → Graphviz source, render to PNG/SVG, companion markdown). When using diagram-as-code, add a comment at the top with usage details and how to regenerate (e.g. `// Usage: Confluence page, embedded PNG/SVG; kept up to date. Regenerate with: dot -Tpng -o out.png file.gv`).

**Step 3: Data gathering**  
Get a narrative from the user (what the diagram should show and why) and collect resources (docs, API specs, screenshots, existing diagrams). For each resource, determine how it fits (which nodes, edges, or groupings it supports) and ask for clarification if the role is unclear. Before implementing, show proposed connections and relationships so the user can confirm or correct. For example:

- Inline: "Proposed flow: System A → System B → System C"
- Simple boxes and arrows in a code block:
  ```
  [A] --> [B] --> [C]
       \_________/
         (sync)
  ```
- Or a short list: "Resource X = node A; Resource Y feeds into B and C."

When using diagram-as-code, add every resource URL to the sources comment section of the file (and to the companion markdown reference list).

**Step 4: Layout and grouping**  
Decide which elements belong together (e.g. by system, team, or phase) and how to show that: clusters or subgraphs (Graphviz), subgraphs or swimlanes (Mermaid), or visual grouping (boxes, spacing). If the chosen tool cannot support the needed grouping or layout, research what other diagram tools or libraries are already available (e.g. via web search) before suggesting a custom image generator. Suggest an alternative: another existing tool (e.g. Graphviz vs Mermaid or libraries in [choosing-diagram-tools-and-format.md](choosing-diagram-tools-and-format.md)) or a custom image generator only when the needs justify it. Explain benefits and downsides; always ask the user before switching tools. When using diagram-as-code, document important layout decisions in comments (e.g. why clusters are split, why certain edges are invisible or weighted).

**Step 5: Color and formatting**  
Based on audience and usage, suggest style and color options. If the deliverable fits a known context (e.g. company slides, product docs), suggest a palette that fits that context: look for the company's brand or design guidelines online or ask the user for the company brand color palette to use; never guess at brand colors. Record the design guidelines for the diagram in a separate markdown document (even when the diagram output is inline). Use [design-guidelines-and-rules.md](design-guidelines-and-rules.md) as a template; the document should define each entity type (data flows, actors, notes, nodes, decision points, etc.) and the style for each (line style, color, shape, weight). As color and formatting choices are made, update that document so it stays an accurate record. Place it in the same path as the diagram with a name like `<name>-design-guidelines.md`. When using diagram-as-code, you may add a short comment at the top of the source file pointing to the design guidelines document; if the user overrides a guideline for a specific element, add a comment at that point in the code (e.g. `// Override: this edge dashed per request to distinguish from main flow`). Ensure sufficient color contrast: WCAG AA minimum 4.5:1 for normal body text and 3:1 for large text (e.g. 18pt+ or 14pt+ bold). Do not rely on color alone to convey meaning; pair color with text labels, icons, or patterns (e.g. dashed vs solid, or shape).

**Step 6: Companion documentation**  
Provide companion documentation for every diagram. When the diagram is inline in the same document, the prose in that document is the companion. When the diagram is delivered as an embedded image, provide a separate companion markdown document (same base name, `.md`). Structure the companion as follows: one section per major grouping (cluster, subgraph, swimlane, or equivalent) so the narrative mirrors the diagram; weave in the text from any note, callout, or annotation nodes; when describing a step or flow, cite the corresponding edge number(s) using "line N" or "lines N–M"; add a short intro or preview that states what the diagram shows and how to read it (e.g. direction of flow, meaning of line styles); include a "Reference links and sources" section (bullet list of the same URLs as in the diagram's sources comment block, each with descriptive link text, sorted alphabetically by title). When the diagram is an embedded image, describe it with specific alt text (e.g. for Markdown: `![description](path/to/image.png)`), not a generic label like "diagram" or "image".

**Step 7: Review**  
Check that all color, style, and layout guidelines are met; look for conflicting information (e.g. a label that contradicts the narrative) and flag it; proofread all written content for spelling and grammar; ensure tone and style are consistent; define every acronym at first use; and ensure every screenshot and image has descriptive alt text (not vague text like "diagram" or "image").

## Graphviz: label wrapping workaround

**Label wrapping:** Graphviz does not wrap long labels automatically. Run a wrap script before producing PNG/SVG (use the project's copy if present, otherwise this skill's `scripts/wrap-graphviz-labels.py`). The script wraps long plain-text labels (notes, box labels), skips record-style labels, uses `\l\l` as paragraph boundary and reflows to a width (default 60), and adds `nojustify=true` to note/box nodes. Example: `python3 wrap-graphviz-labels.py path/to/diagram.gv -o path/to/diagram-wrapped.gv` or `--in-place` to overwrite; `-w N` for width.

## Checklist Before Delivering

- [ ] Design guidelines document (separate .md, same path as diagram) up to date; line styles by edge type; colors from palette or approved; accessibility (contrast, meaning not by color alone).
- [ ] Unique line numbers; follow flow/hierarchy.
- [ ] Sources in diagram (comment block) and companion (reference links section, alphabetical by title).
- [ ] Graphviz (if used): wrap script run (project's or skill's).
- [ ] Companion: one section per major grouping; note content woven in; "line N"/"lines N–M" refs; intro or preview; reference links; alt text (if embedded).
- [ ] Review: layout and style guidelines met; no conflicting information; proofread; consistent tone; acronyms at first use; alt text on all images.
