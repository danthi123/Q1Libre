#!/usr/bin/env python3
"""
Scan Moonraker git history to find the last commit compatible with Python 3.7.
Python 3.8+ indicators: walrus operator ':=' in non-comment code lines.
Note: 'from __future__ import annotations' is 3.7+ compatible (PEP 563), NOT 3.8+.
Run once to identify PINNED_SHA for vendor_moonraker.py.
Usage: python tools/find_moonraker_commit.py
Requires: git, internet access
"""
import subprocess
import sys
import tempfile
import os

REPO = "https://github.com/Arksine/moonraker.git"
SINCE = "2022-01-01"
UNTIL = "2023-12-01"


def has_py38_syntax(path: str) -> bool:
    """Return True if any .py file in path uses Python 3.8+ syntax.

    Reliable 3.8+ indicators:
    - Walrus operator ':=' in non-comment code lines
    - Note: 'from __future__ import annotations' is 3.7+ compatible (PEP 563), NOT 3.8+
    """
    for root, _, files in os.walk(path):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            try:
                lines = open(fp).readlines()
            except Exception:
                continue
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Walrus operator — true 3.8+ syntax
                if ":=" in stripped:
                    return True
    return False


def checkout_sha(tmp: str, sha: str) -> None:
    subprocess.run(["git", "checkout", "--quiet", sha], cwd=tmp,
                   check=True, capture_output=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Cloning moonraker into {tmp}...")
        subprocess.run(["git", "clone", "--quiet", REPO, tmp], check=True)

        # Get commits in the scan window, newest first
        result = subprocess.run(
            ["git", "log", "--oneline",
             f"--after={SINCE}", f"--before={UNTIL}"],
            cwd=tmp, capture_output=True, text=True, check=True
        )
        commits = [line.split()[0] for line in result.stdout.strip().splitlines()]
        if not commits:
            print("ERROR: no commits found in the specified date range.", file=sys.stderr)
            sys.exit(1)
        print(f"Binary searching {len(commits)} commits ({SINCE} to {UNTIL})...")

        def check(sha: str) -> bool:
            checkout_sha(tmp, sha)
            mpath = os.path.join(tmp, "moonraker")
            if not os.path.isdir(mpath):
                return False
            return has_py38_syntax(mpath)

        newest_bad = check(commits[0])
        oldest_bad = check(commits[-1])

        if not newest_bad:
            sha = commits[0]
        elif oldest_bad:
            print("ERROR: even the oldest commit in range has Python 3.8+ syntax.", file=sys.stderr)
            sys.exit(1)
        else:
            # Binary search: commits[lo] has py38, commits[hi] does not
            lo, hi = 0, len(commits) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if check(commits[mid]):
                    lo = mid
                else:
                    hi = mid
            sha = commits[hi]

        full = subprocess.run(
            ["git", "rev-parse", sha], cwd=tmp,
            capture_output=True, text=True
        ).stdout.strip()
        msg = subprocess.run(
            ["git", "log", "-1", "--format=%s", sha], cwd=tmp,
            capture_output=True, text=True
        ).stdout.strip()
        date = subprocess.run(
            ["git", "log", "-1", "--format=%ci", sha], cwd=tmp,
            capture_output=True, text=True
        ).stdout.strip()

        print(f"\nLast Python 3.7-compatible commit: {sha}")
        print(f"Full SHA: {full}")
        print(f"Date:     {date}")
        print(f"Message:  {msg}")


if __name__ == "__main__":
    main()
