# Phase 2A: Moonraker Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the vendored Moonraker from July 2022 to the last Python 3.7-compatible commit (~early 2023), unlocking the update_manager UI and modern API endpoints.

**Architecture:** A new `tools/vendor_moonraker.py` script identifies and downloads the pinned Moonraker commit from GitHub, strips `.git/`, and places the tree in `overlay/home/mks/moonraker/`. The `overlay/control/postinst` gets a Moonraker upgrade block that backs up the existing install, chowns the new tree, and rebuilds pip dependencies before the existing service restart logic runs. The output `.deb` version bumps to `v0.2.0-phase2a`.

**Tech Stack:** Python 3.10+, GitHub archive API (tarball download, no git clone needed), ast module (Python 3.8 syntax check), pytest, existing `tools/build.py` / `tools/extract.py` / `tools/validate.py` pipeline.

---

### Task 1: Find the last Python 3.7-compatible Moonraker commit

**Files:**
- Create: `tools/find_moonraker_commit.py` (one-off research script, not shipped)

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""
Scan Moonraker git history to find the last commit compatible with Python 3.7.
Python 3.8+ indicators: 'from __future__ import annotations', walrus ':='.
Run once to identify PINNED_SHA for vendor_moonraker.py.
Usage: python tools/find_moonraker_commit.py
Requires: git, internet access
"""
import subprocess
import sys
import ast
import tempfile
import os

REPO = "https://github.com/Arksine/moonraker.git"
# Scan commits from 2023-01-01 to 2023-08-01 (safe window for Py3.7 compat)
SINCE = "2023-01-01"
UNTIL = "2023-08-01"

def has_py38_syntax(path: str) -> bool:
    """Return True if any .py file in path uses Python 3.8+ syntax."""
    for root, _, files in os.walk(path):
        for f in files:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(root, f)
            try:
                src = open(fp).read()
            except Exception:
                continue
            if "from __future__ import annotations" in src:
                return True
            if ":=" in src:
                return True
            # Try parsing with py37 ast (will raise on 3.8+ only syntax)
            try:
                ast.parse(src)
            except SyntaxError:
                return True
    return False

def main():
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Cloning moonraker into {tmp}...")
        subprocess.run(["git", "clone", "--quiet", REPO, tmp], check=True)
        # Get commits in the window, newest first
        result = subprocess.run(
            ["git", "log", "--oneline", f"--after={SINCE}", f"--before={UNTIL}"],
            cwd=tmp, capture_output=True, text=True, check=True
        )
        commits = [line.split()[0] for line in result.stdout.strip().splitlines()]
        print(f"Scanning {len(commits)} commits...")
        for sha in commits:
            subprocess.run(["git", "checkout", "--quiet", sha], cwd=tmp, check=True)
            if not has_py38_syntax(os.path.join(tmp, "moonraker")):
                print(f"\nLast Python 3.7-compatible commit: {sha}")
                # Print full SHA
                full = subprocess.run(
                    ["git", "rev-parse", sha], cwd=tmp,
                    capture_output=True, text=True
                ).stdout.strip()
                print(f"Full SHA: {full}")
                return
        print("No compatible commit found in window — widen the range.")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Step 2: Run it**

```bash
cd E:/Projects/q1libre
python tools/find_moonraker_commit.py
```

Expected output:
```
Cloning moonraker into /tmp/...
Scanning N commits...

Last Python 3.7-compatible commit: abc1234
Full SHA: abc1234...
```

**Step 3: Note the full SHA** — you'll hardcode it in Task 2.

**Step 4: Commit the research script**

```bash
git add tools/find_moonraker_commit.py
git commit -m "tools: add moonraker commit finder (research script)"
```

---

### Task 2: Create tools/vendor_moonraker.py

**Files:**
- Create: `tools/vendor_moonraker.py`
- Create: `tests/test_vendor_moonraker.py`

The vendor tool downloads the pinned Moonraker tarball from GitHub, extracts it, and writes it to `overlay/home/mks/moonraker/`. It also validates that the vendored tree has no Python 3.8+ syntax.

**Step 1: Write the failing tests**

```python
# tests/test_vendor_moonraker.py
import subprocess
import sys
import os
import ast
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent

def test_vendor_tool_exists():
    """vendor_moonraker.py must exist before we can run it."""
    assert (PROJECT_ROOT / "tools" / "vendor_moonraker.py").exists()

def test_pinned_sha_constant():
    """PINNED_SHA must be a 40-char hex string."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "vendor_moonraker",
        PROJECT_ROOT / "tools" / "vendor_moonraker.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sha = mod.PINNED_SHA
    assert isinstance(sha, str)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha.lower())

