# Phase 1 Additional Patches — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add all agreed safe Phase 1 patches to Q1Libre: fix postinst security issues, expand Moonraker update_manager, add mks shell QoL aliases, and add a patched sudoers — bundled into the first real test build.

**Architecture:** The build pipeline applies `overlay/` files on top of `base/data/` during the build. Currently `control/` files (like `postinst`) are not overlayable. We extend `build.py` to also honour an `overlay/control/` directory, then place a patched `postinst` there. All other patches are pure overlay file additions. No Klipper source, no xindi, no boot chain touched.

**Tech Stack:** Python 3.10+, pytest, shell scripts (postinst/bashrc), Moonraker config (INI-like), Klipper config syntax. Run tests with `pytest tests/ -v`.

---

## Task 1: Extend build.py to support `overlay/control/` files

Right now `build.py` only overlays into `work/data/`. We need it to also check `overlay/control/` and copy matching files into `work/control/`, so we can ship a patched `postinst` without touching `base/`.

**Files:**
- Modify: `tools/build.py`
- Modify: `tests/test_build.py`

**Step 1: Write the failing test**

Add this test to `tests/test_build.py`:

```python
def test_control_overlay_applied():
    """Files in overlay/control/ must override base/control/ files in built deb."""
    import lzma, tarfile, io
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        base = tmp / "base"
        overlay = tmp / "overlay"
        output = tmp / "dist" / "QD_Q1_SOC"

        # Minimal base
        ctrl = base / "control"
        ctrl.mkdir(parents=True)
        (ctrl / "control").write_text("Package: qd-q1-soc\nVersion: 4.4.24\n")
        (ctrl / "postinst").write_text("#!/bin/sh\n# STOCK postinst\nexit 0\n")

        data = base / "data"
        version_dir = data / "root" / "xindi"
        version_dir.mkdir(parents=True)
        (version_dir / "version").write_text(
            "[version]\nmcu = V0.10.0\nui = V4.4.24\nsoc = V4.4.24\n"
        )
        (base / "debian-binary").write_text("2.0\n")

        # Control overlay — patched postinst
        ctrl_overlay = overlay / "control"
        ctrl_overlay.mkdir(parents=True)
        (ctrl_overlay / "postinst").write_text("#!/bin/sh\n# Q1LIBRE patched postinst\nexit 0\n")

        output.parent.mkdir(parents=True)
        build_firmware(base, overlay, tmp / "patches", output, version="0.1.0")

        assert output.exists()

        # Extract and inspect the built deb's postinst
        from tools.deb import parse_deb
        parts = parse_deb(output.read_bytes())
        with lzma.open(io.BytesIO(parts["control.tar.xz"])) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                postinst_member = tf.getmember("./postinst")
                content = tf.extractfile(postinst_member).read().decode()
        assert "Q1LIBRE patched postinst" in content
        assert "STOCK postinst" not in content
```

**Step 2: Run test to verify it fails**

```
cd E:/Projects/q1libre
pytest tests/test_build.py::test_control_overlay_applied -v
```

Expected: `FAIL` — `AssertionError` because built postinst still contains `STOCK postinst`.

**Step 3: Implement control overlay support in `tools/build.py`**

Find the section in `build_firmware()` that applies overlays. After the loop that copies `overlay/` files into `work/data/`, add a parallel loop for `overlay/control/`:

```python
# Apply control overlays (overlay/control/ → work/control/)
control_overlay = overlay_dir / "control"
if control_overlay.is_dir():
    for src in control_overlay.rglob("*"):
        if src.is_file():
            rel = src.relative_to(control_overlay)
            dst = work_control / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
```

This must come **after** `work_control` is populated from `base/control/` and **before** the tar step.

**Step 4: Run test to verify it passes**

```
pytest tests/test_build.py::test_control_overlay_applied -v
```

Expected: `PASS`

**Step 5: Run full test suite to check no regressions**

```
pytest tests/ -v
```

Expected: all existing tests pass.

**Step 6: Commit**

```bash
git add tools/build.py tests/test_build.py
git commit -m "feat: support overlay/control/ for patching postinst and other control files"
```

---

## Task 2: Create patched `postinst` in `overlay/control/postinst`

