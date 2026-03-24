#!/usr/bin/env python3
"""
Download Python 3.8 packages for arm64 Debian Buster (Debian 10) from official
Debian mirrors. Packages are stored in overlay/root/python38_debs/ and bundled
into the Q1Libre .deb for offline installation on the printer.

Usage: python tools/download_python38.py

Notes:
- python3.8 was never backported to Debian Buster (buster-backports) for arm64.
  The buster-backports arm64 index confirms this.
- python3.8 3.8.7-1 was in Debian testing/bullseye cycle and is available via
  snapshot.debian.org at the archived snapshot URL.
- This is the highest version available for Debian arm64; Debian switched to
  Python 3.9 for bullseye and 3.8 was dropped before the final bullseye release.
- These packages are ABI-compatible with Debian Buster arm64 (same glibc lineage).
"""
import urllib.request
import urllib.error
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "overlay" / "root" / "python38_debs"

# Python 3.8.7-1 arm64 packages from Debian snapshot archive.
# These were in Debian testing during the bullseye development cycle.
# snapshot.debian.org preserves them permanently.
SNAPSHOT_BASE = "http://snapshot.debian.org/archive/debian/20201222T203709Z/pool/main/p/python3.8/"

# Packages needed for python3.8 + venv support (arm64)
# python3.8-distutils is included inside libpython3.8-stdlib (not a separate package)
PACKAGES = [
    "libpython3.8-minimal_3.8.7-1_arm64.deb",
    "python3.8-minimal_3.8.7-1_arm64.deb",
    "libpython3.8-stdlib_3.8.7-1_arm64.deb",
    "libpython3.8_3.8.7-1_arm64.deb",
    "python3.8_3.8.7-1_arm64.deb",
    "python3.8-venv_3.8.7-1_arm64.deb",
]

def download_file(url: str, dest: Path) -> bool:
    """Download a file, return True on success."""
    if dest.exists():
        size_kb = dest.stat().st_size // 1024
        print(f"  Already exists: {dest.name} ({size_kb} KB)")
        return True
    print(f"  Downloading {dest.name}...")
    try:
        urllib.request.urlretrieve(url, dest)
        size_kb = dest.stat().st_size // 1024
        print(f"  OK ({size_kb} KB)")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        if dest.exists():
            dest.unlink()
        return False

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading Python 3.8.7-1 arm64 packages from Debian snapshot archive...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    downloaded = []
    failed = []

    for filename in PACKAGES:
        url = SNAPSHOT_BASE + filename
        dest = OUTPUT_DIR / filename

        if download_file(url, dest):
            downloaded.append(filename)
        else:
            failed.append(filename)

    print(f"\nDownloaded {len(downloaded)} packages to {OUTPUT_DIR}")
    for f in downloaded:
        size_kb = (OUTPUT_DIR / f).stat().st_size // 1024
        print(f"  {f} ({size_kb} KB)")

    if failed:
        print(f"\nFailed to download:")
        for f in failed:
            print(f"  {f}")

    # Verify we have the essential packages
    essential = {"python3.8", "python3.8-venv", "python3.8-minimal"}
    got = set()
    for f in downloaded:
        for pkg in essential:
            if f.startswith(pkg + "_"):
                got.add(pkg)

    missing_essential = essential - got
    if missing_essential:
        print(f"\nERROR: Missing essential packages: {missing_essential}")
        sys.exit(1)

    # Report total size
    total_bytes = sum((OUTPUT_DIR / f).stat().st_size for f in downloaded)
    print(f"\nTotal download size: {total_bytes // (1024*1024)} MB ({total_bytes // 1024} KB)")
    print(f"\nAll essential packages downloaded. Ready to bundle.")

if __name__ == "__main__":
    main()
