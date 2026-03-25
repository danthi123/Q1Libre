# Q1Libre Roadmap

## Pending (Deferred — Higher Risk)

### Gcode Macros
- Improved START_PRINT / END_PRINT macros
- Better pause/resume handling
- Directly affects print behavior — needs careful testing on actual prints

### Python 2→3 Compatibility Landmines
- Found and fixed `buffering=0` in virtual_sdcard.py (PLR) during print testing
- Found and fixed `unicode()` in display/menu.py (Qidi leftover)
- There may be more lurking in rarely-executed code paths:
  - Error handlers
  - Edge cases in PLR recovery (power loss mid-print)
  - Filament runout handling
  - Other Qidi-modified files
- Strategy: find and fix as they surface during real-world use

## Nice-to-Haves (Future Releases)

### MCU Firmware Upgrade (v0.10 → v0.13)
- Biggest remaining upgrade
- Requires careful MCU flashing procedure (risk of bricking MCU)
- Would unlock full v0.13 features (currently running v0.13 host with v0.10 MCU)
- Needs documented recovery procedure before attempting

### Camera/Webcam Integration
- Stock camera works but could benefit from better streaming options
- WebRTC support available in Fluidd v1.36.2
- Crowsnest could replace mjpg-streamer for better performance
- Needs configuration and testing

### KAMP (Klipper Adaptive Meshing & Purging)
- Already integrated (Adaptive_Mesh.cfg included, exclude_object enabled)
- Needs slicer configuration (QIDISlicer EXCLUDE_OBJECT_DEFINE labels)
- Add LINE_PURGE to slicer start gcode for adaptive purge lines
- Documentation for users on how to enable/configure

### Moonraker Notifications
- Push alerts to Telegram, Pushover, etc. on print events
- moonraker-telegram-bot is Python 3.7 compatible, bundleable
- Just needs wheels, systemd service, and user configuration

### Spoolman (Filament Tracking)
- Requires Python 3.9+ (not available on Debian Buster)
- Best approach: run on external host (PC/NAS/Pi), connect via network
- Commented [spoolman] config already in moonraker.conf
- Fluidd 1.36.2 has full UI support once connected

### Timelapse Improvements
- Currently enabled by default but basic
- Could add better default settings, camera angle presets
- Render quality options

## Known Issues

### Fluidd Reconnection Delay
- On page refresh, Fluidd briefly shows "No moonraker connection"
- Goes through: blank → disconnected → reconnecting → connected
- Takes several seconds to fully reconnect
- Normal behavior for websocket-based SPAs on RK3328

## Completed (for reference)

- [x] Build pipeline & overlay system
- [x] Klipper v0.10 → v0.13 (managed fork)
- [x] Moonraker July 2022 → v0.10.0-19
- [x] Fluidd v1.19.0 → v1.36.2
- [x] Moonraker update_manager enabled
- [x] Full offline USB-only install
- [x] Touchscreen/xindi compatibility
- [x] Shell aliases (15)
- [x] mDNS/Avahi
- [x] Sudoers improvements
- [x] Log rotation
- [x] Timelapse enabled
- [x] Documentation (README, install guide, on-printer reference)
- [x] eMMC backup instructions
- [x] GitHub releases (v0.5.0 → v0.5.6)
- [x] PLR Python 3 fix
- [x] numpy/scipy for input shaper
- [x] Probe retry limit (max 50)
- [x] System debloat (~3GB freed)
- [x] Hardcoded DNS removal
- [x] chmod 777 cleanup
- [x] Python 2 unicode() fix
- [x] Spoolman config (commented)
