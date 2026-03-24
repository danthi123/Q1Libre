# Klipper Diff Report

## Summary

| Category | Count |
|----------|------:|
| Qidi-custom | 5 |
| Modified | 25 |
| Identical | 0 |

## Modified Files

### `configfile.py`

**Recommendation:** investigate

```diff
--- upstream/configfile.py
+++ stock/configfile.py
@@ -1,16 +1,11 @@
 # Code for reading and writing the Klipper config file
 #
-# Copyright (C) 2016-2024  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import sys, os, glob, re, time, logging, configparser, io
 
 error = configparser.Error
-
-
-######################################################################
-# Config section parsing helper
-######################################################################
 
 class sentinel:
     pass
@@ -74,8 +69,6 @@
         return self._get_wrapper(self.fileconfig.getboolean, option, default,
                                  note_valid=note_valid)
     def getchoice(self, option, choices, default=sentinel, note_valid=True):
-        if type(choices) == type([]):
-            choices = {i: i for i in choices}
         if choices and type(list(choices.keys())[0]) == int:
             c = self.getint(option, default, note_valid=note_valid)
         else:
@@ -87,15 +80,11 @@
     def getlists(self, option, default=sentinel, seps=(',',), count=None,
                  parser=str, note_valid=True):
         def lparser(value, pos):
-            if len(value.strip()) == 0:
-                # Return an empty list instead of [''] for empty string
-                parts = []
-            else:
-                parts = [p.strip() for p in value.split(seps[pos])]
             if pos:
                 # Nested list
+                parts = [p.strip() for p in value.split(seps[pos])]
                 return tuple([lparser(p, pos - 1) for p in parts if p])
-            res = [parser(p) for p in parts]
+            res = [parser(p.strip()) for p in value.split(seps[pos])]
             if count is not None and len(res) != count:
                 raise error("Option '%s' in section '%s' must have %d elements"
                             % (option, self.section, count))
@@ -130,16 +119,39 @@
     def deprecate(self, option, value=None):
         if not self.fileconfig.has_option(self.section, option):
```

### `extras/bed_mesh.py`

**Recommendation:** investigate

```diff
--- upstream/extras/bed_mesh.py
+++ stock/extras/bed_mesh.py
@@ -1,5 +1,6 @@
 # Mesh Bed Leveling
 #
+# Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
 # Copyright (C) 2018-2019 Eric Callahan <arksine.code@gmail.com>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
@@ -34,7 +35,7 @@
 def lerp(t, v0, v1):
     return (1. - t) * v0 + t * v1
 
-# retrieve comma separated pair from config
+# retreive commma separated pair from config
 def parse_config_pair(config, option, default, minval=None, maxval=None):
     pair = config.getintlist(option, (default, default))
     if len(pair) != 2:
@@ -54,7 +55,7 @@
                 % (option, str(maxval)))
     return pair
 
-# retrieve comma separated pair from a g-code command
+# retreive commma separated pair from a g-code command
 def parse_gcmd_pair(gcmd, name, minval=None, maxval=None):
     try:
         pair = [int(v.strip()) for v in gcmd.get(name).split(',')]
@@ -74,7 +75,7 @@
                              % (name, maxval))
     return pair
 
-# retrieve comma separated coordinate from a g-code command
+# retreive commma separated coordinate from a g-code command
 def parse_gcmd_coord(gcmd, name):
     try:
         v1, v2 = [float(v.strip()) for v in gcmd.get(name).split(',')]
@@ -102,7 +103,6 @@
         self.log_fade_complete = False
         self.base_fade_target = config.getfloat('fade_target', None)
         self.fade_target = 0.
-        self.tool_offset = 0.
         self.gcode = self.printer.lookup_object('gcode')
         self.splitter = MoveSplitter(config, self.gcode)
         # setup persistent storage
@@ -121,11 +121,6 @@
         self.gcode.register_command(
             'BED_MESH_OFFSET', self.cmd_BED_MESH_OFFSET,
             desc=self.cmd_BED_MESH_OFFSET_help)
-        # Register dump webhooks
-        webhooks = self.printer.lookup_object('webhooks')
```

### `extras/force_move.py`

**Recommendation:** investigate

```diff
--- upstream/extras/force_move.py
+++ stock/extras/force_move.py
@@ -1,6 +1,6 @@
 # Utility for manually moving a stepper for diagnostic purposes
 #
-# Copyright (C) 2018-2025  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2018-2019  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import math, logging
@@ -10,6 +10,7 @@
 BUZZ_VELOCITY = BUZZ_DISTANCE / .250
 BUZZ_RADIANS_DISTANCE = math.radians(1.)
 BUZZ_RADIANS_VELOCITY = BUZZ_RADIANS_DISTANCE / .250
+STALL_TIME = 0.100
 
 # Calculate a move's accel_t, cruise_t, and cruise_v
 def calc_move_time(dist, speed, accel):
@@ -31,47 +32,49 @@
     def __init__(self, config):
         self.printer = config.get_printer()
         self.steppers = {}
+        self._enable = config.getboolean("enable_force_move", False)
         # Setup iterative solver
-        self.motion_queuing = self.printer.load_object(config, 'motion_queuing')
-        self.trapq = self.motion_queuing.allocate_trapq()
-        self.trapq_append = self.motion_queuing.lookup_trapq_append()
         ffi_main, ffi_lib = chelper.get_ffi()
+        self.trapq = ffi_main.gc(ffi_lib.trapq_alloc(), ffi_lib.trapq_free)
+        self.trapq_append = ffi_lib.trapq_append
+        self.trapq_finalize_moves = ffi_lib.trapq_finalize_moves
         self.stepper_kinematics = ffi_main.gc(
             ffi_lib.cartesian_stepper_alloc(b'x'), ffi_lib.free)
         # Register commands
-        self._enable_force_move = config.getboolean("enable_force_move", False)
-        if self._enable_force_move:
-            gcode = self.printer.lookup_object('gcode')
-            gcode.register_command('SET_KINEMATIC_POSITION',
-                                   self.cmd_SET_KINEMATIC_POSITION,
-                                   desc=self.cmd_SET_KINEMATIC_POSITION_help)
+        gcode = self.printer.lookup_object('gcode')
+        gcode.register_command('STEPPER_BUZZ', self.cmd_STEPPER_BUZZ,
+                               desc=self.cmd_STEPPER_BUZZ_help)
+        gcode.register_command('SET_KINEMATIC_POSITION',
+                                self.cmd_SET_KINEMATIC_POSITION,
+                                desc=self.cmd_SET_KINEMATIC_POSITION_help)
+        if config.getboolean("enable_force_move", False):
+            gcode.register_command('FORCE_MOVE', self.cmd_FORCE_MOVE,
+                                   desc=self.cmd_FORCE_MOVE_help)
     def register_stepper(self, config, mcu_stepper):
```

