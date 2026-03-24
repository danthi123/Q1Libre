# Qidi reverse-homing support for upstream Klipper
#
# Replicates the Qidi-custom stepper_z reverse homing behaviour as a
# standalone extras module so that upstream stepper.py stays unmodified.
#
# Copyright (C) 2025  Q1Libre contributors
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class QidiStepper:
    """Read [qidi_stepper] config and monkey-patch the Z rail at connect time.

    Config example::

        [qidi_stepper]
        z_endstop_pin_reverse: tmc2209_stepper_z:virtual_endstop
        z_position_endstop_reverse: 248
        z_homing_positive_dir_reverse: true
        z_homing_speed_reverse: 8
        z1_endstop_pin_reverse: tmc2209_stepper_z1:virtual_endstop
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name()

        # ---- read config values (store for later) ----
        self.z_endstop_pin_reverse = config.get('z_endstop_pin_reverse')
        self.z_position_endstop_reverse = config.getfloat(
            'z_position_endstop_reverse')
        self.z_homing_positive_dir_reverse = config.getboolean(
            'z_homing_positive_dir_reverse')
        self.z_homing_speed_reverse = config.getfloat(
            'z_homing_speed_reverse', 8., above=0.)
        self.z1_endstop_pin_reverse = config.get(
            'z1_endstop_pin_reverse', None)

        # Will be populated at connect time
        self.z_rail = None
        self.reversed = False

        self.printer.register_event_handler(
            'klippy:connect', self._handle_connect)

    # ------------------------------------------------------------------
    # Connect-time setup
    # ------------------------------------------------------------------

    def _handle_connect(self):
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()

        # Find the Z rail.  CoreXY kinematics exposes get_rails() which
        # returns rails indexed [X, Y, Z].
        rails = kin.get_rails()
        self.z_rail = None
        for rail in rails:
            name = rail.get_name()
            if name == 'stepper_z':
                self.z_rail = rail
                break
        if self.z_rail is None:
            raise self.printer.config_error(
                "qidi_stepper: could not find stepper_z rail")

        rail = self.z_rail

        # ---- set up reverse endstop pins on the rail ----
        rail.endstops_reverse = []
        rail.endstop_map_reverse = {}
        rail.reversed = False

        ppins = self.printer.lookup_object('pins')

        # Helper: register a reverse endstop for a given pin and stepper
        def _add_reverse_endstop(pin_str, stepper):
            pin_params = ppins.parse_pin(pin_str, True, True)
            pin_name = "%s:%s" % (pin_params['chip_name'], pin_params['pin'])
            mcu_endstop = ppins.setup_pin('endstop', pin_str)
            rail.endstop_map_reverse[pin_name] = {
                'endstop': mcu_endstop,
                'invert': pin_params['invert'],
                'pullup': pin_params['pullup'],
            }
            name = stepper.get_name(short=True)
            rail.endstops_reverse.append((mcu_endstop, name))
            mcu_endstop.add_stepper(stepper)

        steppers = rail.get_steppers()
        # Primary Z stepper (stepper_z) always gets a reverse endstop
        _add_reverse_endstop(self.z_endstop_pin_reverse, steppers[0])

        # Secondary Z stepper (stepper_z1) if configured
        if self.z1_endstop_pin_reverse and len(steppers) > 1:
            _add_reverse_endstop(self.z1_endstop_pin_reverse, steppers[1])

        # ---- store original (primary) homing values ----
        rail.position_endstop_reverse = self.z_position_endstop_reverse
        rail.homing_positive_dir_reverse = self.z_homing_positive_dir_reverse
        rail.homing_speed_reverse = self.z_homing_speed_reverse
        rail.homing_retract_dist_reverse = 0

        # ---- inject homing_params_switch method on the rail ----
        def homing_params_switch(r=rail):
            r.reversed = not r.reversed
            r.endstop_map, r.endstop_map_reverse = (
                r.endstop_map_reverse, r.endstop_map)
            r.endstops, r.endstops_reverse = (
                r.endstops_reverse, r.endstops)
            r.position_endstop, r.position_endstop_reverse = (
                r.position_endstop_reverse, r.position_endstop)
            r.homing_positive_dir, r.homing_positive_dir_reverse = (
                r.homing_positive_dir_reverse, r.homing_positive_dir)
            r.homing_retract_dist, r.homing_retract_dist_reverse = (
                r.homing_retract_dist_reverse, r.homing_retract_dist)
            r.homing_speed, r.homing_speed_reverse = (
                r.homing_speed_reverse, r.homing_speed)

        rail.homing_params_switch = homing_params_switch

        # ---- register gcode command and event handler ----
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command(
            'REVERSE_HOMING', self.cmd_REVERSE_HOMING,
            desc="Home Z using the reverse endstop pins")

        self.printer.register_event_handler(
            'homing:home_rails_end', self._handle_home_rails_end)

        logging.info("qidi_stepper: reverse homing configured for Z rail")

    # ------------------------------------------------------------------
    # REVERSE_HOMING gcode command
    # ------------------------------------------------------------------

    def cmd_REVERSE_HOMING(self, gcmd):
        rail = self.z_rail
        rail.homing_params_switch()
        try:
            from extras.homing import Homing
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

    # ------------------------------------------------------------------
    # Auto-swap back after homing completes
    # ------------------------------------------------------------------

    def _handle_home_rails_end(self, homing_state, rails):
        rail = self.z_rail
        if rail is not None and rail.reversed:
            rail.homing_params_switch()


def load_config(config):
    return QidiStepper(config)
