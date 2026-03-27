# Design Guidelines and Rules

---

These are basic rules the user can override if needed. Use them as a template for the design guidelines to record in the diagram document or code (e.g. a "Design guidelines" comment block).

## Design Rules: Context and Examples

**Line styles**  
Use one style for all edges that represent the same idea: for example, data flow (system-to-system) solid and one color; human or actor actions dashed; note connectors (note to handle) dotted, with default or low weight so they do not drive layout.

**Colors**  
If the user provides a palette, use only those colors unless you need another (and then say why). Document the palette in a comment at the top of the source file.

Accessibility: ensure sufficient color contrast (WCAG AA minimum 4.5:1 for normal body text, 3:1 for large text, e.g. 18pt+ or 14pt+ bold). Do not rely on color alone to convey meaning; pair color with text labels, icons, or patterns (e.g. dashed vs solid, or shape).

**Line numbers**  
Assign a unique number to each meaningful edge. Main flow in sequence; branches and note connectors can use gaps. In companion markdown, always refer to "line N" or "lines N–M" so readers know they map to the diagram.
