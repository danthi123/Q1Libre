# Q1Libre: Gcode macro interrupt support for xindi touchscreen
# Monkey-patches GCodeDispatch._process_commands to support break_flag
# without modifying upstream gcode.py
#
# When xindi sends the "breakmacro" webhook, all gcode lines are skipped
# except CANCEL_PRINT, allowing the touchscreen cancel button to work.

import logging

class GCodeMacroBreaker:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:ready",
                                            self._handle_ready)

    def _handle_ready(self):
        gcode = self.printer.lookup_object('gcode')
        # Inject break_flag attribute onto the gcode object
        gcode.break_flag = False
        # Store reference to the original bound method
        original_process = gcode._process_commands
        # Create wrapper that checks break_flag before dispatching
        def patched_process(commands, need_ack=True):
            if not gcode.break_flag:
                return original_process(commands, need_ack)
            # When break_flag is set, filter out everything except
            # CANCEL_PRINT so the touchscreen cancel actually fires.
            filtered = []
            for line in commands:
                stripped = line.strip()
                cpos = stripped.find(';')
                if cpos >= 0:
                    stripped = stripped[:cpos]
                stripped = stripped.strip().upper()
                if stripped == "CANCEL_PRINT":
                    gcode.break_flag = False
                    try:
                        heaters = self.printer.lookup_object("heaters")
                        heaters.break_flag = False
                    except Exception:
                        pass
                    filtered.append(line)
                # All other commands are silently dropped
            if filtered:
                return original_process(filtered, need_ack)
        # Replace the bound method on the instance
        gcode._process_commands = patched_process
        # Register xindi webhook endpoints
        webhooks = self.printer.lookup_object('webhooks')
        webhooks.register_endpoint("breakmacro", self._handle_breakmacro)
        webhooks.register_endpoint("resumemacro", self._handle_resumemacro)
        logging.info(
            "gcode_macro_break: xindi touchscreen cancel support loaded")

    def _handle_breakmacro(self, web_request):
        gcode = self.printer.lookup_object('gcode')
        gcode.break_flag = True

    def _handle_resumemacro(self, web_request):
        gcode = self.printer.lookup_object('gcode')
        gcode.break_flag = False

def load_config(config):
    return GCodeMacroBreaker(config)
