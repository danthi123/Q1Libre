# Phase 2B: Klipper Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Klipper from Qidi v0.10 fork to upstream v0.13 with Qidi hardware support preserved as extras plugins, enabling update manager UI updates.

**Architecture:** Vendor upstream Klipper v0.13 into overlay. Create a `qidi_extras/` package with 5 modules (qdprobe, chamber_fan, gcode_macro_break, qidi_stepper, adxl345_compat) that get symlinked into Klipper's extras dir. The qidi_stepper module monkey-patches `PrinterRail` to add reverse homing support. The gcode_macro_break module monkey-patches gcode command dispatch for touchscreen cancel. Config migration handles renamed/deprecated options.

**Tech Stack:** Python 3.7, Klipper plugin API, monkey-patching for core behavior injection, existing build pipeline.

---

### Task 1: Create tools/vendor_klipper.py and vendor upstream Klipper

**Files:**
- Create: `tools/vendor_klipper.py`
- Create: `overlay/home/mks/klipper/` (vendored upstream tree)

Mirrors `tools/vendor_moonraker.py` — downloads upstream Klipper at a pinned SHA, strips `.git`, places in overlay. Pin to current upstream HEAD.

**Steps:**
1. Create `tools/vendor_klipper.py` (copy pattern from `vendor_moonraker.py`, change repo URL to `https://github.com/Klipper3d/klipper`)
2. Run it to download and vendor upstream Klipper
3. Verify `overlay/home/mks/klipper/klippy/klippy.py` exists and is the upstream version
4. Commit tool + vendored tree

---

### Task 2: Create qidi_extras/qdprobe.py

**Files:**
- Create: `overlay/home/mks/qidi_extras/qdprobe.py`

Copy directly from `base/data/home/mks/klipper/klippy/extras/qdprobe.py`. No changes needed — it uses standard Klipper probe APIs.

**Steps:**
1. Create `overlay/home/mks/qidi_extras/` directory
2. Copy `qdprobe.py` from base
3. Verify it has `load_config()` function
4. Commit

---

### Task 3: Create qidi_extras/chamber_fan.py

**Files:**
- Create: `overlay/home/mks/qidi_extras/chamber_fan.py`

Copy directly from `base/data/home/mks/klipper/klippy/extras/chamber_fan.py`. No changes needed.

**Steps:**
1. Copy `chamber_fan.py` from base
2. Verify `load_config()` function exists
3. Commit

---

### Task 4: Create qidi_extras/gcode_macro_break.py (monkey-patched version)

**Files:**
- Create: `overlay/home/mks/qidi_extras/gcode_macro_break.py`

This module must work WITHOUT modifications to upstream gcode.py. It:
1. Injects `break_flag` attribute on the gcode object
2. Monkey-patches `_process_commands()` to check `break_flag` before each line
3. Registers the same webhooks (`breakmacro`, `resumemacro`) that xindi uses

```python
# Gcode macro interrupt support for xindi touchscreen
# Monkey-patches GCodeDispatch._process_commands to support break_flag
# without modifying upstream gcode.py

import logging

class GCodeMacroBreaker:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        gcode = self.printer.lookup_object('gcode')
        # Inject break_flag attribute
        gcode.break_flag = False
        # Monkey-patch _process_commands to check break_flag
        original_process = gcode._process_commands
        def patched_process(commands, need_ack=True):
            filtered = []
            for line in commands:
                stripped = line.strip()
                if gcode.break_flag:
                    if stripped.upper() == "CANCEL_PRINT":
                        gcode.break_flag = False
                        try:
                            heaters = self.printer.lookup_object("heaters")
                            heaters.break_flag = False
                        except Exception:
                            pass
                        filtered.append(line)
                    # Skip all other commands when break_flag is set
                    continue
                filtered.append(line)
            return original_process(filtered, need_ack)
        gcode._process_commands = patched_process
        # Register xindi webhooks
        webhooks = self.printer.lookup_object('webhooks')
        webhooks.register_endpoint("breakmacro", self._handle_breakmacro)
        webhooks.register_endpoint("resumemacro", self._handle_resumemacro)
        logging.info("gcode_macro_break: xindi cancel support loaded")

    def _handle_breakmacro(self, web_request):
        gcode = self.printer.lookup_object('gcode')
        gcode.break_flag = True

    def _handle_resumemacro(self, web_request):
        gcode = self.printer.lookup_object('gcode')
        gcode.break_flag = False

def load_config(config):
    return GCodeMacroBreaker(config)
```

