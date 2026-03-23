"""Validate .deb files before deployment.

Checks structural integrity, required members, and content expectations
so problems are caught before the package reaches the printer.

Usage:
    python -m tools.validate <deb_path>
"""

from __future__ import annotations

import argparse
import io
import lzma
import re
import sys
import tarfile
from pathlib import Path

from tools.deb import parse_ar_archive


def validate_deb(deb_path: Path) -> list[str]:
    """Validate a .deb file and return a list of error strings.

    An empty list means the file is valid.

    Args:
        deb_path: Path to the .deb file to validate.

    Returns:
        List of error description strings.  Empty if valid.
    """
    errors: list[str] = []
    deb_path = Path(deb_path)

    # --- File existence and size ---
    if not deb_path.exists():
        return [f"File not found: {deb_path}"]

    file_size = deb_path.stat().st_size
    if file_size < 10_000:
        errors.append(
            f"File size is only {file_size:,} bytes (expected >= 10,000)"
        )

    raw = deb_path.read_bytes()

    # --- 1. Valid ar archive ---
    try:
        members = parse_ar_archive(raw)
    except ValueError as exc:
        return errors + [f"Not a valid ar archive: {exc}"]

    member_names = [m.name for m in members]
    member_map = {m.name: m for m in members}

    # --- 2. Required members ---
    if "debian-binary" not in member_names:
        errors.append("Missing required member: debian-binary")

    control_member_name = None
    for name in member_names:
        if re.match(r"^control\.tar\.", name):
            control_member_name = name
            break
    if control_member_name is None:
        errors.append("Missing required member: control.tar.* (e.g. control.tar.xz)")

    data_member_name = None
    for name in member_names:
        if re.match(r"^data\.tar\.", name):
            data_member_name = name
            break
    if data_member_name is None:
        errors.append("Missing required member: data.tar.* (e.g. data.tar.xz)")

    # --- 3. debian-binary version ---
    if "debian-binary" in member_map:
        version_str = member_map["debian-binary"].data.decode("ascii").strip()
        if version_str != "2.0":
            errors.append(
                f"debian-binary version is {version_str!r}, expected '2.0'"
            )

    # --- 4. Control archive contents ---
    if control_member_name is not None:
        control_data = member_map[control_member_name].data
        try:
            decompressed = lzma.decompress(control_data)
            with tarfile.open(fileobj=io.BytesIO(decompressed), mode="r") as tf:
                tar_names = tf.getnames()
                if "./control" not in tar_names:
                    errors.append(
                        "Control archive missing required file: ./control"
                    )
                if "./postinst" not in tar_names:
                    errors.append(
                        "Control archive missing required file: ./postinst"
                    )
        except Exception as exc:
            errors.append(f"Cannot open control archive: {exc}")

    # --- 5. Data archive contents ---
    if data_member_name is not None:
        data_data = member_map[data_member_name].data
        try:
            decompressed = lzma.decompress(data_data)
            with tarfile.open(fileobj=io.BytesIO(decompressed), mode="r") as tf:
                tar_names = tf.getnames()
                has_version = any("xindi/version" in n for n in tar_names)
                if not has_version:
                    errors.append(
                        "Data archive missing path matching xindi/version"
                    )
        except Exception as exc:
            errors.append(f"Cannot open data archive: {exc}")

    return errors


def main() -> None:
    """CLI entry point for .deb validation."""
    parser = argparse.ArgumentParser(
        description="Validate a .deb package for deployment."
    )
    parser.add_argument("input", type=Path, help="Path to the .deb file")
    args = parser.parse_args()

    errors = validate_deb(args.input)

    if not errors:
        print("VALID")
        sys.exit(0)
    else:
        print("VALIDATION FAILED")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
