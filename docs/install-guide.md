# Q1Libre Installation Guide

Q1Libre patches the stock Qidi Q1 Pro firmware to restore full Klipper functionality, including Fluidd web UI, Moonraker update management, and SSH access with standard tooling.

Repository: <https://github.com/danthi123/Q1Libre>

---

## 1. Prerequisites

- **Stock Qidi Q1 Pro firmware V4.4.24** already installed on your printer.
  Download from the official Qidi repository if needed:
  <https://github.com/QIDITECH/QIDI_Q1_Pro/releases>

- **USB stick** formatted as FAT32 (any size; 1 GB or larger is fine).

- **(Optional) SSH client** for post-install verification.
  - Windows: PuTTY, Windows Terminal with OpenSSH, or MobaXterm.
  - macOS / Linux: built-in `ssh` command.

- **No internet connection required on the printer.** Both offline and online installs are fully supported. All Python dependencies are bundled as wheels inside the release image.

---

## 2. Pre-Install Backup (Strongly Recommended)

Before flashing Q1Libre, back up your printer. SSH into your printer:

```
ssh root@<printer-ip>
```

Default credentials:
- **User:** `root`
- **Password:** `makerbase`

### Full System Backup (Advanced -- Recommended)

Create a complete image of the printer's eMMC storage. This is the only way to fully restore your printer to its exact current state — including all configs, calibration data, wifi setup, and installed software.

From your local machine:

```bash
ssh root@<printer-ip> "dd if=/dev/mmcblk1 bs=4M status=progress" > q1pro_backup.img
```

This creates a full disk image (~14.5 GB for the 16 GB eMMC) and takes approximately 20 minutes over SSH. Store it somewhere safe.