**Steps:**
1. Create the file with the monkey-patched implementation above
2. Verify syntax: `python3 -c "import ast; ast.parse(open('file').read())"`
3. Commit

---

### Task 5: Create qidi_extras/qidi_stepper.py (reverse homing support)

**Files:**
- Create: `overlay/home/mks/qidi_extras/qidi_stepper.py`

This is the most complex module. It monkey-patches `PrinterRail` to support:
- `endstop_pin_reverse` config option
- `position_endstop_reverse`, `homing_positive_dir_reverse`, `homing_speed_reverse`
- `REVERSE_HOMING` gcode command
- `homing_params_switch()` method that swaps primary/reverse endstops

The implementation reads the Qidi-custom config options during `klippy:connect`, looks up the Z rail, and injects the reverse homing infrastructure.

```python
# Qidi Q1 Pro reverse homing support
# Monkey-patches PrinterRail to support dual endstop Z homing
# Required for the Qidi Z homing sequence (probe down, then endstop up)

import logging, collections

class QidiStepper:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:connect",
                                            self._handle_connect)

    def _handle_connect(self):
        # Find the Z rail and inject reverse homing if configured
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        for rail in kin.get_rails():
            name = rail.get_name()
            if name != "stepper_z":
                continue
            # Check if reverse homing is configured by looking at
            # the original config sections
            configfile = self.printer.lookup_object('configfile')
            # Read the raw config to check for endstop_pin_reverse
            # This is already parsed by the Qidi stepper code in the
            # stock firmware. For upstream, we need to handle it here.
            self._setup_reverse_homing(rail)

    def _setup_reverse_homing(self, rail):
        # Read config for stepper_z reverse homing options
        configfile = self.printer.lookup_object('configfile')
        config = configfile.read_main_config()

        if not config.fileconfig.has_option('stepper_z', 'endstop_pin_reverse'):
            return

        endstop_pin_reverse = config.fileconfig.get('stepper_z', 'endstop_pin_reverse')
        position_endstop_reverse = config.fileconfig.getfloat(
            'stepper_z', 'position_endstop_reverse')
        homing_positive_dir_reverse = config.fileconfig.getboolean(
            'stepper_z', 'homing_positive_dir_reverse')
        homing_speed_reverse = config.fileconfig.getfloat(
            'stepper_z', 'homing_speed_reverse',
            fallback=rail.homing_speed)

        # Setup reverse endstop
        ppins = self.printer.lookup_object('pins')
        mcu_endstop_reverse = ppins.setup_pin('endstop', endstop_pin_reverse)
        for stepper in rail.get_steppers():
            mcu_endstop_reverse.add_stepper(stepper)

        # Store reverse homing params on the rail
        rail.endstops_reverse = [(mcu_endstop_reverse, 'stepper_z')]
        rail.endstop_map_reverse = {}
        rail.position_endstop_reverse = position_endstop_reverse
        rail.homing_positive_dir_reverse = homing_positive_dir_reverse
        rail.homing_speed_reverse = homing_speed_reverse
        rail.homing_retract_dist_reverse = 0
        rail.reversed = False

        # Inject homing_params_switch method
        def homing_params_switch():
            rail.reversed = not rail.reversed
            rail.endstop_map, rail.endstop_map_reverse = (
                rail.endstop_map_reverse, rail.endstop_map)
            rail.endstops, rail.endstops_reverse = (
                rail.endstops_reverse, rail.endstops)
            rail.position_endstop, rail.position_endstop_reverse = (
                rail.position_endstop_reverse, rail.position_endstop)
            rail.homing_positive_dir, rail.homing_positive_dir_reverse = (
                rail.homing_positive_dir_reverse, rail.homing_positive_dir)
            rail.homing_retract_dist, rail.homing_retract_dist_reverse = (
                rail.homing_retract_dist_reverse, rail.homing_retract_dist)
            rail.homing_speed, rail.homing_speed_reverse = (
                rail.homing_speed_reverse, rail.homing_speed)
        rail.homing_params_switch = homing_params_switch

        # Register REVERSE_HOMING gcode command
        gcode = self.printer.lookup_object('gcode')
        def cmd_REVERSE_HOMING(gcmd):
            homing_params_switch()
            try:
                from klippy.extras.homing import Homing
                homing_state = Homing(self.printer)
                homing_state.set_axes([2])
                kin = self.printer.lookup_object('toolhead').get_kinematics()
                kin.home(homing_state)
            except self.printer.command_error:
                if self.printer.is_shutdown():
                    raise self.printer.command_error(
                        "Homing failed due to printer shutdown")
                self.printer.lookup_object('stepper_enable').motor_off()
                raise
        gcode.register_command("REVERSE_HOMING", cmd_REVERSE_HOMING)

        # Auto-switch back after homing completes
        def handle_home_rails_end(homing_state, rails):
            if rail.reversed:
                homing_params_switch()
        self.printer.register_event_handler(
            "homing:home_rails_end", handle_home_rails_end)

        logging.info("qidi_stepper: reverse homing configured for stepper_z")

def load_config(config):
    return QidiStepper(config)
```