Three security/correctness fixes in one shot:
1. Replace `chmod 777 -R /home/mks/klipper_config` with proper permissions
2. Remove the hardcoded Cloudflare DNS override (`cp resolv.conf`)
3. Remove the IPv6 disable (`cat sysctl.conf > /etc/sysctl.conf`)

**Files:**
- Create: `overlay/control/postinst`
- Modify: `tests/test_build.py` (add content validation test)

**Step 1: Write the failing test**

Add to `tests/test_build.py`:

```python
def test_patched_postinst_content():
    """The real overlay/control/postinst must not contain chmod 777, resolv.conf override, or IPv6 disable."""
    postinst = Path("overlay/control/postinst")
    assert postinst.exists(), "overlay/control/postinst must exist"
    content = postinst.read_text()
    assert "chmod 777" not in content, "chmod 777 must be removed"
    assert "resolv.conf" not in content, "hardcoded DNS override must be removed"
    assert "sysctl.conf" not in content, "IPv6 disable must be removed"
    assert "chmod 755" in content or "chmod 644" in content, "proper permissions must be set"
```

**Step 2: Run test to verify it fails**

```
pytest tests/test_build.py::test_patched_postinst_content -v
```

Expected: `FAIL` — `overlay/control/postinst` does not exist yet.

**Step 3: Create `overlay/control/postinst`**

Copy the stock `base/control/postinst` as the starting point, then apply these three changes:

**Change A — Replace `chmod 777 -R` block (around line 164):**

Remove:
```bash
#修改文件权限
chmod 777 -R /home/mks/klipper_config
chmod 700 /root/xindi/build/xindi
chown -R mks:mks /home/mks/klipper/
chown mks:mks /home/mks/klipper_config/gcode_macro.cfg
chown mks:mks /home/mks/klipper_config/printer.cfg
chmod 700 /usr/bin/makerbase-automount
```

Replace with:
```bash
#修改文件权限 (Q1Libre: fixed permissions - removed chmod 777 spray)
find /home/mks/klipper_config -type d -exec chmod 755 {} \;
find /home/mks/klipper_config -type f -exec chmod 644 {} \;
chmod 700 /root/xindi/build/xindi
chown -R mks:mks /home/mks/klipper/
chown -R mks:mks /home/mks/klipper_config/
chmod 700 /usr/bin/makerbase-automount
```

**Change B — Remove the hardcoded DNS override (around line 161):**

Remove this line:
```bash
cp -fp /root/etc/resolv.conf /etc/resolv.conf # 添加cloudfare dns server作为首选项
```

Keep the lines before/after it intact. The device tree and udev rule copies above it are fine.

**Change C — Remove the IPv6 disable (around line 172):**

Remove this line:
```bash
#禁用IPV6
cat /root/sysctl.conf > /etc/sysctl.conf
```

**Change D — Add Q1Libre marker install** (add before the service restart block):
```bash
# Q1Libre: install version marker
if [ -f /root/q1libre_version.txt ]; then
    echo "Q1Libre firmware installed" >> /var/log/q1libre_install.log
    echo "  Version: $(cat /root/q1libre_version.txt)" >> /var/log/q1libre_install.log
    echo "  Date: $(date)" >> /var/log/q1libre_install.log
fi
```

**Step 4: Run test to verify it passes**

```
pytest tests/test_build.py::test_patched_postinst_content -v
```

Expected: `PASS`

**Step 5: Run full suite**

```
pytest tests/ -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add overlay/control/postinst tests/test_build.py
git commit -m "fix: replace chmod 777 spray with proper permissions, remove hardcoded DNS and IPv6 disable"
```

---

## Task 3: Add Mainsail to Moonraker `update_manager`

The existing `overlay/home/mks/klipper_config/moonraker.conf` already has Fluidd. Add Mainsail so users who prefer Mainsail also get update tracking.

**Files:**
- Modify: `overlay/home/mks/klipper_config/moonraker.conf`
- Modify: `tests/test_build.py`

**Step 1: Write the failing test**

Add to `tests/test_build.py`:

```python
def test_moonraker_has_mainsail_update_manager():
    """overlay moonraker.conf must include an [update_manager mainsail] section."""
    moonraker = Path("overlay/home/mks/klipper_config/moonraker.conf")
    assert moonraker.exists()
    content = moonraker.read_text()
    assert "[update_manager mainsail]" in content
    assert "mainsail-crew/mainsail" in content
```

