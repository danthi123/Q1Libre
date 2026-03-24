"""Build pipeline: apply overlays/patches to stock firmware and produce a .deb.

Takes the extracted base/ directory (from tools.extract), applies overlay files
and patches, updates version markers, and repacks into a .deb that xindi
accepts as a firmware update.

Usage:
    python -m tools.build [--base BASE] [--overlay OVERLAY] [-o OUTPUT] [--version VER]
"""

from __future__ import annotations

import argparse
import io
import lzma
import shutil
import tarfile
import tempfile
from pathlib import Path

from tools.deb import build_deb
from tools.version import read_version, write_version

DEFAULT_VERSION = "0.3.0"


def _build_tar_xz(source_dir: Path) -> bytes:
    """Build a .tar.xz archive from a directory tree.

    Walks *source_dir*, creates an uncompressed tar in memory, then
    compresses with lzma.  Paths inside the tar start with ``./`` and
    use forward slashes.

    Args:
        source_dir: Root directory whose contents become the archive.

    Returns:
        Compressed bytes (xz format).
    """
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w", format=tarfile.GNU_FORMAT) as tf:
        for item in sorted(source_dir.rglob("*")):
            rel = item.relative_to(source_dir)
            arcname = "./" + rel.as_posix()
            # For text files (scripts, configs), strip Windows CRLF line endings
            # so they work correctly on Linux. Binary files are left as-is.
            if item.is_file() and item.suffix in (
                "", ".py", ".sh", ".cfg", ".conf", ".txt", ".md", ".service",
            ):
                data = item.read_bytes()
                if b"\r\n" in data:
                    data = data.replace(b"\r\n", b"\n")
                    info = tf.gettarinfo(str(item), arcname=arcname)
                    info.size = len(data)
                    tf.addfile(info, io.BytesIO(data))
                    continue
            # Use recursive=False to avoid tf.add() re-adding children
            # of directories (we iterate over them individually via rglob).
            tf.add(str(item), arcname=arcname, recursive=False)

    return lzma.compress(tar_buf.getvalue(), preset=6)


def build_firmware(
    base_dir: Path,
    overlay_dir: Path,
    patches_dir: Path,
    output_path: Path,
    q1libre_version: str,
) -> None:
    """Build a patched firmware .deb from base, overlays, and patches.

    Args:
        base_dir: Extracted stock firmware (contains data/, control/,
            debian-binary).
        overlay_dir: Directory of overlay files to copy into data/.
        patches_dir: Directory of patch files (placeholder, unused in Phase 1).
        output_path: Where to write the resulting .deb file.
        q1libre_version: Version string for q1libre (e.g. ``"0.1.0"``).
    """
    base_dir = Path(base_dir)
    overlay_dir = Path(overlay_dir)
    patches_dir = Path(patches_dir)
    output_path = Path(output_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        work = Path(tmpdir) / "work"

        # 1. Copy base/data and base/control to work dir
        shutil.copytree(base_dir / "data", work / "data")
        shutil.copytree(base_dir / "control", work / "control")

        # 2. Apply overlays — copy each file into the matching data/ path,
        #    but skip anything under overlay/control/ (those belong in control.tar.xz,
        #    not data.tar.xz, and are handled separately in step 2b).
        control_overlay = overlay_dir / "control"
        if overlay_dir.is_dir():
            for src_file in overlay_dir.rglob("*"):
                if src_file.is_file():
                    if control_overlay.is_dir() and src_file.is_relative_to(control_overlay):
                        continue
                    rel = src_file.relative_to(overlay_dir)
                    dest = work / "data" / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest)

        # 2b. Apply control overlays (overlay/control/ → work/control/)
        if control_overlay.is_dir():
            for src in control_overlay.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(control_overlay)
                    dst = work / "control" / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        # 3. Apply patches — placeholder for Phase 1
        pass

        # 4. Update version marker
        version_file = work / "data" / "root" / "xindi" / "version"
        if version_file.exists():
            write_version(
                version_file,
                soc=f"V4.4.24-q1libre{q1libre_version}",
            )

        # 5. Add Q1Libre marker file
        marker = work / "data" / "root" / "q1libre_version.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            f"q1libre {q1libre_version}\n"
            f"base: V4.4.24\n"
        )

        # 6. Build tar archives
        control_tar = _build_tar_xz(work / "control")
        data_tar = _build_tar_xz(work / "data")

        # 7. Read debian-binary from base
        debian_binary_path = base_dir / "debian-binary"
        debian_binary = (
            debian_binary_path.read_bytes()
            if debian_binary_path.exists()
            else b"2.0\n"
        )

        # 8. Build .deb and write output
        deb_bytes = build_deb(debian_binary, control_tar, data_tar)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(deb_bytes)

        print(f"Built {output_path} ({len(deb_bytes):,} bytes)")
        print(f"  control.tar.xz: {len(control_tar):,} bytes")
        print(f"  data.tar.xz:    {len(data_tar):,} bytes")
        print(f"  version:        q1libre {q1libre_version}")


def main() -> None:
    """CLI entry point for firmware build."""
    parser = argparse.ArgumentParser(
        description="Build patched Q1 firmware .deb from base + overlays."
    )
    parser.add_argument(
        "--base", default="base", help="Base directory (default: base)"
    )
    parser.add_argument(
        "--overlay", default="overlay", help="Overlay directory (default: overlay)"
    )
    parser.add_argument(
        "--patches", default="patches", help="Patches directory (default: patches)"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="dist/QD_Q1_SOC",
        help="Output .deb path (default: dist/QD_Q1_SOC)",
    )
    parser.add_argument(
        "--version", default=DEFAULT_VERSION, help=f"Q1Libre version (default: {DEFAULT_VERSION})"
    )
    args = parser.parse_args()

    build_firmware(
        base_dir=Path(args.base),
        overlay_dir=Path(args.overlay),
        patches_dir=Path(args.patches),
        output_path=Path(args.output),
        q1libre_version=args.version,
    )


if __name__ == "__main__":
    main()