NOTE: This implementation is a starting point. The exact upstream Klipper v0.13 API for
PrinterRail, Homing, and kinematics may differ. The implementer MUST:
1. Read upstream `klippy/stepper.py` to verify attribute names
2. Read upstream `klippy/extras/homing.py` to verify Homing class API
3. Test on the actual printer

**Steps:**
1. Create the file
2. Verify syntax
3. Commit

---

### Task 6: Create qidi_extras/adxl345_compat.py

**Files:**
- Create: `overlay/home/mks/qidi_extras/adxl345_compat.py`

This module wraps upstream's adxl345 to gracefully handle the missing tap detection
MCU commands. It's loaded as `[adxl345_compat]` in a supplementary config.

Actually, upstream's adxl345 won't try to send `adxl345_status` because that command
doesn't exist in upstream code. The tap detection was Qidi-specific. So upstream
adxl345 should just work. We only need this if the printer.cfg references Qidi-specific
adxl345 config options.

**Decision:** Skip this task — upstream adxl345 should work. If testing reveals issues,
add a compat wrapper later.

---

### Task 7: Config migration script

**Files:**
- Create: `tools/migrate_config.py`

Script that transforms a Qidi printer.cfg to work with upstream Klipper:
- `samples_result: submaxmin` -> `samples_result: median`
- Comment out `max_accel_to_decel` (deprecated in upstream)
- Mark Qidi-custom options (`endstop_pin_reverse` etc.) with `# Q1Libre:` comments
  so they're ignored by upstream but preserved for qidi_stepper.py to read

The tricky part: upstream's config parser will reject unknown options like
`endstop_pin_reverse`. The qidi_stepper.py module reads them directly from the
fileconfig before upstream validates the section. We need to ensure qidi_stepper
loads BEFORE the stepper sections are validated, OR we prefix these options so
upstream ignores them (e.g., `#qidi_endstop_pin_reverse`).

Actually, the cleanest approach: move the Qidi-custom stepper options into a
separate config section `[qidi_stepper]` that qidi_stepper.py reads, and comment
out the raw options in `[stepper_z]`/`[stepper_z1]`.

```ini
# In printer.cfg, migrate from:
[stepper_z]
endstop_pin_reverse:tmc2209_stepper_z:virtual_endstop
position_endstop_reverse:248
homing_positive_dir_reverse:true
homing_speed_reverse: 8

# To:
[stepper_z]
# Qidi reverse homing options moved to [qidi_stepper] section
#endstop_pin_reverse:tmc2209_stepper_z:virtual_endstop
#position_endstop_reverse:248
#homing_positive_dir_reverse:true
#homing_speed_reverse: 8

[qidi_stepper]
# Reverse homing for Z axis (managed by Q1Libre qidi_extras)
z_endstop_pin_reverse: tmc2209_stepper_z:virtual_endstop
z_position_endstop_reverse: 248
z_homing_positive_dir_reverse: true
z_homing_speed_reverse: 8
z1_endstop_pin_reverse: tmc2209_stepper_z1:virtual_endstop
```