def test_no_py38_syntax_in_vendored_tree():
    """Vendored moonraker must be Python 3.7-compatible."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present — run vendor_moonraker.py first")
    violations = []
    for py_file in moonraker_dir.rglob("*.py"):
        src = py_file.read_text(errors="replace")
        if "from __future__ import annotations" in src:
            violations.append(str(py_file))
            continue
        if ":=" in src:
            violations.append(str(py_file))
            continue
        try:
            ast.parse(src)
        except SyntaxError:
            violations.append(str(py_file))
    assert violations == [], f"Python 3.8+ syntax found in: {violations}"

def test_vendored_tree_has_expected_structure():
    """Vendored moonraker must have moonraker/ and scripts/ subdirectories."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present")
    assert (moonraker_dir / "moonraker").is_dir(), "Missing moonraker/ subdir"
    assert (moonraker_dir / "scripts").is_dir(), "Missing scripts/ subdir"
    assert (moonraker_dir / "moonraker" / "moonraker.py").exists(), "Missing moonraker.py"

def test_no_dot_git_in_vendored_tree():
    """Vendored tree must not contain .git directory."""
    moonraker_dir = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored tree not yet present")
    assert not (moonraker_dir / ".git").exists(), ".git must be stripped"
```

**Step 2: Run tests to verify they fail**

```bash
cd E:/Projects/q1libre
pytest tests/test_vendor_moonraker.py -v
```

Expected: `test_vendor_tool_exists` FAILS with AssertionError (file doesn't exist yet).

**Step 3: Write tools/vendor_moonraker.py**

Replace `PINNED_SHA` with the full 40-char SHA you found in Task 1.

```python
#!/usr/bin/env python3
"""
Download and vendor the pinned Moonraker release into overlay/home/mks/moonraker/.

Usage:
    python tools/vendor_moonraker.py [--output PATH]

The vendored tree is committed to the Q1Libre repo so builds are reproducible
and require no internet access at build time or on the printer.
"""
import argparse
import ast
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

# Last Python 3.7-compatible Moonraker commit.
# Identified by tools/find_moonraker_commit.py — do not change without re-running.
PINNED_SHA = "REPLACE_WITH_FULL_40_CHAR_SHA_FROM_TASK_1"

GITHUB_TARBALL = f"https://github.com/Arksine/moonraker/archive/{PINNED_SHA}.tar.gz"
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "overlay" / "home" / "mks" / "moonraker"


def check_py37_compat(path: Path) -> list[str]:
    """Return list of files with Python 3.8+ syntax."""
    violations = []
    for py_file in path.rglob("*.py"):
        src = py_file.read_text(errors="replace")
        if "from __future__ import annotations" in src:
            violations.append(str(py_file))
            continue
        if ":=" in src:
            violations.append(str(py_file))
            continue
        try:
            ast.parse(src)
        except SyntaxError:
            violations.append(str(py_file))
    return violations


