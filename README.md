# Q1Libre

**Open firmware patches for the Qidi Q1 Pro 3D printer.**

Q1Libre upgrades the stock Qidi Q1 Pro firmware with modern versions of Klipper, Moonraker, and Fluidd while preserving full touchscreen functionality and all Qidi hardware support. No special hardware needed -- just a USB stick.

GitHub: <https://github.com/danthi123/Q1Libre>

---

## Features

- **Klipper v0.13** -- upgraded from stock v0.10, via a [managed fork](https://github.com/danthi123/klipper/tree/q1-pro) with all Qidi hardware patches preserved
- **Moonraker v0.10.0-19** -- latest upstream, replacing the July 2022 stock build
- **Fluidd v1.36.2** -- upgraded from stock v1.19.0
- **Moonraker update_manager enabled** -- manage future updates directly from the Fluidd web UI
- **Security hardened** -- `chmod 777` replaced with proper `755`/`644` permissions; improved sudoers configuration
- **mDNS / Avahi support** -- printer discoverable on your network as `mkspi.local`
- **Shell aliases** -- convenient shortcuts for common SSH management tasks
- **Timelapse** -- enabled by default with moonraker-timelapse integration
- **Log rotation** -- prevents log files from filling the eMMC
- **Full touchscreen (xindi) functionality preserved**
- **MCU firmware unchanged** -- remains at v0.10; no MCU reflash needed (fully backward compatible with host v0.13)
- **Works offline** -- no internet connection required on the printer

## Prerequisites

- A Qidi Q1 Pro running **stock firmware V4.4.24**
  - Download from: <https://github.com/QIDITECH/QIDI_Q1_Pro/releases>
- A **FAT32-formatted USB stick**
- (Optional) SSH access for backups: `root@<printer-ip>`, password `makerbase`

## Backup (Before You Flash)

Backing up before flashing any firmware is strongly recommended.

### Full System Backup (Advanced -- Recommended)

Create a complete image of the printer's eMMC. This is the only way to fully restore your printer to its exact current state, including all configs, calibration, wifi setup, and installed software.

From your computer:

```bash
ssh root@<printer-ip> "dd if=/dev/mmcblk1 bs=4M status=progress" > q1pro_backup.img
```

This creates a full disk image (~14.5 GB for the 16 GB eMMC) and takes approximately 20 minutes over SSH. Store it somewhere safe. If you ever need to do a full restore, follow the [official eMMC flash procedure](https://wiki.qidi3d.com/en/Memo/flash-emmc) using this image instead of the factory image.

### Configuration Backup (Quick)

At minimum, back up your printer configuration and gcode files:

```bash
scp -r root@<printer-ip>:~/klipper_config ./klipper_config_backup
scp -r root@<printer-ip>:~/gcode_files ./gcode_files_backup
```

Default SSH credentials: `root@<printer-ip>`, password `makerbase`.

**Note:** Calibration data (bed mesh, input shaper) is preserved during Q1Libre updates. You do not need to re-run calibration after flashing.

## Installation

There are two installation methods: a pre-built release (recommended) or building from source.

Both methods support **offline** and **online** installations -- the printer does not need an internet connection.

### Option A: Pre-Built Release (Recommended)

1. Download `QD_Q1_SOC` from the [latest GitHub release](https://github.com/danthi123/Q1Libre/releases).
2. Create a folder called `QD_Update` on a FAT32-formatted USB stick.
3. Place `QD_Q1_SOC` inside the `QD_Update/` folder.
4. Plug the USB stick into the printer -- it will detect and install the update automatically.

### Option B: Build from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/danthi123/Q1Libre.git
   cd Q1Libre
   ```
2. Place the stock `QD_Q1_SOC` firmware file (from V4.4.24) into the `stock/` directory.
3. Extract the stock firmware:
   ```bash
   python tools/extract.py stock/QD_Q1_SOC
   ```
4. Build the patched firmware:
   ```bash
   python tools/build.py
   ```
5. Copy `dist/QD_Q1_SOC` to the `QD_Update/` folder on a FAT32-formatted USB stick.
6. Plug the USB stick into the printer -- it will detect and install the update automatically.

## What Gets Changed

| Component         | Stock V4.4.24       | Q1Libre             |
|-------------------|---------------------|---------------------|
| Klipper           | v0.10               | v0.13               |
| Moonraker         | July 2022 build     | v0.10.0-19 (latest) |
| Fluidd            | v1.19.0             | v1.36.2             |
| Update manager    | Disabled            | Enabled             |
| File permissions  | 777 everywhere      | Proper 755/644      |
| Sudoers           | Permissive          | Hardened             |
| mDNS (Avahi)      | Not available       | mkspi.local          |
| Log rotation      | None                | Enabled             |
| Shell aliases     | None                | Added               |
| MCU firmware      | v0.10               | v0.10 (unchanged)   |
| Touchscreen       | Functional          | Functional          |

## Rollback / Recovery

### Restore stock firmware

Download the official V4.4.24 firmware from the [QIDI Q1 Pro releases page](https://github.com/QIDITECH/QIDI_Q1_Pro/releases), place it in `QD_Update/` on a USB stick, and flash the same way.

### Restore from full system backup

If you created a full eMMC backup image before flashing (see [Backup](#full-system-backup-advanced--recommended) above), you can restore it using the [official eMMC flash procedure](https://wiki.qidi3d.com/en/Memo/flash-emmc) with your backup image instead of the factory image:

1. Follow the eMMC flash guide to connect to the printer's eMMC storage from your computer.
2. Use a tool like [balenaEtcher](https://etcher.balena.io/) or `dd` to write your `q1pro_backup.img` to the eMMC:
   ```bash
   dd if=q1pro_backup.img of=/dev/<emmc-device> bs=4M status=progress
   ```
3. This restores your printer to the exact state it was in when the backup was taken, including all configs, calibration data, and wifi settings.

### Worst-case recovery (bricked printer)

If the printer is unresponsive and USB flashing does not work, follow the official eMMC flash procedure with the factory image:

<https://wiki.qidi3d.com/en/Memo/flash-emmc>

## Project Status

### Completed

- [x] Build pipeline & overlay system
- [x] Klipper v0.10 → v0.13 (managed fork with Qidi patches)
- [x] Moonraker July 2022 → v0.10.0-19
- [x] Fluidd v1.19.0 → v1.36.2
- [x] Moonraker update_manager enabled
- [x] Full offline USB-only install (all wheels bundled including numpy/scipy)
- [x] Touchscreen/xindi compatibility preserved
- [x] Shell aliases (15)
- [x] mDNS/Avahi
- [x] Sudoers improvements
- [x] Log rotation
- [x] Timelapse enabled by default
- [x] Documentation (README, install guide, on-printer reference)
- [x] Full eMMC backup instructions
- [x] GitHub release (v0.5.3)
- [x] PLR Python 3 fix (buffering bug)
- [x] Probe retry limit (max 50, prevents infinite calibration loop)
- [x] System debloat (~3GB freed — removes cross-compilers, XFCE, CUPS, Python 2, etc.)
- [x] Hardcoded DNS removal (Chinese DNS replaced with DHCP + Cloudflare/Google fallback)
- [x] chmod 777 cleanup (stock 777/666 swept to proper 755/644)
- [x] Python 2 `unicode()` fix in display/menu.py
- [x] Spoolman config (commented, ready for external Spoolman server)

### Pending (Deferred — Higher Risk)

- [ ] **Gcode macros** — Improved START_PRINT/END_PRINT, pause/resume macros. Directly affects print behavior so needs careful testing.
- [ ] **Other Python 2→3 landmines** — We found `buffering=0` and `unicode()` so far. There could be more lurking in rarely-executed code paths (error handlers, PLR recovery edge cases, filament runout handling, etc.).

### Nice-to-Haves (Future Releases)

- [ ] **MCU firmware upgrade** (v0.10 → v0.13) — requires careful flashing procedure, biggest remaining upgrade
- [ ] **Camera/webcam integration improvements**
- [ ] **KAMP** (Klipper Adaptive Meshing & Purging) — already integrated, needs slicer config + docs
- [ ] **Moonraker notifications** (Telegram/Pushover on print events)
- [ ] **Spoolman** — filament tracking (requires Docker or Python 3.9+ on external host)

## Known Limitations

- **MCU firmware remains at v0.10** while the host runs v0.13. These versions are backward compatible, but the version mismatch is worth noting.

## Contributing

Contributions are welcome. Please open an issue or pull request on the [GitHub repository](https://github.com/danthi123/Q1Libre).

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**, matching Klipper.

## Credits

- [Qidi Technology](https://github.com/QIDITECH) for the Q1 Pro hardware and stock firmware
- [Klipper](https://github.com/Klipper3d/klipper), [Moonraker](https://github.com/Arksine/moonraker), and [Fluidd](https://github.com/fluidd-core/fluidd) open-source projects
- The Q1Libre community for testing and feedback
