# Qidi Q1 Pro Firmware Analysis

## Overview

The Qidi Q1 Pro runs on a Rockchip rk3328 SoC (ROC-RK3328-CC board) with Armbian
Buster (Debian) arm64. The printing stack consists of Klipper ~v0.10 (forked),
Moonraker, and Fluidd served via nginx. A proprietary C++ middleware called
**xindi** (packaged as `makerbase-client`) bridges the Klipper ecosystem with the
TJC touchscreen display, USB drive monitoring, and Qidi cloud services.

## QD_Q1_SOC — Debian Package

**Format:** Standard `.deb` (ar archive containing `debian-binary`, `control.tar.xz`,
`data.tar.xz`).

| Field | Value |
|-------|-------|
| Package | Makerbase-Client |
| Version | 0.1.1 |
| Architecture | arm64 |
| Maintainer | Makerbase |
| Total files | 123 |

### Control Scripts

- **preinst** — Backs up existing configs, disables running services before
  installation.
- **postinst** — Merges configs, installs files into target locations, restarts
  services. Uses `chmod 777` extensively.
- **postrm** — Empty (no cleanup on removal).

## File Inventory

| Path | Description |
|------|-------------|
| `/home/mks/klipper/klippy/` | Klipper ~v0.10 fork (28 modified files) |
| `/home/mks/moonraker/` | Moonraker components |
| `/home/mks/klipper_config/` | printer.cfg, gcode_macro.cfg, moonraker.conf, etc. |
| `/root/xindi/build/xindi` | Proprietary middleware (12 MB, C++, aarch64 ELF) |
| `/root/xindi/version` | Version tracking file |
| `/home/mks/tjc` | TJC display command file (85 KB, custom encoding) |
| `/root/QIDILink-client/frpc` | Cloud relay client (13 MB) |
| `/root/etc/rk3328-roc-cc.dtb` | Device tree blob for rk3328 |
| `/root/etc/c_helper.so` | Klipper C helper library |
| `/root/hid-flash` | MCU firmware flasher |
| `/root/uart` | UART communication tool |
| (various) | Sample gcode files (3DBenchy, calibration prints) |

## Klipper Modifications

28 files are modified relative to upstream Klipper ~v0.10. They fall into four
categories.

### Qidi-Custom Hardware Modules

New modules not present in upstream Klipper:

- `qdprobe.py` — Qidi-specific probe implementation
- `chamber_fan.py` — Chamber fan control
- `gcode_macro_break.py` — G-code macro break/cancel handling

### Modified Core

Changes to Klipper's core runtime:

- `klippy.py`
- `mcu.py`
- `toolhead.py`
- `stepper.py`
- `gcode.py`
- `configfile.py`

### Modified Extras

Changes to Klipper's extras (plugins):

- `bed_mesh.py`
- `force_move.py`
- `gcode_move.py`
- `heaters.py`
- `homing.py`
- `print_stats.py`
- `probe.py`
- `smart_effector.py`
- `spi_temperature.py`
- `virtual_sdcard.py`
- `x_twist_compensation.py`
- `gcode_shell_command.py`
- `hall_filament_width_sensor.py`

### TMC Stepper Drivers

All TMC driver modules carry modifications:

- `tmc.py`
- `tmc2130.py`
- `tmc2208.py`
- `tmc2209.py`
- `tmc2240.py`
- `tmc2660.py`
- `tmc5160.py`
- `tmc_uart.py`

## xindi Binary Analysis

| Property | Value |
|----------|-------|
| Type | C++ binary, aarch64 ELF, dynamically linked |
| Size | 12 MB |
| Key libraries | Boost.Beast (HTTP/WebSocket), WebSocket++, nlohmann/json |

### Communication Channels

- **Moonraker** — Connects via `ws://localhost:7125/websocket`
- **TJC display** — Serial communication over `/dev/ttyS1`
- **USB drives** — Monitors `/dev/sda1` for mount events

### Key Capabilities

- Firmware update detection and application
- TJC touchscreen page rendering and navigation
- WiFi network management
- QIDILink cloud connectivity
- Printer state tracking (temperatures, print progress, errors)
- API endpoint handling for local and remote control

### Notable Strings

The binary contains printer state tracking variables, Moonraker API endpoints,
TJC display page commands, and update-related command strings.

## QD_Q1_UI — TJC Display Firmware

| Property | Value |
|----------|-------|
| Size | 11.2 MB |
| Magic bytes | `0x00 0x01 "BT"` |
| File size self-reference | Offset `0x3c` |
| HMI marker | Offset `0x0090dc91` |

### Contents

- Multi-language UI strings: English, French, German, Italian, Spanish,
  Portuguese, Turkish, Chinese
- Page definitions for the TJC touchscreen interface
- Embedded images and fonts
- QIDI Link login and account UI strings in all supported languages

## System Architecture

### Hardware

- **SoC:** Rockchip rk3328 (ROC-RK3328-CC board)
- **Display:** TJC touchscreen (800x480)

### Operating System

- Armbian Buster (Debian), arm64
- **User:** `mks` (home: `/home/mks`), root has full access

### Serial Ports

| Port | Connected To |
|------|-------------|
| `/dev/ttyS0` | Toolhead MCU (U_1) |
| `/dev/ttyS1` | TJC display |
| `/dev/ttyS2` | Main MCU |

### Services

| Service | Description |
|---------|-------------|
| klipper | 3D printer firmware (Klipper ~v0.10 fork) |
| moonraker | Klipper API server |
| makerbase-client | xindi middleware |
| frpc | Cloud relay tunnel to Qidi servers |
| nginx | Web server hosting Fluidd UI |
