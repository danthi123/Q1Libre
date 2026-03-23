# Q1Libre Design Document

**Date:** 2026-03-23
**Status:** Approved
**Target:** Qidi Q1 Pro (rk3328 SoC, TJC touchscreen, dual MCU)

## Problem

Qidi Q1 Pro ships with Klipper ~v0.10 (circa 2020-2021) and hasn't received a firmware update in ~2 years. The stock firmware has security issues (chmod 777 everywhere), disabled features (update_manager, KlipperScreen), and an ancient Klipper version missing years of upstream improvements.

FreeDi exists as an alternative but requires `dd`-flashing a full Armbian image to eMMC — effectively a nuclear reinstall requiring SSH access and technical confidence. There is no option for incremental, USB-stick-only upgrades.

## Solution

Q1Libre is a build system that produces `.deb` packages compatible with the stock `xindi` update mechanism. Users copy a file to a USB stick, plug it into the printer, and the stock update flow handles installation. No special hardware, no eMMC flashing, fully reversible by re-applying stock firmware.

## Differentiator vs FreeDi

| Aspect | FreeDi | Q1Libre |
|--------|--------|---------|
| Install method | `dd` full image to eMMC | USB stick, stock update mechanism |
| Reversibility | Requires re-flash | Apply stock .deb same way |
| Hardware needed | SSH + USB (or eMMC reader) | USB stick only |
| OS | Replaces with new Armbian | Keeps stock Armbian |
| Display | Custom FreeDi LCD firmware | Stock TJC display (initially) |
| Approach | Clean slate | Surgical patches |

## Architecture

### Project Structure

```
q1libre/
├── base/                    # Extracted stock firmware (gitignored)
├── patches/                 # Patch files organized by component
│   ├── klipper/            # Klipper source patches
│   ├── moonraker/          # Moonraker patches
│   ├── configs/            # printer.cfg, macros, moonraker.conf
│   └── system/             # systemd units, scripts, permissions
├── overlay/                 # Files that replace stock files wholesale
│   ├── klipper/            # Eventually: upstream Klipper + Qidi modules
│   └── scripts/            # Custom scripts
├── tools/
│   ├── extract.py          # Extracts stock .deb for analysis
│   ├── build.py            # Builds patched .deb for deployment
│   ├── diff.py             # Diffs stock vs upstream Klipper
│   └── validate.py         # Validates built package
├── docs/
│   ├── firmware-analysis.md
│   ├── update-protocol.md
│   ├── installation.md
│   ├── rollback.md
│   └── development.md
└── README.md
```

### Build Pipeline

1. **Extract** — `tools/extract.py` unpacks stock `QD_Q1_SOC` .deb into `base/`
2. **Patch** — `tools/build.py` copies base, applies patches, overlays files, bumps version
3. **Package** — Repack into valid `.deb` with updated control/install scripts
4. **Validate** — `tools/validate.py` checks deb structure, permissions, syntax
5. **Deploy** — User copies output to USB as `QD_Update/QD_Q1_SOC`

### Safety Mechanisms

- Automatic config backup before install (preserved from stock preinst)
- Version tracking in `root/xindi/version`
- Rollback via stock firmware .deb applied the same way
- Additive postinst changes only — stock safety checks preserved

## Stock Firmware Analysis

### QD_Q1_SOC (Debian Package)

- **Package:** Makerbase-Client v0.1.1, arm64
- **Maintainer:** Makerbase
- **Contents:** 123 files including:
  - Klipper (~v0.10) with 28 modified klippy files
  - Moonraker components (authorization, metadata, update_manager, klippy_apis, machine)
  - `xindi` — C++ binary (12MB, aarch64, Boost.Beast/WebSocket++/nlohmann-json). Proprietary middleware bridging TJC touchscreen to Klipper/Moonraker
  - `frpc` — QIDILink cloud relay client
  - Config files, gcode samples, install scripts
  - Device tree for rk3328

