# Phase 2B: Klipper Upgrade via Managed Fork

**Date:** 2026-03-24
**Status:** Approved
**Branch:** phase2b-klipper-upgrade

## Goal

Upgrade Klipper from the 2-year-old Qidi v0.10 fork to current upstream v0.13
by maintaining a Q1Libre fork of Klipper with Qidi's hardware-specific changes
applied on top.

## Key Learnings from Approach A

Approach A (pure plugin) failed because:
1. MCU firmware has Qidi-custom command formats (thermocouple, adxl345)
2. C helper library must be compiled from matching source
3. Stock V4.4.24 deb only ships 30 overlay files — needs matching base
4. Qidi klippy uses Python 2-style imports
5. Multiple API mismatches between V4.4.24 deb files and eMMC base

## Architecture

### The Fork

Create `danthi123/klipper` forked from `Klipper3d/klipper`.
Create a `q1-pro` branch from current upstream HEAD.
Apply Qidi's changes as a single commit on top:

- 24 modified extras from V4.4.24 deb
- 6 modified core files from V4.4.24 deb
- `adxl345.py` from eMMC base (MCU command compat)

This gives us upstream Klipper v0.13 with all Qidi hardware support.

### Q1Libre Build

- Vendor the fork into `overlay/home/mks/klipper/`
- Postinst rebuilds klippy-env with Python 3 via virtualenv
- Postinst does `git reset --hard` to vendored fork SHA
- Postinst sets git remote to `danthi123/klipper`, branch `q1-pro`
- c_helper.so auto-compiles on first Klipper startup (~30s on ARM)
- Config migration for renamed options

### Update Manager

Moonraker auto-detects the git remote from `/home/mks/klipper/.git`.
Since the remote points to our fork and branch is `q1-pro`, the update
manager tracks our fork. Shows valid=True, can update from UI.

### Python 3 klippy-env

Upstream Klipper v0.13 requires Python 3. Postinst uses `virtualenv`
(already installed on the printer) to create a Python 3.7 venv:

```bash
virtualenv -p python3 /home/mks/klippy-env
/home/mks/klippy-env/bin/pip install -r /home/mks/klipper/scripts/klippy-requirements.txt
```

### Files Applied from Qidi (30 + 1)

**Core (6):** klippy.py, mcu.py, stepper.py, gcode.py, configfile.py, toolhead.py
**Extras (24):** bed_mesh, chamber_fan, force_move, gcode_macro_break,
gcode_move, gcode_shell_command, hall_filament_width_sensor, heaters,
homing, print_stats, probe, qdprobe, smart_effector, spi_temperature,
tmc, tmc2130, tmc2208, tmc2209, tmc2240, tmc2660, tmc5160, tmc_uart,
virtual_sdcard, x_twist_compensation
**eMMC compat (1):** adxl345.py

## Rollback

- `/home/mks/klipper.bak/` created during install
- `/home/mks/klippy-env.bak/` Python 2 venv preserved
- SSH recovery: restore both directories, restart klipper
- Re-applying previous Q1Libre deb also restores

## Testing

1. Klippy: ready
2. Both MCUs communicating (mcu + U_1)
3. Touchscreen works (xindi connects)
4. All heaters report temps
5. 0 warnings, 0 failed components
6. Update manager: klipper valid=True, tracking fork

## Version

Output deb: v0.4.0