### `extras/gcode_move.py`

**Recommendation:** investigate

```diff
--- upstream/extras/gcode_move.py
+++ stock/extras/gcode_move.py
@@ -1,6 +1,6 @@
 # G-Code G1 movement commands (and associated coordinate manipulation)
 #
-# Copyright (C) 2016-2025  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import logging
@@ -8,6 +8,18 @@
 class GCodeMove:
     def __init__(self, config):
         self.printer = printer = config.get_printer()
+        printer.register_event_handler("klippy:ready", self._handle_ready)
+        printer.register_event_handler("klippy:shutdown", self._handle_shutdown)
+        printer.register_event_handler("toolhead:set_position",
+                                       self.reset_last_position)
+        printer.register_event_handler("toolhead:manual_move",
+                                       self.reset_last_position)
+        printer.register_event_handler("gcode:command_error",
+                                       self.reset_last_position)
+        printer.register_event_handler("extruder:activate_extruder",
+                                       self._handle_activate_extruder)
+        printer.register_event_handler("homing:home_rails_end",
+                                       self._handle_home_rails_end)
         self.is_printer_ready = False
         # Register g-code commands
         gcode = printer.lookup_object('gcode')
@@ -30,7 +42,6 @@
         self.base_position = [0.0, 0.0, 0.0, 0.0]
         self.last_position = [0.0, 0.0, 0.0, 0.0]
         self.homing_position = [0.0, 0.0, 0.0, 0.0]
-        self.axis_map = {'X':0, 'Y': 1, 'Z': 2, 'E': 3}
         self.speed = 25.
         self.speed_factor = 1. / 60.
         self.extrude_factor = 1.
@@ -38,23 +49,29 @@
         self.saved_states = {}
         self.move_transform = self.move_with_transform = None
         self.position_with_transform = (lambda: [0., 0., 0., 0.])
-        # Register callbacks
-        printer.register_event_handler("klippy:ready", self._handle_ready)
-        printer.register_event_handler("klippy:shutdown", self._handle_shutdown)
-        printer.register_event_handler("klippy:analyze_shutdown",
-                                       self._handle_analyze_shutdown)
-        printer.register_event_handler("toolhead:set_position",
-                                       self.reset_last_position)
-        printer.register_event_handler("toolhead:manual_move",
-                                       self.reset_last_position)
```

### `extras/hall_filament_width_sensor.py`

**Recommendation:** investigate

```diff
--- upstream/extras/hall_filament_width_sensor.py
+++ stock/extras/hall_filament_width_sensor.py
@@ -30,8 +30,7 @@
                              - self.measurement_max_difference)
         self.diameter =self.nominal_filament_dia
         self.is_active =config.getboolean('enable', False)
-        self.runout_dia_min=config.getfloat('min_diameter', 1.0)
-        self.runout_dia_max=config.getfloat('max_diameter', self.max_diameter)
+        self.runout_dia=config.getfloat('min_diameter', 1.0)
         self.is_log =config.getboolean('logging', False)
         # Use the current diameter instead of nominal while the first
         # measurement isn't in place
@@ -49,13 +48,11 @@
         # Start adc
         self.ppins = self.printer.lookup_object('pins')
         self.mcu_adc = self.ppins.setup_pin('adc', self.pin1)
-        self.mcu_adc.setup_adc_sample(ADC_REPORT_TIME,
-                                      ADC_SAMPLE_TIME, ADC_SAMPLE_COUNT)
-        self.mcu_adc.setup_adc_callback(self.adc_callback)
+        self.mcu_adc.setup_minmax(ADC_SAMPLE_TIME, ADC_SAMPLE_COUNT)
+        self.mcu_adc.setup_adc_callback(ADC_REPORT_TIME, self.adc_callback)
         self.mcu_adc2 = self.ppins.setup_pin('adc', self.pin2)
-        self.mcu_adc2.setup_adc_sample(ADC_REPORT_TIME,
-                                       ADC_SAMPLE_TIME, ADC_SAMPLE_COUNT)
-        self.mcu_adc2.setup_adc_callback(self.adc2_callback)
+        self.mcu_adc2.setup_minmax(ADC_SAMPLE_TIME, ADC_SAMPLE_COUNT)
+        self.mcu_adc2.setup_adc_callback(ADC_REPORT_TIME, self.adc2_callback)
         # extrude factor updating
         self.extrude_factor_update_timer = self.reactor.register_timer(
             self.extrude_factor_update_event)
@@ -85,14 +82,12 @@
         self.reactor.update_timer(self.extrude_factor_update_timer,
                                   self.reactor.NOW)
 
-    def adc_callback(self, samples):
+    def adc_callback(self, read_time, read_value):
         # read sensor value
-        read_time, read_value = samples[-1]
         self.lastFilamentWidthReading = round(read_value * 10000)
 
-    def adc2_callback(self, samples):
+    def adc2_callback(self, read_time, read_value):
         # read sensor value
-        read_time, read_value = samples[-1]
         self.lastFilamentWidthReading2 = round(read_value * 10000)
         # calculate diameter
         diameter_new = round((self.dia2 - self.dia1)/
@@ -129,8 +124,8 @@
         # Update filament array for lastFilamentWidthReading
         self.update_filament_array(last_epos)
```

### `extras/heaters.py`

**Recommendation:** investigate

