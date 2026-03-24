# QoL Patches Design — 2026-03-24

## Overview

Four low-risk, additive patches deployed via the existing .deb overlay system.

## 1. Shell Aliases

Extend `overlay/home/mks/.bashrc` with 8 new aliases (15 total):

| Alias | Command |
|-------|---------|
| `myip` | Show printer IP |
| `diskfree` | Show disk usage for / and /home |
| `kversion` | Show Klipper version |
| `mversion` | Show Moonraker version |
| `xerr` | Tail xindi errors via journalctl |
| `dtail` | Last 30 dmesg lines |
| `cdlog` | cd to klipper_logs |
| `cdgcode` | cd to gcode_files |

Existing aliases unchanged: `klog`, `mlog`, `krestart`, `mrestart`, `kmrestart`, `q1status`, `cdcfg`.

## 2. mDNS/Avahi

New file: `overlay/etc/avahi/services/q1libre.service`

Advertises:
- `_http._tcp` on port 80 (Fluidd web UI)
- `_moonraker._tcp` on port 7125 (Moonraker API)

Uses `%h` wildcard for existing hostname (no hostname changes).

postinst addition: enable and restart avahi-daemon if present, no-op otherwise.

No nsswitch.conf changes needed (Armbian Buster has mdns4 by default).

## 3. Sudoers

Extend `overlay/etc/sudoers.d/q1libre` with:
- `systemctl restart/status` for nginx and avahi-daemon
- `journalctl` (log viewing)
- `shutdown` and `reboot` (power management)

All NOPASSWD, specific command paths. File permissions 0440.

## 4. Documentation

Three files:
- **README.md** (repo root): Community-facing — features, install, rollback
- **overlay/home/mks/Q1LIBRE_README.txt**: On-printer reference — aliases, file locations, web UI access
- **docs/install-guide.md**: Detailed install guide, verification, troubleshooting, building from source
