#!/usr/bin/env python3
"""
Download and vendor the pinned Moonraker release into overlay/home/mks/moonraker/.

The pinned SHA targets the latest Moonraker master at tool creation time.
To update: run this script again — it will re-fetch and update PINNED_SHA.

Usage:
    python tools/vendor_moonraker.py [--output PATH] [--update]
"""
import argparse
import json
import re
import shutil
import ssl
import sys
import tarfile
import urllib.request
from pathlib import Path

# Pinned Moonraker commit SHA — latest master at time of vendoring.
# Re-run this tool with --update to refresh to a newer commit.
PINNED_SHA = "4ba6fd228f264564f6613197fd9abb18ec068cf4"

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
GITHUB_API = "https://api.github.com/repos/Arksine/moonraker/commits/master"
GITHUB_TARBALL = "https://github.com/Arksine/moonraker/archive/{sha}.tar.gz"


def _safe_extractall(tf: tarfile.TarFile, dest: Path) -> None:
    for member in tf.getmembers():
        # Reject absolute paths and path traversal
        member_path = Path(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"Unsafe path in tarball: {member.name!r}")
    tf.extractall(dest)


def get_latest_sha() -> str:
    """Fetch the latest Moonraker master commit SHA from GitHub API."""
    print("Fetching latest Moonraker commit SHA from GitHub...")
    req = urllib.request.Request(
        GITHUB_API,
        headers={"Accept": "application/vnd.github.v3+json",
                 "User-Agent": "q1libre-vendor-tool"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    sha = data["sha"]
    msg = data["commit"]["message"].splitlines()[0]
    print(f"Latest: {sha[:12]} - {msg}")
    return sha


def vendor(sha: str, output: Path) -> None:
    import tempfile

    url = GITHUB_TARBALL.format(sha=sha)
    print(f"Downloading Moonraker {sha[:12]}...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tarball = tmp_path / "moonraker.tar.gz"

        # Atomic download using urlopen with explicit SSL context
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "q1libre-vendor-tool"}
        )
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            data = resp.read()
        tmp_dl = tarball.with_suffix(".tmp")
        try:
            tmp_dl.write_bytes(data)
            tmp_dl.rename(tarball)
        finally:
            if tmp_dl.exists():
                tmp_dl.unlink()

        print(f"Downloaded {tarball.stat().st_size // 1024} KB")

        # Extract
        with tarfile.open(tarball) as tf:
            _safe_extractall(tf, tmp_path)

        # GitHub tarballs extract to moonraker-<sha>/
        extracted = next(tmp_path.glob("moonraker-*"))

        # Remove .git if present
        git_dir = extracted / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        # Write to output, replacing existing
        if output.exists():
            print(f"Removing existing {output}")
            shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)

        for item in extracted.iterdir():
            dest = output / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        file_count = sum(1 for _ in output.rglob("*") if _.is_file())
        print(f"Vendored Moonraker {sha[:12]} -> {output} ({file_count} files)")


def update_pinned_sha(new_sha: str) -> None:
    """Update the PINNED_SHA constant in this file, preserving line endings."""
    this_file = Path(__file__)
    src = this_file.read_bytes().decode("utf-8")
    updated = re.sub(
        r'^(PINNED_SHA\s*=\s*)["\'].*?["\']',
        rf'\g<1>"{new_sha}"',
        src,
        count=1,
        flags=re.MULTILINE,
    )
    if updated == src:
        raise ValueError("PINNED_SHA pattern not found in source file")
    this_file.write_bytes(updated.encode("utf-8"))
    print(f"Updated PINNED_SHA in {this_file.name}")


def main():
    parser = argparse.ArgumentParser(description="Vendor pinned Moonraker release")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--update", action="store_true",
                        help="Fetch latest SHA and update PINNED_SHA constant")
    args = parser.parse_args()

    global PINNED_SHA

    if args.update or PINNED_SHA == "PLACEHOLDER":
        sha = get_latest_sha()
        update_pinned_sha(sha)
        PINNED_SHA = sha
    else:
        sha = PINNED_SHA

    vendor(sha, args.output)


if __name__ == "__main__":
    main()