```diff
--- upstream/extras/heaters.py
+++ stock/extras/heaters.py
@@ -1,6 +1,6 @@
 # Tracking of PWM controlled heaters and their temperature control
 #
-# Copyright (C) 2016-2025  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2020  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import os, logging, threading
@@ -11,18 +11,14 @@
 ######################################################################
 
 KELVIN_TO_CELSIUS = -273.15
-MAX_HEAT_TIME = 3.0
+MAX_HEAT_TIME = 5.0
 AMBIENT_TEMP = 25.
 PID_PARAM_BASE = 255.
-MAX_MAINTHREAD_TIME = 5.0
-QUELL_STALE_TIME = 7.0
-MIN_PWM_CHANGE_RATIO = 0.05
 
 class Heater:
     def __init__(self, config, sensor):
         self.printer = config.get_printer()
-        self.name = config.get_name()
-        self.short_name = short_name = self.name.split()[-1]
+        self.name = config.get_name().split()[-1]
         # Setup sensor
         self.sensor = sensor
         self.min_temp = config.getfloat('min_temp', minval=KELVIN_TO_CELSIUS)
@@ -38,10 +34,8 @@
                          is not None)
         self.can_extrude = self.min_extrude_temp <= 0. or is_fileoutput
         self.max_power = config.getfloat('max_power', 1., above=0., maxval=1.)
-        self.min_pwm_change = self.max_power * MIN_PWM_CHANGE_RATIO
         self.smooth_time = config.getfloat('smooth_time', 1., above=0.)
         self.inv_smooth_time = 1. / self.smooth_time
-        self.verify_mainthread_time = -999.
         self.lock = threading.Lock()
         self.last_temp = self.smoothed_temp = self.target_temp = 0.
         self.last_temp_time = 0.
@@ -61,24 +55,21 @@
         self.mcu_pwm.setup_cycle_time(pwm_cycle_time)
         self.mcu_pwm.setup_max_duration(MAX_HEAT_TIME)
         # Load additional modules
-        self.printer.load_object(config, "verify_heater %s" % (short_name,))
+        self.printer.load_object(config, "verify_heater %s" % (self.name,))
         self.printer.load_object(config, "pid_calibrate")
         gcode = self.printer.lookup_object("gcode")
```

### `extras/homing.py`

**Recommendation:** investigate

```diff
--- upstream/extras/homing.py
+++ stock/extras/homing.py
@@ -1,6 +1,6 @@
 # Helper code for implementing homing operations
 #
-# Copyright (C) 2016-2024  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import logging, math
@@ -29,23 +29,16 @@
         self.endstop_name = endstop_name
         self.stepper_name = stepper.get_name()
         self.start_pos = stepper.get_mcu_position()
-        self.start_cmd_pos = stepper.mcu_to_commanded_position(self.start_pos)
         self.halt_pos = self.trig_pos = None
     def note_home_end(self, trigger_time):
         self.halt_pos = self.stepper.get_mcu_position()
         self.trig_pos = self.stepper.get_past_mcu_position(trigger_time)
-    def verify_no_probe_skew(self, haltpos):
-        new_start_pos = self.stepper.get_mcu_position(self.start_cmd_pos)
-        if new_start_pos != self.start_pos:
-            logging.warning(
-                "Stepper '%s' position skew after probe: pos %d now %d",
-                self.stepper.get_name(), self.start_pos, new_start_pos)
 
 # Implementation of homing/probing moves
 class HomingMove:
     def __init__(self, printer, endstops, toolhead=None):
         self.printer = printer
-        self.endstops = [es for es in endstops if es[0].get_steppers()]
+        self.endstops = endstops
         if toolhead is None:
             toolhead = printer.lookup_object('toolhead')
         self.toolhead = toolhead
@@ -71,9 +64,7 @@
             sname = stepper.get_name()
             kin_spos[sname] += offsets.get(sname, 0) * stepper.get_step_dist()
         thpos = self.toolhead.get_position()
-        cpos = kin.calc_position(kin_spos)
-        return [cp if cp is not None else tp
-                for cp, tp in zip(cpos, thpos[:3])] + thpos[3:]
+        return list(kin.calc_position(kin_spos))[:3] + thpos[3:]
     def homing_move(self, movepos, speed, probe_pos=False,
                     triggered=True, check_triggered=True):
         # Notify start of homing/probing move
@@ -107,14 +98,11 @@
         trigger_times = {}
         move_end_print_time = self.toolhead.get_last_move_time()
         for mcu_endstop, name in self.endstops:
```

### `extras/print_stats.py`

**Recommendation:** investigate

```diff
--- upstream/extras/print_stats.py
+++ stock/extras/print_stats.py
@@ -15,11 +15,6 @@
         self.gcode.register_command(
             "SET_PRINT_STATS_INFO", self.cmd_SET_PRINT_STATS_INFO,
             desc=self.cmd_SET_PRINT_STATS_INFO_help)
-        printer.register_event_handler("extruder:activate_extruder",
-                                       self._handle_activate_extruder)
-    def _handle_activate_extruder(self):
-        gc_status = self.gcode_move.get_status()
-        self.last_epos = gc_status['position'].e
     def _update_filament_usage(self, eventtime):
         gc_status = self.gcode_move.get_status(eventtime)
         cur_epos = gc_status['position'].e
```

### `extras/probe.py`

**Recommendation:** investigate

```diff
--- upstream/extras/probe.py
+++ stock/extras/probe.py
@@ -1,6 +1,6 @@
 # Z-Probe support
 #
-# Copyright (C) 2017-2024  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2017-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import logging
@@ -12,213 +12,53 @@
 consider reducing the Z axis minimum position so the probe
 can travel further (the Z minimum position can be negative).
 """
+_NERVER = 9999999
 
-# Calculate the average Z from a set of positions
-def calc_probe_z_average(positions, method='average'):
-    if method != 'median':
-        # Use mean average
-        inv_count = 1. / float(len(positions))
-        return manual_probe.ProbeResult(
-            *[sum([pos[i] for pos in positions]) * inv_count
-              for i in range(len(positions[0]))])
-    # Use median
-    z_sorted = sorted(positions, key=(lambda p: p.bed_z))
-    middle = len(positions) // 2
-    if (len(positions) & 1) == 1:
-        # odd number of samples
-        return z_sorted[middle]
-    # even number of samples
-    return calc_probe_z_average(z_sorted[middle-1:middle+1], 'average')
-
-
-######################################################################
-# Probe device implementation helpers
-######################################################################
-
-# Helper to implement common probing commands
-class ProbeCommandHelper:
-    def __init__(self, config, probe, query_endstop=None,
-                 can_set_z_offset=True):
+class PrinterProbe:
+    def __init__(self, config, mcu_probe):
         self.printer = config.get_printer()
-        self.probe = probe
-        self.query_endstop = query_endstop
         self.name = config.get_name()
-        gcode = self.printer.lookup_object('gcode')
-        # QUERY_PROBE command
```

### `extras/smart_effector.py`

**Recommendation:** investigate

