---
name: q1libre-printer-diag
description: Run diagnostics on the Q1 Pro printer via SSH. Use this skill whenever the user reports a printer error, asks to check logs, mentions "check the printer", "what's wrong", "debug", "troubleshoot", shows a Fluidd error screenshot, mentions "Klippy disconnected", "moonraker error", "klipper crash", service failures, or any printer misbehavior. Also use proactively after deploying a new build to verify everything is working.
---

# Q1 Pro Printer Diagnostics

SSH access: `root@192.168.0.248` (passwordless key auth configured).

When diagnosing issues, gather all relevant data in parallel before drawing conclusions. Don't guess — read the logs.

## Quick Health Check

Run these in parallel to get a full picture fast:

```bash
# Service status
ssh root@192.168.0.248 "systemctl status klipper moonraker --no-pager -l 2>&1 | head -30"

# Klipper errors (last 50 lines, filtered)
ssh root@192.168.0.248 "tail -100 /home/mks/klipper_logs/klippy.log | grep -i 'error\|exception\|traceback\|shutdown\|warning'"

# Moonraker errors
ssh root@192.168.0.248 "tail -50 /home/mks/klipper_logs/moonraker.log | grep -i 'error\|exception\|traceback\|warning'"

# xindi (touchscreen) status
ssh root@192.168.0.248 "systemctl status xindi --no-pager 2>&1 | head -10"

# Python/pip versions in klippy-env
ssh root@192.168.0.248 "/home/mks/klippy-env/bin/python --version && /home/mks/klippy-env/bin/pip list 2>/dev/null | head -20"

# Disk space (eMMC is small, 16GB)
ssh root@192.168.0.248 "df -h / /home"

# Q1Libre version
ssh root@192.168.0.248 "cat /root/q1libre_version.txt 2>/dev/null"
```

## Deep Dive Commands

### Klipper crash / "Unhandled exception"
```bash
# Find the exception in the log
ssh root@192.168.0.248 "grep -n 'Unhandled exception\|Traceback' /home/mks/klipper_logs/klippy.log | tail -5"
# Then read the full traceback (replace LINE with the line number)
ssh root@192.168.0.248 "sed -n 'LINE,+20p' /home/mks/klipper_logs/klippy.log"
```

### Moonraker 404 / update_manager issues
```bash
ssh root@192.168.0.248 "grep -i 'update_manager\|404\|error' /home/mks/klipper_logs/moonraker.log | tail -20"
# Check if update_manager is enabled in config
ssh root@192.168.0.248 "grep -A3 'update_manager' /home/mks/klipper_config/moonraker.conf | head -10"
```

### Probe / bed leveling stuck
```bash
# Count retries
ssh root@192.168.0.248 "grep -c 'Retrying' /home/mks/klipper_logs/klippy.log"
# Check probe readings
ssh root@192.168.0.248 "grep 'probe at.*is z=' /home/mks/klipper_logs/klippy.log | tail -20"
```

### MCU communication
```bash
ssh root@192.168.0.248 "grep -i 'mcu\|shutdown\|lost comm\|timeout' /home/mks/klipper_logs/klippy.log | tail -10"
```

### Touchscreen / xindi
```bash
ssh root@192.168.0.248 "systemctl status xindi --no-pager -l"
ssh root@192.168.0.248 "file /usr/bin/xindi"
ssh root@192.168.0.248 "md5sum /usr/bin/xindi /usr/bin/udp_server"
```

### Git repo state (for update_manager version display)
```bash
ssh root@192.168.0.248 "cd /home/mks/moonraker && git describe --tags --always --dirty 2>/dev/null"
ssh root@192.168.0.248 "cd /home/mks/klipper && git describe --tags --always --dirty 2>/dev/null"
```

## Common Issues & Root Causes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Klippy not connected" | Klipper crashed | Check klippy.log for traceback |
| "No moonraker connection" | Moonraker crashed or slow startup | Check moonraker.log, wait 30s, restart |
| Probe infinite retry | Hardware probe issue OR tolerance too tight | Check probe readings spread |
| "can't have unbuffered text I/O" | Python 2→3 compat bug | Fix `buffering=0` → `buffering=1` |
| "ModuleNotFoundError" | Missing pip package in klippy-env | Install via bundled wheels |
| Touchscreen frozen | xindi crash or corrupt binary | `systemctl restart xindi`, check md5 |
| "sudo: q1libre is world writable" | CRLF in postinst or bad permissions | `chmod 0440 /etc/sudoers.d/q1libre` |
| Version shows old/dirty | Git repo not reset properly | Check git state, may need re-init |
