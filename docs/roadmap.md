# Q1Libre Roadmap

## Pending (Deferred — Higher Risk)

### Gcode Macros
- Improved START_PRINT / END_PRINT macros
- Better pause/resume handling
- Directly affects print behavior — needs careful testing on actual prints

### chmod 777 Cleanup
- Stock firmware sets 777 on many files and directories
- Our new files use proper 755/644, but existing stock files remain at 777
- Risk: xindi or other stock binaries may depend on world-writable permissions
- Needs audit of which files xindi/klippy/moonraker actually write to

### Hardcoded DNS Removal
- Stock firmware hardcodes Chinese DNS servers
- Should be switched to DHCP-provided DNS
- Risk: could break network on setups where DHCP doesn't provide DNS

### Python 2→3 Compatibility Landmines
- Found and fixed `buffering=0` in virtual_sdcard.py (PLR) during print testing
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
- Needs configuration and testing

### KAMP (Klipper Adaptive Meshing & Purging)
- Partially present in printer config (macros exist)
- Needs verification and documentation
- Could improve first-layer quality and reduce waste

### Moonraker Notifications
- Push alerts to Telegram, Pushover, etc. on print events
- Moonraker v0.10.0-19 supports this natively
- Just needs configuration in moonraker.conf

### Timelapse Improvements
- Currently enabled by default but basic
- Could add better default settings, camera angle presets
- Render quality options

## Known Issues

### Fluidd Reconnection Delay
- On page refresh, Fluidd briefly shows "No moonraker connection"
- Goes through: blank → disconnected → reconnecting → connected
- Takes several seconds to fully reconnect
- Likely websocket reconnection timing — investigating

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
- [x] GitHub releases (v0.5.0 → v0.5.3)
- [x] PLR Python 3 fix
- [x] numpy/scipy for input shaper