```diff
--- upstream/extras/smart_effector.py
+++ stock/extras/smart_effector.py
@@ -48,13 +48,13 @@
             bit_time += bit_step
         return bit_time
 
-class SmartEffectorProbe:
+class SmartEffectorEndstopWrapper:
     def __init__(self, config):
         self.printer = config.get_printer()
         self.gcode = self.printer.lookup_object('gcode')
         self.probe_accel = config.getfloat('probe_accel', 0., minval=0.)
         self.recovery_time = config.getfloat('recovery_time', 0.4, minval=0.)
-        self.probe_wrapper = probe.ProbeEndstopWrapper(config)
+        self.probe_wrapper = self.probe_wrapper_2 = probe.ProbeEndstopWrapper(config)
         # Wrappers
         self.get_mcu = self.probe_wrapper.get_mcu
         self.add_stepper = self.probe_wrapper.add_stepper
@@ -64,16 +64,6 @@
         self.query_endstop = self.probe_wrapper.query_endstop
         self.multi_probe_begin = self.probe_wrapper.multi_probe_begin
         self.multi_probe_end = self.probe_wrapper.multi_probe_end
-        self.get_position_endstop = self.probe_wrapper.get_position_endstop
-        # Common probe implementation helpers
-        self.cmd_helper = probe.ProbeCommandHelper(
-            config, self, self.probe_wrapper.query_endstop)
-        self.probe_offsets = probe.ProbeOffsetsHelper(config)
-        self.param_helper = probe.ProbeParameterHelper(config)
-        self.homing_helper = probe.HomingViaProbeHelper(
-            config, self, self.probe_offsets, self.param_helper)
-        self.probe_session = probe.ProbeSessionHelper(
-            config, self.param_helper, self.homing_helper.start_probe_session)
         # SmartEffector control
         control_pin = config.get('control_pin', None)
         if control_pin:
@@ -88,14 +78,16 @@
         self.gcode.register_command("SET_SMART_EFFECTOR",
                                     self.cmd_SET_SMART_EFFECTOR,
                                     desc=self.cmd_SET_SMART_EFFECTOR_help)
-    def get_probe_params(self, gcmd=None):
-        return self.param_helper.get_probe_params(gcmd)
-    def get_offsets(self, gcmd=None):
-        return self.probe_offsets.get_offsets(gcmd)
-    def get_status(self, eventtime):
-        return self.cmd_helper.get_status(eventtime)
-    def start_probe_session(self, gcmd):
-        return self.probe_session.start_probe_session(gcmd)
+        self.gcode.register_command("CHANGE_PIN",
+                                    self.cmd_CHANGE_PIN,
+                                    desc=self.cmd_CHANGE_PIN_help)
```

### `extras/spi_temperature.py`

**Recommendation:** investigate

```diff
--- upstream/extras/spi_temperature.py
+++ stock/extras/spi_temperature.py
@@ -4,7 +4,7 @@
 # Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
-import math, logging
+import math
 from . import bus
 
 
@@ -13,7 +13,6 @@
 ######################################################################
 
 REPORT_TIME = 0.300
-MAX_INVALID_COUNT = 3
 
 class SensorBase:
     def __init__(self, config, chip_type, config_cmd=None, spi_mode=1):
@@ -29,9 +28,8 @@
         self.mcu = mcu = self.spi.get_mcu()
         # Reader chip configuration
         self.oid = oid = mcu.create_oid()
-        mcu.register_serial_response(
-            self._handle_spi_response,
-            "thermocouple_result oid=%c next_clock=%u value=%u fault=%c", oid)
+        mcu.register_response(self._handle_spi_response,
+                              "thermocouple_result", oid)
         mcu.register_config_callback(self._build_config)
     def setup_minmax(self, min_temp, max_temp):
         adc_range = [self.calc_adc(min_temp), self.calc_adc(max_temp)]
@@ -49,21 +47,17 @@
         self._report_clock = self.mcu.seconds_to_clock(REPORT_TIME)
         self.mcu.add_config_cmd(
             "query_thermocouple oid=%u clock=%u rest_ticks=%u"
-            " min_value=%u max_value=%u max_invalid_count=%u" % (
+            " min_value=%u max_value=%u" % (
                 self.oid, clock, self._report_clock,
-                self.min_sample_value, self.max_sample_value,
-                MAX_INVALID_COUNT), is_init=True)
+                self.min_sample_value, self.max_sample_value), is_init=True)
     def _handle_spi_response(self, params):
-        if params['fault']:
-            self.handle_fault(params['value'], params['fault'])
-            return
-        temp = self.calc_temp(params['value'])
+        temp = self.calc_temp(params['value'], params['fault']) 
         next_clock      = self.mcu.clock32_to_clock64(params['next_clock'])
         last_read_clock = next_clock - self._report_clock
         last_read_time  = self.mcu.clock_to_print_time(last_read_clock)
```

### `extras/tmc.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc.py
+++ stock/extras/tmc.py
@@ -5,7 +5,6 @@
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import logging, collections
 import stepper
-from . import bulk_sensor
 
 
 ######################################################################
@@ -128,7 +127,7 @@
         self.adc_temp_reg = self.fields.lookup_register("adc_temp")
         if self.adc_temp_reg is not None:
             pheaters = self.printer.load_object(config, 'heaters')
-            pheaters.register_monitor(config)
+            # pheaters.register_monitor(config)
     def _query_register(self, reg_info, try_clear=False):
         last_value, reg_name, mask, err_mask, cs_actual_mask = reg_info
         cleared_flags = 0
@@ -162,7 +161,9 @@
             if count >= 3:
                 fmt = self.fields.pretty_format(reg_name, val)
                 raise self.printer.command_error("TMC '%s' reports error: %s"
-                                                 % (self.stepper_name, fmt))
+                                                % (self.stepper_name, fmt))
+            if "uv_cp" in fmt:
+                try_clear = True
             if try_clear and val & err_mask:
                 try_clear = False
                 cleared_flags |= val & err_mask
@@ -221,96 +222,6 @@
             self.last_drv_fields = {n: v for n, v in fields.items() if v}
         return {'drv_status': self.last_drv_fields, 'temperature': temp}
 
