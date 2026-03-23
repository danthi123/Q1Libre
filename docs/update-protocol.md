# Qidi Q1 Pro Update Protocol

## How Updates Work

The xindi middleware (running as the `makerbase-client` service) monitors for USB
drives. When a USB drive is mounted at `/home/mks/gcode_files/sda1/`, xindi checks
for a `QD_Update/` directory and processes recognized files according to the table
below.

## Update Files

| File | Action |
|------|--------|
| `QD_Q1_SOC` | `dpkg -i --force-overwrite <file>; sync` |
| `QD_Q1_UI` | Copy to `/root/800_480.tft`, then serial-flash to TJC display |
| `QD_Q1_PATCH` | Unknown — appears in strings but behavior is unclear |
| `mks.deb` | `dpkg -i --force-overwrite /home/mks/gcode_files/sda1/QD_Update/mks.deb; sync` |
| `QD_MCU/MCU` | Copy to `/root/klipper.bin`, flash via `hid-flash` to ttyS0 |
| `gcode_macro.cfg` | Copied to `/home/mks/klipper_config/` |
| `printer.cfg` | Copied to `/home/mks/klipper_config/` |
| `MKS_THR.cfg` | Copied to `/home/mks/klipper_config/` |
| `QD_Gcode/*.gcode` | Copied to `/home/mks/gcode_files/` |

## Recovery Mechanisms

These special filenames trigger recovery actions when placed on the USB drive:

| File | Action |
|------|--------|
| `mksscreen.recovery` | Copied to `/root/800_480.tft` for display recovery |
| `mksclient.recovery` | Installed via `dpkg -i --force-overwrite` |
| `mks-super.sh` | Arbitrary shell script execution from USB as root |
| `QD_factory_mode.txt` | Triggers factory mode |

## Online Updates

xindi checks `.qidi3dprinter.com/QD_Q1` for available firmware versions. When a
new version is found, it downloads and applies SOC and UI updates over the network.

The update method is controlled by the `method` value in `config.mksini`:

| Value | Behavior |
|-------|----------|
| `0` | LAN only (no internet update checks) |
| `1` | Internet updates enabled |

## Security Notes

- **`mks-super.sh` is a backdoor.** Any shell script placed on a USB drive with
  this filename is executed as root with no verification or signature checking.
- **`chmod 777`** is used extensively in the postinst script, leaving installed
  files world-writable.
- The `mks` user has restricted sudo access, but root services (xindi, frpc) run
  unrestricted.
- **frpc** establishes an outbound tunnel to Qidi cloud servers, enabling remote
  access to the printer.
