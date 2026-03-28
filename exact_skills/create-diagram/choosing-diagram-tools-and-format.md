# Choosing Diagram Tools and Format

This guide helps you choose between diagram-as-code tools (e.g. Mermaid and Graphviz/DOT) for a diagram, and whether to keep the diagram inline in the document or in a separate file (embedded image). Both .gv and .mmd source files can be committed to a repo; the main differences are layout control, where the diagram renders, and whether you need a separate build step.

---

## Choose Graphviz (DOT) when:

- The diagram is a multi-system or multi-cluster data or process flow with many nodes and edges.
- You need strict control over rank order, clusters, and edge weight (for example, notes that must not drive layout).
- You want numbered edge labels and consistent line styles by type, with a commented sources section in the same file.
- You can run `dot` (and optionally a wrap script) to produce PNG or SVG.
- The diagram will be delivered as an embedded image with companion markdown.

**Why Graphviz fits complex flow diagrams:** It supports rank direction, ordering, edge weight, constraint, invisible edges, and compound clusters. Notes can be attached via handle nodes so they do not dominate layout. Clusters are first-class; you can attach edges to cluster boundaries. Numbered and HTML-like edge labels render consistently. Node types include records (Mrecord), note shapes, and custom styling. A wrap script can reflow long labels; output is PNG/SVG via `dot`.

---

## Choose Mermaid when:

- The diagram is simple to moderate: flowcharts, sequence diagrams, or other types Mermaid supports well.
- You want the diagram to render inline in Markdown (e.g. GitHub, Confluence, Notion) so diagram and prose live in one file.
- You do not need fine-grained layout control (weight, constraint, invisible edges) or complex clusters.
- You prefer no separate render step, or the platform renders Mermaid from a code block.

**Why Mermaid fits simple or inline use:** There is no render step when the platform supports Mermaid; you edit diagram and text in one place. It works well for sequence diagrams, simple flowcharts, and quick sketches. Both .mmd and .gv can be committed to a repo; the difference is whether the reader sees the diagram via inline rendering (Mermaid in the doc) or via an embedded image (PNG/SVG from either tool).

**Mermaid caveats:** Edge labels and styling are supported to varying degrees depending on diagram type (flowchart, sequence, etc.). For diagrams that need many numbered edges, strict clustering, or fine layout control, prefer Graphviz. For sources: keep a comment block in the .mmd file or in the Markdown file that contains the inline diagram, and list the same URLs in the companion document's reference section.

---

## Inline vs Embedded: When to Use a Separate File

The diagram can live **inline** in the same document as the prose, or in a **separate file** that you render to an image and embed. Both approaches can use Mermaid or Graphviz source; the choice is how the audience sees the diagram and how you maintain it.

### Inline (diagram in the same document)

The diagram source lives in the same document as the prose. The viewer (GitHub, Confluence, Notion, etc.) renders it when the page is opened. In practice this usually means Mermaid inside a Markdown code block; most platforms do not render Graphviz inline.

| Pros | Cons |
|------|------|
| Single file for diagram and text | Only works where the platform supports the format (e.g. Mermaid) |
| No separate build step | Complex diagrams can make the file long and harder to edit |
| Diagram and prose stay in one place | Layout control is limited (Mermaid) |
| Easy to edit in place | Graphviz cannot be rendered inline on most platforms |

**Use inline when:** The diagram is simple, Mermaid is sufficient, and you want everything in one Markdown file with no image build.

### Embedded (separate diagram file, render then embed)

The diagram source is a separate file (.gv or .mmd). You run a render step (`dot`, Mermaid CLI, etc.) to produce PNG or SVG, and the document embeds that image (e.g. `![alt](path/to/diagram.png)`).

| Pros | Cons |
|------|------|
| Works on any platform that displays images | Requires a render step |
| Graphviz and Mermaid both supported | Two artifacts to keep in sync (source and image) |
| Full layout control with Graphviz | Document does not index diagram text unless you add narrative |
| Source can be processed (e.g. wrap script) and versioned | |