-######################################################################
-# Record driver status
-######################################################################
-
-class TMCStallguardDump:
-    def __init__(self, config, mcu_tmc):
-        self.printer = config.get_printer()
-        self.stepper_name = ' '.join(config.get_name().split()[1:])
-        self.mcu_tmc = mcu_tmc
-        self.mcu = self.mcu_tmc.get_mcu()
-        self.fields = self.mcu_tmc.get_fields()
-        self.sg2_supp = False
-        self.sg4_reg_name = None
-        # It is possible to support TMC2660, just disable it for now
-        if not self.fields.all_fields.get("DRV_STATUS", None):
-            return
```

### `extras/tmc2130.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc2130.py
+++ stock/extras/tmc2130.py
@@ -200,21 +200,12 @@
         cmd = self._build_cmd([reg, 0x00, 0x00, 0x00, 0x00], chain_pos)
         self.spi.spi_send(cmd)
         if self.printer.get_start_args().get('debugoutput') is not None:
-            return {
-                "spi_status": 0,
-                "data": 0,
-                "#receive_time": .0,
-            }
+            return 0
         params = self.spi.spi_transfer(cmd)
         pr = bytearray(params['response'])
         pr = pr[(self.chain_len - chain_pos) * 5 :
                 (self.chain_len - chain_pos + 1) * 5]
-        return {
-            "spi_status": pr[0],
-            "data": (pr[1] << 24) | (pr[2] << 16) | (pr[3] << 8) | pr[4],
-            "#receive_time": params["#receive_time"],
-        }
-
+        return (pr[1] << 24) | (pr[2] << 16) | (pr[3] << 8) | pr[4]
     def reg_write(self, reg, val, chain_pos, print_time=None):
         minclock = 0
         if print_time is not None:
@@ -232,8 +223,6 @@
         pr = pr[(self.chain_len - chain_pos) * 5 :
                 (self.chain_len - chain_pos + 1) * 5]
         return (pr[1] << 24) | (pr[2] << 16) | (pr[3] << 8) | pr[4]
-    def get_mcu(self):
-        return self.spi.get_mcu()
 
 # Helper to setup an spi daisy chain bus from settings in a config section
 def lookup_tmc_spi_chain(config):
@@ -269,20 +258,11 @@
         self.tmc_frequency = tmc_frequency
     def get_fields(self):
         return self.fields
-    def get_register_raw(self, reg_name):
+    def get_register(self, reg_name):
         reg = self.name_to_reg[reg_name]
         with self.mutex:
-            resp = self.tmc_spi.reg_read(reg, self.chain_pos)
-        return resp
-    def decode_spi_status(spi_status):
-        return {
-            "standstill": spi_status >> 3 & 0x1,
-            "sg2": spi_status >> 2 & 0x1,
-            "driver_error": spi_status >> 1 & 0x1,
```

### `extras/tmc2208.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc2208.py
+++ stock/extras/tmc2208.py
@@ -197,7 +197,7 @@
         self.get_status = cmdhelper.get_status
         # Setup basic register values
         self.fields.set_field("mstep_reg_select", True)
-        tmc.TMCStealthchopHelper(config, self.mcu_tmc)
+        tmc.TMCStealthchopHelper(config, self.mcu_tmc, TMC_FREQUENCY)
         # Allow other registers to be set from the config
         set_config_field = self.fields.set_config_field
         # GCONF
@@ -215,7 +215,6 @@
         set_config_field(config, "pwm_freq", 1)
         set_config_field(config, "pwm_autoscale", True)
         set_config_field(config, "pwm_autograd", True)
-        set_config_field(config, "freewheel", 0)
         set_config_field(config, "pwm_reg", 8)
         set_config_field(config, "pwm_lim", 12)
         # TPOWERDOWN
```

### `extras/tmc2209.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc2209.py
+++ stock/extras/tmc2209.py
@@ -73,8 +73,7 @@
         self.get_status = cmdhelper.get_status
         # Setup basic register values
         self.fields.set_field("mstep_reg_select", True)
-        tmc.TMCStealthchopHelper(config, self.mcu_tmc)
-        tmc.TMCVcoolthrsHelper(config, self.mcu_tmc)
+        tmc.TMCStealthchopHelper(config, self.mcu_tmc, TMC_FREQUENCY)
         # Allow other registers to be set from the config
         set_config_field = self.fields.set_config_field
         # GCONF
@@ -84,12 +83,6 @@
         set_config_field(config, "hstrt", 5)
         set_config_field(config, "hend", 0)
         set_config_field(config, "tbl", 2)
-        # COOLCONF
-        set_config_field(config, "semin", 0)
-        set_config_field(config, "seup", 0)
-        set_config_field(config, "semax", 0)
-        set_config_field(config, "sedn", 0)
-        set_config_field(config, "seimin", 0)
         # IHOLDIRUN
         set_config_field(config, "iholddelay", 8)
         # PWMCONF
@@ -98,7 +91,6 @@
         set_config_field(config, "pwm_freq", 1)
         set_config_field(config, "pwm_autoscale", True)
         set_config_field(config, "pwm_autograd", True)
-        set_config_field(config, "freewheel", 0)
         set_config_field(config, "pwm_reg", 8)
         set_config_field(config, "pwm_lim", 12)
         # TPOWERDOWN
```

### `extras/tmc2240.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc2240.py
+++ stock/extras/tmc2240.py
@@ -58,9 +58,8 @@
 ReadRegisters = [
     "GCONF", "GSTAT", "IOIN", "DRV_CONF", "GLOBALSCALER", "IHOLD_IRUN",
     "TPOWERDOWN", "TSTEP", "TPWMTHRS", "TCOOLTHRS", "THIGH", "ADC_VSUPPLY_AIN",
-    "ADC_TEMP", "OTW_OV_VTH", "MSCNT", "MSCURACT", "CHOPCONF", "COOLCONF",
-    "DRV_STATUS", "PWMCONF", "PWM_SCALE", "PWM_AUTO", "SG4_THRS", "SG4_RESULT",
-    "SG4_IND"
+    "ADC_TEMP", "MSCNT", "MSCURACT", "CHOPCONF", "COOLCONF", "DRV_STATUS",
+    "PWMCONF", "PWM_SCALE", "PWM_AUTO", "SG4_THRS", "SG4_RESULT", "SG4_IND"
 ]
 
 Fields = {}
@@ -96,7 +95,7 @@
     "s2vsb":                    0x01 << 13,
     "stealth":                  0x01 << 14,
     "fsactive":                 0x01 << 15,
-    "cs_actual":                0x1F << 16,
+    "csactual":                 0x1F << 16,
     "stallguard":               0x01 << 24,
     "ot":                       0x01 << 25,
     "otpw":                     0x01 << 26,
@@ -260,11 +259,6 @@
     "s2vsa":            (lambda v: "1(ShortToSupply_A!)" if v else ""),
     "s2vsb":            (lambda v: "1(ShortToSupply_B!)" if v else ""),
     "adc_temp":         (lambda v: "0x%04x(%.1fC)" % (v, ((v - 2038) / 7.7))),
-    "adc_vsupply":      (lambda v: "0x%04x(%.3fV)" % (v, v * 0.009732)),
-    "adc_ain":          (lambda v: "0x%04x(%.3fmV)" % (v, v * 0.3052)),
-    "overvoltage_vth":  (lambda v: "0x%04x(%.3fV)" % (v, v * 0.009732)),
-    "overtempprewarning_vth": (lambda v:
-                               "0x%04x(%.1fC)" % (v, ((v - 2038) / 7.7))),
 })
 
 