**Step 2: Run test to verify it fails**

```
pytest tests/test_build.py::test_moonraker_has_mainsail_update_manager -v
```

Expected: `FAIL`

**Step 3: Add Mainsail section to `overlay/home/mks/klipper_config/moonraker.conf`**

After the existing `[update_manager fluidd]` block (after line 53), add:

```ini
[update_manager mainsail]
type: web
channel: stable
repo: mainsail-crew/mainsail
path: ~/mainsail
```

**Step 4: Run test to verify it passes**

```
pytest tests/test_build.py::test_moonraker_has_mainsail_update_manager -v
```

Expected: `PASS`

**Step 5: Commit**

```bash
git add overlay/home/mks/klipper_config/moonraker.conf tests/test_build.py
git commit -m "feat: add Mainsail to moonraker update_manager"
```

---

## Task 4: Add mks user shell QoL aliases

A `.bashrc` overlay for the `mks` user with aliases for the most common debugging tasks: tailing logs and restarting services.

**Files:**
- Create: `overlay/home/mks/.bashrc`
- Modify: `tests/test_build.py`

**Step 1: Write the failing test**

Add to `tests/test_build.py`:

```python
def test_mks_bashrc_has_aliases():
    """overlay .bashrc must define klog, mlog, and krestart aliases."""
    bashrc = Path("overlay/home/mks/.bashrc")
    assert bashrc.exists(), "overlay/home/mks/.bashrc must exist"
    content = bashrc.read_text()
    assert "klog" in content
    assert "mlog" in content
    assert "krestart" in content
```

**Step 2: Run test to verify it fails**

```
pytest tests/test_build.py::test_mks_bashrc_has_aliases -v
```

Expected: `FAIL` — file does not exist.

**Step 3: Create `overlay/home/mks/.bashrc`**

```bash
# Q1Libre .bashrc for mks user
# Sourced for interactive shells

# Source system bashrc if it exists
if [ -f /etc/bash.bashrc ]; then
    . /etc/bash.bashrc
fi

# Source system profile
if [ -f /etc/profile ]; then
    . /etc/profile
fi

# ── Q1Libre aliases ──────────────────────────────────────────────────────────

# Tail the Klipper log (last 50 lines, follow)
alias klog='tail -n 50 -f ~/klipper_logs/klippy.log'

# Tail the Moonraker log (last 50 lines, follow)
alias mlog='tail -n 50 -f ~/klipper_logs/moonraker.log'

# Restart Klipper service
alias krestart='sudo systemctl restart klipper.service && echo "Klipper restarted"'

# Restart Moonraker service
alias mrestart='sudo systemctl restart moonraker.service && echo "Moonraker restarted"'

# Restart both Klipper and Moonraker
alias kmrestart='sudo systemctl restart klipper.service moonraker.service && echo "Klipper + Moonraker restarted"'

# Show Q1Libre status
alias q1status='/root/scripts/q1libre_info.sh'

# Show printer config directory
alias cdcfg='cd ~/klipper_config && ls'

# ── Prompt ───────────────────────────────────────────────────────────────────
PS1='\[\e[1;32m\]\u@\h\[\e[0m\]:\[\e[1;34m\]\w\[\e[0m\]\$ '

export PATH="$PATH:/home/mks/.local/bin"
```

**Step 4: Run test to verify it passes**

```
pytest tests/test_build.py::test_mks_bashrc_has_aliases -v
```

Expected: `PASS`

**Step 5: Run full suite**

```
pytest tests/ -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add overlay/home/mks/.bashrc tests/test_build.py
git commit -m "feat: add mks user .bashrc with klog/mlog/krestart aliases and useful shell setup"
```

---

## Task 5: Add sudoers override for klipper/moonraker service restarts

The stock sudoers blocks `mks` from ALL `systemctl` commands (`!/bin/systemctl`). Our `.bashrc` aliases use `sudo systemctl restart`. We need a narrow override that allows only the safe service restarts.

**Files:**
- Create: `overlay/etc/sudoers.d/q1libre`
- Modify: `tests/test_build.py`

**Step 1: Write the failing test**

Add to `tests/test_build.py`:

