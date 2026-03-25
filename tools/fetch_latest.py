"""Fetch latest stable versions of Klipper, Moonraker, and Fluidd into the overlay.

Updates the vendored copies so the next build ships current releases.
Also updates the postinst SHA/version references automatically.

Klipper:   pulls latest from danthi123/klipper q1-pro branch.
Moonraker: pulls latest from Arksine/moonraker master (dev channel).
Fluidd:    downloads latest GitHub release (fluidd.zip).

Usage:
    python -m tools.fetch_latest [--klipper] [--moonraker] [--fluidd] [--all]
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OVERLAY = PROJECT_ROOT / "overlay"
POSTINST = OVERLAY / "control" / "postinst"


def _api_get(url: str) -> dict | list:
    """GET a GitHub API URL and return parsed JSON."""
    req = Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _clone_and_update(
    repo_url: str,
    branch: str,
    overlay_dir: Path,
    sha_pattern: str,
    version_pattern: str,
    postinst_text: str,
    label: str,
) -> tuple[str | None, str]:
    """Clone a git repo, update the overlay dir, and patch postinst.

    Returns (version_or_None, updated_postinst_text).
    """
    # Read current SHA from postinst
    current_sha_match = re.search(sha_pattern + r'"([^"]+)"', postinst_text)
    current_sha = current_sha_match.group(1) if current_sha_match else ""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        repo = tmp / "repo"

        # Shallow clone
        subprocess.run(
            ["git", "clone", "--depth=50", "--single-branch", "--branch", branch,
             repo_url, str(repo)],
            check=True, capture_output=True, text=True,
        )

        # Fetch tags for git describe
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "--tags"],
            check=True, capture_output=True, text=True,
        )

        # Get HEAD SHA
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        )
        new_sha = result.stdout.strip()

        if new_sha == current_sha:
            print(f"  {label} already at latest ({new_sha[:12]}), skipping")
            return None, postinst_text

        # Get version description
        result = subprocess.run(
            ["git", "-C", str(repo), "describe", "--tags", "--always"],
            check=True, capture_output=True, text=True,
        )
        version = result.stdout.strip()

        print(f"  Updating {label}: {current_sha[:12] or 'unknown'} -> {version} ({new_sha[:12]})")

        # Remove old overlay dir
        if overlay_dir.exists():
            shutil.rmtree(overlay_dir)

        # Copy new files (without .git)
        shutil.copytree(
            repo, overlay_dir,
            ignore=shutil.ignore_patterns(".git", ".github", "__pycache__"),
        )

    # Update postinst with new version and SHA
    postinst_text = re.sub(
        version_pattern + r'"[^"]+"',
        version_pattern + f'"{version}"',
        postinst_text,
    )
    postinst_text = re.sub(
        sha_pattern + r'"[^"]+"',
        sha_pattern + f'"{new_sha}"',
        postinst_text,
    )

    print(f"  {label} updated to {version}")
    return version, postinst_text


def fetch_klipper() -> str | None:
    """Fetch latest Klipper from the Q1Libre fork."""
    print("Fetching latest Klipper (q1-pro branch)...")
    postinst_text = POSTINST.read_text(encoding="utf-8")

    version, postinst_text = _clone_and_update(
        repo_url="https://github.com/danthi123/klipper.git",
        branch="q1-pro",
        overlay_dir=OVERLAY / "home" / "mks" / "klipper",
        sha_pattern='KLIPPER_SHA=',
        version_pattern='KLIPPER_VERSION=',
        postinst_text=postinst_text,
        label="Klipper",
    )

    if version:
        POSTINST.write_text(postinst_text, encoding="utf-8")
    return version


def fetch_moonraker() -> str | None:
    """Fetch latest Moonraker from upstream master."""
    print("Fetching latest Moonraker...")
    postinst_text = POSTINST.read_text(encoding="utf-8")

    version, postinst_text = _clone_and_update(
        repo_url="https://github.com/Arksine/moonraker.git",
        branch="master",
        overlay_dir=OVERLAY / "home" / "mks" / "moonraker",
        sha_pattern='VENDORED_SHA=',
        version_pattern='MOONRAKER_VERSION=',
        postinst_text=postinst_text,
        label="Moonraker",
    )

    if version:
        POSTINST.write_text(postinst_text, encoding="utf-8")
    return version


def fetch_fluidd() -> str | None:
    """Fetch latest stable Fluidd release into the overlay."""
    print("Fetching latest Fluidd release...")
    release = _api_get("https://api.github.com/repos/fluidd-core/fluidd/releases/latest")
    tag = release["tag_name"]

    fluidd_dir = OVERLAY / "home" / "mks" / "fluidd"

    # Check current version
    release_info = fluidd_dir / ".release_info" if fluidd_dir.exists() else None
    if release_info and release_info.exists():
        current = release_info.read_text().strip()
        if current == tag:
            print(f"  Fluidd already at {tag}, skipping")
            return None

    # Find the fluidd.zip asset
    zip_asset = None
    for asset in release.get("assets", []):
        if asset["name"] == "fluidd.zip":
            zip_asset = asset
            break

    if not zip_asset:
        print(f"  ERROR: No fluidd.zip found in release {tag}")
        return None

    print(f"  Downloading Fluidd {tag}...")
    req = Request(zip_asset["browser_download_url"])
    with urlopen(req, timeout=60) as resp:
        zip_data = resp.read()

    # Remove old fluidd
    if fluidd_dir.exists():
        shutil.rmtree(fluidd_dir)
    fluidd_dir.mkdir(parents=True)

    # Extract zip
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        zf.extractall(fluidd_dir)

    # Write version marker
    (fluidd_dir / ".release_info").write_text(tag)

    print(f"  Fluidd updated to {tag}")
    return tag


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch latest stable Klipper, Moonraker, and Fluidd into overlay."
    )
    parser.add_argument("--klipper", action="store_true", help="Update Klipper only")
    parser.add_argument("--moonraker", action="store_true", help="Update Moonraker only")
    parser.add_argument("--fluidd", action="store_true", help="Update Fluidd only")
    parser.add_argument("--all", action="store_true", help="Update all dependencies")
    args = parser.parse_args()

    # Default to --all if nothing specified
    if not args.klipper and not args.moonraker and not args.fluidd:
        args.all = True

    results = []
    if args.all or args.klipper:
        r = fetch_klipper()
        if r:
            results.append(f"Klipper {r}")
    if args.all or args.moonraker:
        r = fetch_moonraker()
        if r:
            results.append(f"Moonraker {r}")
    if args.all or args.fluidd:
        r = fetch_fluidd()
        if r:
            results.append(f"Fluidd {r}")

    if results:
        print(f"\nUpdated: {', '.join(results)}")
        print("Run `python -m tools.build` to build with new versions.")
    else:
        print("\nEverything up to date.")


if __name__ == "__main__":
    main()