@@ -352,7 +346,7 @@
         if config.get("uart_pin", None) is not None:
             # use UART for communication
             self.mcu_tmc = tmc_uart.MCU_TMC_uart(config, Registers, self.fields,
-                                                 7, TMC_FREQUENCY)
+                                                 3, TMC_FREQUENCY)
         else:
             # Use SPI bus for communication
             self.mcu_tmc = tmc2130.MCU_TMC_SPI(config, Registers, self.fields,
@@ -368,10 +362,7 @@
         # Setup basic register values
         tmc.TMCWaveTableHelper(config, self.mcu_tmc)
         self.fields.set_config_field(config, "offset_sin90", 0)
-        tmc.TMCStealthchopHelper(config, self.mcu_tmc)
-        tmc.TMCVcoolthrsHelper(config, self.mcu_tmc)
```

### `extras/tmc2660.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc2660.py
+++ stock/extras/tmc2660.py
@@ -198,14 +198,11 @@
         self.fields = fields
     def get_fields(self):
         return self.fields
-    def get_register_raw(self, reg_name):
+    def get_register(self, reg_name):
         new_rdsel = ReadRegisters.index(reg_name)
         reg = self.name_to_reg["DRVCONF"]
         if self.printer.get_start_args().get('debugoutput') is not None:
-            return {
-                'data': 0,
-                '#receive_time': .0,
-            }
+            return 0
         with self.mutex:
             old_rdsel = self.fields.get_field("rdsel")
             val = self.fields.set_field("rdsel", new_rdsel)
@@ -215,12 +212,7 @@
                 self.spi.spi_send(msg)
             params = self.spi.spi_transfer(msg)
         pr = bytearray(params['response'])
-        return {
-            'data': (pr[0] << 16) | (pr[1] << 8) | pr[2],
-            '#receive_time': params['#receive_time'],
-        }
-    def get_register(self, reg_name):
-        return self.get_register_raw(reg_name)['data']
+        return (pr[0] << 16) | (pr[1] << 8) | pr[2]
     def set_register(self, reg_name, val, print_time=None):
         minclock = 0
         if print_time is not None:
@@ -231,8 +223,6 @@
             self.spi.spi_send(msg, minclock)
     def get_tmc_frequency(self):
         return None
-    def get_mcu(self):
-        return self.spi.get_mcu()
 
 
 ######################################################################
```

### `extras/tmc5160.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc5160.py
+++ stock/extras/tmc5160.py
@@ -118,7 +118,7 @@
     "s2vsb":                    0x01 << 13,
     "stealth":                  0x01 << 14,
     "fsactive":                 0x01 << 15,
-    "cs_actual":                0x1F << 16,
+    "csactual":                 0xFF << 16,
     "stallguard":               0x01 << 24,
     "ot":                       0x01 << 25,
     "otpw":                     0x01 << 26,
@@ -241,9 +241,6 @@
 }
 Fields["TSTEP"] = {
     "tstep":                    0xfffff << 0
-}
-Fields["THIGH"] = {
-    "thigh":                    0xfffff << 0
 }
 
 SignedFields = ["cur_a", "cur_b", "sgt", "xactual", "vactual", "pwm_scale_auto"]
@@ -338,10 +335,7 @@
         self.get_status = cmdhelper.get_status
         # Setup basic register values
         tmc.TMCWaveTableHelper(config, self.mcu_tmc)
-        tmc.TMCStealthchopHelper(config, self.mcu_tmc)
-        tmc.TMCVcoolthrsHelper(config, self.mcu_tmc)
-        tmc.TMCVhighHelper(config, self.mcu_tmc)
-        # Allow other registers to be set from the config
+        tmc.TMCStealthchopHelper(config, self.mcu_tmc, TMC_FREQUENCY)
         set_config_field = self.fields.set_config_field
         #   GCONF
         set_config_field(config, "multistep_filt", True)
```

### `extras/tmc_uart.py`

**Recommendation:** investigate

```diff
--- upstream/extras/tmc_uart.py
+++ stock/extras/tmc_uart.py
@@ -175,10 +175,7 @@
             self.analog_mux.activate(instance_id)
         msg = self._encode_read(0xf5, addr, reg)
         params = self.tmcuart_send_cmd.send([self.oid, msg, 10])
-        return {
-            'data': self._decode_read(reg, params['read']),
-            '#receive_time': params['#receive_time']
-        }
+        return self._decode_read(reg, params['read'])
     def reg_write(self, instance_id, addr, reg, val, print_time=None):
         minclock = 0
         if print_time is not None:
@@ -187,8 +184,6 @@
             self.analog_mux.activate(instance_id)
         msg = self._encode_write(0xf5, addr, reg | 0x80, val)
         self.tmcuart_send_cmd.send([self.oid, msg, 0], minclock=minclock)
-    def get_mcu(self):
-        return self.mcu
 
 # Lookup a (possibly shared) tmc uart
 def lookup_tmc_uart_bitbang(config, max_addr):
@@ -230,21 +225,16 @@
     def _do_get_register(self, reg_name):
         reg = self.name_to_reg[reg_name]
         if self.printer.get_start_args().get('debugoutput') is not None:
-            return {
-                'data': 0,
-                '#receive_time': 0.
-            }
+            return 0
         for retry in range(5):
             val = self.mcu_uart.reg_read(self.instance_id, self.addr, reg)
-            if val['data'] is not None:
+            if val is not None:
                 return val
         raise self.printer.command_error(
             "Unable to read tmc uart '%s' register %s" % (self.name, reg_name))
-    def get_register_raw(self, reg_name):
+    def get_register(self, reg_name):
         with self.mutex:
             return self._do_get_register(reg_name)