def vendor(output: Path) -> None:
    import tempfile

    print(f"Downloading Moonraker {PINNED_SHA[:12]}...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tarball = tmp_path / "moonraker.tar.gz"

        # Download
        urllib.request.urlretrieve(GITHUB_TARBALL, tarball)
        print(f"Downloaded {tarball.stat().st_size // 1024} KB")

        # Extract
        with tarfile.open(tarball) as tf:
            tf.extractall(tmp_path)

        # GitHub tarballs extract to moonraker-<sha>/
        extracted = next(tmp_path.glob("moonraker-*"))

        # Remove .git if present (shouldn't be in tarball, but be safe)
        git_dir = extracted / ".git"
        if git_dir.exists():
            shutil.rmtree(git_dir)

        # Validate Python 3.7 compatibility
        violations = check_py37_compat(extracted / "moonraker")
        if violations:
            print("ERROR: Python 3.8+ syntax found:")
            for v in violations:
                print(f"  {v}")
            sys.exit(1)

        # Write to output, replacing existing
        if output.exists():
            print(f"Removing existing {output}")
            shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)

        # Copy contents of extracted/ into output/
        for item in extracted.iterdir():
            dest = output / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        print(f"Vendored Moonraker {PINNED_SHA[:12]} → {output}")
        print(f"Files: {sum(1 for _ in output.rglob('*'))}")


def main():
    parser = argparse.ArgumentParser(description="Vendor pinned Moonraker release")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})"
    )
    args = parser.parse_args()
    vendor(args.output)


if __name__ == "__main__":
    main()
```

**Step 4: Run the tests**

```bash
pytest tests/test_vendor_moonraker.py::test_vendor_tool_exists \
       tests/test_vendor_moonraker.py::test_pinned_sha_constant -v
```

Expected: Both PASS. (The vendored-tree tests will still skip — that's correct.)

**Step 5: Commit**

```bash
git add tools/vendor_moonraker.py tests/test_vendor_moonraker.py
git commit -m "feat: add vendor_moonraker tool with Python 3.7 compat check"
```

---

### Task 3: Run the vendor tool and commit the vendored tree

**Files:**
- Create: `overlay/home/mks/moonraker/` (entire tree, ~500 files)

**Step 1: Run the vendor tool**

```bash
cd E:/Projects/q1libre
python tools/vendor_moonraker.py
```

Expected output:
```
Downloading Moonraker abc1234...
Downloaded XXXX KB
Vendored Moonraker abc1234 → .../overlay/home/mks/moonraker
Files: ~500
```

**Step 2: Run the vendored-tree tests**

```bash
pytest tests/test_vendor_moonraker.py -v
```

Expected: All 4 tests PASS (including the previously-skipped tree structure and syntax tests).

**Step 3: Check what was created**

```bash
ls overlay/home/mks/moonraker/
```

Expected: `moonraker/`, `scripts/`, `README.md`, etc. — no `.git/`.

**Step 4: Commit the vendored tree**

```bash
git add overlay/home/mks/moonraker/
git commit -m "vendor: moonraker pinned at <first 12 chars of SHA>"
```

Note: this commit will be large (~500 files). That's expected and intentional.

---

### Task 4: Update postinst with Moonraker upgrade block

**Files:**
- Modify: `overlay/control/postinst` (insert before line ~178, before the service restart block)

**Step 1: Write the failing test**

Add to `tests/test_postinst.py` (create if it doesn't exist):

```python
# tests/test_postinst.py
from pathlib import Path
import pytest

POSTINST = Path(__file__).parent.parent / "overlay" / "control" / "postinst"

def read_postinst() -> str:
    return POSTINST.read_text()

def test_postinst_backs_up_moonraker():
    """postinst must back up existing moonraker before replacing it."""
    src = read_postinst()
    assert "moonraker.bak" in src, "postinst must create moonraker.bak backup"

def test_postinst_chowns_new_moonraker():
    """postinst must chown the new moonraker tree to mks:mks."""
    src = read_postinst()
    assert "chown -R mks:mks /home/mks/moonraker" in src

