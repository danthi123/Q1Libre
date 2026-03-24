# Phase 2A: Moonraker Upgrade Design

**Date:** 2026-03-23
**Status:** Approved

## Goal

Upgrade the stock Moonraker (July 2022, commit `bdd0222`) to the last version
compatible with Python 3.7 (estimated January–March 2023). This unlocks the
update_manager UI in Fluidd, the `/machine/update/status` API endpoint, and
modern print history/timelapse APIs — without requiring a Python version upgrade.

## Context

- Stock Moonraker: `bdd0222` (2022-07-24)
- Python on printer: 3.7 (Armbian Buster)
- Modern Moonraker requires Python 3.8+ (walrus operators, `from __future__ import annotations`)
- Phase 1 already ships a compatible `moonraker.conf` with `[update_manager]` enabled

## Approach

**Vendor a pinned commit** into `overlay/home/mks/moonraker/`. Commit the
vendored tree to the Q1Libre repo so builds are reproducible and require no
internet access on the printer during install.

## Section 1 — Version Selection & Vendoring

**Target:** Last Moonraker commit before Python 3.8 was required.
Identified by scanning for first use of `from __future__ import annotations`
or walrus operators (`:=`) in the moonraker source.

**New tool:** `tools/vendor_moonraker.py`
- Clones moonraker at the pinned commit SHA (hardcoded for reproducibility)
- Strips `.git/` directory
- Writes output to `overlay/home/mks/moonraker/`
- Pinned SHA stored as a constant in the tool

**Vendored tree** committed to Q1Libre repo — no internet required at build
time or on the printer during install.

## Section 2 — Installation

**postinst additions (in `overlay/control/postinst`):**

```bash
# Stop moonraker
systemctl stop moonraker.service || true

# Back up existing moonraker for rollback
if [ -d /home/mks/moonraker ]; then
    rm -rf /home/mks/moonraker.bak
    cp -a /home/mks/moonraker /home/mks/moonraker.bak
fi

# New moonraker tree is placed by dpkg from overlay
chown -R mks:mks /home/mks/moonraker

# Rebuild venv dependencies for new version
sudo -u mks /home/mks/moonraker-env/bin/pip install \
    -r /home/mks/moonraker/scripts/moonraker-requirements.txt \
    --quiet 2>/dev/null || true

# Restart moonraker (existing postinst restart handles this)
```

**Python environment:** Python 3.7 venv is reused as-is. Only pip packages
are updated to match new moonraker requirements. No venv rebuild needed.

**Config compatibility:** Phase 1 `moonraker.conf` overlay uses the correct
modern section format. No config changes required.

**Database (LMDB):** Schema is forwards-compatible across this version range.
Existing database carries over without migration.

## Section 3 — Rollback

If Moonraker fails to start after upgrade, recover via SSH:

```bash
sudo systemctl stop moonraker
rm -rf /home/mks/moonraker
mv /home/mks/moonraker.bak /home/mks/moonraker
sudo systemctl start moonraker
```

Re-applying the Phase 1 `.deb` also fully restores the stock Moonraker.

## Section 4 — Testing Checklist

Before shipping the Phase 2A `.deb`:

1. `tools/vendor_moonraker.py` produces a clean tree at the pinned SHA
2. Build pipeline: vendored moonraker lands correctly in output `.deb`
3. No Python 3.8+ syntax in vendored tree (automated check in vendor tool)

On-printer smoke tests after flash:

- `systemctl status moonraker` — active/running
- `curl http://localhost:7125/server/info` — returns JSON with new version string
- `curl http://localhost:7125/machine/update/status` — returns HTTP 200
- Fluidd UI loads and update manager panel is visible

## Version

Output `.deb` version: `v0.2.0-phase2a`
