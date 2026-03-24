#!/usr/bin/env python3
"""
Scan Moonraker git history to find the last commit compatible with Python 3.7.
Python 3.8+ indicators: 'from __future__ import annotations', walrus ':='.
Run once to identify PINNED_SHA for vendor_moonraker.py.
Usage: python tools/find_moonraker_commit.py
Requires: git, internet access

Result: 6c27885702aefb8760780f2dcbcedda873c4b81f
  date:  2021-05-18 19:12:54 -0400
  msg:   file_manager: send "root_update" notification for all registered directories
  (next commit 96e6924 introduced 'from __future__ import annotations')
"""
import subprocess
import sys
import ast
import tempfile
import os
import re

REPO = "https://github.com/Arksine/moonraker.git"

# Walrus operator: identifier followed by :=  (not !=, <=, >=)
_WALRUS_RE = re.compile(r'[A-Za-z_]\w*\s*:=')


def has_py38_syntax(tmp: str, sha: str) -> bool:
    """Checkout sha and return True if any .py file in moonraker/ uses Python 3.8+ syntax."""
    subprocess.run(["git", "checkout", "--quiet", sha], cwd=tmp,
                   check=True, capture_output=True)
    mpath = os.path.join(tmp, "moonraker")
    if not os.path.isdir(mpath):
        return False  # moonraker/ subdir not present yet
    for root, _, files in os.walk(mpath):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            try:
                src = open(fp, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if "from __future__ import annotations" in src:
                return True
            if _WALRUS_RE.search(src):
                return True
            try:
                ast.parse(src)
            except SyntaxError:
                return True
    return False


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Cloning moonraker into {tmp}...")
        subprocess.run(["git", "clone", "--quiet", REPO, tmp], check=True)

        # Get all commits up to today, newest first
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=tmp, capture_output=True, text=True, check=True
        )
        commits = [line.split()[0] for line in result.stdout.strip().splitlines()]
        print(f"Binary searching {len(commits)} commits...")

        newest_bad = has_py38_syntax(tmp, commits[0])
        oldest_bad = has_py38_syntax(tmp, commits[-1])

        if not newest_bad:
            sha = commits[0]
        elif oldest_bad:
            print("ERROR: even the oldest commit has Python 3.8+ syntax.", file=sys.stderr)
            sys.exit(1)
        else:
            # Binary search: commits[lo] has py38, commits[hi] does not
            lo, hi = 0, len(commits) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if has_py38_syntax(tmp, commits[mid]):
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