def test_postinst_rebuilds_moonraker_venv():
    """postinst must pip install new moonraker requirements."""
    src = read_postinst()
    assert "moonraker-requirements.txt" in src
    assert "pip install" in src

def test_postinst_moonraker_upgrade_before_restart():
    """Moonraker upgrade block must come before the service restart block."""
    src = read_postinst()
    backup_pos = src.find("moonraker.bak")
    restart_pos = src.find("systemctl restart moonraker.service")
    assert backup_pos != -1, "backup step not found"
    assert restart_pos != -1, "restart step not found"
    assert backup_pos < restart_pos, "upgrade block must precede service restart"
```

**Step 2: Run the tests to verify they fail**

```bash
pytest tests/test_postinst.py -v
```

Expected: All 4 tests FAIL (upgrade block doesn't exist yet).

**Step 3: Edit overlay/control/postinst**

Insert the following block just before the `#重启各类服务令` comment (around line 178). Find the exact location with:

```bash
grep -n "重启各类服务令" overlay/control/postinst
```

Insert this block immediately before that line:

```bash
# Q1Libre Phase 2A: Upgrade Moonraker to pinned version
echo "Q1Libre: upgrading Moonraker..."

# Back up existing moonraker for rollback
if [ -d /home/mks/moonraker ]; then
    rm -rf /home/mks/moonraker.bak
    cp -a /home/mks/moonraker /home/mks/moonraker.bak
    echo "Q1Libre: moonraker backed up to /home/mks/moonraker.bak"
fi

# New moonraker tree is installed by dpkg from overlay/home/mks/moonraker/
chown -R mks:mks /home/mks/moonraker

# Rebuild venv dependencies for new moonraker version
if [ -f /home/mks/moonraker/scripts/moonraker-requirements.txt ]; then
    echo "Q1Libre: updating moonraker pip dependencies..."
    sudo -u mks /home/mks/moonraker-env/bin/pip install \
        -r /home/mks/moonraker/scripts/moonraker-requirements.txt \
        --quiet 2>/dev/null || true
fi
```

**Step 4: Run the tests**