If you ever need to do a full restore from this image, follow the [official eMMC flash procedure](https://wiki.qidi3d.com/en/Memo/flash-emmc) using your backup image instead of the factory image.

### Configuration Backup (Quick)

At minimum, back up your printer configuration and gcode files:

| Path | Contents | Priority |
|------|----------|----------|
| `~/klipper_config/` | Printer configs, bed mesh data, input shaper calibration | High |
| `~/gcode_files/` | Your sliced gcode files | High |
| `~/moonraker/` | Moonraker installation and database | Optional |
| `~/klipper/` | Klipper installation | Optional |

From your local machine, use `scp` to pull files off the printer:

```bash
# Back up printer configs (includes bed mesh, input shaper data)
scp -r root@<printer-ip>:~/klipper_config/ ./backup/klipper_config/

# Back up gcode files
scp -r root@<printer-ip>:~/gcode_files/ ./backup/gcode_files/

# Optional: back up moonraker and klipper directories
scp -r root@<printer-ip>:~/moonraker/ ./backup/moonraker/
scp -r root@<printer-ip>:~/klipper/ ./backup/klipper/
```

**Note on calibration data:** Bed mesh profiles and input shaper calibration are stored within `klipper_config/` and are preserved during Q1Libre updates. You do not need to re-run calibration after flashing.

---

## 3. Installation -- Pre-Built Release (Recommended)

This is the simplest method. No build tools or source code required.

### Steps

1. **Download the latest release** from GitHub:
   <https://github.com/danthi123/Q1Libre/releases>

   Download the file named `QD_Q1_SOC` (no file extension).

2. **Prepare the USB stick.**
   Create a folder called `QD_Update` at the root of your FAT32-formatted USB stick:

   ```
   USB Root/
     QD_Update/
       QD_Q1_SOC
   ```

   The file must be named exactly `QD_Q1_SOC` with no extension.

3. **Plug the USB stick into the printer** (use the USB port on the side of the machine).

4. **Wait for the update to complete.**
   The printer auto-detects the update file and begins installation. This takes approximately 2--3 minutes. The touchscreen will show update progress.

5. **Wait for the printer to restart services.**
   After installation completes, the printer restarts its software services automatically. Give it about 30 seconds before attempting to connect.

Do not power off the printer or remove the USB stick during the update process.

---

## 4. Installation -- Build from Source

Use this method if you want to build the firmware image yourself, for example to include custom modifications.

### Steps

1. **Clone the repository:**

   ```bash
   git clone https://github.com/danthi123/Q1Libre.git
   cd Q1Libre
   ```

2. **Place the stock firmware in the `stock/` directory.**
   Download `QD_Q1_SOC` from the official Qidi V4.4.24 release and copy it into the `stock/` folder:

   ```
   Q1Libre/
     stock/
       QD_Q1_SOC
   ```

3. **Extract the stock firmware:**

   ```bash
   python -m tools.extract stock/QD_Q1_SOC
   ```

4. **Build the patched image:**

   ```bash
   python -m tools.build
   ```

   To specify a custom version number:

   ```bash
   python -m tools.build --version X.Y.Z
   ```

5. **Copy the output to USB.**
   The built image is written to `dist/QD_Q1_SOC`. Copy it to your USB stick following the same folder structure described in Section 3:

   ```
   USB Root/
     QD_Update/
       QD_Q1_SOC
   ```

6. **Flash the printer** using the same USB process described in Section 3.

---

## 5. Post-Install Verification Checklist

After installation, verify that everything is working correctly.

### SSH access

SSH into the printer:

```bash
ssh root@<printer-ip>
```

You should see the **Q1Libre banner** upon login, confirming the patched firmware is active.

### Service status

Check that the core services are running:

```bash
systemctl status klipper moonraker
```

Both `klipper` and `moonraker` should show as **active (running)**.

### Q1Libre status

Run the status command to see installed versions and system info:

```bash
q1status
```

Alternatively, from root:

```bash
/root/scripts/q1libre_info.sh
```

### Web UI

Open a browser and navigate to:

```
http://<printer-ip>
```

Fluidd should load, showing version **v1.36.2**. Navigate to **Settings -> Software Updates** and confirm that entries for Klipper, Moonraker, and Fluidd are visible.

### Shell aliases

The following convenience aliases are available over SSH:

| Alias | Description |
|-------|-------------|
| `klog` | Tail the Klipper log |
| `mlog` | Tail the Moonraker log |
| `myip` | Show the printer's IP address |
| `kversion` | Show the installed Klipper version |
| `mversion` | Show the installed Moonraker version |

### Touchscreen

Verify that the touchscreen responds normally and displays printer status. No additional configuration is needed.

---

## 6. Troubleshooting

### "Klipper not ready" after install

Services may still be starting. Wait 30 seconds and refresh the web UI. If the issue persists, restart Klipper via SSH:

```bash
krestart
```

### Moonraker warnings about deprecated config

These are cosmetic warnings and can be safely ignored. They do not affect functionality.

### Web UI not loading

Check that nginx is running:

```bash
systemctl status nginx
```

If it is not active, restart it:

```bash
sudo systemctl restart nginx.service
```

Then retry loading the web UI in your browser.

### Touchscreen unresponsive

Check the xindi service:

```bash
systemctl status xindi
```

The touchscreen should not normally require a restart after flashing Q1Libre.

### update_manager shows errors

The update manager may need an internet connection for the initial git fetch. This does not affect local functionality. Updates work offline for local version tracking.

### "MCU protocol error"

This is extremely unlikely after a Q1Libre install. If you see this error, restore the stock firmware using the recovery procedure described in Section 7 below, then retry the Q1Libre installation.

---

## 7. Rollback / Recovery

### Normal rollback to stock firmware

1. Download the stock V4.4.24 firmware (`QD_Q1_SOC`) from the official Qidi repository:
   <https://github.com/QIDITECH/QIDI_Q1_Pro/releases>

2. Place it on a FAT32 USB stick using the same `QD_Update/QD_Q1_SOC` folder structure.

3. Plug the USB into the printer and let the update complete, exactly as with the Q1Libre install.

This restores the stock Qidi firmware. Your printer configuration files in `klipper_config/` are preserved, but Q1Libre-specific improvements (Fluidd, Moonraker updates, shell aliases, etc.) will be removed.

### Emergency recovery (bricked printer)

If the printer is unresponsive and cannot boot far enough to read a USB update, you will need to flash the eMMC directly. Follow the official Qidi instructions:

<https://wiki.qidi3d.com/en/Memo/flash-emmc>

This procedure requires opening the printer's electronics enclosure and connecting the eMMC to a computer. It fully restores the printer to factory state.
