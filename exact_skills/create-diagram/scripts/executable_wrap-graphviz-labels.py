#!/usr/bin/env python3
"""
Pre-process a Graphviz .gv file to wrap long text in node labels using textwrap.

Only wraps plain-text labels (e.g. note and box descriptions). Skips:
- Record-style labels (contain "|", used by Mrecord)
- Empty labels
- Short labels (under the wrap width)

Graphviz uses \\l for left-aligned line breaks. A double break \\l\\l marks
a paragraph boundary; single \\l are wrap breaks and are stripped before
wrapping so each run reflows paragraphs. The script splits on \\l\\l, wraps
each paragraph to the given width, joins lines with \\l and paragraphs with \\l\\l.

Usage:
  python wrap-graphviz-labels.py team-data-systems.gv
  python wrap-graphviz-labels.py team-data-systems.gv -o team-data-systems-wrapped.gv
  python wrap-graphviz-labels.py team-data-systems.gv --width 50 --in-place
"""

import argparse
import re
import sys
import textwrap


# Match label="..." where the string can contain \" and \\ (and \l, \n, etc.)
# We match: label=" then any sequence of: non-quote-non-backslash, or backslash+any char.
LABEL_PATTERN = re.compile(
    r'(\blabel=")((?:[^"\\]|\\.)*)(")',
    re.DOTALL,
)


# Paragraph boundary in label text (double line break)
PARA_SEP = "\\l\\l"


def wrap_label_content(content: str, width: int) -> str:
    """
    Wrap label text to width. \\l\\l is a paragraph boundary; single \\l are
    stripped so each paragraph is reflowed on every run. Split on \\l\\l,
    wrap each paragraph, join lines with \\l and paragraphs with \\l\\l.
    """
    # Normalize literal newlines to space
    content = content.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    paragraphs = content.split(PARA_SEP)
    wrapped = []
    for para in paragraphs:
        # Strip single \l (wrap breaks) to space so we reflow the paragraph
        block = para.replace("\\l", " ").strip()
        if not block:
            wrapped.append("")
            continue
        filled = textwrap.fill(
            block, width=width, break_long_words=False,
            initial_indent="", subsequent_indent="",
        )
        filled = filled.replace("\r\n", "\\l").replace("\r", "\\l").replace("\n", "\\l")
        # Trailing \l so Graphviz left-justifies the last line (stops it rendering indented)
        if filled:
            filled = filled + "\\l"
        wrapped.append(filled)
    return PARA_SEP.join(wrapped)


def normalize_line_breaks(content: str) -> str:
    """Replace any literal newlines/carriage returns with \\l so the file never has multi-line label strings."""
    return content.replace("\r\n", "\\l").replace("\r", "\\l").replace("\n", "\\l")


def should_wrap(content: str, width: int) -> bool:
    """Skip record labels, empty labels, and short labels."""
    if not content or len(content) < width:
        return False
    # Record-style labels (Mrecord) use | and sometimes < > for port names
    if "|" in content or "{" in content:
        return False
    return True


def process(content: str, width: int) -> str:
    """Replace each wrapable label's content with wrapped version; normalize all labels to use \\l only."""
    def repl(match: re.Match) -> str:
        prefix, label_content, suffix = match.groups()
        # Always normalize: no literal \\n or \\r in the output (Graphviz expects \\l for left-aligned lines)
        normalized = normalize_line_breaks(label_content)
        content = normalized if not should_wrap(normalized, width) else wrap_label_content(normalized, width)
        escaped = content.replace('"', '\\"').replace("\n", "\\l").replace("\r", "")
        return f"{prefix}{escaped}{suffix}"

    text = LABEL_PATTERN.sub(repl, content)
    # Add nojustify=true to note/box nodes so multi-line labels are left-aligned (no indent)
    text = re.sub(
        r'(shape=(?:note|box),)\s+(?!nojustify)(\w+=)',
        r'\1 nojustify=true, \2',
        text,
    )
    return text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wrap long text in Graphviz node labels using textwrap.",
    )
    parser.add_argument(
        "input",
        metavar="FILE",
        help="Input .gv file",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file (ignored if -o is set)",
    )
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=60,
        metavar="N",
        help="Wrap width in characters (default: 60)",
    )
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"Error reading {args.input}: {e}", file=sys.stderr)
        sys.exit(1)

    out_text = process(text, args.width)

    if args.output:
        out_path = args.output
    elif args.in_place:
        out_path = args.input
    else:
        sys.stdout.write(out_text)
        return

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_text)
    except OSError as e:
        print(f"Error writing {out_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if out_path == args.input:
        print(f"Updated {out_path} (in-place)", file=sys.stderr)
    else:
        print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
