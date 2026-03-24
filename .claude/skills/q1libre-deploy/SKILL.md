---
name: q1libre-deploy
description: Deploy a Q1Libre .deb build to the printer via SSH and verify the installation. Use this skill whenever the user says "install on printer", "deploy", "flash", "push to printer", "install the build", "update the printer", or wants to test a new build on the actual hardware. Also use after building a new .deb when the user wants to test it.
---

# Deploy Q1Libre to Printer

Deploy a built .deb to the Q1 Pro printer via SSH and verify everything works.

SSH access: `root@192.168.0.248` (passwordless key auth).

## Deploy Sequence

### 1. Find the latest build

```bash
ls -la E:/Projects/q1libre/dist/q1libre-v*.deb
```

Use the most recent `.deb` file, or the specific version the user requests.

### 2. Copy to printer

```bash
scp E:/Projects/q1libre/dist/q1libre-v<VERSION>.deb root@192.168.0.248:/tmp/q1libre.deb
```

This takes ~30 seconds for a ~70MB file over LAN.

### 3. Stop services and install

```bash
ssh root@192.168.0.248 "systemctl stop klipper moonraker 2>/dev/null; dpkg -i --force-overwrite /tmp/q1libre.deb 2>&1"
```

Watch for:
- **"INSTALL SUCCESS"** at the end — good
- **"unable to execute installed makerbase-client package post-installation script"** — CRLF bug in postinst. Fix with:
  ```bash
  ssh root@192.168.0.248 "sed -i 's/\r$//' /var/lib/dpkg/info/makerbase-client.postinst && dpkg --configure makerbase-client"
  ```
- **"sudo: q1libre is world writable"** — cosmetic warning during install, fixed by postinst. Harmless if install completes.

### 4. Verify services

```bash
ssh root@192.168.0.248 "systemctl status klipper moonraker --no-pager -l 2>&1 | head -25"
```

Both should show `active (running)`. Moonraker log should show `Klippy ready` within ~15 seconds.

### 5. Verify web UI

Ask the user to check `http://192.168.0.248` in their browser. Should show Fluidd dashboard with:
- Klippy: Ready (green)
- Temperature readings
- No warnings (or expected ones)

### 6. Verify touchscreen

Ask the user to check the touchscreen responds to taps. xindi must be running:
```bash
ssh root@192.168.0.248 "systemctl status xindi --no-pager | head -5"
```

### 7. Cleanup

```bash
ssh root@192.168.0.248 "rm /tmp/q1libre.deb"
```

## Post-Deploy Diagnostics

If anything looks wrong after deploy, use the `q1libre-printer-diag` skill to investigate.

## Important Notes

- The install runs the full postinst which rebuilds klippy-env, installs wheels, and resets git repos. This takes 2-3 minutes.
- The printer's IP may change after install if DHCP lease expires. Check router or touchscreen for new IP.
- xindi and udp_server are stock Qidi binaries — our overlay must never overwrite them or the touchscreen breaks.
- After deploy, the previous klipper and moonraker are backed up to `*.bak` directories.
