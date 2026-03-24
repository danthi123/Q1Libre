#!/usr/bin/env python3
"""Migrate a Qidi printer.cfg to work with upstream Klipper v0.13.

Transformations performed:
  1. In [stepper_z]: comment out endstop_pin_reverse, position_endstop_reverse,
     homing_positive_dir_reverse, homing_speed_reverse
  2. In [stepper_z1]: comment out endstop_pin_reverse
  3. Create a [qidi_stepper] section with the extracted values
  4. Replace samples_result: submaxmin with samples_result: median everywhere
  5. Comment out max_accel_to_decel line
  6. Add [gcode_macro_break] section if not already present

The script is idempotent -- running it twice produces the same output.

Usage:
    python tools/migrate_config.py /path/to/printer.cfg
"""

import re
import sys
import os


def migrate_config(path):
    with open(path, 'r') as f:
        text = f.read()

    lines = text.split('\n')

    # -- Pass 1: collect values and comment out Qidi-custom options ----------

    # Track which section we are in
    current_section = None
    # Values extracted for the new [qidi_stepper] section
    qidi_vals = {}
    # Options to comment-out per section
    z_opts = {
        'endstop_pin_reverse',
        'position_endstop_reverse',
        'homing_positive_dir_reverse',
        'homing_speed_reverse',
    }
    z1_opts = {
        'endstop_pin_reverse',
    }

    new_lines = []
    has_qidi_stepper = False
    has_gcode_macro_break = False

    for line in lines:
        stripped = line.strip()

        # Detect section headers
        m = re.match(r'^\[([^\]]+)\]', stripped)
        if m:
            current_section = m.group(1).strip()
            if current_section == 'qidi_stepper':
                has_qidi_stepper = True
            if current_section == 'gcode_macro_break':
                has_gcode_macro_break = True

        # --- stepper_z: comment out and extract reverse homing options ---
        if current_section == 'stepper_z' and not stripped.startswith('#'):
            key_match = re.match(r'^(\w+)\s*[:=]\s*(.*)', stripped)
            if key_match:
                key = key_match.group(1)
                val = key_match.group(2).strip()
                if key in z_opts:
                    # Map to qidi_stepper key names (prefix z_)
                    qidi_key = 'z_' + key
                    qidi_vals[qidi_key] = val
                    new_lines.append('#' + line + '  # migrated to [qidi_stepper]')
                    continue

        # --- stepper_z1: comment out endstop_pin_reverse ---
        if current_section == 'stepper_z1' and not stripped.startswith('#'):
            key_match = re.match(r'^(\w+)\s*[:=]\s*(.*)', stripped)
            if key_match:
                key = key_match.group(1)
                val = key_match.group(2).strip()
                if key in z1_opts:
                    qidi_key = 'z1_' + key
                    qidi_vals[qidi_key] = val
                    new_lines.append('#' + line + '  # migrated to [qidi_stepper]')
                    continue

        # --- samples_result: submaxmin -> median (everywhere) ---
        if not stripped.startswith('#'):
            sub = re.sub(
                r'(samples_result\s*[:=]\s*)submaxmin',
                r'\1median',
                line)
            if sub != line:
                line = sub
        # Also handle the #*# saved config section
        if stripped.startswith('#*#'):
            sub = re.sub(
                r'(samples_result\s*=\s*)submaxmin',
                r'\1median',
                line)
            if sub != line:
                line = sub

        # --- max_accel_to_decel: comment out ---
        if current_section == 'printer' and not stripped.startswith('#'):
            key_match = re.match(r'^(max_accel_to_decel)\s*[:=]', stripped)
            if key_match:
                new_lines.append('#' + line + '  # deprecated in upstream Klipper')
                continue

        new_lines.append(line)

    # -- Pass 2: inject [qidi_stepper] section if values were extracted ------

    if qidi_vals and not has_qidi_stepper:
        # Build the section
        section_lines = ['', '[qidi_stepper]']
        # Canonical order
        key_order = [
            'z_endstop_pin_reverse',
            'z_position_endstop_reverse',
            'z_homing_positive_dir_reverse',
            'z_homing_speed_reverse',
            'z1_endstop_pin_reverse',
        ]
        for k in key_order:
            if k in qidi_vals:
                section_lines.append('%s: %s' % (k, qidi_vals[k]))
        section_lines.append('')

        # Insert before the SAVE_CONFIG block if present, otherwise append
        save_idx = None
        for i, line in enumerate(new_lines):
            if line.strip().startswith('#*# <'):
                save_idx = i
                break

        if save_idx is not None:
            for j, sl in enumerate(section_lines):
                new_lines.insert(save_idx + j, sl)
        else:
            new_lines.extend(section_lines)

    # -- Pass 3: add [gcode_macro_break] if missing --------------------------

    if not has_gcode_macro_break:
        # Check again after potential insertion
        full_text = '\n'.join(new_lines)
        if '[gcode_macro_break]' not in full_text:
            # Insert before SAVE_CONFIG or append
            block = ['', '[gcode_macro_break]',
                     '# Used for cancel print in a macro', '']
            save_idx = None
            for i, line in enumerate(new_lines):
                if line.strip().startswith('#*# <'):
                    save_idx = i
                    break
            if save_idx is not None:
                for j, sl in enumerate(block):
                    new_lines.insert(save_idx + j, sl)
            else:
                new_lines.extend(block)

    # -- Write output --------------------------------------------------------

    output = '\n'.join(new_lines)
    with open(path, 'w') as f:
        f.write(output)

    print("Migrated: %s" % path)
    if qidi_vals:
        print("  Created [qidi_stepper] with keys: %s"
              % ', '.join(sorted(qidi_vals.keys())))
    else:
        print("  No reverse-homing options found (already migrated?)")


def main():
    if len(sys.argv) != 2:
        print("Usage: %s /path/to/printer.cfg" % sys.argv[0], file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print("Error: file not found: %s" % path, file=sys.stderr)
        sys.exit(1)
    migrate_config(path)


if __name__ == '__main__':
    main()