```bash
pytest tests/test_postinst.py -v
```

Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add overlay/control/postinst tests/test_postinst.py
git commit -m "feat: add moonraker upgrade block to postinst"
```

---

### Task 5: Bump version to v0.2.0-phase2a

**Files:**
- Modify: `tools/build.py` or wherever the default version string is defined

**Step 1: Find where the version is set**

```bash
grep -rn "v0.1.0\|phase1\|version" tools/build.py | head -20
```

**Step 2: Write the failing test**

Add to `tests/test_build.py`:

```python
def test_phase2a_version_string():
    """Default build version must reflect Phase 2A."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build", Path(__file__).parent.parent / "tools" / "build.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "DEFAULT_VERSION"), "build.py must have DEFAULT_VERSION"
    assert "0.2.0" in mod.DEFAULT_VERSION or "phase2a" in mod.DEFAULT_VERSION
```

**Step 3: Run the test to verify it fails**

```bash
pytest tests/test_build.py::test_phase2a_version_string -v
```

Expected: FAIL.

**Step 4: Update the version in tools/build.py**

Find the `DEFAULT_VERSION` constant (or equivalent) and change it from `"0.1.0"` to `"0.2.0-phase2a"`.

**Step 5: Run the test**

```bash
pytest tests/test_build.py::test_phase2a_version_string -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add tools/build.py tests/test_build.py
git commit -m "feat: bump version to v0.2.0-phase2a"
```

---

### Task 6: Integration test — moonraker lands in built .deb

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Write the failing test**

Add to `tests/test_integration.py`:

```python
def test_moonraker_in_built_deb(tmp_path, stock_deb):
    """Built deb must contain the upgraded moonraker tree."""
    # Build
    output_deb = tmp_path / "q1libre-test.deb"
    result = subprocess.run(
        [sys.executable, "-m", "tools.build",
         "--base", str(BASE_DIR),
         "--overlay", str(OVERLAY_DIR),
         "-o", str(output_deb)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

    # Re-extract and check moonraker is present
    from tools.extract import extract_deb
    extracted = tmp_path / "extracted"
    extract_deb(output_deb, extracted)

    moonraker_py = extracted / "data" / "home" / "mks" / "moonraker" / "moonraker" / "moonraker.py"
    assert moonraker_py.exists(), "moonraker.py must be present in built deb"

def test_moonraker_version_newer_than_stock(tmp_path, stock_deb):
    """Vendored moonraker must be newer than stock (July 2022)."""
    moonraker_dir = OVERLAY_DIR / "home" / "mks" / "moonraker"
    if not moonraker_dir.exists():
        pytest.skip("Vendored moonraker not present")
    # Check for features that didn't exist in July 2022 Moonraker
    # update_manager endpoint was added later
    app_py = moonraker_dir / "moonraker" / "app.py"
    assert app_py.exists()
    src = app_py.read_text()
    assert "update_manager" in src.lower(), "Newer Moonraker must have update_manager"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_integration.py::test_moonraker_in_built_deb \
       tests/test_integration.py::test_moonraker_version_newer_than_stock -v
```

Expected: FAIL (or skip if no stock deb present — that's fine, integration tests need stock deb).

**Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All non-integration tests PASS. Integration tests PASS if stock deb is present at `stock/QD_Q1_SOC`, skip otherwise.

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration tests for moonraker upgrade in built deb"
```

---

### Task 7: Build and validate the Phase 2A .deb

**Files:**
- Output: `dist/q1libre-v0.2.0-phase2a.deb`

**Step 1: Run the full build**

```bash
cd E:/Projects/q1libre
python -m tools.build \
    --base base/ \
    --overlay overlay/ \
    --version 0.2.0-phase2a \
    -o dist/q1libre-v0.2.0-phase2a.deb
```

Expected output:
```
Building q1libre v0.2.0-phase2a...
Applying overlays...
control.tar.xz: XXX KB
data.tar.xz: XX MB  ← larger than Phase 1 due to moonraker tree
Output: dist/q1libre-v0.2.0-phase2a.deb (XX MB)
```

**Step 2: Validate the .deb**

```bash
python -m tools.validate dist/q1libre-v0.2.0-phase2a.deb
```

Expected: `Validation passed`

**Step 3: Verify moonraker is in the deb**

```bash
python -c "
from tools.deb import parse_deb
from pathlib import Path
import tarfile, io
deb = parse_deb(Path('dist/q1libre-v0.2.0-phase2a.deb'))
with tarfile.open(fileobj=io.BytesIO(deb['data'])) as tf:
    moonraker_files = [m for m in tf.getnames() if 'moonraker/moonraker.py' in m]
    print('moonraker.py found:', moonraker_files)
"
```

Expected: prints `moonraker.py found: ['./home/mks/moonraker/moonraker/moonraker.py']`

**Step 4: Commit the built deb**

```bash
git add dist/q1libre-v0.2.0-phase2a.deb
git commit -m "release: v0.2.0-phase2a Moonraker upgrade"
```

---

## On-Printer Smoke Test Checklist

After flashing `dist/q1libre-v0.2.0-phase2a.deb` via USB:

```bash
# 1. Moonraker is running
systemctl status moonraker

# 2. New version string
curl -s http://localhost:7125/server/info | python3 -m json.tool | grep version

# 3. Update manager endpoint now exists (was 404 before)
curl -s http://localhost:7125/machine/update/status | python3 -m json.tool

# 4. Backup exists
ls -la /home/mks/moonraker.bak/
```

## Rollback If Moonraker Fails

```bash
sudo systemctl stop moonraker
rm -rf /home/mks/moonraker
mv /home/mks/moonraker.bak /home/mks/moonraker
sudo systemctl start moonraker
```
