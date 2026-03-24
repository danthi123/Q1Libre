# QoL Patches Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 4 low-risk QoL patches: extended shell aliases, mDNS/avahi, sudoers expansion, and documentation.

**Architecture:** All patches use the existing overlay system — files in `overlay/` replace stock files in the built .deb. postinst handles runtime setup (permissions, service enablement). Tests validate overlay file content statically.

**Tech Stack:** Bash (aliases, postinst), XML (avahi service), sudoers syntax, Markdown/plain text (docs), Python pytest (tests)

---

### Task 1: Extend sudoers rules

**Files:**
- Modify: `overlay/etc/sudoers.d/q1libre`
- Modify: `tests/test_build.py` (extend `test_sudoers_override_exists`)

**Step 1: Update the test to require new rules**

In `tests/test_build.py`, update `test_sudoers_override_exists` (line 296):

```python
def test_sudoers_override_exists():
    """overlay sudoers.d/q1libre must allow service management and power commands without blanket sudo."""
    sudoers = Path(__file__).resolve().parent.parent / "overlay" / "etc" / "sudoers.d" / "q1libre"
    assert sudoers.exists(), "overlay/etc/sudoers.d/q1libre must exist"
    content = sudoers.read_text()
    assert "klipper.service" in content
    assert "moonraker.service" in content
    assert "nginx.service" in content
    assert "avahi-daemon.service" in content
    assert "journalctl" in content
    assert "/usr/sbin/shutdown" in content
    assert "/usr/sbin/reboot" in content
    assert "NOPASSWD" in content
    # Must NOT grant blanket sudo
    assert "ALL=(ALL) ALL" not in content
```

**Step 2: Run test to verify it fails**

Run: `cd /e/Projects/q1libre && python -m pytest tests/test_build.py::test_sudoers_override_exists -v`
Expected: FAIL — `nginx.service` not in content

**Step 3: Update the sudoers file**

Replace `overlay/etc/sudoers.d/q1libre` with:

```
# Q1Libre sudoers additions
# Allows mks user to manage services and system without a password

# Klipper / Moonraker service management
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart klipper.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart moonraker.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart klipper.service moonraker.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl status klipper.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl status moonraker.service

# Nginx and Avahi service management
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl status nginx.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart avahi-daemon.service
mks ALL=(ALL) NOPASSWD: /usr/bin/systemctl status avahi-daemon.service

# Log viewing
mks ALL=(ALL) NOPASSWD: /usr/bin/journalctl

# Power management
mks ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
mks ALL=(ALL) NOPASSWD: /usr/sbin/reboot
```

**Step 4: Run test to verify it passes**

Run: `cd /e/Projects/q1libre && python -m pytest tests/test_build.py::test_sudoers_override_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add overlay/etc/sudoers.d/q1libre tests/test_build.py
git commit -m "feat: expand sudoers with nginx, avahi, journalctl, power management"
```

---

### Task 2: Extend shell aliases

**Files:**
- Modify: `overlay/home/mks/.bashrc`
- Modify: `tests/test_build.py` (extend `test_mks_bashrc_has_aliases`)

**Step 1: Update the test to require new aliases**

In `tests/test_build.py`, update `test_mks_bashrc_has_aliases` (line 284):

```python
def test_mks_bashrc_has_aliases():
    """overlay .bashrc must define all Q1Libre aliases."""
    bashrc = Path(__file__).resolve().parent.parent / "overlay" / "home" / "mks" / ".bashrc"
    assert bashrc.exists(), "overlay/home/mks/.bashrc must exist"
    content = bashrc.read_text()
    # Original aliases
    assert "alias klog=" in content
    assert "alias mlog=" in content
    assert "alias krestart=" in content
    assert "klippy.log" in content
    assert "moonraker.log" in content
    # New aliases
    assert "alias myip=" in content
    assert "alias diskfree=" in content
    assert "alias kversion=" in content
    assert "alias mversion=" in content
    assert "alias xerr=" in content
    assert "alias dtail=" in content
    assert "alias cdlog=" in content
    assert "alias cdgcode=" in content
```