-    def get_register(self, reg_name):
-        return self.get_register_raw(reg_name)['data']
     def set_register(self, reg_name, val, print_time=None):
         reg = self.name_to_reg[reg_name]
         if self.printer.get_start_args().get('debugoutput') is not None:
@@ -253,15 +243,13 @@
             for retry in range(5):
```

### `extras/virtual_sdcard.py`

**Recommendation:** investigate

```diff
--- upstream/extras/virtual_sdcard.py
+++ stock/extras/virtual_sdcard.py
@@ -1,21 +1,19 @@
 # Virtual sdcard support (print files directly from a host g-code file)
 #
-# Copyright (C) 2018-2024  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
-import os, sys, logging, io
+import os, sys, logging
+reload(sys)
+sys.setdefaultencoding('utf-8')
 
 VALID_GCODE_EXTS = ['gcode', 'g', 'gco']
-
-DEFAULT_ERROR_GCODE = """
-{% if 'heaters' in printer %}
-   TURN_OFF_HEATERS
-{% endif %}
-"""
 
 class VirtualSD:
     def __init__(self, config):
         self.printer = config.get_printer()
+        self.printer.register_event_handler("klippy:shutdown",
+                                            self.handle_shutdown)
         # sdcard state
         sd = config.get('path')
         self.sdcard_dirname = os.path.normpath(os.path.expanduser(sd))
@@ -31,7 +29,12 @@
         # Error handling
         gcode_macro = self.printer.load_object(config, 'gcode_macro')
         self.on_error_gcode = gcode_macro.load_template(
-            config, 'on_error_gcode', DEFAULT_ERROR_GCODE)
+            config, 'on_error_gcode', '')
+        
+        # power lose resume
+        self.lines = 0
+        self.save_every_n_lines = 50
+        
         # Register commands
         self.gcode = self.printer.lookup_object('gcode')
         for cmd in ['M20', 'M21', 'M23', 'M24', 'M25', 'M26', 'M27']:
@@ -44,9 +47,7 @@
         self.gcode.register_command(
             "SDCARD_PRINT_FILE", self.cmd_SDCARD_PRINT_FILE,
             desc=self.cmd_SDCARD_PRINT_FILE_help)
-        self.printer.register_event_handler("klippy:analyze_shutdown",
-                                            self._handle_analyze_shutdown)
```

### `gcode.py`

**Recommendation:** investigate

```diff
--- upstream/gcode.py
+++ stock/gcode.py
@@ -1,26 +1,20 @@
 # Parse gcode commands
 #
-# Copyright (C) 2016-2025  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
-import os, re, logging, collections, shlex, operator
+import os, re, logging, collections, shlex
 
 class CommandError(Exception):
     pass
 
-# Custom "tuple" class for coordinates - add easy access to x, y, z components
-class Coord(tuple):
-    __slots__ = ()
-    def __new__(cls, t):
-        if len(t) < 4:
-            t = tuple(t) + (0,) * (4 - len(t))
-        return tuple.__new__(cls, t)
-    x = property(operator.itemgetter(0))
-    y = property(operator.itemgetter(1))
-    z = property(operator.itemgetter(2))
-    e = property(operator.itemgetter(3))
+Coord = collections.namedtuple('Coord', ('x', 'y', 'z', 'e'))
+priority_queue = []
+set_gcode_offset_r = re.compile(
+    r'^\s*SET_GCODE_OFFSET(?:\s+[a-zA-Z_]+=[+-]?\d*\.?\d+)*\s+MOVE=1(?:\s+[a-zA-Z_]+=[+-]?\d*\.?\d+)*(?:\s|$)',
+    re.IGNORECASE
+    )
 
-# Class for handling gcode command parameters (gcmd)
 class GCodeCommand:
     error = CommandError
     def __init__(self, gcode, command, commandline, params, need_ack):
@@ -39,18 +33,19 @@
         return self._params
     def get_raw_command_parameters(self):
         command = self._command
-        origline = self._commandline
-        param_start = len(command)
-        param_end = len(origline)
-        if origline[:param_start].upper() != command:
-            # Skip any gcode line-number and ignore any trailing checksum
-            param_start += origline.upper().find(command)
-            end = origline.rfind('*')
-            if end >= 0 and origline[end+1:].isdigit():
-                param_end = end
```

### `klippy.py`

**Recommendation:** investigate

```diff
--- upstream/klippy.py
+++ stock/klippy.py
@@ -1,7 +1,7 @@
 #!/usr/bin/env python2
 # Main code for host side printer firmware
 #
-# Copyright (C) 2016-2024  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2020  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import sys, os, gc, optparse, logging, time, collections, importlib
@@ -20,6 +20,31 @@
 Once the underlying issue is corrected, use the "RESTART"
 command to reload the config and restart the host software.
 Printer is halted