```python
def test_sudoers_override_exists():
    """overlay sudoers.d/q1libre must allow klipper/moonraker restarts."""
    sudoers = Path("overlay/etc/sudoers.d/q1libre")
    assert sudoers.exists(), "overlay/etc/sudoers.d/q1libre must exist"
    content = sudoers.read_text()
    assert "klipper.service" in content
    assert "moonraker.service" in content
    assert "NOPASSWD" in content
    # Must NOT grant blanket sudo
    assert "ALL=(ALL) ALL" not in content
```

**Step 2: Run test to verify it fails**

```
pytest tests/test_build.py::test_sudoers_override_exists -v
```

Expected: `FAIL`

**Step 3: Create `overlay/etc/sudoers.d/q1libre`**

```
# Q1Libre sudoers additions
# Allows mks user to restart klipper/moonraker without a password
# This is required for the shell aliases (krestart, mrestart, kmrestart)
# Syntax validated: visudo -c -f /etc/sudoers.d/q1libre

mks ALL=(ALL) NOPASSWD: /bin/systemctl restart klipper.service
mks ALL=(ALL) NOPASSWD: /bin/systemctl restart moonraker.service
mks ALL=(ALL) NOPASSWD: /bin/systemctl restart klipper.service moonraker.service
mks ALL=(ALL) NOPASSWD: /bin/systemctl status klipper.service
mks ALL=(ALL) NOPASSWD: /bin/systemctl status moonraker.service
```

> ⚠️ **Note:** This file must have `0440` permissions to be read by sudo. The stock `postinst` already sets `chmod 0440` on `/etc/sudoers.d/mks`. We need the build to set the same on this file, OR the patched `postinst` must `chmod 0440 /etc/sudoers.d/q1libre`. Add this to `overlay/control/postinst` at the end of the permissions block:
> ```bash
> chmod 0440 /etc/sudoers.d/q1libre 2>/dev/null || true
> ```

**Step 4: Run test to verify it passes**

```
pytest tests/test_build.py::test_sudoers_override_exists -v
```

Expected: `PASS`

**Step 5: Update `overlay/control/postinst` to chmod the new sudoers file**

In `overlay/control/postinst`, in the permissions block (Change A area from Task 2), append:
```bash
# Q1Libre: set correct sudoers permissions
chmod 0440 /etc/sudoers.d/q1libre 2>/dev/null || true
```

**Step 6: Run full suite**

```
pytest tests/ -v
```

Expected: all pass.

**Step 7: Commit**

```bash
git add overlay/etc/sudoers.d/q1libre overlay/control/postinst tests/test_build.py
git commit -m "feat: add sudoers override allowing klipper/moonraker service restarts without password"
```

---

## Task 6: Integration test — verify all patches land in built deb

Add one integration test that builds a real-ish deb (using the fake base pattern) and asserts all five patch sets are present in the output.

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Write the failing test**

Add to `tests/test_integration.py`:

```python
def test_phase1_patches_in_built_deb():
    """All Phase 1 patch files must be present in a built deb's data archive."""
    import lzma, tarfile, io
    from tools.build import build_firmware
    from tools.deb import parse_deb

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Copy real overlay and patches
        import shutil
        overlay = Path("overlay")
        patches = Path("patches")
        base = tmp / "base"

        # Minimal base
        ctrl = base / "control"
        ctrl.mkdir(parents=True)
        (ctrl / "control").write_text("Package: qd-q1-soc\nVersion: 4.4.24\n")
        (ctrl / "postinst").write_text("#!/bin/sh\n# STOCK\nexit 0\n")
        data = base / "data"
        version_dir = data / "root" / "xindi"
        version_dir.mkdir(parents=True)
        (version_dir / "version").write_text(
            "[version]\nmcu = V0.10.0\nui = V4.4.24\nsoc = V4.4.24\n"
        )
        (base / "debian-binary").write_text("2.0\n")

        output = tmp / "dist" / "QD_Q1_SOC"
        output.parent.mkdir(parents=True)
        build_firmware(base, overlay, patches, output, version="0.1.0-test")

        parts = parse_deb(output.read_bytes())

        # Check data.tar.xz for overlay files
        with lzma.open(io.BytesIO(parts["data.tar.xz"])) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                names = tf.getnames()

        assert any("moonraker.conf" in n for n in names), "moonraker.conf missing"
        assert any(".bashrc" in n for n in names), ".bashrc missing"
        assert any("q1libre" in n for n in names), "sudoers/q1libre missing"

        # Check control.tar.xz for patched postinst
        with lzma.open(io.BytesIO(parts["control.tar.xz"])) as lz:
            with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
                postinst = tf.extractfile("./postinst").read().decode()
        assert "chmod 777" not in postinst, "chmod 777 still in postinst"
        assert "Q1Libre" in postinst or "q1libre" in postinst.lower(), \
            "Q1Libre marker missing from postinst"
```