**Step 2: Run test to verify it fails**

Run: `cd /e/Projects/q1libre && python -m pytest tests/test_build.py::test_mks_bashrc_has_aliases -v`
Expected: FAIL — `alias myip=` not in content

**Step 3: Add new aliases to .bashrc**

Append before the `# ── Prompt ──` line in `overlay/home/mks/.bashrc`:

```bash
# ── Network & System ────────────────────────────────────────────────────────
# Show printer IP address
alias myip='hostname -I | awk "{print \$1}"'

# Show disk usage summary
alias diskfree='df -h / /home | tail -n +2'

# ── Versions ────────────────────────────────────────────────────────────────
# Show Klipper version
alias kversion='~/klippy-env/bin/python ~/klipper/klippy/chelper/__init__.py 2>/dev/null; cd ~/klipper && git describe --tags --always 2>/dev/null; cd ~'

# Show Moonraker version
alias mversion='cd ~/moonraker && git describe --tags --always 2>/dev/null; cd ~'

# ── Additional Logs ─────────────────────────────────────────────────────────
# Tail xindi errors
alias xerr='sudo journalctl -u xindi -n 50 --no-pager'

# Last 30 dmesg lines
alias dtail='dmesg | tail -30'

# ── Navigation ──────────────────────────────────────────────────────────────
# Go to klipper logs directory
alias cdlog='cd ~/klipper_logs && ls'

# Go to gcode files directory
alias cdgcode='cd ~/gcode_files && ls'
```

**Step 4: Run test to verify it passes**

Run: `cd /e/Projects/q1libre && python -m pytest tests/test_build.py::test_mks_bashrc_has_aliases -v`
Expected: PASS

**Step 5: Commit**

```bash
git add overlay/home/mks/.bashrc tests/test_build.py
git commit -m "feat: add network, version, log, and navigation shell aliases"
```

---

### Task 3: Add mDNS/Avahi service advertisement

**Files:**
- Create: `overlay/etc/avahi/services/q1libre.service`
- Modify: `overlay/control/postinst` (add avahi enablement near service restart block)
- Create: `tests/test_avahi.py`

**Step 1: Write the test**

Create `tests/test_avahi.py`:

```python
"""Tests for Avahi/mDNS overlay files."""
from pathlib import Path

OVERLAY = Path(__file__).resolve().parent.parent / "overlay"


def test_avahi_service_file_exists():
    """Avahi service definition must exist in overlay."""
    svc = OVERLAY / "etc" / "avahi" / "services" / "q1libre.service"
    assert svc.exists(), "overlay/etc/avahi/services/q1libre.service must exist"


def test_avahi_service_file_valid_xml():
    """Avahi service file must be parseable XML."""
    import xml.etree.ElementTree as ET
    svc = OVERLAY / "etc" / "avahi" / "services" / "q1libre.service"
    tree = ET.parse(svc)
    root = tree.getroot()
    assert root.tag == "service-group"


def test_avahi_service_advertises_http():
    """Avahi service must advertise HTTP on port 80."""
    content = (OVERLAY / "etc" / "avahi" / "services" / "q1libre.service").read_text()
    assert "_http._tcp" in content
    assert "<port>80</port>" in content


def test_avahi_service_advertises_moonraker():
    """Avahi service must advertise Moonraker on port 7125."""
    content = (OVERLAY / "etc" / "avahi" / "services" / "q1libre.service").read_text()
    assert "_moonraker._tcp" in content
    assert "<port>7125</port>" in content


def test_postinst_enables_avahi():
    """postinst must enable avahi-daemon if available."""
    postinst = OVERLAY / "control" / "postinst"
    content = postinst.read_text(encoding="utf-8")
    assert "avahi-daemon" in content
    assert "systemctl enable avahi-daemon" in content
```

**Step 2: Run tests to verify they fail**

Run: `cd /e/Projects/q1libre && python -m pytest tests/test_avahi.py -v`
Expected: FAIL — file not found