This requires updating `qidi_stepper.py` (Task 5) to read from `[qidi_stepper]`
config section instead of parsing stepper_z raw config.

**Steps:**
1. Create `tools/migrate_config.py` that:
   - Reads printer.cfg
   - Finds `[stepper_z]` and `[stepper_z1]` sections
   - Extracts and comments out Qidi-custom options
   - Creates `[qidi_stepper]` section with the extracted values
   - Fixes `samples_result: submaxmin` -> `median`
   - Comments out `max_accel_to_decel`
   - Writes the modified config
2. Test with the stock printer.cfg from base/
3. Commit

---

### Task 8: Update qidi_stepper.py to read from [qidi_stepper] section

**Files:**
- Modify: `overlay/home/mks/qidi_extras/qidi_stepper.py`

Update to read config from `[qidi_stepper]` section instead of raw stepper_z parsing.
This is much cleaner — qidi_stepper.py becomes a proper Klipper extra with its own
config section.

**Steps:**
1. Update the `__init__` to read from config (which will be `[qidi_stepper]`)
2. Update `_setup_reverse_homing` to use the config values
3. Commit

---

### Task 9: Update postinst for Klipper upgrade

**Files:**
- Modify: `overlay/control/postinst`

Add to the postinst:
1. Stop klipper before replacing files
2. Backup existing klipper to klipper.bak
3. chown new klipper tree
4. Git reset to vendored SHA (same pattern as moonraker)
5. Symlink qidi_extras modules into klippy/extras/
6. Exclude symlinks from git
7. Run config migration script
8. Commit klipper git state clean

**Steps:**
1. Read current postinst
2. Add Klipper upgrade block before the service restart section
3. Test that postinst has correct syntax
4. Commit

---

### Task 10: Update build.py and bump version

**Files:**
- Modify: `tools/build.py` (DEFAULT_VERSION -> "0.4.0")
- Modify: `tests/test_build.py` (version assertion)

**Steps:**
1. Update version
2. Run tests
3. Commit

---

### Task 11: Build, validate, deploy, and test on printer

**Files:**
- Output: `dist/q1libre-v0.4.0.deb`

**Steps:**
1. Run full test suite
2. Build deb
3. Validate deb
4. Deploy to printer via SCP
5. Install via dpkg
6. Run smoke tests:
   - `klippy_state: ready`
   - Both MCUs communicating
   - Update manager shows klipper valid=True
   - Touchscreen responsive
   - Temps reading correctly
7. If all pass, commit and push

---

## On-Printer Smoke Test Checklist

```bash
# 1. Klipper ready
curl -s http://localhost:7125/server/info | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['klippy_state'])"

# 2. MCUs connected
grep "mcu:" /home/mks/klipper_logs/klippy.log | tail -1

# 3. Update manager status
curl -s http://localhost:7125/machine/update/status | python3 -c "
import sys,json
v = json.load(sys.stdin)['result']['version_info']['klipper']
print('valid=%s dirty=%s behind=%d' % (v['is_valid'], v['is_dirty'], len(v.get('commits_behind',[]))))
"

# 4. Heater temps
curl -s http://localhost:7125/printer/objects/query?heater_bed&extruder | python3 -m json.tool | head -10

# 5. Warnings
curl -s http://localhost:7125/server/info | python3 -c "
import sys,json; d=json.load(sys.stdin)['result']
print('warnings: %d, failed: %s' % (len(d['warnings']), d['failed_components']))
"
```

## Rollback

```bash
sudo systemctl stop klipper
rm -rf /home/mks/klipper
mv /home/mks/klipper.bak /home/mks/klipper
sudo systemctl start klipper
```