**Step 2: Run test to verify it fails**

```
pytest tests/test_integration.py::test_phase1_patches_in_built_deb -v
```

Expected: `FAIL` (some files missing until Tasks 2–5 complete)

**Step 3: Verify it passes once all prior tasks are done**

After Tasks 1–5 are complete:
```
pytest tests/test_integration.py::test_phase1_patches_in_built_deb -v
```

Expected: `PASS`

**Step 4: Run full suite**

```
pytest tests/ -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration test verifying all Phase 1 patches land in built deb"
```

---

## Task 7: Build the test deb and verify

Do a real build against the actual extracted base and confirm the output is valid.

**Files:**
- No code changes — just build + validate

**Step 1: Run the build**

```bash
cd E:/Projects/q1libre
python -m tools.build --base base --overlay overlay --patches patches -o dist/q1libre-v0.1.0-phase1.deb --version 0.1.0
```

Expected output: something like:
```
Built dist/q1libre-v0.1.0-phase1.deb
  control.tar.xz: XXXX bytes
  data.tar.xz:    XXXX bytes
```

**Step 2: Validate the built deb**

```bash
python -m tools.validate dist/q1libre-v0.1.0-phase1.deb
```

Expected: `OK` or similar success output, no errors.

**Step 3: Inspect postinst in the built deb**

Quick sanity check — extract and view the postinst:
```bash
python -c "
import lzma, tarfile, io
from tools.deb import parse_deb
from pathlib import Path
parts = parse_deb(Path('dist/q1libre-v0.1.0-phase1.deb').read_bytes())
with lzma.open(io.BytesIO(parts['control.tar.xz'])) as lz:
    with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
        print(tf.extractfile('./postinst').read().decode())
"
```

Verify: no `chmod 777`, no `resolv.conf` copy, no `sysctl.conf` copy, Q1Libre marker present.

**Step 4: Inspect data files in the built deb**

```bash
python -c "
import lzma, tarfile, io
from tools.deb import parse_deb
from pathlib import Path
parts = parse_deb(Path('dist/q1libre-v0.1.0-phase1.deb').read_bytes())
with lzma.open(io.BytesIO(parts['data.tar.xz'])) as lz:
    with tarfile.open(fileobj=io.BytesIO(lz.read())) as tf:
        for m in sorted(tf.getnames()):
            print(m)
"
```

Verify: `.bashrc`, `moonraker.conf`, `sudoers.d/q1libre`, `q1libre_info.sh`, `10-armbian-header`, `logrotate.d/q1libre` all present.

**Step 5: Commit the built artifact (gitignored) or just tag**

```bash
git tag v0.1.0-phase1
git push origin v0.1.0-phase1  # if pushing
```

Or just keep the dist/ file locally for flashing to the printer.

---

## Summary of all new overlay files

| Path | What it does |
|------|-------------|
| `overlay/control/postinst` | Fixed permissions, no hardcoded DNS, no IPv6 disable |
| `overlay/home/mks/.bashrc` | klog/mlog/krestart/q1status aliases |
| `overlay/etc/sudoers.d/q1libre` | Allow passwordless klipper/moonraker restart |
| `overlay/home/mks/klipper_config/moonraker.conf` | *(already exists)* + Mainsail update_manager |

Already in overlay (no changes needed):
- `overlay/home/mks/klipper_config/moonraker.conf` — `[octoprint_compat]`, `[history]`, `[timelapse]`, `[update_manager]`, `[update_manager fluidd]` ✅
- `overlay/etc/logrotate.d/q1libre` ✅
- `overlay/root/scripts/q1libre_info.sh` ✅
- `overlay/root/10-armbian-header` ✅
