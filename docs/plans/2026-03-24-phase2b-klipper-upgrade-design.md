# Phase 2B: Klipper Upgrade Design

**Date:** 2026-03-24
**Status:** Approved
**Branch:** phase2b-klipper-upgrade

## Goal

Upgrade the Qidi-forked Klipper v0.10 to upstream Klipper v0.13 while preserving
all Qidi hardware support and touchscreen functionality. The update manager should
show Klipper as valid=True with a working update path.

## Key Findings from Compatibility Test

1. **MCU protocol is compatible** — upstream v0.13 host talks to v0.10 MCU firmware
   without protocol errors. No MCU firmware flash needed.
2. **Config compatibility issues (fixable):**
   - `samples_result: submaxmin` -> `median`
   - `max_accel_to_decel` -> deprecated, use `minimum_cruise_ratio`
   - `endstop_pin_reverse`, `position_endstop_reverse`, `homing_speed_reverse`,
     `homing_positive_dir_reverse` -> Qidi-custom stepper options, need compat module
3. **Approach A (Klipper extras plugin) is viable.**

## Architecture

Vendor upstream Klipper v0.13 as the base. Qidi-specific behavior is provided by
a separate `qidi_extras/` package that gets symlinked into Klipper's extras directory.
No upstream core files are modified.

### Directory Layout

```
/home/mks/klipper/              <- upstream Klipper v0.13 (clean git)
/home/mks/qidi_extras/          <- Q1Libre maintained modules
    qdprobe.py                  <- dual probe pin switching
    chamber_fan.py              <- chamber fan control
    gcode_macro_break.py        <- xindi touchscreen cancel (monkey-patches gcode)
    qidi_stepper.py             <- translates Qidi stepper config options
    hall_filament_width_sensor_compat.py <- old ADC callback API wrapper (if needed)
```

Postinst symlinks qidi_extras modules into `/home/mks/klipper/klippy/extras/`.

### Module Details

**qdprobe.py** (135 lines) — unchanged from Qidi. Provides QIDI_PROBE_PIN_1/PIN_2
gcode commands for dual probe pin switching. Uses standard Klipper probe APIs.

**chamber_fan.py** (59 lines) — unchanged from Qidi. Monitors heater temps,
controls chamber fan speed. Uses standard reactor timer and heater APIs.

**gcode_macro_break.py** (15 lines) — modified to work without core gcode.py changes.
Injects `break_flag` attribute on gcode object and monkey-patches the command dispatch
method to check it before each command. This preserves xindi touchscreen cancel.

**qidi_stepper.py** (NEW) — translates Qidi-custom stepper config options into
upstream-compatible behavior:
- `endstop_pin_reverse` -> handled at config load time
- `position_endstop_reverse` -> mapped to upstream position_endstop with homing_override
- `homing_speed_reverse` -> mapped to upstream second_homing_speed
- `homing_positive_dir_reverse` -> mapped to upstream homing_positive_dir

**hall_filament_width_sensor_compat.py** — wraps upstream sensor with old ADC callback
API signature if the Qidi config uses the old format.

### Config Migration

Postinst runs a config migration script that:
- `samples_result: submaxmin` -> `median`
- Comments out `max_accel_to_decel`, adds `minimum_cruise_ratio` equivalent
- Leaves Qidi stepper options as-is (handled by qidi_stepper.py)

### Modules Dropped (now in upstream)

- `tmc2240.py` — upstream has it
- `x_twist_compensation.py` — upstream has it
- `gcode_shell_command.py` — upstream has it

### Git Management

Same as Moonraker: postinst does `git reset --hard` to vendored SHA, excludes
symlinked extras from git status, so update manager shows valid=True.

## Rollback

- `/home/mks/klipper.bak/` created during install
- SSH recovery: `rm -rf /home/mks/klipper && mv /home/mks/klipper.bak /home/mks/klipper`
- Re-applying previous Q1Libre deb also fully restores

## Testing Checklist

1. Klipper reaches `ready` state
2. Both MCUs communicating (mcu + U_1)
3. Touchscreen works (xindi connects, display updates)
4. All heaters report temps (extruder, bed, chamber)
5. Home X/Y/Z works (qdprobe, reverse homing)
6. Bed mesh works (probe, smart_effector)
7. Cancel from touchscreen during macro (gcode_macro_break)

## Version

Output deb: v0.4.0
