"""Extract stock QD_Q1_SOC .deb firmware into a base/ directory.

Pure-Python implementation — no dpkg required. Works cross-platform.

Usage:
    python -m tools.extract <input.deb> [-o output_dir]
"""

from __future__ import annotations

import argparse
import io
import sys
import tarfile
from pathlib import Path

from tools.deb import parse_deb


def extract_tar_xz(data: bytes, dest: Path) -> int:
    """Extract a .tar.xz blob into *dest*.

    Args:
        data: Raw bytes of the .tar.xz archive.
        dest: Directory to extract into (created if needed).

    Returns:
        Number of files extracted.
    """
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
        tf.extractall(path=dest, filter="data")
        count = len(tf.getmembers())
    return count


def extract_deb(deb_path: str, output_dir: str) -> None:
    """Extract a .deb package into *output_dir*.

    Creates three things inside *output_dir*:
    - ``debian-binary`` — text file with the deb format version
    - ``control/`` — contents of control.tar.xz
    - ``data/`` — contents of data.tar.xz

    Args:
        deb_path: Path to the .deb file.
        output_dir: Directory to extract into (created if needed).
    """
    raw = Path(deb_path).read_bytes()
    members = parse_deb(raw)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Save debian-binary
    db = members.get("debian-binary")
    if db is not None:
        (out / "debian-binary").write_bytes(db.data)

    # Extract control archive
    count_ctrl = 0
    control_member = members.get("control.tar.xz")
    if control_member is not None:
        control_dir = out / "control"
        count_ctrl = extract_tar_xz(control_member.data, control_dir)
        print(f"  control: {count_ctrl} files -> {control_dir}")

    # Extract data archive
    count_data = 0
    data_member = members.get("data.tar.xz")
    if data_member is not None:
        data_dir = out / "data"
        count_data = extract_tar_xz(data_member.data, data_dir)
        print(f"  data:    {count_data} files -> {data_dir}")

    total = count_ctrl + count_data
    print(f"  total:   {total} files extracted to {out}")


def main() -> None:
    """CLI entry point for firmware extraction."""
    parser = argparse.ArgumentParser(
        description="Extract a .deb firmware package into its components."
    )
    parser.add_argument("input", help="Path to .deb file (e.g. QD_Q1_SOC)")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output directory (default: <input>.extracted)",
    )
    args = parser.parse_args()

    output = args.output or f"{args.input}.extracted"
    print(f"Extracting {args.input} -> {output}")
    extract_deb(args.input, output)


if __name__ == "__main__":
    main()
