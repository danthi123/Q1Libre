"""Compare stock Qidi Klipper modifications against upstream Klipper.

Categorizes .py files as Qidi-custom, modified, or identical relative to
upstream, and produces a markdown report to guide porting decisions.

Usage:
    python -m tools.diff --stock base/data/home/mks/klipper/klippy \
                         --upstream /tmp/klipper/klippy
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


def categorize_klipper_mods(
    stock_dir: Path,
    upstream_dir: Path,
) -> dict[str, list[str]]:
    """Compare .py files in *stock_dir* against *upstream_dir*.

    Walks *stock_dir* recursively and checks whether each ``.py`` file
    has a counterpart at the same relative path in *upstream_dir*.

    Returns:
        A dict with three keys:

        - ``"qidi_custom"`` — files only in stock (no upstream match)
        - ``"modified"``    — files in both dirs that differ
        - ``"identical"``   — files in both dirs that are byte-identical
    """
    result: dict[str, list[str]] = {
        "qidi_custom": [],
        "modified": [],
        "identical": [],
    }

    for stock_file in sorted(stock_dir.rglob("*.py")):
        rel = stock_file.relative_to(stock_dir).as_posix()
        upstream_file = upstream_dir / rel

        if not upstream_file.exists():
            result["qidi_custom"].append(rel)
        elif stock_file.read_bytes() != upstream_file.read_bytes():
            result["modified"].append(rel)
        else:
            result["identical"].append(rel)

    return result


def _first_line_docstring(path: Path) -> str:
    """Return the first line of the module docstring, or ''."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(('"""', "'''")):
            doc = stripped.strip("\"'").strip()
            return doc
        if stripped and not stripped.startswith("#"):
            break
    return ""


def generate_diff_report(
    stock_dir: Path,
    upstream_dir: Path,
    output_path: Path,
) -> None:
    """Write a markdown report comparing stock vs upstream Klipper files.

    The report contains:

    - Summary counts per category
    - Unified diff snippets (first 50 lines) for modified files
    - File size and docstring for Qidi-custom files
    - A porting recommendation for each file

    Args:
        stock_dir:   Path to the stock klippy directory.
        upstream_dir: Path to the upstream klippy directory.
        output_path: Where to write the ``.md`` report.
    """
    cats = categorize_klipper_mods(stock_dir, upstream_dir)

    lines: list[str] = []
    lines.append("# Klipper Diff Report\n")
    lines.append("## Summary\n")
    lines.append(f"| Category | Count |")
    lines.append(f"|----------|------:|")
    lines.append(f"| Qidi-custom | {len(cats['qidi_custom'])} |")
    lines.append(f"| Modified | {len(cats['modified'])} |")
    lines.append(f"| Identical | {len(cats['identical'])} |")
    lines.append("")

    # --- Modified files ---------------------------------------------------
    if cats["modified"]:
        lines.append("## Modified Files\n")
        for rel in cats["modified"]:
            lines.append(f"### `{rel}`\n")
            lines.append("**Recommendation:** investigate\n")

            stock_text = (stock_dir / rel).read_text(
                encoding="utf-8", errors="replace"
            )
            upstream_text = (upstream_dir / rel).read_text(
                encoding="utf-8", errors="replace"
            )
            diff = list(
                difflib.unified_diff(
                    upstream_text.splitlines(keepends=True),
                    stock_text.splitlines(keepends=True),
                    fromfile=f"upstream/{rel}",
                    tofile=f"stock/{rel}",
                )
            )
            snippet = "".join(diff[:50])
            if snippet:
                lines.append("```diff")
                lines.append(snippet.rstrip("\n"))
                lines.append("```\n")

    # --- Qidi-custom files ------------------------------------------------
    if cats["qidi_custom"]:
        lines.append("## Qidi-Custom Files\n")
        for rel in cats["qidi_custom"]:
            fpath = stock_dir / rel
            size = fpath.stat().st_size
            doc = _first_line_docstring(fpath)
            lines.append(f"### `{rel}`\n")
            lines.append(f"- **Size:** {size} bytes")
            if doc:
                lines.append(f"- **Docstring:** {doc}")
            lines.append("- **Recommendation:** port\n")

    # --- Identical files --------------------------------------------------
    if cats["identical"]:
        lines.append("## Identical Files\n")
        for rel in cats["identical"]:
            lines.append(f"- `{rel}` — **Recommendation:** drop")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compare stock Qidi Klipper against upstream.",
    )
    parser.add_argument(
        "--stock",
        required=True,
        help="Path to stock klippy dir (e.g. base/data/home/mks/klipper/klippy)",
    )
    parser.add_argument(
        "--upstream",
        required=True,
        help="Path to upstream klippy dir (e.g. /tmp/klipper/klippy)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="docs/klipper-diff-report.md",
        help="Output report path (default: docs/klipper-diff-report.md)",
    )
    args = parser.parse_args()

    stock_dir = Path(args.stock)
    upstream_dir = Path(args.upstream)
    output_path = Path(args.output)

    if not stock_dir.is_dir():
        print(f"error: stock dir not found: {stock_dir}", file=sys.stderr)
        sys.exit(1)
    if not upstream_dir.is_dir():
        print(f"error: upstream dir not found: {upstream_dir}", file=sys.stderr)
        sys.exit(1)

    generate_diff_report(stock_dir, upstream_dir, output_path)
    cats = categorize_klipper_mods(stock_dir, upstream_dir)
    total = sum(len(v) for v in cats.values())
    print(f"Report written to {output_path}  ({total} files compared)")


if __name__ == "__main__":
    main()