+"""
+
+message_protocol_error1 = """
+This is frequently caused by running an older version of the
+firmware on the MCU(s). Fix by recompiling and flashing the
+firmware.
+"""
+
+message_protocol_error2 = """
+Once the underlying issue is corrected, use the "RESTART"
+command to reload the config and restart the host software.
+"""
+
+message_mcu_connect_error = """
+Once the underlying issue is corrected, use the
+"FIRMWARE_RESTART" command to reset the firmware, reload the
+config, and restart the host software.
+Error configuring printer
+"""
+
+message_shutdown = """
+Once the underlying issue is corrected, use the
+"FIRMWARE_RESTART" command to reset the firmware, reload the
+config, and restart the host software.
+Printer is shutdown
 """
 
 class Printer:
@@ -60,18 +85,24 @@
         if (msg != message_ready
             and self.start_args.get('debuginput') is not None):
             self.request_exit('error_exit')
-    def update_error_msg(self, oldmsg, newmsg):
-        if (self.state_message != oldmsg
-            or self.state_message in (message_ready, message_startup)
```

### `mcu.py`

**Recommendation:** investigate

```diff
--- upstream/mcu.py
+++ stock/mcu.py
@@ -1,162 +1,19 @@
 # Interface to Klipper micro-controller code
 #
-# Copyright (C) 2016-2026  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
-import sys, os, zlib, logging, math, struct
+import sys, os, zlib, logging, math
 import serialhdl, msgproto, pins, chelper, clocksync
 
 class error(Exception):
     pass
 
-# Minimum time host needs to get scheduled events queued into mcu
-MIN_SCHEDULE_TIME = 0.100
-# The maximum number of clock cycles an MCU is expected
-# to schedule into the future, due to the protocol and firmware.
-MAX_SCHEDULE_TICKS = (1<<31) - 1
-# Maximum time all MCUs can internally schedule into the future.
-# Directly caused by the limitation of MAX_SCHEDULE_TICKS.
-MAX_NOMINAL_DURATION = 3.0
-
-######################################################################
-# Command transmit helper classes
-######################################################################
-
-# Generate a dummy response to query commands when in debugging mode
-class DummyResponse:
-    def __init__(self, serial, name, oid=None):
-        params = {}
-        if oid is not None:
-            params['oid'] = oid
-        msgparser = serial.get_msgparser()
-        resp = msgparser.create_dummy_response(name, params)
-        resp['#sent_time'] = 0.
-        resp['#receive_time'] = 0.
-        self._response = resp
-    def get_response(self, cmds, cmd_queue, minclock=0, reqclock=0, retry=True):
-        return dict(self._response)
-
-# Class to retry sending of a query command until a given response is received
-class RetryAsyncCommand:
-    TIMEOUT_TIME = 5.0
-    RETRY_TIME = 0.500
-    def __init__(self, serial, name, oid=None):
-        self.serial = serial
-        self.name = name
```

### `stepper.py`

**Recommendation:** investigate

```diff
--- upstream/stepper.py
+++ stock/stepper.py
@@ -1,10 +1,11 @@
 # Printer stepper support
 #
-# Copyright (C) 2016-2025  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import math, logging, collections
 import chelper
+from extras.homing import Homing
 
 class error(Exception):
     pass
@@ -14,29 +15,26 @@
 # Steppers
 ######################################################################
 
-MIN_BOTH_EDGE_DURATION = 0.000000500
-MIN_OPTIMIZED_BOTH_EDGE_DURATION = 0.000000150
-MAX_STEPCOMPRESS_ERROR = 0.000025
+MIN_BOTH_EDGE_DURATION = 0.000000200
 
 # Interface to low-level mcu and chelper code
 class MCU_stepper:
-    def __init__(self, config, step_pin_params, dir_pin_params,
+    def __init__(self, name, step_pin_params, dir_pin_params,
                  rotation_dist, steps_per_rotation,
                  step_pulse_duration=None, units_in_radians=False):
-        self._name = config.get_name()
+        self._name = name
         self._rotation_dist = rotation_dist
         self._steps_per_rotation = steps_per_rotation
         self._step_pulse_duration = step_pulse_duration
         self._units_in_radians = units_in_radians
         self._step_dist = rotation_dist / steps_per_rotation
-        self._mcu = mcu = step_pin_params['chip']
-        self._oid = mcu.create_oid()
-        mcu.register_config_callback(self._build_config)
+        self._mcu = step_pin_params['chip']
+        self._oid = oid = self._mcu.create_oid()
+        self._mcu.register_config_callback(self._build_config)
         self._step_pin = step_pin_params['pin']
         self._invert_step = step_pin_params['invert']
-        printer = mcu.get_printer()
-        if dir_pin_params['chip'] is not mcu:
-            raise printer.config_error(
+        if dir_pin_params['chip'] is not self._mcu:
+            raise self._mcu.get_printer().config_error(
```

### `toolhead.py`

**Recommendation:** investigate

```diff
--- upstream/toolhead.py
+++ stock/toolhead.py
@@ -1,9 +1,10 @@
 # Code for coordinating events on the printer toolhead
 #
-# Copyright (C) 2016-2025  Kevin O'Connor <kevin@koconnor.net>
+# Copyright (C) 2016-2021  Kevin O'Connor <kevin@koconnor.net>
 #
 # This file may be distributed under the terms of the GNU GPLv3 license.
 import math, logging, importlib
+from pickle import NONE
 import mcu, chelper, kinematics.extruder
 
 # Common suffixes: _d is distance (in mm), _v is velocity (in
@@ -17,18 +18,17 @@
         self.start_pos = tuple(start_pos)
         self.end_pos = tuple(end_pos)
         self.accel = toolhead.max_accel
-        self.junction_deviation = toolhead.junction_deviation
         self.timing_callbacks = []
         velocity = min(speed, toolhead.max_velocity)
         self.is_kinematic_move = True
-        self.axes_d = axes_d = [ep - sp for sp, ep in zip(start_pos, end_pos)]
+        self.axes_d = axes_d = [end_pos[i] - start_pos[i] for i in (0, 1, 2, 3)]
         self.move_d = move_d = math.sqrt(sum([d*d for d in axes_d[:3]]))
         if move_d < .000000001:
             # Extrude only move
-            self.end_pos = ((start_pos[0], start_pos[1], start_pos[2])
-                            + self.end_pos[3:])
+            self.end_pos = (start_pos[0], start_pos[1], start_pos[2],
+                            end_pos[3])
             axes_d[0] = axes_d[1] = axes_d[2] = 0.
-            self.move_d = move_d = max([abs(ad) for ad in axes_d[3:]])
+            self.move_d = move_d = abs(axes_d[3])
             inv_move_d = 0.
             if move_d:
                 inv_move_d = 1. / move_d
@@ -45,10 +45,8 @@
         self.max_start_v2 = 0.
         self.max_cruise_v2 = velocity**2
         self.delta_v2 = 2.0 * move_d * self.accel
-        self.next_junction_v2 = 999999999.9
-        # Setup for minimum_cruise_ratio checks
-        self.max_mcr_start_v2 = 0.
-        self.mcr_delta_v2 = 2.0 * move_d * toolhead.mcr_pseudo_accel
+        self.max_smoothed_v2 = 0.
+        self.smooth_delta_v2 = 2.0 * move_d * toolhead.max_accel_to_decel
     def limit_speed(self, speed, accel):
         speed2 = speed**2
         if speed2 < self.max_cruise_v2:
```

## Qidi-Custom Files

### `extras/chamber_fan.py`

- **Size:** 2472 bytes
- **Recommendation:** port

### `extras/gcode_macro_break.py`

- **Size:** 645 bytes
- **Recommendation:** port

### `extras/gcode_shell_command.py`

- **Size:** 3159 bytes
- **Recommendation:** port

### `extras/qdprobe.py`

- **Size:** 7276 bytes
- **Recommendation:** port

### `extras/x_twist_compensation.py`

- **Size:** 27391 bytes
- **Recommendation:** port
