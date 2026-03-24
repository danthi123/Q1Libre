"""Download all Klipper Python wheels for offline installation.

Downloads pre-built wheels (and sdists where no wheel exists) for all
packages in klippy-requirements.txt, targeting Python 3.7 on aarch64
(Debian Buster, glibc 2.28).  Also bundles pip and setuptools for
bootstrapping the virtualenv.

Usage:
    python -m tools.download_wheels [--output DIR]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Where wheels land inside the overlay (shipped in the .deb)
DEFAULT_OUTPUT = Path("overlay/root/klippy-wheels")

# ---------- Package lists ----------
# Bootstrap packages (installed FIRST so pip can handle manylinux wheels)
BOOTSTRAP_PACKAGES = [
    # pip 23.2.1 is the last version supporting Python 3.7
    "pip>=23,<23.3",
    # setuptools 67.8.0 is the last version supporting Python 3.7
    "setuptools>=67,<68",
]

# Klipper klippy-requirements.txt for Python 3.7 on aarch64
KLIPPY_PACKAGES_WHEEL = [
    # greenlet — native, needs cp37 aarch64
    "greenlet==2.0.2",
    # cffi — native, needs cp37 aarch64
    "cffi==1.14.6",
    # pycparser — pure Python
    "pycparser",
    # Jinja2 — pure Python
    "Jinja2==2.11.3",
    # markupsafe — native, needs cp37 aarch64
    "markupsafe==1.1.1",
    # pyserial — pure Python
    "pyserial==3.4",
    # wrapt — native, needs cp37 aarch64
    "wrapt",
    # aenum — pure Python
    "aenum",
    # numpy — native, needed for input shaper calibration
    "numpy==1.21.6",
    # scipy — native, needed for trigger_analog and advanced signal processing
    "scipy==1.7.3",
]

# Packages that only have sdist (no wheel) on PyPI for this platform
KLIPPY_PACKAGES_SDIST = [
    "python-can==3.3.4",
]

# Platform tags we accept for native (compiled) wheels
PLATFORM_TAGS = [
    "manylinux2014_aarch64",
    "manylinux_2_17_aarch64",
]


def _pip_download(
    specs: list[str],
    dest: Path,
    *,
    only_binary: bool = True,
    platform: str | None = None,
) -> None:
    """Run pip download for a list of package specs."""
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--no-deps",
        "--dest", str(dest),
    ]
    if only_binary:
        cmd += ["--only-binary=:all:"]
        if platform:
            cmd += [
                "--platform", platform,
                "--python-version", "37",
                "--implementation", "cp",
                "--abi", "cp37m",
            ]
    else:
        # sdist download — no platform filter
        cmd += ["--no-binary=:all:"]

    cmd += specs
    print(f"  Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)


def download_wheels(output_dir: Path) -> None:
    """Download all required wheels and sdists into *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clear old wheels
    for f in output_dir.iterdir():
        if f.suffix in (".whl", ".gz"):
            f.unlink()
            print(f"  Removed old: {f.name}")

    print("=== Downloading bootstrap packages (pip, setuptools) ===")
    # These are pure-python, download as py3-none-any
    _pip_download(BOOTSTRAP_PACKAGES, output_dir, only_binary=True, platform=None)

    print("\n=== Downloading klippy wheels (native aarch64) ===")
    # Try manylinux2014 first, then manylinux_2_17
    for pkg in KLIPPY_PACKAGES_WHEEL:
        downloaded = False
        for plat in PLATFORM_TAGS:
            try:
                _pip_download([pkg], output_dir, only_binary=True, platform=plat)
                downloaded = True
                break
            except subprocess.CalledProcessError:
                continue
        if not downloaded:
            # Try pure-python (no platform constraint)
            print(f"  No native wheel for {pkg}, trying pure-python...")
            _pip_download([pkg], output_dir, only_binary=True, platform=None)

    print("\n=== Downloading sdist packages ===")
    for pkg in KLIPPY_PACKAGES_SDIST:
        _pip_download([pkg], output_dir, only_binary=False)

    print("\n=== Downloaded wheels ===")
    for f in sorted(output_dir.iterdir()):
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Klipper wheels for offline install.")
    parser.add_argument(
        "--output", "-o",
        default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    download_wheels(Path(args.output))


if __name__ == "__main__":
    main()