**Step 3: Create the avahi service file**

Create `overlay/etc/avahi/services/q1libre.service`:

```xml
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">%h</name>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <txt-record>path=/</txt-record>
    <txt-record>product=Q1Libre</txt-record>
  </service>
  <service>
    <type>_moonraker._tcp</type>
    <port>7125</port>
  </service>
</service-group>
```

**Step 4: Add avahi enablement to postinst**

Insert before the service restart block (before line 352 `#重启各类服务令`):

```bash
# Q1Libre: Enable mDNS/Avahi if available
if command -v avahi-daemon >/dev/null 2>&1; then
    systemctl enable avahi-daemon 2>/dev/null || true
    systemctl restart avahi-daemon 2>/dev/null || true
fi
```

**Step 5: Run tests to verify they pass**

Run: `cd /e/Projects/q1libre && python -m pytest tests/test_avahi.py -v`
Expected: ALL PASS

**Step 6: Run full test suite**

Run: `cd /e/Projects/q1libre && python -m pytest -v`
Expected: ALL PASS (existing tests unaffected)

**Step 7: Commit**

```bash
git add overlay/etc/avahi/services/q1libre.service overlay/control/postinst tests/test_avahi.py
git commit -m "feat: add mDNS/Avahi service advertisement for web UI and Moonraker"
```

---

### Task 4: Documentation — on-printer README

**Files:**
- Create: `overlay/home/mks/Q1LIBRE_README.txt`

**Step 1: Write the on-printer readme**

Create `overlay/home/mks/Q1LIBRE_README.txt` with:
- Q1Libre version/description header
- All 15 aliases with descriptions
- Key file locations (printer.cfg, moonraker.conf, gcodes, logs)
- Web UI access (IP or hostname.local)
- Rollback instructions (reflash stock via USB)

**Step 2: Commit**

```bash
git add overlay/home/mks/Q1LIBRE_README.txt
git commit -m "docs: add on-printer Q1Libre reference guide"
```

---

### Task 5: Documentation — repo README rewrite

**Files:**
- Modify: `README.md` (repo root)

**Step 1: Rewrite README.md**

Replace with community-facing content:
- What Q1Libre is (one paragraph)
- Features list (Moonraker v0.10.0-19, Klipper v0.13, update manager, security, mDNS, aliases)
- Install instructions (download .deb, USB, power on)
- Rollback (reflash stock)
- Links to docs/ for details
- License, credits

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for community users"
```

---

### Task 6: Documentation — install guide

**Files:**
- Create: `docs/install-guide.md`

**Step 1: Write the install guide**

Create `docs/install-guide.md` with:
- Prerequisites (stock Qidi Q1 Pro firmware v4.4.24, FAT32 USB stick)
- Step-by-step install (download .deb, create QD_Update/QD_Q1_SOC, plug in, wait)
- Post-install verification checklist (SSH, services, web UI, update manager)
- Troubleshooting (klipper not starting, moonraker warnings, can't reach hostname.local, etc.)
- Building from source (clone, extract stock, build, validate)

**Step 2: Commit**

```bash
git add docs/install-guide.md
git commit -m "docs: add detailed install guide with troubleshooting"
```

---

### Task 7: Build and validate

**Step 1: Bump version to 0.5.0**

In `tools/build.py`, update `DEFAULT_VERSION` from `"0.4.0"` to `"0.5.0"`.

**Step 2: Build the .deb**

Run: `cd /e/Projects/q1libre && python -m tools.build`
Expected: `Built dist\QD_Q1_SOC` with new size

**Step 3: Validate**

Run: `cd /e/Projects/q1libre && python -m tools.validate dist/QD_Q1_SOC`
Expected: `VALID`

**Step 4: Run full test suite**

Run: `cd /e/Projects/q1libre && python -m pytest -v`
Expected: ALL PASS

**Step 5: Commit and push**

```bash
git add tools/build.py
git commit -m "chore: bump version to 0.5.0 for QoL patches"
git push origin main
```