### QD_Q1_UI (TJC Display Firmware)

- 11.2MB binary, magic `0x00 0x01 "BT"`
- File size self-referenced at offset 0x3c
- Multi-language UI strings (EN, FR, DE, IT, ES, PT, TR, CN, JP)
- Contains page definitions, images, fonts for TJC touchscreen

### Update Mechanism (from xindi strings)

- xindi monitors USB at `/home/mks/gcode_files/sda1/QD_Update/`
- Recognized files: `QD_Q1_SOC`, `QD_Q1_UI`, `QD_Q1_PATCH`, `mks.deb`
- SOC install: `dpkg -i --force-overwrite <file>; sync`
- UI install: copied to `/root/800_480.tft`, flashed via serial to TJC display
- MCU update: `hid-flash /root/klipper.bin ttyS0`
- Also supports: `mks-super.sh` (arbitrary script execution), config file replacement

### Qidi Klipper Modifications (28 files)

**Qidi-specific hardware modules:**
- `qdprobe.py` — Qidi's custom probe implementation
- `chamber_fan.py` — Chamber fan control
- `gcode_macro_break.py` — Macro break functionality

**Modified core files:**
- `klippy.py`, `mcu.py`, `toolhead.py`, `stepper.py`, `gcode.py`, `configfile.py`

**Modified extras:**
- `bed_mesh.py`, `force_move.py`, `gcode_move.py`, `gcode_shell_command.py`
- `hall_filament_width_sensor.py`, `heaters.py`, `homing.py`, `print_stats.py`
- `probe.py`, `smart_effector.py`, `spi_temperature.py`, `virtual_sdcard.py`
- `x_twist_compensation.py`
- TMC drivers: `tmc.py`, `tmc2130.py`, `tmc2208.py`, `tmc2209.py`, `tmc2240.py`, `tmc2660.py`, `tmc5160.py`, `tmc_uart.py`

### Key System Details

- **SoC:** Rockchip rk3328 (ROC-RK3328-CC board)
- **OS:** Armbian (Debian Buster, arm64)
- **Serial ports:** `/dev/ttyS0` (toolhead MCU U_1), `/dev/ttyS1` (TJC display), `/dev/ttyS2` (main MCU)
- **Services:** klipper, moonraker, makerbase-client (xindi), frpc, nginx (fluidd)
- **User:** `mks` (home: /home/mks), root access via sudo with restrictions

## Phased Rollout

### Phase 1: Quick Wins (Patches Only)

No Klipper version change. Low risk, high value.

**Config improvements:**
- Uncomment `update_manager` in moonraker.conf
- Improve printer.cfg defaults
- Add KAMP-style adaptive mesh macros

**Security fixes:**
- Replace `chmod 777` with proper permissions
- Fix sudoers config
- Remove hardcoded DNS override

**QoL improvements:**
- Re-enable KlipperScreen as optional toggle
- Proper log rotation
- SSH banner with Q1Libre version/status

### Phase 2: Klipper Upgrade

Port Qidi hardware modules to upstream Klipper v0.12+ API:
1. Identify fork point via git bisect against upstream history
2. Triage 28 modified files: hardware support vs backported fixes vs behavioral tweaks
3. Create `qidi_extras/` as standard Klipper plugin modules
4. Package upstream Klipper + qidi_extras in overlay

### Phase 3: Full Liberation

- Upstream Klipper + Moonraker with Qidi hardware support
- Community-maintained configs and macros
- Still deployed via stock USB mechanism

## Distribution

- Pre-built `.deb` files as GitHub Releases
- Stock firmware files never in repo (copyright)
- Users provide their own stock .deb or extract tool references known Qidi source
- License: GPLv3 (matching Klipper)

## Constraints

- `xindi` binary is kept as-is (proprietary, needed for TJC display)
- TJC display firmware (`QD_Q1_UI`) not modified
- Device tree (`rk3328-roc-cc.dtb`) not modified
- Stock Armbian OS preserved