**Use a separate file and embed when:** The diagram is complex, you need Graphviz, you want to keep the diagram in code for future updates (regenerate consistently), or you want companion markdown that describes the flow (searchable, line numbers, sources). A separate file also makes it easier to run tools (e.g. a label-wrapping script) on the source.

---

## When to Write a Custom Image-Generating Script

Use Mermaid or Graphviz when they meet your needs; they are maintained, widely supported, and keep diagram-as-code in a standard format. Consider a **custom script or library** when:

- **Dynamic data:** The diagram must be generated from runtime or frequently changing data (APIs, databases, config) and you need programmatic control over layout and styling that goes beyond templating .gv or .mmd.
- **Domain-specific or custom layout:** The diagram type or layout rules are not well served by Mermaid's built-in types or Graphviz's layout engines (e.g. custom swimlanes, strict grid placement, or a format neither tool targets).
- **Interactive or in-app diagrams:** The diagram is part of an application UI (editing, drag-and-drop, real-time updates) rather than a static asset for docs; you need a library that renders in the browser or app runtime.
- **Pixel-perfect or brand-specific output:** You need exact control over positioning, styling, or export (e.g. for print or brand guidelines) that DOT or Mermaid do not give you.
- **Integration in a pipeline:** You are generating images from code in a language or environment where calling `dot` or Mermaid CLI is awkward, and a native library (e.g. Python, JavaScript) fits your stack better.

**When not to:** For static, documentation-style diagrams (flowcharts, data flow, architecture) that Mermaid or Graphviz can express, prefer those tools so the diagram stays in a standard, editable format and does not depend on custom code.

---

## Popular Libraries for Diagramming

Libraries can generate diagram source (e.g. DOT or Mermaid), render it to image/SVG, or provide interactive diagram UIs. Choose by language, output (static image vs interactive), and whether you need to stay in a standard format (DOT/Mermaid) or want full programmatic control.

### JavaScript / TypeScript

- **Mermaid (library):** Render Mermaid from code; good for generating .mmd or embedding in apps. [mermaid.js](https://mermaid.js.org/)
- **React Flow:** Node-based diagrams and editors in React; drag-and-drop, zoom, pan. Suited to interactive UIs and flow builders. [reactflow.dev](https://reactflow.dev/)
- **AntV X6:** Graph editing and visualization (SVG/HTML); DAG, ER, flowcharts, lineage. Custom nodes and extensions. [x6.antv.antgroup.com](https://x6.antv.antgroup.com/)
- **GoJS:** Commercial diagramming framework; org charts, flowcharts, industrial diagrams; automatic layout, data binding. [gojs.net](https://gojs.net/)
- **JSPlumb:** Connectors and flowcharts; works with vanilla JS or React/Angular/Vue. [jsplumb.org](https://jsplumb.org/)
- **D3:** Low-level SVG/canvas; use when you need custom visualizations rather than prebuilt diagram types. [d3js.org](https://d3js.org/)

### Python

- **graphviz:** Create and render DOT from Python; thin wrapper around the Graphviz engine. Good for scripting .gv and exporting PNG/SVG. [pypi.org/project/graphviz](https://pypi.org/project/graphviz/)
- **pydot / PyGraphviz:** Python interfaces to Graphviz (DOT); create or modify graphs programmatically then render. [pypi.org/project/pydot](https://pypi.org/project/pydot/)
- **Diagrams:** "Diagram as code" for cloud/system architecture; uses Graphviz under the hood. Icons for AWS, GCP, Azure, Kubernetes, etc. [pypi.org/project/diagrams](https://pypi.org/project/diagrams/)
- **PHART:** Renders graphs (NetworkX, GraphML, DOT) to ASCII, Unicode, SVG, HTML, or Mermaid. Pure Python; useful when you want text or Mermaid output without a Graphviz install. (Search PyPI or GitHub for "phart" or "PHART diagram".)

For static docs, prefer Mermaid or Graphviz source files where possible; use libraries when you need to generate that source from data or when you need interactive or custom output.
